from rich.console import Console
from rich.text import Text
from textual.geometry import Size

from agtop.tui.widgets import BrailleChart, _pct_to_color

_BRAILLE_BLANK = "\u2800"
_BLOCK_BLANK = " "


class _FixedSizeBrailleChart(BrailleChart):
    def __init__(self, width: int, height: int, glyph_mode: str = "dots") -> None:
        super().__init__(glyph_mode=glyph_mode)
        self._fixed_size = Size(width, height)

    @property
    def size(self) -> Size:
        return self._fixed_size


def _render_chart(
    data: list[float], width: int, height: int, glyph_mode: str = "dots"
) -> Text:
    chart = _FixedSizeBrailleChart(width=width, height=height, glyph_mode=glyph_mode)
    chart._data = data
    rendered = chart.render()
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


def test_vertical_line_color_comes_from_current_reading() -> None:
    value = 80.0
    rendered = _render_chart(data=[value], width=1, height=4, glyph_mode="dots")

    styles = _column_styles(rendered=rendered, width=1, height=4, col=0)

    assert len(styles) == 4
    assert len(set(styles)) == 1
    assert styles[0] == _pct_to_color(value)


def test_zero_and_tiny_values_keep_fill_contract() -> None:
    rendered = _render_chart(data=[0.0, 1.0], width=2, height=2, glyph_mode="dots")
    rows = rendered.plain.splitlines()

    assert rows[0][0] == _BRAILLE_BLANK
    assert rows[1][0] == _BRAILLE_BLANK

    non_blank_count = sum(1 for row in rows if row[1] != _BRAILLE_BLANK)
    assert non_blank_count == 1

    tiny_value_styles = _column_styles(rendered=rendered, width=2, height=2, col=1)
    assert tiny_value_styles == [_pct_to_color(1.0)]


def test_block_mode_uses_block_glyphs_with_uniform_color() -> None:
    value = 80.0
    rendered = _render_chart(data=[value], width=1, height=4, glyph_mode="block")
    rows = rendered.plain.splitlines()

    assert rows[0][0] == "\u2582"
    assert rows[1][0] == "\u2588"
    assert rows[2][0] == "\u2588"
    assert rows[3][0] == "\u2588"

    styles = _column_styles(rendered=rendered, width=1, height=4, col=0)
    assert len(styles) == 4
    assert len(set(styles)) == 1
    assert styles[0] == _pct_to_color(value)
