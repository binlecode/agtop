"""Textual widgets for the agtop hardware dashboard."""

from collections import deque

from textual.app import ComposeResult
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Sparkline, Static

from agtop.models import SystemSnapshot
from agtop.power_scaling import (
    DEFAULT_CPU_FLOOR_W,
    DEFAULT_GPU_FLOOR_W,
    clamp_percent,
    power_to_percent,
)


_BLOCK_CHARS = " ▁▂▃▄▅▆▇█"


def _block_spark(history, width=8):
    """Render a short inline sparkline using block characters."""
    vals = list(history)[-width:]
    if not vals:
        return " " * width
    hi = max(vals) or 1
    return "".join(_BLOCK_CHARS[min(8, int(v / hi * 8))] for v in vals)


class MetricsUpdated(Message):
    """Posted by AgtopApp when a new hardware snapshot is ready."""

    def __init__(self, snapshot: SystemSnapshot, ram: dict, processes: dict) -> None:
        self.snapshot = snapshot
        self.ram = ram  # from get_ram_metrics_dict()
        self.processes = processes  # {"cpu": [...], "memory": [...]}
        super().__init__()


class HardwareDashboard(Widget):
    """Hardware metrics panel: CPU/GPU/ANE/RAM/Power charts + status line."""

    def __init__(self, config, **kwargs) -> None:
        super().__init__(**kwargs)
        self._config = config
        cfg = config

        maxlen = max(2, cfg.avg_window)
        swap_maxlen = max(2, cfg.alert_sustain_samples + 1)

        self._ecpu_hist: deque = deque([0] * maxlen, maxlen=maxlen)
        self._pcpu_hist: deque = deque([0] * maxlen, maxlen=maxlen)
        self._gpu_hist: deque = deque([0] * maxlen, maxlen=maxlen)
        self._ane_hist: deque = deque([0] * maxlen, maxlen=maxlen)
        self._ram_hist: deque = deque([0] * maxlen, maxlen=maxlen)
        self._cpupwr_hist: deque = deque([0] * maxlen, maxlen=maxlen)
        self._gpupwr_hist: deque = deque([0] * maxlen, maxlen=maxlen)

        self._swap_hist: deque = deque([], maxlen=swap_maxlen)

        self._cpu_peak_w: float = 0.0
        self._gpu_peak_w: float = 0.0

        self._high_bw_counter: int = 0
        self._high_pkg_counter: int = 0

        # Per-core history (dict: index -> deque)
        self._core_hist: dict = {}

    def compose(self) -> ComposeResult:
        cfg = self._config

        yield Static("E-CPU 0% @0MHz", id="ecpu-label", classes="metric-label")
        yield Sparkline(
            list(self._ecpu_hist),
            summary_function=max,
            id="ecpu-chart",
            classes="metric-chart",
        )

        yield Static("P-CPU 0% @0MHz", id="pcpu-label", classes="metric-label")
        yield Sparkline(
            list(self._pcpu_hist),
            summary_function=max,
            id="pcpu-chart",
            classes="metric-chart",
        )

        from textual.containers import Horizontal

        with Horizontal(classes="metric-pair"):
            with Widget(classes="metric-col"):
                yield Static("GPU 0% @0MHz", id="gpu-label", classes="metric-label")
                yield Sparkline(
                    list(self._gpu_hist),
                    summary_function=max,
                    id="gpu-chart",
                    classes="metric-chart",
                )
            with Widget(classes="metric-col"):
                yield Static("ANE 0%", id="ane-label", classes="metric-label")
                yield Sparkline(
                    list(self._ane_hist),
                    summary_function=max,
                    id="ane-chart",
                    classes="metric-chart",
                )

        yield Static("RAM 0%", id="ram-label", classes="metric-label")
        yield Sparkline(
            list(self._ram_hist),
            summary_function=max,
            id="ram-chart",
            classes="metric-chart",
        )

        with Horizontal(classes="metric-pair"):
            with Widget(classes="metric-col"):
                yield Static("CPU Power 0W", id="cpupwr-label", classes="metric-label")
                yield Sparkline(
                    list(self._cpupwr_hist),
                    summary_function=max,
                    id="cpupwr-chart",
                    classes="metric-chart",
                )
            with Widget(classes="metric-col"):
                yield Static("GPU Power 0W", id="gpupwr-label", classes="metric-label")
                yield Sparkline(
                    list(self._gpupwr_hist),
                    summary_function=max,
                    id="gpupwr-chart",
                    classes="metric-chart",
                )

        yield Static(
            "thermal: Nominal  alerts: none", id="status-line", classes="status-line"
        )

        if cfg.show_cores:
            yield Static("", id="ecores-row", classes="core-row")
            yield Static("", id="pcores-row", classes="core-row")

    def update_metrics(self, message: MetricsUpdated) -> None:
        """Update all dashboard widgets from new metrics. Called by AgtopApp."""
        s = message.snapshot
        ram = message.ram
        cfg = self._config

        ecpu = clamp_percent(s.ecpu_util_pct)
        pcpu = clamp_percent(s.pcpu_util_pct)
        gpu = clamp_percent(s.gpu_util_pct)
        ane_pct = clamp_percent(s.ane_watts / cfg.ane_max_power * 100)
        ram_pct = clamp_percent(ram.get("used_percent", 0))

        self._ecpu_hist.append(ecpu)
        self._pcpu_hist.append(pcpu)
        self._gpu_hist.append(gpu)
        self._ane_hist.append(ane_pct)
        self._ram_hist.append(ram_pct)

        # Power percents
        self._cpu_peak_w = max(self._cpu_peak_w, s.cpu_watts)
        self._gpu_peak_w = max(self._gpu_peak_w, s.gpu_watts)
        cpu_pwr_pct = power_to_percent(
            power_w=s.cpu_watts,
            mode=cfg.power_scale,
            profile_ref_w=cfg.cpu_chart_ref_w,
            peak_w=self._cpu_peak_w,
            floor_w=DEFAULT_CPU_FLOOR_W,
        )
        gpu_pwr_pct = power_to_percent(
            power_w=s.gpu_watts,
            mode=cfg.power_scale,
            profile_ref_w=cfg.gpu_chart_ref_w,
            peak_w=self._gpu_peak_w,
            floor_w=DEFAULT_GPU_FLOOR_W,
        )
        self._cpupwr_hist.append(cpu_pwr_pct)
        self._gpupwr_hist.append(gpu_pwr_pct)

        self._swap_hist.append(max(0.0, float(ram.get("swap_used_GB", 0.0) or 0.0)))

        # Update sparklines
        self.query_one("#ecpu-chart", Sparkline).data = list(self._ecpu_hist)
        self.query_one("#pcpu-chart", Sparkline).data = list(self._pcpu_hist)
        self.query_one("#gpu-chart", Sparkline).data = list(self._gpu_hist)
        self.query_one("#ane-chart", Sparkline).data = list(self._ane_hist)
        self.query_one("#ram-chart", Sparkline).data = list(self._ram_hist)
        self.query_one("#cpupwr-chart", Sparkline).data = list(self._cpupwr_hist)
        self.query_one("#gpupwr-chart", Sparkline).data = list(self._gpupwr_hist)

        # Update labels
        cpu_temp = " ({:.0f}°C)".format(s.cpu_temp_c) if s.cpu_temp_c > 0 else ""
        gpu_temp = " ({:.0f}°C)".format(s.gpu_temp_c) if s.gpu_temp_c > 0 else ""
        self.query_one("#ecpu-label", Static).update(
            "E-CPU {}% @{}MHz{}".format(ecpu, s.ecpu_freq_mhz, cpu_temp)
        )
        self.query_one("#pcpu-label", Static).update(
            "P-CPU {}% @{}MHz{}".format(pcpu, s.pcpu_freq_mhz, cpu_temp)
        )
        self.query_one("#gpu-label", Static).update(
            "GPU {}% @{}MHz{}".format(gpu, s.gpu_freq_mhz, gpu_temp)
        )
        self.query_one("#ane-label", Static).update(
            "ANE {}% ({:.1f}W)".format(ane_pct, s.ane_watts)
        )

        used_gb = ram.get("used_GB", 0.0)
        total_gb = ram.get("total_GB", 0.0)
        swap_used = ram.get("swap_used_GB", 0.0)
        swap_total = ram.get("swap_total_GB", 0.0)
        if (swap_total or 0.0) >= 0.1:
            ram_label = "RAM {}/{}GB sw:{}/{}GB".format(
                used_gb, total_gb, swap_used, swap_total
            )
        else:
            ram_label = "RAM {}/{}GB".format(used_gb, total_gb)
        self.query_one("#ram-label", Static).update(ram_label)

        self.query_one("#cpupwr-label", Static).update(
            "CPU Power {:.2f}W".format(s.cpu_watts)
        )
        self.query_one("#gpupwr-label", Static).update(
            "GPU Power {:.2f}W".format(s.gpu_watts)
        )

        # Update per-core rows
        if cfg.show_cores:
            self._update_core_row("#ecores-row", s.e_cores, "E")
            self._update_core_row("#pcores-row", s.p_cores, "P")

        # Compute and update status/alerts
        self._compute_alerts(s, ram)

    def _update_core_row(self, widget_id: str, cores: list, prefix: str) -> None:
        """Update a core-row Static with inline block sparklines, 4 per line."""
        if not cores:
            self.query_one(widget_id, Static).update("")
            return
        parts = []
        for i, core in enumerate(cores):
            hist = self._core_hist.setdefault(
                (prefix, core.index),
                deque([0] * 8, maxlen=8),
            )
            hist.append(core.active_pct)
            spark = _block_spark(hist, width=8)
            parts.append(
                "{}{} {}% {}".format(prefix, core.index + 1, core.active_pct, spark)
            )
            if (i + 1) % 4 == 0 and i + 1 < len(cores):
                parts.append("\n")
        self.query_one(widget_id, Static).update("  ".join(parts))

    def _compute_alerts(self, s: SystemSnapshot, ram: dict) -> None:
        """Compute alert flags and update the status line."""
        cfg = self._config

        # Bandwidth saturation: compare total BW to total capacity (cpu + gpu refs).
        # The old dashing TUI fired on the hottest individual channel; since
        # SystemSnapshot only exposes the aggregate total, we normalise against
        # the sum of cpu and gpu channel references — the closest equivalent.
        total_bw_ref = max(cfg.max_cpu_bw + cfg.max_gpu_bw, 1.0)
        bw_pct = (
            clamp_percent(s.bandwidth_gbps / total_bw_ref * 100)
            if s.bandwidth_available
            else 0
        )
        if s.bandwidth_available and bw_pct >= cfg.alert_bw_sat_percent:
            self._high_bw_counter += 1
        else:
            self._high_bw_counter = 0
        bw_alert = self._high_bw_counter >= cfg.alert_sustain_samples

        # Package power
        pkg_pct = clamp_percent(s.package_watts / max(cfg.package_ref_w, 1.0) * 100)
        if pkg_pct >= cfg.alert_package_power_percent:
            self._high_pkg_counter += 1
        else:
            self._high_pkg_counter = 0
        pkg_alert = self._high_pkg_counter >= cfg.alert_sustain_samples

        # Swap rise
        swap_history_points = cfg.alert_sustain_samples + 1
        swap_rise = (
            max(0.0, self._swap_hist[-1] - self._swap_hist[0])
            if len(self._swap_hist) > 1
            else 0.0
        )
        swap_total = float(ram.get("swap_total_GB", 0.0) or 0.0)
        swap_alert = (
            swap_total >= 0.1
            and len(self._swap_hist) >= swap_history_points
            and swap_rise >= cfg.alert_swap_rise_gb
        )

        # Thermal
        thermal_alert = s.thermal_state not in ("Nominal", "Unknown")

        active_alerts = []
        if thermal_alert:
            active_alerts.append("THERMAL")
        if bw_alert:
            active_alerts.append("BW>{}%".format(cfg.alert_bw_sat_percent))
        if swap_alert:
            active_alerts.append("SWAP+{:.1f}G".format(swap_rise))
        if pkg_alert:
            active_alerts.append("PKG>{}%".format(cfg.alert_package_power_percent))
        alerts_str = ", ".join(active_alerts) if active_alerts else "none"

        self.query_one("#status-line", Static).update(
            "thermal: {}  alerts: {}".format(s.thermal_state, alerts_str)
        )
