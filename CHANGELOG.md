# Changelog

All notable changes to `binlecode/agtop` should be documented in this file.

This project follows a Keep a Changelog-style format and uses version tags for releases.

## [0.3.1] - 2026-02-17

### Changed
- Extracted `DashboardState` and `DashboardConfig` dataclasses into `agtop/state.py` and metric/widget update functions into `agtop/updaters.py`, slimming `_run_dashboard()` to a focused render loop.
- Added `--subsamples` CLI option for sampler-level smoothing via multi-delta averaging within each interval.
- Added cross-platform tests for state factories, metric updates, and widget binding.

## [0.3.0] - 2026-02-17

### Added
- Added SMC temperature reader (`agtop/smc.py`) for CPU and GPU die temperatures via IOKit ctypes, no sudo required.
- Added CPU and GPU temperature display in gauge titles (e.g. "P-CPU Usage: 12% @ 3504 MHz (58°C)").

### Changed
- Replaced `vm_stat` subprocess with `psutil.virtual_memory()` for RAM metrics, eliminating fork/exec overhead every sample interval.
- Split test suite into CI-safe and macOS-local groups using pytest markers.

## [0.2.0] - 2026-02-17

### Added
- Added `GradientText` widget for per-line gradient coloring in the process panel based on CPU utilization.

### Changed
- Changed default `--interval` from 1s to 2s to reduce sampling overhead (aligned with btop's default).
- Changed default `--show_cores` to on for a full per-core dashboard out of the box (disable with `--no-show_cores`).
- Changed default `--power-scale` from `auto` to `profile` for stable, meaningful power chart percentages from the first frame.
- Replaced `psutil.virtual_memory()` with `os.sysconf` for total RAM and `vm_stat` for used RAM; psutil retained for swap and process metrics.
- Rewrote README with consolidated structure: Key Features, How It Works (OS-level API mechanism), Architecture (Mermaid system diagram), and Signal Sources.
- Revised release operations guide as combined tutorial and runbook.

### Fixed
- Fixed RAM usage to match Activity Monitor by using macOS `vm_stat` page counts (`internal - purgeable + wired + compressor`) instead of psutil's `total - available` which over-reports usage.
- Fixed swap percent calculation to use raw byte values instead of pre-rounded GB values.

## [0.1.10] - 2026-02-16

Initial IOReport-only release. All prior versions used a legacy backend and are not documented here.

---

## Release Notes Process

For each new release:
1. Move completed items from `Unreleased` into a new version section.
2. Add release date in `YYYY-MM-DD` format.
3. Keep entries concise and user-impact focused.
4. Tag and publish release after changelog update.
