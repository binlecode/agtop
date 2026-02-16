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

## [0.1.2] - 2026-02-16

### Added
- Added `scripts/update_formula.py` to auto-update `Formula/agtop.rb` `url` and `sha256` from a target tag.
- Added `scripts/release_prepare.py` to automate version bump, changelog sync, optional formula update, and release validation commands.

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
