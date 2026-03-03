"""Textual widgets for the agtop hardware dashboard."""

from collections import deque

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Static

from agtop.models import SystemSnapshot
from agtop.power_scaling import (
    DEFAULT_CPU_FLOOR_W,
    DEFAULT_GPU_FLOOR_W,
    clamp_percent,
    power_to_percent,
)


_COOL_RGB = (66, 135, 245)  # blue
_HOT_RGB = (240, 70, 64)  # red

# Cumulative braille fill bits for a left-column vertical pole, indexed 0 (bottom
# dot only) to 3 (all 4 dots filled): dots 7 / 7+3 / 7+3+2 / 7+3+2+1.
_BRAILLE_FILL_BITS = [0x40, 0x44, 0x46, 0x47]
_BRAILLE_FULL = 0x47  # all 4 left-column dots
_BRAILLE_BLANK = "\u2800"
_BLOCK_FILL_GLYPHS = ["\u2582", "\u2584", "\u2586", "\u2588"]
_BLOCK_FULL_GLYPH = "\u2588"
_BLOCK_BLANK = " "


def _pct_to_color(pct: float) -> str:
    """Map 0-100 percentage to a blue->red RGB color."""
    p = min(100.0, max(0.0, float(pct))) / 100.0
    r = round(_COOL_RGB[0] + (_HOT_RGB[0] - _COOL_RGB[0]) * p)
    g = round(_COOL_RGB[1] + (_HOT_RGB[1] - _COOL_RGB[1]) * p)
    b = round(_COOL_RGB[2] + (_HOT_RGB[2] - _COOL_RGB[2]) * p)
    return "rgb({},{},{})".format(r, g, b)


def _braille_vbar(v: float) -> str:
    """Map 0–100 % to a filled vertical pole (4 levels, bottom to top)."""
    n = max(0, min(4, round(v / 100 * 4)))
    if n == 0 and v > 0:
        n = 1
    if n == 0:
        return _BRAILLE_BLANK
    return chr(0x2800 | _BRAILLE_FILL_BITS[n - 1])


class BrailleChart(Widget):
    """Sparkline chart with `dots` (braille) or `block` glyph modes.

    Each character is one time sample. The dot position encodes the value:
    4 dot levels per terminal row, so height=2 gives 8 levels, height=4 gives 16.
    """

    DEFAULT_CSS = """
    BrailleChart {
        height: 2;
    }
    """

    def __init__(self, glyph_mode: str = "dots", **kwargs) -> None:
        super().__init__(**kwargs)
        self._data = []
        self._glyph_mode = self._normalize_glyph_mode(glyph_mode)

    @staticmethod
    def _normalize_glyph_mode(value: str) -> str:
        return "block" if str(value).strip().lower() == "block" else "dots"

    @property
    def data(self):
        return self._data

    @data.setter
    def data(self, values) -> None:
        self._data = values
        self.refresh()

    @property
    def glyph_mode(self) -> str:
        return self._glyph_mode

    def set_glyph_mode(self, glyph_mode: str) -> None:
        normalized = self._normalize_glyph_mode(glyph_mode)
        if normalized == self._glyph_mode:
            return
        self._glyph_mode = normalized
        self.refresh()

    def render(self):
        width = self.size.width
        height = self.size.height
        if width <= 0 or height <= 0:
            return ""
        if self._glyph_mode == "block":
            blank_glyph = _BLOCK_BLANK
            full_glyph = _BLOCK_FULL_GLYPH
            partial_glyphs = _BLOCK_FILL_GLYPHS
        else:
            blank_glyph = _BRAILLE_BLANK
            full_glyph = chr(0x2800 | _BRAILLE_FULL)
            partial_glyphs = [chr(0x2800 | bits) for bits in _BRAILLE_FILL_BITS]
        n = width  # 1 sample per character
        dlen = len(self._data)
        offset = dlen - n
        total = height * 4  # 4 dot positions per terminal row
        out = Text()
        for row in range(height):
            for col in range(width):
                i = offset + col
                v = min(100.0, max(0.0, float(self._data[i]) if i >= 0 else 0.0))
                line_color = _pct_to_color(v)
                level = max(0, min(total, round(v / 100 * total)))
                if v > 0 and level == 0:
                    level = 1
                if level > 0:
                    dot_row = height - 1 - (level - 1) // 4
                    if row > dot_row:
                        # below the peak row: fully filled segment
                        out.append(full_glyph, style=line_color)
                    elif row == dot_row:
                        # peak row: partial fill
                        pos = (level - 1) % 4  # 0 = bottom dot, 3 = top dot
                        out.append(partial_glyphs[pos], style=line_color)
                    else:
                        out.append(blank_glyph)
                else:
                    out.append(blank_glyph)
            if row < height - 1:
                out.append("\n")
        return out


def _braille_spark(history, width_chars: int = 8) -> str:
    """Inline braille sparkline, 1 sample per character, 8 dot levels."""
    if width_chars <= 0:
        return ""
    n = width_chars
    vals = list(history)[-n:]
    vals = [0.0] * (n - len(vals)) + [min(100.0, max(0.0, float(v))) for v in vals]
    return "".join(_braille_vbar(v) for v in vals)


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
        self._chart_glyph = getattr(cfg, "chart_glyph", "dots")

        maxlen = 500
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

        with Vertical(id="cpu-section"):
            with Vertical(classes="cpu-half"):
                yield Static(
                    "P-CPU   0% @0MHz",
                    id="pcpu-summary-row",
                    classes="cpu-summary-row",
                )
                yield BrailleChart(
                    glyph_mode=self._chart_glyph,
                    id="pcpu-chart",
                    classes="metric-chart",
                )
                if cfg.show_cores:
                    yield Static("", id="pcores-grid", classes="core-grid")
            with Vertical(classes="cpu-half"):
                yield Static(
                    "E-CPU   0% @0MHz",
                    id="ecpu-summary-row",
                    classes="cpu-summary-row",
                )
                yield BrailleChart(
                    glyph_mode=self._chart_glyph,
                    id="ecpu-chart",
                    classes="metric-chart",
                )
                if cfg.show_cores:
                    yield Static("", id="ecores-grid", classes="core-grid")

        yield Static("GPU 0% @0MHz", id="gpu-label", classes="metric-label")
        yield BrailleChart(
            glyph_mode=self._chart_glyph, id="gpu-chart", classes="metric-chart"
        )

        yield Static("ANE 0%", id="ane-label", classes="metric-label")
        yield BrailleChart(
            glyph_mode=self._chart_glyph, id="ane-chart", classes="metric-chart"
        )

        yield Static("RAM 0%", id="ram-label", classes="metric-label")
        yield BrailleChart(
            glyph_mode=self._chart_glyph, id="ram-chart", classes="metric-chart"
        )

        yield Static("CPU Power 0W", id="cpupwr-label", classes="metric-label")
        yield BrailleChart(
            glyph_mode=self._chart_glyph, id="cpupwr-chart", classes="metric-chart"
        )

        yield Static("GPU Power 0W", id="gpupwr-label", classes="metric-label")
        yield BrailleChart(
            glyph_mode=self._chart_glyph, id="gpupwr-chart", classes="metric-chart"
        )

        yield Static(
            "thermal: Nominal  alerts: none", id="status-line", classes="status-line"
        )

    @property
    def chart_glyph(self) -> str:
        return self._chart_glyph

    def set_chart_glyph(self, glyph_mode: str) -> None:
        self._chart_glyph = BrailleChart._normalize_glyph_mode(glyph_mode)
        for chart in self.query(BrailleChart):
            chart.set_glyph_mode(self._chart_glyph)

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
        if s.cpu_watts > 0 and cpu_pwr_pct == 0:
            cpu_pwr_pct = 1
        gpu_pwr_pct = power_to_percent(
            power_w=s.gpu_watts,
            mode=cfg.power_scale,
            profile_ref_w=cfg.gpu_chart_ref_w,
            peak_w=self._gpu_peak_w,
            floor_w=DEFAULT_GPU_FLOOR_W,
        )
        if s.gpu_watts > 0 and gpu_pwr_pct == 0:
            gpu_pwr_pct = 1
        self._cpupwr_hist.append(cpu_pwr_pct)
        self._gpupwr_hist.append(gpu_pwr_pct)

        self._swap_hist.append(max(0.0, float(ram.get("swap_used_GB", 0.0) or 0.0)))

        # Update charts
        chart_data = (
            ("#pcpu-chart", self._pcpu_hist),
            ("#ecpu-chart", self._ecpu_hist),
            ("#gpu-chart", self._gpu_hist),
            ("#ane-chart", self._ane_hist),
            ("#ram-chart", self._ram_hist),
            ("#cpupwr-chart", self._cpupwr_hist),
            ("#gpupwr-chart", self._gpupwr_hist),
        )
        for widget_id, data in chart_data:
            self.query_one(widget_id, BrailleChart).data = data

        # Update labels
        cpu_temp = " ({:.0f}°C)".format(s.cpu_temp_c) if s.cpu_temp_c > 0 else ""
        gpu_temp = " ({:.0f}°C)".format(s.gpu_temp_c) if s.gpu_temp_c > 0 else ""
        self._update_cluster_summary_row(
            "#pcpu-summary-row",
            "P-CPU",
            pcpu,
            s.pcpu_freq_mhz,
            cpu_temp,
        )
        self._update_cluster_summary_row(
            "#ecpu-summary-row",
            "E-CPU",
            ecpu,
            s.ecpu_freq_mhz,
            cpu_temp,
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
            self._update_core_two_col("#pcores-grid", s.p_cores, "P")
            self._update_core_two_col("#ecores-grid", s.e_cores, "E")

        # Compute and update status/alerts
        self._compute_alerts(s, ram)

    _CORE_GRID_SEP = " │ "
    _CORE_HIST_MAXLEN = 500
    _CORE_MIN_SPARK_CHARS = 3

    def _update_cluster_summary_row(
        self,
        widget_id: str,
        label: str,
        util_pct: int,
        freq_mhz: int,
        cpu_temp: str,
    ) -> None:
        """Render one full-width cluster summary line."""
        widget = self.query_one(widget_id, Static)
        avail = max(widget.size.width, 1)
        line = "{} {:3d}% @{}MHz{}".format(label, util_pct, freq_mhz, cpu_temp)
        widget.update(line[:avail].ljust(avail))

    def _format_core_entry(self, prefix: str, core, col_width: int) -> str:
        """Format one core row, adapting spark width to the column."""
        if col_width <= 0:
            return ""
        hist = self._core_hist.setdefault(
            (prefix, core.index),
            deque(
                [0] * self._CORE_MIN_SPARK_CHARS,
                maxlen=self._CORE_HIST_MAXLEN,
            ),
        )
        hist.append(core.active_pct)
        base = "{}{:02d} {:3d}%".format(prefix, core.index, core.active_pct)
        if col_width <= len(base):
            return base[:col_width].ljust(col_width)
        max_spark_w = col_width - len(base) - 1
        spark_w = max(1, max_spark_w)
        entry = "{} {}".format(base, _braille_spark(hist, width_chars=spark_w))
        return entry[:col_width].ljust(col_width)

    def _update_core_two_col(self, widget_id: str, cores: list, prefix: str) -> None:
        """Render one cluster's cores as two vertical columns with one divider."""
        widget = self.query_one(widget_id, Static)
        if not cores:
            widget.update("")
            return

        avail = max(widget.size.width, len(self._CORE_GRID_SEP) + 2)
        left_w = max(1, (avail - len(self._CORE_GRID_SEP)) // 2)
        right_w = max(1, avail - len(self._CORE_GRID_SEP) - left_w)

        rows = []
        for i in range(0, len(cores), 2):
            left = self._format_core_entry(prefix, cores[i], left_w)
            right = (
                self._format_core_entry(prefix, cores[i + 1], right_w)
                if i + 1 < len(cores)
                else "".ljust(right_w)
            )
            rows.append("{}{}{}".format(left, self._CORE_GRID_SEP, right))
        widget.update("\n".join(rows))

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
