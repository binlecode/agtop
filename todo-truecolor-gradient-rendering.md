# TODO: Progressive Gradient Rendering (With Safe Fallback)

## Goal
Implement progressive bar/chart coloring (`green -> yellow -> orange -> red`) with safe capability-aware fallbacks. Deliver stepped per-widget coloring first, and smooth per-cell truecolor only in an experimental path.

## Non-Goals
- Do not change metric collection/parsing logic in `agtop/utils.py` and `agtop/parsers.py`.
- Do not change power/utilization math.
- Do not break existing `--color` usage.

## Compatibility Summary
- Expected impact on `utils` compatibility: none (rendering-only change).
- Main changes are in UI/render path (`agtop/agtop.py`) and potentially a small rendering helper module.

## Design Overview

### 1) Color Capability Detection Layer
- Add a helper to detect terminal color capability at runtime.
- Capability levels:
  - `mono`: no color or forced monochrome.
  - `basic`: 8/16 colors.
  - `xterm256`: 256-color mode.
  - `truecolor`: 24-bit color mode.
- Precedence (highest to lowest):
  - `AGTOP_COLOR_MODE=mono|basic|256|truecolor` -> force explicit mode.
  - `NO_COLOR` -> force `mono`.
  - `FORCE_COLOR` / `CLICOLOR_FORCE` -> enable styling if terminal supports it.
  - `TERM=dumb` -> `mono`.
  - `COLORTERM=truecolor|24bit` -> `truecolor`.
  - terminal-reported color depth (via `blessed.Terminal`) -> `xterm256` or `basic`.
  - else `basic`.
  - `--color` is not a capability signal; it is only a render fallback seed/index when dynamic mapping is disabled or fails.

### 2) Gradient Color Mapping
- Define a normalized value input range: `0..100`.
- Define color stops:
  - `0%` = green
  - `50%` = yellow
  - `75%` = orange
  - `100%` = red
- For `truecolor`:
  - linearly interpolate RGB between nearest stops (used by experimental renderer).
- For `xterm256`:
  - quantize interpolated RGB to nearest 256-color palette index.
- For `basic`:
  - threshold color switching only (green/yellow/red).
- For `mono`:
  - force monochrome path (disable dynamic mapping and use color index `0` for widgets).

### 3) Rendering Integration Strategy
- Keep existing `dashing` widgets for layout.
- Render-time behavior options:
  - Option A (minimal invasive): dynamically set widget `color` per gauge/chart frame (threshold/quantized only; compatible with current `dashing` integer color path).
  - Option B (full gradient): patch/fork `dashing` drawing paths to emit per-cell ANSI color (required for smooth left-to-right gradient and truecolor escape sequences).
- Recommended rollout:
  - Phase 1: dynamic per-widget color (low risk).
  - Phase 3: experimental patched gradient rendering behind feature flag.

### 4) Fallback Behavior
- Default to current behavior unless capability is confidently detected.
- If detection fails or any rendering exception occurs:
  - fallback to current static color path immediately.
- Add an explicit override env var for troubleshooting:
  - `AGTOP_COLOR_MODE=auto|truecolor|256|basic|mono`
  - `auto` means "no explicit override"; use detection path.
- Add explicit conflict handling:
  - invalid `AGTOP_COLOR_MODE` -> warn once, continue with `auto`.
  - unsupported forced mode (for example `truecolor` on non-styling output) -> degrade to best available mode.

## Implementation Plan

## Code-Level Implementation Spec

### File Changes
- [ ] Add `agtop/color_modes.py`.
- [ ] Update `agtop/agtop.py` imports and startup initialization.
- [ ] Add `tests/test_color_modes.py`.
- [ ] Optional experimental path: add `agtop/experimental_gradient.py` and tests only when Phase 3 starts.

### `agtop/color_modes.py` API
- [ ] Add mode constants:
  - [ ] `COLOR_MODE_AUTO = "auto"`
  - [ ] `COLOR_MODE_MONO = "mono"`
  - [ ] `COLOR_MODE_BASIC = "basic"`
  - [ ] `COLOR_MODE_256 = "xterm256"`
  - [ ] `COLOR_MODE_TRUECOLOR = "truecolor"`
- [ ] Add canonical gradient stops:
  - [ ] `COLOR_STOPS = ((0, (0, 200, 0)), (50, (230, 220, 0)), (75, (255, 140, 0)), (100, (220, 0, 0)))`
- [ ] Add helper functions:
  - [ ] `clamp_percent_0_100(value: float) -> int`
  - [ ] `parse_color_mode_override(raw: str | None) -> str | None`
  - [ ] `detect_color_mode(env: Mapping[str, str], terminal) -> str`
  - [ ] `value_to_rgb(percent: float) -> tuple[int, int, int]`
  - [ ] `value_to_color_index(percent: float, mode: str, terminal, seed_color: int) -> int`
- [ ] Add expected behavior:
  - [ ] `detect_color_mode(...)` returns one of `mono|basic|xterm256|truecolor` only (never `auto`).
  - [ ] `parse_color_mode_override(...)` returns only explicit modes; `auto` and invalid values return `None` (caller may warn once for invalid).
  - [ ] `value_to_color_index(...)` never raises; always returns an int.
  - [ ] `mono` returns `0` (no forced accent color).
  - [ ] `basic` maps by threshold: `<50 green`, `50-74 yellow`, `>=75 red`.
  - [ ] `xterm256` and baseline `truecolor` use `terminal.rgb_downconvert(*value_to_rgb(percent))`.

### `agtop/agtop.py` Integration Points
- [ ] Add imports near existing top-level imports:
  - [ ] `import os`
  - [ ] `from blessed import Terminal`
  - [ ] `from .color_modes import detect_color_mode, parse_color_mode_override, value_to_color_index`
- [ ] Add startup initialization inside `main()` before widgets are created:
  - [ ] `terminal = Terminal()`
  - [ ] `mode_override = parse_color_mode_override(os.getenv("AGTOP_COLOR_MODE"))`
  - [ ] `color_mode = mode_override or detect_color_mode(os.environ, terminal)`
  - [ ] `dynamic_color_enabled = color_mode in {"basic", "xterm256", "truecolor"}`
  - [ ] `experimental_gradient = os.getenv("AGTOP_EXPERIMENTAL_GRADIENT") == "1"`
- [ ] Add small internal helper in `main()`:
  - [ ] `def color_for(percent: float) -> int: return value_to_color_index(percent, color_mode, terminal, args.color)`
- [ ] Update widget colors in the sampling loop after value assignment:
  - [ ] `cpu1_gauge.color = color_for(cpu_metrics_dict["E-Cluster_active"])`
  - [ ] `cpu2_gauge.color = color_for(cpu_metrics_dict["P-Cluster_active"])`
  - [ ] `gpu_gauge.color = color_for(gpu_metrics_dict["active"])`
  - [ ] `ane_gauge.color = color_for(ane_util_percent)`
  - [ ] per-core gauges:
    - [ ] `gauge.color = color_for(core_active)`
    - [ ] `gauge.border_color = gauge.color`
  - [ ] power charts:
    - [ ] `cpu_power_chart.color = color_for(cpu_power_percent)`
    - [ ] `gpu_power_chart.color = color_for(gpu_power_percent)`
- [ ] Keep non-breaking fallback:
  - [ ] Wrap only dynamic color assignment block in `try/except Exception`.
  - [ ] On exception, set `dynamic_color_enabled = False` and restore all widget colors to `args.color`.
  - [ ] Do not alter metric/title/chart append logic.
  - [ ] When `color_mode == "mono"`, set all widget/border/chart colors to `0` once at initialization.

### Precedence and Conflict Rules (Code)
- [ ] Implement exact precedence:
  - [ ] valid `AGTOP_COLOR_MODE` explicit mode wins.
  - [ ] `NO_COLOR` forces `mono` unless explicit override is set to another mode.
  - [ ] `TERM=dumb` forces `mono` when mode is auto.
  - [ ] auto mode picks truecolor when `COLORTERM in {"truecolor", "24bit"}` or terminal reports 24-bit.
  - [ ] auto mode picks 256 when terminal reports `>= 256` colors.
  - [ ] else basic.
- [ ] Forced unsupported mode degradation:
  - [ ] forced `truecolor` on non-styling output degrades to `basic` or `mono` (never crashes).
  - [ ] forced `256` on low-color output degrades to `basic`.
- [ ] `--color` scope:
  - [ ] never used by `detect_color_mode`.
  - [ ] used as static fallback seed when dynamic mapping is disabled or fails.

### Phase 3 Module Boundary (Do Not Start In Phase 1/2)
- [ ] `agtop/experimental_gradient.py` owns all per-cell ANSI rendering.
- [ ] `agtop/agtop.py` should only switch widget classes behind `AGTOP_EXPERIMENTAL_GRADIENT=1`.
- [ ] No monkey patching of site-packages in place.

### Test Cases to Implement
- [ ] `tests/test_color_modes.py`:
  - [ ] `test_parse_color_mode_override_valid_values`
  - [ ] `test_parse_color_mode_override_auto_returns_none`
  - [ ] `test_parse_color_mode_override_invalid_returns_none`
  - [ ] `test_detect_color_mode_no_color_precedence`
  - [ ] `test_detect_color_mode_term_dumb`
  - [ ] `test_detect_color_mode_colorterm_truecolor`
  - [ ] `test_detect_color_mode_256_from_terminal_depth`
  - [ ] `test_value_to_rgb_boundaries`
  - [ ] `test_value_to_rgb_interpolation_midpoints`
  - [ ] `test_value_to_color_index_basic_thresholds`
  - [ ] `test_value_to_color_index_mono_returns_zero`
  - [ ] `test_forced_truecolor_degrades_when_terminal_has_no_styling`
  - [ ] `test_forced_256_degrades_when_terminal_depth_is_low`
  - [ ] `test_value_to_color_index_never_raises`
- [ ] Add lightweight fake terminal object in tests with:
  - [ ] `number_of_colors`
  - [ ] `does_styling`
  - [ ] `rgb_downconvert(r, g, b)`

### Pseudocode Skeleton (Phase 1/2)
```python
# agtop/agtop.py
terminal = Terminal()
mode_override = parse_color_mode_override(os.getenv("AGTOP_COLOR_MODE"))
color_mode = mode_override or detect_color_mode(os.environ, terminal)
dynamic_color_enabled = color_mode in {"basic", "xterm256", "truecolor"}

def color_for(percent):
    return value_to_color_index(percent, color_mode, terminal, args.color)

# inside update loop, after gauge.value updates
if dynamic_color_enabled:
    try:
        cpu1_gauge.color = color_for(cpu_metrics_dict["E-Cluster_active"])
        # ... repeat for each gauge/chart ...
    except Exception:
        dynamic_color_enabled = False
        # reset all widget colors/border colors to args.color
```

## Phase 1: Capability and Color Engine
- [ ] Add `agtop/color_modes.py` (or similar) with:
  - [ ] `detect_color_mode(env, terminal) -> mode`
  - [ ] `value_to_rgb(percent) -> (r,g,b)`
  - [ ] `value_to_color_index(percent, mode) -> int` (for current `dashing` rendering path)
- [ ] Unit tests for detection and interpolation edge cases:
  - [ ] `NO_COLOR` precedence
  - [ ] `AGTOP_COLOR_MODE` explicit override precedence
  - [ ] `TERM=dumb`
  - [ ] truecolor detection via `COLORTERM`
  - [ ] forced-color env handling (`FORCE_COLOR` / `CLICOLOR_FORCE`)
  - [ ] interpolation boundaries (`0, 50, 75, 100`)

## Phase 2: UI Wiring (Non-breaking)
- [ ] Integrate color mode detection in `agtop/agtop.py` startup.
- [ ] Apply per-widget color updates by metric value:
  - [ ] CPU gauges
  - [ ] GPU gauge
  - [ ] ANE gauge
  - [ ] power charts (single widget color per frame)
- [ ] Keep `--color` as fallback/default seed for non-gradient modes.
- [ ] Add safe try/except wrapper to fallback to static colors on render errors.
- [ ] Maintain default behavior if no env override is set and dynamic coloring is unavailable.

## Phase 3: Experimental Smooth Truecolor Gradient
- [ ] Confirm and document that current `dashing` path is single-color-per-widget.
- [ ] If not, create local patched renderer module (minimal fork) for:
  - [ ] `HGauge` gradient fill
  - [ ] `VGauge` gradient fill
  - [ ] optional `HChart` gradient
- [ ] Guard behind a feature flag:
  - [ ] `AGTOP_EXPERIMENTAL_GRADIENT=1`
- [ ] Default remains stable non-fork behavior unless flag enabled.

## Phase 4: CLI and Docs
- [ ] Add docs in `README.md`:
  - [ ] Explain automatic color capability detection.
  - [ ] Explain `AGTOP_COLOR_MODE` overrides.
  - [ ] Mention fallback to monochrome/static color.
- [ ] Add short troubleshooting section for terminals with unexpected colors.

## Testing Plan

### Automated
- [ ] Unit tests for color detection and mapping.
- [ ] Unit tests for precedence and forced-mode degradation logic.
- [ ] Snapshot-style tests for generated ANSI sequences (experimental renderer only).
- [ ] Existing tests must remain green:
  - [ ] `.venv/bin/python -m pytest -q`

### Manual
- [ ] macOS Terminal.app
- [ ] iTerm2
- [ ] VS Code integrated terminal
- [ ] SSH session with limited TERM support
- [ ] Validate fallback:
  - [ ] `NO_COLOR=1 agtop ...`
  - [ ] `TERM=dumb agtop ...`
  - [ ] `AGTOP_COLOR_MODE=mono agtop ...`
  - [ ] `AGTOP_COLOR_MODE=truecolor agtop ...` on non-truecolor terminal degrades cleanly

## Acceptance Criteria
- [ ] Baseline (default path): on capable terminals, gauges/charts show value-responsive stepped coloring with no regressions.
- [ ] Experimental path (`AGTOP_EXPERIMENTAL_GRADIENT=1`): on truecolor terminals, gauges/charts show smooth or near-smooth gradient progression.
- [ ] On lower-capability terminals, output remains readable and stable via stepped/static colors.
- [ ] No regression in metrics, parser behavior, or runtime stability.
- [ ] Existing CLI usage continues to work without required new flags.

## Risks and Mitigations
- Risk: `dashing` limitations prevent smooth per-cell gradients.
  - Mitigation: ship phase 1 stepped color first; keep phase 3 optional.
- Risk: terminal capability mis-detection.
  - Mitigation: explicit env override + conservative fallback.
- Risk: readability issues on light/dark themes.
  - Mitigation: tune color stops and test across common terminals.
