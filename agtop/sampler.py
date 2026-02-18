"""Unified metrics sampler with IOReport backend."""

import plistlib
import re
import struct
import subprocess
import time
from typing import NamedTuple


class SampleResult(NamedTuple):
    cpu_metrics: dict
    gpu_metrics: dict
    thermal_pressure: str
    bandwidth_metrics: dict
    timestamp: float
    cpu_temp_c: float = 0.0  # max CPU die temperature (Celsius), 0 if unavailable
    gpu_temp_c: float = 0.0  # max GPU die temperature (Celsius), 0 if unavailable


class IOReportSampler:
    """Direct IOReport sampling. No sudo required."""

    def __init__(self, interval):
        from .ioreport import IOReportSubscription
        from .smc import SMCReader

        self._sub = IOReportSubscription(
            [
                ("Energy Model", None),
                ("CPU Stats", "CPU Core Performance States"),
                ("GPU Stats", "GPU Performance States"),
            ]
        )
        self._interval = interval
        self._prev_sample = None
        self._prev_time = None
        self._core_counts = _get_core_counts()
        self._dvfs = _read_dvfs_tables()
        self._smc = SMCReader()

    def sample(self):
        from .ioreport import cf_release

        new_sample = self._sub.sample()
        new_time = time.monotonic()

        if self._prev_sample is None:
            self._prev_sample = new_sample
            self._prev_time = new_time
            return None

        items = self._sub.delta(self._prev_sample, new_sample)
        elapsed_s = new_time - self._prev_time

        cf_release(self._prev_sample)
        self._prev_sample = new_sample
        self._prev_time = new_time

        if elapsed_s <= 0:
            return None

        temps = self._smc.read_temperatures()
        cpu_temp = max(temps.cpu_temps_c) if temps.cpu_temps_c else 0.0
        gpu_temp = max(temps.gpu_temps_c) if temps.gpu_temps_c else 0.0

        return self._convert(items, elapsed_s, cpu_temp, gpu_temp)

    def _convert(self, items, elapsed_s, cpu_temp_c=0.0, gpu_temp_c=0.0):
        """Convert IOReport items to the same dict format as parsers.py output."""
        cpu_energy_j = 0.0
        gpu_energy_j = 0.0
        ane_energy_j = 0.0

        e_core_data = {}
        p_core_data = {}
        gpu_freq_mhz = 0
        gpu_active_pct = 0

        p_count = self._core_counts["p_count"]

        ecpu_freqs = self._dvfs.get("ecpu", [])
        pcpu_freqs = self._dvfs.get("pcpu", [])
        gpu_freqs = self._dvfs.get("gpu", [])

        for item in items:
            if item.group == "Energy Model":
                energy_j = _energy_to_joules(item.integer_value, item.unit)
                if "CPU Energy" in item.channel:
                    cpu_energy_j += energy_j
                elif "GPU" in item.channel:
                    gpu_energy_j += energy_j
                elif "ANE" in item.channel:
                    ane_energy_j += energy_j

            elif (
                item.group == "CPU Stats"
                and item.subgroup == "CPU Core Performance States"
            ):
                if "ECPU" in item.channel:
                    freq, active = _compute_residency_metrics(
                        item.state_residencies, ecpu_freqs
                    )
                    idx = _parse_core_index(item.channel, "ECPU")
                    if idx is not None:
                        e_core_data[idx] = (freq, active)
                elif "PCPU" in item.channel:
                    freq, active = _compute_residency_metrics(
                        item.state_residencies, pcpu_freqs
                    )
                    idx = _parse_core_index(item.channel, "PCPU")
                    if idx is not None:
                        p_core_data[idx] = (freq, active)

            elif (
                item.group == "GPU Stats" and item.subgroup == "GPU Performance States"
            ):
                if "GPUPH" in item.channel:
                    gpu_freq_mhz, gpu_active_pct = _compute_residency_metrics(
                        item.state_residencies, gpu_freqs
                    )

        # Scale energy to match parsers.py convention:
        # parsers.py returns cpu_W = energy_mJ / 1000 = energy_J
        # agtop.py does cpu_power_W = cpu_W / sample_interval
        # Scale so that dividing by sample_interval gives correct watts.
        scale = self._interval / elapsed_s if elapsed_s > 0 else 1.0
        cpu_e = cpu_energy_j * scale
        gpu_e = gpu_energy_j * scale
        ane_e = ane_energy_j * scale
        package_e = cpu_e + gpu_e + ane_e

        cpu_metrics = {
            "E-Cluster_active": 0,
            "E-Cluster_freq_Mhz": 0,
            "P-Cluster_active": 0,
            "P-Cluster_freq_Mhz": 0,
            "ane_W": ane_e,
            "cpu_W": cpu_e,
            "gpu_W": gpu_e,
            "package_W": package_e,
            "e_core": [],
            "p_core": [],
        }

        e_freqs = []
        e_actives = []
        for cluster_idx in sorted(e_core_data):
            freq, active = e_core_data[cluster_idx]
            sys_idx = p_count + cluster_idx
            cpu_metrics["e_core"].append(sys_idx)
            cpu_metrics["E-Cluster" + str(sys_idx) + "_active"] = active
            cpu_metrics["E-Cluster" + str(sys_idx) + "_freq_Mhz"] = freq
            e_freqs.append(freq)
            e_actives.append(active)

        if e_freqs:
            cpu_metrics["E-Cluster_freq_Mhz"] = max(e_freqs)
        if e_actives:
            cpu_metrics["E-Cluster_active"] = int(sum(e_actives) / len(e_actives))

        p_freqs = []
        p_actives = []
        for cluster_idx in sorted(p_core_data):
            freq, active = p_core_data[cluster_idx]
            sys_idx = cluster_idx
            cpu_metrics["p_core"].append(sys_idx)
            cpu_metrics["P-Cluster" + str(sys_idx) + "_active"] = active
            cpu_metrics["P-Cluster" + str(sys_idx) + "_freq_Mhz"] = freq
            p_freqs.append(freq)
            p_actives.append(active)

        if p_freqs:
            cpu_metrics["P-Cluster_freq_Mhz"] = max(p_freqs)
        if p_actives:
            cpu_metrics["P-Cluster_active"] = int(sum(p_actives) / len(p_actives))

        gpu_metrics = {
            "freq_MHz": gpu_freq_mhz,
            "active": gpu_active_pct,
        }

        bandwidth_metrics = {
            "ECPU DCS RD": 0.0,
            "ECPU DCS WR": 0.0,
            "PCPU DCS RD": 0.0,
            "PCPU DCS WR": 0.0,
            "GFX DCS RD": 0.0,
            "GFX DCS WR": 0.0,
            "MEDIA DCS": 0.0,
            "DCS RD": 0.0,
            "DCS WR": 0.0,
            "_available": False,
        }

        return SampleResult(
            cpu_metrics=cpu_metrics,
            gpu_metrics=gpu_metrics,
            thermal_pressure="Unknown",
            bandwidth_metrics=bandwidth_metrics,
            timestamp=time.time(),
            cpu_temp_c=cpu_temp_c,
            gpu_temp_c=gpu_temp_c,
        )

    def close(self):
        from .ioreport import cf_release

        if self._prev_sample is not None:
            cf_release(self._prev_sample)
            self._prev_sample = None
        self._sub.close()
        self._smc.close()


def create_sampler(interval):
    """Create an IOReport sampler.

    Returns (sampler, backend_name) where backend_name is always 'ioreport'.
    """
    return (IOReportSampler(interval), "ioreport")


# --- Private helpers ---


def _get_core_counts():
    """Get P-core and E-core counts from sysctl."""
    p_count = 0
    e_count = 0
    try:
        result = subprocess.run(
            ["sysctl", "-n", "hw.perflevel0.logicalcpu"],
            capture_output=True,
            text=True,
            check=False,
        )
        p_count = int(result.stdout.strip())
    except (ValueError, OSError):
        pass
    try:
        result = subprocess.run(
            ["sysctl", "-n", "hw.perflevel1.logicalcpu"],
            capture_output=True,
            text=True,
            check=False,
        )
        e_count = int(result.stdout.strip())
    except (ValueError, OSError):
        pass
    return {"p_count": p_count, "e_count": e_count}


def _energy_to_joules(value, unit):
    """Convert energy value to joules based on unit label."""
    unit_lower = unit.lower().strip()
    if unit_lower == "nj":
        return value / 1e9
    if unit_lower in ("uj", "\u00b5j"):
        return value / 1e6
    if unit_lower == "mj":
        return value / 1e3
    if unit_lower == "j":
        return float(value)
    # Unknown unit — assume nJ (common on Apple Silicon)
    return value / 1e9


_CORE_INDEX_PATTERN = re.compile(r"^[EP]CPU(\d+)")


def _parse_core_index(channel_name, prefix):
    """Extract core index from channel name like 'ECPU000' or 'PCPU130'.

    Channel names use zero-padded multi-digit format. The first digits
    after the prefix encode the core number (e.g. ECPU010 → core 1,
    PCPU130 → core 13).
    """
    m = _CORE_INDEX_PATTERN.match(channel_name)
    if not m:
        return None
    raw = m.group(1)
    # Strip trailing zero that IOReport appends (e.g. "000" → core 0,
    # "010" → core 1, "130" → core 13). The last digit is always 0.
    if len(raw) >= 2:
        raw = raw[:-1]
    try:
        return int(raw)
    except ValueError:
        return None


def _compute_residency_metrics(residencies, freq_table=None):
    """Compute weighted average frequency and active percentage.

    State names can be:
    - Plain integers like "600" (frequency in MHz directly)
    - "V{n}P{m}" (CPU DVFS state — n is the table index)
    - "P{n}" (GPU performance state — n is the table index)
    - "IDLE", "DOWN", "OFF" (inactive states)

    freq_table: list of MHz values indexed by state position, from
    lowest to highest frequency. Used to resolve V{n}P{m} / P{n} names.

    Returns (freq_mhz, active_percent) as (int, int).
    """
    if freq_table is None:
        freq_table = []

    total_ns = 0
    active_ns = 0
    weighted_freq_sum = 0

    for name, ns in residencies:
        total_ns += ns
        name_upper = name.upper()
        if name_upper in ("IDLE", "DOWN", "OFF", "UNKNOWN", ""):
            continue

        freq_mhz = _resolve_state_freq(name, freq_table)
        if freq_mhz is None:
            continue

        active_ns += ns
        weighted_freq_sum += freq_mhz * ns

    if total_ns <= 0 or active_ns <= 0:
        return (0, 0)

    avg_freq = int(weighted_freq_sum / active_ns)
    active_pct = int(active_ns / total_ns * 100)
    return (avg_freq, active_pct)


_VP_PATTERN = re.compile(r"^V(\d+)P\d+$")
_P_PATTERN = re.compile(r"^P(\d+)$")


def _resolve_state_freq(name, freq_table):
    """Resolve a P-state name to a frequency in MHz.

    Returns frequency as int, or None if the state is unrecognized.
    """
    # Try plain integer (e.g. "600" for 600 MHz)
    try:
        return int(name)
    except ValueError:
        pass

    # Try V{n}P{m} pattern — n is the index into the freq table
    m = _VP_PATTERN.match(name)
    if m:
        idx = int(m.group(1))
        if 0 <= idx < len(freq_table):
            return freq_table[idx]
        return 0

    # Try P{n} pattern (GPU) — n is the index into the freq table
    m = _P_PATTERN.match(name)
    if m:
        idx = int(m.group(1))
        if 0 <= idx < len(freq_table):
            return freq_table[idx]
        return 0

    return None


def _read_dvfs_tables():
    """Read DVFS frequency tables from IOKit pmgr device via ioreg.

    Returns dict with keys 'ecpu', 'pcpu', 'gpu', each a list of
    MHz values in ascending frequency order (indexed by V-state or P-state).
    """
    try:
        result = subprocess.run(
            ["ioreg", "-a", "-r", "-d", "1", "-n", "pmgr"],
            capture_output=True,
            check=False,
        )
        data = plistlib.loads(result.stdout)
    except Exception:
        return {"ecpu": [], "pcpu": [], "gpu": []}

    if isinstance(data, list) and data:
        data = data[0]
    if not isinstance(data, dict):
        return {"ecpu": [], "pcpu": [], "gpu": []}

    # Parse all voltage-states entries that contain real frequencies
    tables = {}
    for key, val in data.items():
        if not key.startswith("voltage-states") or not isinstance(val, bytes):
            continue
        if len(val) < 8:
            continue
        n_entries = len(val) // 8
        freqs = []
        for i in range(n_entries):
            freq_hz, _voltage = struct.unpack_from("<II", val, i * 8)
            freqs.append(freq_hz // 1_000_000)
        # Only keep tables where most entries have real frequencies (>50 MHz)
        real_count = sum(1 for f in freqs if f > 50)
        if real_count >= max(1, len(freqs) // 2):
            tables[key] = freqs

    # Match tables to clusters by entry count and frequency range.
    # P-core: most entries (15-25 states) and highest max frequency (>2 GHz)
    # E-core: fewer entries (5-12 states), moderate max frequency
    # GPU: 10-20 states, max frequency < 2 GHz
    #
    # Strategy: pick P-core first (most distinctive — highest max freq and
    # most entries), then E-core (fewest entries with real freqs), then GPU.
    ecpu = []
    pcpu = []
    gpu = []

    candidates = sorted(tables.items())

    # P-core: highest max frequency, typically >2 GHz, most entries
    best_pcpu_key = None
    best_pcpu_max = 0
    for key, freqs in candidates:
        max_freq = max(freqs) if freqs else 0
        if len(freqs) >= 15 and max_freq > best_pcpu_max:
            best_pcpu_max = max_freq
            best_pcpu_key = key
    if best_pcpu_key:
        pcpu = tables[best_pcpu_key]

    # E-core: small table (5-12 entries), not the pcpu table
    for key, freqs in candidates:
        if key == best_pcpu_key:
            continue
        if 5 <= len(freqs) <= 12:
            ecpu = freqs
            break

    # GPU: 10-20 entries, not pcpu or ecpu, first match
    for key, freqs in candidates:
        if key == best_pcpu_key:
            continue
        if freqs is ecpu:
            continue
        if 10 <= len(freqs) <= 20:
            gpu = freqs
            break

    return {"ecpu": ecpu, "pcpu": pcpu, "gpu": gpu}
