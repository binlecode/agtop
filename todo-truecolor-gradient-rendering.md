# TODO: Truecolor Gradient Rendering (With Safe Fallback)

## Goal
Implement progressive bar/chart coloring (`green -> yellow -> orange -> red`) using truecolor when supported, while preserving current behavior on terminals that do not support advanced colors.

## Non-Goals
- Do not change metric collection/parsing logic in `asitop/utils.py` and `asitop/parsers.py`.
- Do not change power/utilization math.
- Do not break existing `--color` usage.

## Compatibility Summary
- Expected impact on `utils` compatibility: none (rendering-only change).
- Main changes are in UI/render path (`asitop/asitop.py`) and potentially a small rendering helper module.

## Design Overview

### 1) Color Capability Detection Layer
- Add a helper to detect terminal color capability at runtime.
- Capability levels:
  - `mono`: no color or forced monochrome.
  - `basic`: 8/16 colors.
  - `xterm256`: 256-color mode.
  - `truecolor`: 24-bit color mode.
- Detection signals (in order):
  - `NO_COLOR` -> force `mono`.
  - `TERM=dumb` -> force `mono`.
  - `COLORTERM=truecolor|24bit` -> `truecolor`.
  - `TERM` contains `256color` -> `xterm256`.
  - else `basic`.

### 2) Gradient Color Mapping
- Define a normalized value input range: `0..100`.
- Define color stops:
  - `0%` = green
  - `50%` = yellow
  - `75%` = orange
  - `100%` = red
- For `truecolor`:
  - linearly interpolate RGB between nearest stops.
- For `xterm256`:
  - quantize to nearest 256-color palette index.
- For `basic`:
  - threshold color switching only (green/yellow/red).
- For `mono`:
  - keep current single-color behavior.

### 3) Rendering Integration Strategy
- Keep existing `dashing` widgets for layout.
- Render-time behavior options:
  - Option A (minimal invasive): dynamically set widget `color` per gauge/chart frame (threshold/quantized only).
  - Option B (full gradient): patch/fork `dashing` drawing paths to emit per-cell ANSI color (required for smooth left-to-right gradient).
- Recommended rollout:
  - Phase 1: dynamic per-widget color (low risk).
  - Phase 2: optional patched gradient rendering behind feature flag.

### 4) Fallback Behavior
- Default to current behavior unless capability is confidently detected.
- If detection fails or any rendering exception occurs:
  - fallback to current static color path immediately.
- Add an explicit override env var for troubleshooting:
  - `ASITOP_COLOR_MODE=auto|truecolor|256|basic|mono`

## Implementation Plan

## Phase 1: Capability and Color Engine
- [ ] Add `asitop/color_modes.py` (or similar) with:
  - [ ] `detect_color_mode(env, term_info) -> mode`
  - [ ] `value_to_rgb(percent) -> (r,g,b)`
  - [ ] `value_to_ansi(percent, mode) -> color token/index`
- [ ] Unit tests for detection and interpolation edge cases:
  - [ ] `NO_COLOR` precedence
  - [ ] `TERM=dumb`
  - [ ] truecolor detection via `COLORTERM`
  - [ ] interpolation boundaries (`0, 50, 75, 100`)

## Phase 2: UI Wiring (Non-breaking)
- [ ] Integrate color mode detection in `asitop/asitop.py` startup.
- [ ] Apply per-widget color updates by metric value:
  - [ ] CPU gauges
  - [ ] GPU gauge
  - [ ] ANE gauge
  - [ ] power charts (if feasible with current `dashing`)
- [ ] Keep `--color` as fallback/default seed for non-gradient modes.
- [ ] Add safe try/except wrapper to fallback to static colors on render errors.

## Phase 3: Optional True Smooth Gradient
- [ ] Evaluate if current `dashing` supports per-character/per-cell color.
- [ ] If not, create local patched renderer module (minimal fork) for:
  - [ ] `HGauge` gradient fill
  - [ ] `VGauge` gradient fill
  - [ ] optional `HChart` gradient
- [ ] Guard behind a feature flag:
  - [ ] `ASITOP_EXPERIMENTAL_GRADIENT=1`
- [ ] Default remains stable non-fork behavior unless flag enabled.

## Phase 4: CLI and Docs
- [ ] Add docs in `README.md`:
  - [ ] Explain automatic color capability detection.
  - [ ] Explain `ASITOP_COLOR_MODE` overrides.
  - [ ] Mention fallback to monochrome/static color.
- [ ] Add short troubleshooting section for terminals with unexpected colors.

## Testing Plan

### Automated
- [ ] Unit tests for color detection and mapping.
- [ ] Snapshot-style tests for generated ANSI sequences (where practical).
- [ ] Existing tests must remain green:
  - [ ] `.venv/bin/python -m pytest -q`

### Manual
- [ ] macOS Terminal.app
- [ ] iTerm2
- [ ] VS Code integrated terminal
- [ ] SSH session with limited TERM support
- [ ] Validate fallback:
  - [ ] `NO_COLOR=1 asitop ...`
  - [ ] `TERM=dumb asitop ...`
  - [ ] `ASITOP_COLOR_MODE=mono asitop ...`

## Acceptance Criteria
- [ ] On truecolor terminals, gauges/charts show smooth or near-smooth gradient progression.
- [ ] On lower-capability terminals, output remains readable and stable via stepped/static colors.
- [ ] No regression in metrics, parser behavior, or runtime stability.
- [ ] Existing CLI usage continues to work without required new flags.

## Risks and Mitigations
- Risk: `dashing` limitations prevent smooth per-cell gradients.
  - Mitigation: ship phase 1 stepped color first; keep phase 2 optional.
- Risk: terminal capability mis-detection.
  - Mitigation: explicit env override + conservative fallback.
- Risk: readability issues on light/dark themes.
  - Mitigation: tune color stops and test across common terminals.
