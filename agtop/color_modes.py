from __future__ import annotations

from typing import Mapping

COLOR_MODE_AUTO = "auto"
COLOR_MODE_MONO = "mono"
COLOR_MODE_BASIC = "basic"
COLOR_MODE_256 = "xterm256"
COLOR_MODE_TRUECOLOR = "truecolor"

_MODE_ALIASES = {
    "mono": COLOR_MODE_MONO,
    "basic": COLOR_MODE_BASIC,
    "256": COLOR_MODE_256,
    "xterm256": COLOR_MODE_256,
    "truecolor": COLOR_MODE_TRUECOLOR,
}

# green -> yellow -> orange -> red
COLOR_STOPS = (
    (0.0, (0, 200, 0)),
    (50.0, (230, 220, 0)),
    (75.0, (255, 140, 0)),
    (100.0, (220, 0, 0)),
)

_BASIC_GREEN = 2
_BASIC_YELLOW = 3
_BASIC_RED = 1


def clamp_percent_0_100(value: float) -> int:
    return max(0, min(100, int(value)))


def parse_color_mode_override(raw: str | None) -> str | None:
    if raw is None:
        return None
    normalized = raw.strip().lower()
    if not normalized or normalized == COLOR_MODE_AUTO:
        return None
    return _MODE_ALIASES.get(normalized)


def _is_truthy_env(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() not in {"", "0", "false", "no", "off"}


def detect_color_mode(env: Mapping[str, str], terminal) -> str:
    if _is_truthy_env(env.get("NO_COLOR")):
        return COLOR_MODE_MONO

    if env.get("TERM", "").strip().lower() == "dumb":
        return COLOR_MODE_MONO

    forced_style = _is_truthy_env(env.get("FORCE_COLOR")) or _is_truthy_env(
        env.get("CLICOLOR_FORCE")
    )
    does_styling = bool(getattr(terminal, "does_styling", False) or forced_style)
    if not does_styling:
        return COLOR_MODE_MONO

    colorterm = env.get("COLORTERM", "").strip().lower()
    if colorterm in {"truecolor", "24bit"}:
        return COLOR_MODE_TRUECOLOR

    colors = int(getattr(terminal, "number_of_colors", 0) or 0)
    if colors >= (1 << 24):
        return COLOR_MODE_TRUECOLOR
    if colors >= 256:
        return COLOR_MODE_256
    if colors > 0:
        return COLOR_MODE_BASIC
    return COLOR_MODE_BASIC


def _linear_channel(start: int, end: int, ratio: float) -> int:
    # Avoid banker's rounding drift for .5 steps.
    return int(start + (end - start) * ratio + 0.5)


def value_to_rgb(percent: float) -> tuple[int, int, int]:
    p = float(clamp_percent_0_100(percent))

    if p <= COLOR_STOPS[0][0]:
        return COLOR_STOPS[0][1]
    if p >= COLOR_STOPS[-1][0]:
        return COLOR_STOPS[-1][1]

    for idx in range(len(COLOR_STOPS) - 1):
        p0, c0 = COLOR_STOPS[idx]
        p1, c1 = COLOR_STOPS[idx + 1]
        if p0 <= p <= p1:
            span = p1 - p0
            ratio = 0.0 if span <= 0 else (p - p0) / span
            return (
                _linear_channel(c0[0], c1[0], ratio),
                _linear_channel(c0[1], c1[1], ratio),
                _linear_channel(c0[2], c1[2], ratio),
            )

    return COLOR_STOPS[-1][1]


def _basic_color_index(percent: float) -> int:
    p = clamp_percent_0_100(percent)
    if p < 50:
        return _BASIC_GREEN
    if p < 75:
        return _BASIC_YELLOW
    return _BASIC_RED


def value_to_color_index(percent: float, mode: str, terminal, seed_color: int) -> int:
    try:
        mode = mode or COLOR_MODE_BASIC
        does_styling = bool(getattr(terminal, "does_styling", False))
        colors = int(getattr(terminal, "number_of_colors", 0) or 0)

        if mode == COLOR_MODE_MONO:
            return 0

        if not does_styling or colors <= 0:
            return 0

        if mode == COLOR_MODE_BASIC:
            return _basic_color_index(percent)

        if mode == COLOR_MODE_256:
            if colors < 256:
                return _basic_color_index(percent)
            rgb = value_to_rgb(percent)
            return int(terminal.rgb_downconvert(*rgb))

        if mode == COLOR_MODE_TRUECOLOR:
            if colors >= (1 << 24):
                rgb = value_to_rgb(percent)
                return int(terminal.rgb_downconvert(*rgb))
            if colors >= 256:
                rgb = value_to_rgb(percent)
                return int(terminal.rgb_downconvert(*rgb))
            return _basic_color_index(percent)

        return int(seed_color)
    except Exception:
        return int(seed_color)
