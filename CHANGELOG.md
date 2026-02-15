# Changelog

All notable changes to the `binlecode/silitop` fork should be documented in this file.

This project follows a Keep a Changelog-style format and uses version tags for releases.

## [Unreleased]

### Added
- No changes yet.

### Changed
- No changes yet.

### Fixed
- No changes yet.

## [0.0.24] - 2026-02-15

### Added
- Added maintainer metadata for `binlecode` in package author fields.

### Changed
- Renamed repository from `binlecode/asitop` to `binlecode/silitop`.
- Renamed Homebrew tap formula from `asitop` to `silitop` to avoid collision with `homebrew/core/asitop`.
- Updated Homebrew install and bottling docs to use `binlecode/silitop/silitop`.

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

Fork baseline release tracking started in `binlecode/silitop`.

### Added
- Homebrew formula at `Formula/silitop.rb` for tap-based installation.
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
