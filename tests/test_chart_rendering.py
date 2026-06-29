"""Chart color degradation, NO_COLOR, and time-window labeling.

These validate two presentation contracts through the real render path
(`BrailleChart._render_text`, which `render()` delegates to) and the public
`resolve_color_mode` env resolver:

  * the blue->red gradient degrades across terminal color tiers and disappears
    entirely under NO_COLOR / dumb terminals (no broken truecolor escapes), and
  * the visible chart span is labeled so the window is not silently ambiguous.
"""

from types import SimpleNamespace

from agtop.tui.widgets import (
    BrailleChart,
    HardwareDashboard,
    _format_window_span,
    resolve_color_mode,
)


def _render_styles(color_mode: str):
    """Style strings emitted by a fully-active chart in the given color tier."""
    chart = BrailleChart(color_mode=color_mode)
    chart.data = [80] * 8  # every column non-zero so each cell is styled
    text = chart._render_text(width=8, height=2)
    return [span.style for span in text.spans]


# --- NO_COLOR / tier resolution (https://no-color.org external contract) -----


def test_no_color_overrides_a_truecolor_terminal():
    # Presence of NO_COLOR disables color regardless of terminal capability.
    assert resolve_color_mode(env={"NO_COLOR": "1", "COLORTERM": "truecolor"}) == "none"


def test_color_tier_detected_from_colorterm_and_term():
    assert resolve_color_mode(env={"COLORTERM": "truecolor"}) == "truecolor"
    assert resolve_color_mode(env={"COLORTERM": "24bit"}) == "truecolor"
    assert resolve_color_mode(env={"TERM": "xterm-256color"}) == "256"
    assert resolve_color_mode(env={"TERM": "xterm"}) == "16"


def test_dumb_and_unknown_terminals_get_no_color():
    assert resolve_color_mode(env={"TERM": "dumb"}) == "none"
    assert resolve_color_mode(env={}) == "none"


def test_console_color_system_is_preferred_when_present():
    class _Console:
        color_system = "256"

    # A detected console color system wins over env heuristics...
    assert resolve_color_mode(_Console(), env={"COLORTERM": "truecolor"}) == "256"

    # ...but NO_COLOR still overrides even a truecolor console.
    class _TrueConsole:
        color_system = "truecolor"

    assert resolve_color_mode(_TrueConsole(), env={"NO_COLOR": "1"}) == "none"


# --- the resolved tier actually shapes rendered output -----------------------


def test_truecolor_render_emits_rgb_styles():
    styles = _render_styles("truecolor")
    assert styles  # cells are styled
    assert all(s.startswith("rgb(") for s in styles)


def test_256_render_degrades_to_color_cube_indices():
    styles = _render_styles("256")
    assert styles
    assert all(s.startswith("color(") for s in styles)


def test_16_render_degrades_to_named_severity_ramp():
    styles = _render_styles("16")
    assert styles
    assert set(styles) <= {"blue", "green", "yellow", "red"}


def test_none_render_emits_no_color_styles():
    # NO_COLOR / dumb terminals: not a single color escape is produced.
    no_color_mode = resolve_color_mode(env={"NO_COLOR": "1"})
    assert no_color_mode == "none"
    chart = BrailleChart(color_mode=no_color_mode)
    chart.data = [80] * 8
    text = chart._render_text(width=8, height=2)
    assert text.spans == []


def test_16_ramp_is_cool_to_hot():
    # Low utilization reads cool, high utilization reads hot — the ramp must not
    # invert, or the severity cue would be backwards.
    low = set(_render_styles_for_value("16", 10.0))
    high = set(_render_styles_for_value("16", 95.0))
    assert low == {"blue"}
    assert high == {"red"}


def _render_styles_for_value(color_mode: str, value: float):
    chart = BrailleChart(color_mode=color_mode)
    chart.data = [value] * 8
    text = chart._render_text(width=8, height=2)
    return [span.style for span in text.spans]


# --- chart time-window label -------------------------------------------------


def test_window_span_formats_seconds_minutes_and_hours():
    assert _format_window_span(45) == "45s"
    assert _format_window_span(120) == "2m"  # exact minute drops the seconds
    assert _format_window_span(128) == "2m08s"  # seconds zero-padded
    assert _format_window_span(3600) == "1h"
    assert _format_window_span(3660) == "1h01m"


def test_window_span_is_never_negative():
    assert _format_window_span(-5) == "0s"


def test_window_label_is_safe_before_layout():
    # _chart_window_label runs inside the per-frame alert path; before the chart
    # is laid out the width query fails, and it must degrade to "" rather than
    # raising and taking down the render loop.
    dash = HardwareDashboard(
        config=SimpleNamespace(
            alert_sustain_samples=3, chart_glyph="dots", sample_interval=2
        )
    )
    assert dash._chart_window_label() == ""
