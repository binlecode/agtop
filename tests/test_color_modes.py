from agtop.color_modes import (
    COLOR_MODE_256,
    COLOR_MODE_BASIC,
    COLOR_MODE_MONO,
    COLOR_MODE_TRUECOLOR,
    detect_color_mode,
    parse_color_mode_override,
    value_to_color_index,
    value_to_rgb,
)


class FakeTerminal:
    def __init__(self, number_of_colors=256, does_styling=True):
        self.number_of_colors = number_of_colors
        self.does_styling = does_styling

    def rgb_downconvert(self, r, g, b):
        # Deterministic pseudo-index for testing.
        return (r + g + b) % 256


def test_parse_color_mode_override_valid_values():
    assert parse_color_mode_override("mono") == COLOR_MODE_MONO
    assert parse_color_mode_override("basic") == COLOR_MODE_BASIC
    assert parse_color_mode_override("256") == COLOR_MODE_256
    assert parse_color_mode_override("xterm256") == COLOR_MODE_256
    assert parse_color_mode_override("truecolor") == COLOR_MODE_TRUECOLOR
    assert parse_color_mode_override(" TRUECOLOR ") == COLOR_MODE_TRUECOLOR


def test_parse_color_mode_override_auto_returns_none():
    assert parse_color_mode_override("auto") is None
    assert parse_color_mode_override(" AUTO ") is None


def test_parse_color_mode_override_invalid_returns_none():
    assert parse_color_mode_override("bogus") is None
    assert parse_color_mode_override("") is None
    assert parse_color_mode_override(None) is None


def test_detect_color_mode_no_color_precedence():
    env = {"NO_COLOR": "1", "COLORTERM": "truecolor", "TERM": "xterm-256color"}
    terminal = FakeTerminal(number_of_colors=1 << 24, does_styling=True)
    assert detect_color_mode(env, terminal) == COLOR_MODE_MONO


def test_detect_color_mode_term_dumb():
    env = {"TERM": "dumb"}
    terminal = FakeTerminal(number_of_colors=256, does_styling=True)
    assert detect_color_mode(env, terminal) == COLOR_MODE_MONO


def test_detect_color_mode_colorterm_truecolor():
    env = {"COLORTERM": "truecolor", "TERM": "xterm-256color"}
    terminal = FakeTerminal(number_of_colors=256, does_styling=True)
    assert detect_color_mode(env, terminal) == COLOR_MODE_TRUECOLOR


def test_detect_color_mode_256_from_terminal_depth():
    env = {"TERM": "xterm-256color"}
    terminal = FakeTerminal(number_of_colors=256, does_styling=True)
    assert detect_color_mode(env, terminal) == COLOR_MODE_256


def test_detect_color_mode_force_color_enables_styling():
    env = {"FORCE_COLOR": "1", "TERM": "xterm"}
    terminal = FakeTerminal(number_of_colors=16, does_styling=False)
    assert detect_color_mode(env, terminal) == COLOR_MODE_BASIC


def test_value_to_rgb_boundaries():
    assert value_to_rgb(0) == (0, 200, 0)
    assert value_to_rgb(50) == (230, 220, 0)
    assert value_to_rgb(75) == (255, 140, 0)
    assert value_to_rgb(100) == (220, 0, 0)


def test_value_to_rgb_interpolation_midpoints():
    # 25% between green/yellow
    assert value_to_rgb(25) == (115, 210, 0)
    # 60% between yellow/orange
    assert value_to_rgb(60) == (240, 188, 0)
    # 90% between orange/red
    assert value_to_rgb(90) == (234, 56, 0)


def test_value_to_rgb_uses_fractional_percent():
    assert value_to_rgb(25.1) != value_to_rgb(25.9)


def test_value_to_color_index_basic_thresholds():
    terminal = FakeTerminal(number_of_colors=16, does_styling=True)
    assert value_to_color_index(10, COLOR_MODE_BASIC, terminal, seed_color=2) == 2
    assert value_to_color_index(50, COLOR_MODE_BASIC, terminal, seed_color=2) == 3
    assert value_to_color_index(90, COLOR_MODE_BASIC, terminal, seed_color=2) == 1


def test_value_to_color_index_mono_returns_zero():
    terminal = FakeTerminal(number_of_colors=1 << 24, does_styling=True)
    assert value_to_color_index(80, COLOR_MODE_MONO, terminal, seed_color=7) == 0


def test_forced_truecolor_degrades_when_terminal_has_no_styling():
    terminal = FakeTerminal(number_of_colors=1 << 24, does_styling=False)
    assert value_to_color_index(80, COLOR_MODE_TRUECOLOR, terminal, seed_color=7) == 0


def test_forced_256_degrades_when_terminal_depth_is_low():
    terminal = FakeTerminal(number_of_colors=16, does_styling=True)
    # 80% -> red in basic mapping
    assert value_to_color_index(80, COLOR_MODE_256, terminal, seed_color=7) == 1


def test_value_to_color_index_never_raises():
    class BrokenTerminal:
        does_styling = True
        number_of_colors = 256

        def rgb_downconvert(self, *_args, **_kwargs):
            raise RuntimeError("broken")

    terminal = BrokenTerminal()
    assert value_to_color_index(45, COLOR_MODE_256, terminal, seed_color=5) == 5
