"""BrailleChart glyph geometry and per-column coloring, through the real
render path.

The chart is exercised the way the TUI uses it: mounted in a minimal host
``App`` (a mount point only — the widget, its ``data`` setter, and ``render()``
are the production code under test), given a fixed cell size so the geometry
assertions are deterministic regardless of the terminal the suite runs under.
"""

import asyncio

from rich.console import Console
from rich.text import Text
from textual.app import App, ComposeResult

from agtop.tui.widgets import BrailleChart

_BRAILLE_BLANK = "⠀"
_BLOCK_BLANK = " "


class _ChartHost(App):
    """Mounts one BrailleChart pinned to an exact cell size."""

    def __init__(self, width, height, glyph_mode, color_mode) -> None:
        super().__init__()
        self._w = width
        self._h = height
        self._glyph_mode = glyph_mode
        # Pin the color tier so rendered styles are deterministic regardless of
        # the terminal the suite runs under (CI has no TERM, which otherwise
        # resolves to the "none" tier and drops all color).
        self._color_mode = color_mode
        self.chart = None

    def compose(self) -> ComposeResult:
        chart = BrailleChart(glyph_mode=self._glyph_mode, color_mode=self._color_mode)
        chart.styles.width = self._w
        chart.styles.height = self._h
        self.chart = chart
        yield chart


def _render_chart(
    data, width, height, glyph_mode="dots", color_mode="truecolor"
) -> Text:
    async def _run() -> Text:
        app = _ChartHost(width, height, glyph_mode, color_mode)
        async with app.run_test(size=(width + 8, height + 8)) as pilot:
            app.chart.data = data
            await pilot.pause()
            return app.chart.render()

    rendered = asyncio.run(_run())
    assert isinstance(rendered, Text)
    return rendered


def _offset(row: int, col: int, width: int) -> int:
    return row * (width + 1) + col


def _column_styles(rendered: Text, width: int, height: int, col: int) -> list[str]:
    console = Console(color_system="truecolor", width=120)
    styles: list[str] = []
    for row in range(height):
        offset = _offset(row=row, col=col, width=width)
        glyph = rendered.plain[offset]
        if glyph not in (_BRAILLE_BLANK, _BLOCK_BLANK):
            style = rendered.get_style_at_offset(console, offset)
            styles.append(str(style))
    return styles


def test_vertical_line_paints_one_color_for_the_whole_column() -> None:
    # A high reading fills the whole column, and every cell shares one color.
    rendered = _render_chart(data=[80.0], width=1, height=4, glyph_mode="dots")
    styles = _column_styles(rendered=rendered, width=1, height=4, col=0)

    assert len(styles) == 4
    assert len(set(styles)) == 1
    assert styles[0].startswith("rgb(")  # truecolor tier emits an rgb() style


def test_column_color_tracks_the_current_reading() -> None:
    # The column color is derived from the latest value, so two different
    # readings must produce two different colors (not a fixed hue).
    cool = set(_column_styles(_render_chart([20.0], 1, 4), width=1, height=4, col=0))
    hot = set(_column_styles(_render_chart([95.0], 1, 4), width=1, height=4, col=0))

    assert len(cool) == 1 and len(hot) == 1
    assert cool != hot


def test_zero_and_tiny_values_keep_fill_contract() -> None:
    rendered = _render_chart(data=[0.0, 1.0], width=2, height=2, glyph_mode="dots")
    rows = rendered.plain.splitlines()

    assert rows[0][0] == _BRAILLE_BLANK
    assert rows[1][0] == _BRAILLE_BLANK

    non_blank_count = sum(1 for row in rows if row[1] != _BRAILLE_BLANK)
    assert non_blank_count == 1

    tiny_value_styles = _column_styles(rendered=rendered, width=2, height=2, col=1)
    assert len(tiny_value_styles) == 1
    assert tiny_value_styles[0].startswith("rgb(")


def test_block_mode_uses_block_glyphs_with_uniform_color() -> None:
    rendered = _render_chart(data=[80.0], width=1, height=4, glyph_mode="block")
    rows = rendered.plain.splitlines()

    assert rows[0][0] == "▂"
    assert rows[1][0] == "█"
    assert rows[2][0] == "█"
    assert rows[3][0] == "█"

    styles = _column_styles(rendered=rendered, width=1, height=4, col=0)
    assert len(styles) == 4
    assert len(set(styles)) == 1
    assert styles[0].startswith("rgb(")
