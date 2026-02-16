# Changelog

All notable changes to `binlecode/agtop` should be documented in this file.

This project follows a Keep a Changelog-style format and uses version tags for releases.

## [Unreleased]

### Added
- No changes yet.

### Changed
- No changes yet.

### Fixed
- No changes yet.

## [0.1.10] - 2026-02-16

### Added
- No changes yet.

### Changed
- No changes yet.

### Fixed
- No changes yet.

## [0.1.9] - 2026-02-16

### Added
- Added manual `workflow_dispatch` support to `release-formula.yml` for targeted formula re-sync by tag.

### Changed
- No changes yet.

### Fixed
- Fixed `release-formula.yml` formula sync step to avoid shell heredoc parsing failures in CI.
- Fixed missing ANE power metrics on M3/M4 chips by explicitly requesting the `ane_power` sampler and adding fallback parsing logic for `ane_power` (mW) vs `ane_energy` (mJ).

## [0.1.8] - 2026-02-16

### Added
- Added `GUIDE-release-operations.md` as the canonical end-to-end release runbook with failure playbooks.

### Changed
- Refactored release automation to use a race-safe, serialized formula sync workflow on tag pushes.
- Updated release documentation/checklist to standardize on `scripts/tag_release.sh` and CI-driven formula synchronization.
- Hardened `scripts/tag_release.sh` to fast-forward local `main` from `origin/main` before tagging/pushing.

### Fixed
- No changes yet.

## [0.1.7] - 2026-02-16

### Added
- No changes yet.

### Changed
- Refined startup status output formatting (`[1/3]`, `[2/3]`, `[3/3]`) for cleaner, predictable spacing.
- Ensured startup banner/status lines are cleared once the first dashboard frame renders.

### Fixed
- Prevented non-sudo startup hangs by making internal `powermetrics` invocation non-interactive (`sudo -n`) and timing out clearly if the first sample cannot be read.

## [0.1.6] - 2026-02-16

### Added
- Added configurable bottleneck alert thresholds:
  - `--alert-bw-sat-percent`
  - `--alert-package-power-percent`
  - `--alert-swap-rise-gb`
  - `--alert-sustain-samples`
- Added CLI contract coverage for the new alert threshold flags and validation failures.

### Changed
- Updated the power/status title line to include active bottleneck alerts (thermal, bandwidth saturation, swap growth, package power).
- Reorganized `README.md` into a more systematic structure with quick-reference sections.
- Marked Priority 5 (`Bottleneck signals and alerts`) as complete in `TODO-btop-inspired-enhancements.md`.

### Fixed
- Fixed terminal redraw behavior for environments lacking cursor-addressing support by forcing full-screen clear before each frame (prevents repeated border/header line printing).

## [0.1.5] - 2026-02-16

### Added
- Added `pyproject.toml` packaging metadata (`PEP 517/518`) and removed legacy `setup.py`.

### Changed
- Improved `powermetrics` startup error guidance for missing binary, sudo/permission issues, and subprocess startup failures.
- Migrated packaging metadata from `setup.py` to `pyproject.toml` and updated release automation/scripts to validate `[project].version`.
- Updated release docs/guides to reference `pyproject.toml` and modern build commands.
- Updated package author metadata to `binlecode` only.

### Fixed
- Ensured cursor restore and `powermetrics` subprocess termination run from a shared `finally` cleanup path.

## [0.1.4] - 2026-02-16

### Added
- No changes yet.

### Changed
- Added explicit GitHub Actions `run-name` values to disambiguate workflow run titles between `main-ci` and `release-formula`.
- Updated release documentation example version to `0.1.4`.
- Bumped package version in `setup.py` to `0.1.4`.

### Fixed
- Reduced CI/CD run-list ambiguity caused by identical workflow display titles for different pipelines.

## [0.1.3] - 2026-02-16

### Added
- Added split GitHub Actions workflows: `.github/workflows/main-ci.yml` for `main` validation and `.github/workflows/release-formula.yml` for tag-driven formula synchronization.
- Added `scripts/tag_release.sh` to enforce version/tag checks and push release tags consistently.
- Added functional regression tests for CLI invocation/import safety and `powermetrics` partial-frame recovery.

### Changed
- Refactored CLI argument handling to use `build_parser()`, runtime-only parsing, `--show_cores` as a boolean flag, and a `cli(argv=None)` entrypoint.
- Updated `console_scripts` entrypoint in `setup.py` to `agtop.agtop:cli`.
- Updated testing policy to emphasize functional tests over internal unit-detail coverage, and removed legacy unit-detail test files.
- Updated release documentation to reflect split CI/CD workflow and the current release version example.

### Fixed
- Prevented import-time CLI argument parsing failures when `agtop.agtop` is imported by other tools/processes.

## [0.1.2] - 2026-02-16

### Added
- Added `.github/workflows/main-push.yml` to run lint/tests on `main` push and auto-sync `Formula/agtop.rb` when a matching release tag exists.
- Added `ruff` as a development dependency for linting and formatting.

### Changed
- Bumped package version in `setup.py` to `0.1.2`.

### Fixed
- Updated `Formula/agtop.rb` checksum for `v0.0.25` source tarball to match GitHub download content.

## [0.1.1] - 2026-02-16

### Added
- No changes yet.

### Changed
- Enabled gradient-based bar rendering for dynamic color modes by default (CPU/GPU usage and power bars), while keeping `AGTOP_EXPERIMENTAL_GRADIENT` as an explicit override.

### Fixed
- Removed integer quantization in gradient color mapping so bar steps can use slightly different shades across the full green-to-red range.
- Added regression coverage to ensure fractional percent inputs produce distinct interpolated colors.

## [0.1.0] - 2026-02-16

### Added
- Renamed Python package and CLI module to `agtop` (`agtop/agtop.py`).
- Updated tests and module imports to `agtop.*`.

### Changed
- Updated CLI startup/help strings and repository links to `binlecode/agtop`.
- Updated runtime temp file prefix to `/tmp/agtop_powermetrics*`.
- Removed legacy console alias from package entry points.
- Updated docs and operational guides to use `agtop` naming.

### Fixed
- Restored functional module invocation for `.venv/bin/python -m agtop.agtop --help`.

## [0.0.25] - 2026-02-15

### Added
- No changes yet.

### Changed
- No changes yet.

### Fixed
- Avoided startup crashes when stale temp powermetrics files cannot be removed due to permissions.

## [0.0.24] - 2026-02-15

### Added
- Added maintainer metadata for `binlecode` in package author fields.

### Changed
- Updated repository and tap branding during fork transition.
- Updated installation and bottling docs for tap-based distribution.

## [0.0.23] - 2026-02-15

### Added
- SoC profile resolution module with direct support for Apple Silicon families `M1` through `M4`.
- Tiered fallback handling for unknown future Apple M-series names (`base`, `Pro`, `Max`, `Ultra`).
- Power scaling helpers with `auto` (rolling peak) and `profile` (reference-based) modes.
- New CLI option: `--power-scale {auto,profile}`.
- Unit tests for SoC profile resolution, parser resilience, and power scaling logic.

### Changed
- Refactored `get_soc_info()` to consume profile metadata while preserving backward-compatible keys.
- Updated README compatibility and CLI usage documentation for modern Apple Silicon positioning.

### Fixed
- Hardened parser behavior for missing and partial `powermetrics` payload fields.

## [0.0.22] - 2026-02-15

Fork baseline release tracking started in the initial fork repository.

### Added
- Homebrew formula for tap-based installation.
- Formula test to verify CLI help output.

### Changed
- Formula install flow pinned to Homebrew-managed Python virtualenv helper for reliable packaging.

---

## Release Notes Process

For each new release:
1. Move completed items from `Unreleased` into a new version section.
2. Add release date in `YYYY-MM-DD` format.
3. Keep entries concise and user-impact focused.
4. Tag and publish release after changelog update.
