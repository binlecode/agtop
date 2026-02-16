import plistlib
from pathlib import Path
from tempfile import TemporaryDirectory

from agtop import utils


REQUIRED_BANDWIDTH_KEYS = [
    "ECPU DCS RD",
    "ECPU DCS WR",
    "PCPU DCS RD",
    "PCPU DCS WR",
    "GFX DCS RD",
    "GFX DCS WR",
    "MEDIA DCS",
    "DCS RD",
    "DCS WR",
]


def _assert_percent(value):
    assert isinstance(value, int)
    assert 0 <= value <= 100


def _assert_non_negative_number(value):
    assert isinstance(value, (int, float))
    assert value >= 0


def _assert_bandwidth_contract(metric_map):
    assert isinstance(metric_map, dict)
    assert isinstance(metric_map.get("_available"), bool)
    for key in REQUIRED_BANDWIDTH_KEYS:
        assert key in metric_map
        _assert_non_negative_number(metric_map[key])


def test_parse_powermetrics_returns_false_when_file_missing():
    with TemporaryDirectory() as tmpdir:
        base = Path(tmpdir) / "agtop_powermetrics"
        result = utils.parse_powermetrics(path=str(base), timecode="123")
        assert result is False


def test_parse_powermetrics_returns_contract_for_valid_frame():
    payload = {
        "timestamp": 1700000001,
        "processor": {
            "clusters": [
                {
                    "name": "E0",
                    "freq_hz": 2000000000,
                    "idle_ratio": 0.92,
                    "cpus": [
                        {"cpu": 0, "freq_hz": 2000000000, "idle_ratio": 0.90},
                        {"cpu": 1, "freq_hz": 2000000000, "idle_ratio": 0.85},
                    ],
                },
                {
                    "name": "P0",
                    "freq_hz": 3200000000,
                    "idle_ratio": 0.88,
                    "down_ratio": 0.04,
                    "cpus": [
                        {
                            "cpu": 2,
                            "freq_hz": 3200000000,
                            "idle_ratio": 0.80,
                            "down_ratio": 0.05,
                        },
                        {
                            "cpu": 3,
                            "freq_hz": 3200000000,
                            "idle_ratio": 0.78,
                            "down_ratio": 0.06,
                        },
                    ],
                },
            ],
            "cpu_energy": 2400.0,
            "gpu_energy": 1200.0,
            "ane_energy": 300.0,
        },
        "gpu": {"freq_hz": 500000000, "idle_ratio": 0.25},
        "thermal_pressure": "Nominal",
        "bandwidth_counters": [
            {"name": "ECPU0 DCS RD", "value": 2_000_000_000},
            {"name": "ECPU0 DCS WR", "value": 1_000_000_000},
            {"name": "PCPU0 DCS RD", "value": 4_000_000_000},
            {"name": "PCPU0 DCS WR", "value": 2_000_000_000},
            {"name": "GFX DCS RD", "value": 6_000_000_000},
            {"name": "GFX DCS WR", "value": 1_000_000_000},
            {"name": "DCS RD", "value": 14_000_000_000},
            {"name": "DCS WR", "value": 4_000_000_000},
        ],
    }

    with TemporaryDirectory() as tmpdir:
        base = Path(tmpdir) / "agtop_powermetrics"
        base.write_bytes(plistlib.dumps(payload, fmt=plistlib.FMT_XML))
        result = utils.parse_powermetrics(path=str(base), timecode="")

    assert result is not False
    cpu_metrics, gpu_metrics, thermal_pressure, bandwidth_metrics, timestamp = result

    assert isinstance(timestamp, int)
    assert timestamp >= 0
    assert isinstance(thermal_pressure, str)
    assert thermal_pressure != ""

    _assert_percent(cpu_metrics["E-Cluster_active"])
    _assert_percent(cpu_metrics["P-Cluster_active"])
    _assert_non_negative_number(cpu_metrics["E-Cluster_freq_Mhz"])
    _assert_non_negative_number(cpu_metrics["P-Cluster_freq_Mhz"])
    _assert_non_negative_number(cpu_metrics["cpu_W"])
    _assert_non_negative_number(cpu_metrics["gpu_W"])
    _assert_non_negative_number(cpu_metrics["ane_W"])
    _assert_non_negative_number(cpu_metrics["package_W"])
    assert isinstance(cpu_metrics["e_core"], list)
    assert isinstance(cpu_metrics["p_core"], list)
    assert all(
        isinstance(core_id, int) and core_id >= 0 for core_id in cpu_metrics["e_core"]
    )
    assert all(
        isinstance(core_id, int) and core_id >= 0 for core_id in cpu_metrics["p_core"]
    )

    _assert_percent(gpu_metrics["active"])
    _assert_non_negative_number(gpu_metrics["freq_MHz"])

    _assert_bandwidth_contract(bandwidth_metrics)
    assert bandwidth_metrics["_available"] is True
    assert bandwidth_metrics["DCS RD"] > 0
    assert bandwidth_metrics["DCS WR"] > 0


def test_parse_powermetrics_falls_back_to_previous_complete_frame():
    payload = {
        "timestamp": 1700000004,
        "processor": {},
        "gpu": {},
        "thermal_pressure": "Nominal",
        "bandwidth_counters": [
            {"name": "DCS RD", "value": 3_000_000_000},
            {"name": "DCS WR", "value": 2_000_000_000},
        ],
    }
    complete_frame = plistlib.dumps(payload, fmt=plistlib.FMT_XML)
    partial_frame = b"<plist><dict><key>bandwidth_counters</key>"

    with TemporaryDirectory() as tmpdir:
        base = Path(tmpdir) / "agtop_powermetrics"
        base.write_bytes(complete_frame + b"\x00" + partial_frame)
        result = utils.parse_powermetrics(path=str(base), timecode="")

    assert result is not False
    _, _, _, bandwidth_metrics, timestamp = result
    assert timestamp == 1700000004
    _assert_bandwidth_contract(bandwidth_metrics)
    assert bandwidth_metrics["_available"] is True
    assert bandwidth_metrics["DCS RD"] > 0
    assert bandwidth_metrics["DCS WR"] > 0


def test_parse_powermetrics_handles_absent_or_malformed_bandwidth_counters():
    malformed_payloads = [
        {
            "timestamp": 1700000002,
            "processor": {},
            "gpu": {},
            "thermal_pressure": "Nominal",
        },
        {
            "timestamp": 1700000003,
            "processor": {},
            "gpu": {},
            "thermal_pressure": "Nominal",
            "bandwidth_counters": {"not": "a-list"},
        },
    ]

    for payload in malformed_payloads:
        with TemporaryDirectory() as tmpdir:
            base = Path(tmpdir) / "agtop_powermetrics"
            base.write_bytes(plistlib.dumps(payload, fmt=plistlib.FMT_XML))
            result = utils.parse_powermetrics(path=str(base), timecode="")

        assert result is not False
        _, _, _, bandwidth_metrics, _ = result
        _assert_bandwidth_contract(bandwidth_metrics)
        assert bandwidth_metrics["_available"] is False
