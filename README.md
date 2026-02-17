# agtop

Apple GPU Top for Apple Silicon.

![](images/agtop.png)

## Project Status

`agtop` is an independent hard fork with its own release cycle and maintenance policy.

Origin attribution: this project is inspired by `tlkh/asitop` and is now refactored to a new utility as `binlecode/agtop`.

## At a Glance

- Platform: Apple Silicon macOS.
- Permission model: **no `sudo` required** — reads Apple Silicon metrics directly via IOReport. Falls back to `powermetrics` (requires `sudo`) if IOReport is unavailable.
- Core value: combines CPU/GPU/ANE/power/memory/bandwidth/process signals in one terminal dashboard.
- Compatibility model: explicit M1-M4 support plus tiered fallback for future Apple Silicon names.

## Key Features

- **No sudo needed**: uses Apple's IOReport framework to read power, frequency, and residency metrics in-process via ctypes.
- Real-time dashboard: E/P CPU clusters, optional per-core gauges/history, GPU, ANE, RAM/swap, and memory bandwidth.
- Diagnosis-oriented status line: thermal state, bandwidth saturation, swap growth, and package power alerts.
- Process visibility: top CPU/RSS processes with optional regex filter (`--proc-filter`).
- Profile-aware scaling: `--power-scale auto|profile` for consistent chart interpretation across SoC classes.
- Automatic DVFS frequency table discovery from IOKit for accurate per-core MHz reporting.

## Installation

This project uses the source repo itself as the tap remote (not a separate `homebrew-*` tap repo).

```shell
brew tap --custom-remote binlecode/agtop https://github.com/binlecode/agtop.git
brew install binlecode/agtop/agtop
```

### Upgrade / Uninstall

```shell
brew update
brew upgrade binlecode/agtop/agtop
brew uninstall binlecode/agtop/agtop
```

## Quick Start

```shell
agtop --help
agtop
agtop --interval 1 --avg 30 --power-scale profile
agtop --show_cores --core-view both --interval 1 --avg 30 --power-scale profile
agtop --proc-filter "python|ollama|vllm|docker|mlx"
agtop --alert-bw-sat-percent 90 --alert-package-power-percent 85 --alert-swap-rise-gb 0.5 --alert-sustain-samples 4
```

To force the legacy `powermetrics` backend (requires `sudo`):

```shell
AGTOP_FORCE_POWERMETRICS=1 sudo agtop
```

## CLI Quick Reference

| Option | Purpose | Default |
| --- | --- | --- |
| `--interval` | Dashboard and sampling interval (seconds) | `1` |
| `--color` | Display color theme (0-8) | `2` |
| `--avg` | Rolling average window (seconds) | `30` |
| `--show_cores` | Enable per-core panels | `off` |
| `--core-view gauge\|history\|both` | Per-core visualization mode when cores are shown | `gauge` |
| `--power-scale auto\|profile` | Power chart scaling mode | `auto` |
| `--proc-filter REGEX` | Filter process panel command names | empty |
| `--alert-bw-sat-percent` | Sustained bandwidth saturation threshold | `85` |
| `--alert-package-power-percent` | Sustained package-power threshold (profile-relative) | `85` |
| `--alert-swap-rise-gb` | Swap-growth threshold over sustained samples | `0.3` |
| `--alert-sustain-samples` | Consecutive samples required for sustained alerts | `3` |

## Telemetry Model (What / How / Why)

| Signal Domain | Primary Source | Why |
| --- | --- | --- |
| CPU utilization (per-core/cluster) | `psutil` | Aligns better with Activity Monitor / btop-style load semantics |
| CPU/GPU freq, power, residency | IOReport (`libIOReport.dylib`) via ctypes | In-process, no sudo, no subprocess overhead |
| DVFS frequency tables | IOKit `pmgr` device via `ioreg` | Maps P-state indices to actual MHz values |
| SoC identity and profile hints | `sysctl`, `system_profiler`, built-in SoC profiles | Stable scaling defaults and compatibility across chip families |
| Bandwidth counters, thermal pressure | `powermetrics` plist (fallback only) | Not available from IOReport; shown as N/A with IOReport backend |

### Backend Selection

agtop automatically selects the best available backend at startup:

1. **IOReport** (default): reads Apple Silicon metrics directly via the private `libIOReport.dylib` C library using Python ctypes. No sudo, no subprocess, no temp files.
2. **powermetrics** (fallback): spawns a privileged `powermetrics` subprocess. Used when IOReport is unavailable or when `AGTOP_FORCE_POWERMETRICS=1` is set.

The active backend is shown during startup: `[2/3] Backend: ioreport ...`

## Troubleshooting

- **Bandwidth shows N/A**: bandwidth counters are not available from the IOReport backend. Use `AGTOP_FORCE_POWERMETRICS=1 sudo agtop` for bandwidth data.
- **Thermal shows "Unknown"**: thermal pressure is not exposed by IOReport. Use the powermetrics fallback for thermal readings.
- **Frequencies show 0 MHz**: DVFS table discovery failed for your SoC. File an issue with your chip model (`sysctl -n machdep.cpu.brand_string`).
- **`Failed to start powermetrics`**: only applies to the powermetrics fallback. The IOReport backend does not need `sudo`.
- **Metric differences versus other tools**: small differences are expected due to sampling windows and source timing.

## Development

Install local dev dependencies (repo `.venv`):

```bash
.venv/bin/python -m pip install -e ".[dev]"
```

Validate CLI and run the app in development:

```bash
.venv/bin/python -m agtop.agtop --help
.venv/bin/python -m agtop.agtop --interval 1 --avg 30 --power-scale profile
.venv/bin/python -m agtop.agtop --show_cores --core-view both --interval 1 --avg 30 --power-scale profile
```

Run tests:

```bash
.venv/bin/python -m pytest -q
```

Run lint + format:

```bash
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format .
```

## Maintainer Release (Homebrew Tap)

Systematic release runbook: `GUIDE-release-operations.md`

### Topology

- Source repo: `binlecode/agtop`
- Tap repo: `binlecode/homebrew-agtop`
- Tap users run: `binlecode/agtop`
- Formula name: `agtop`

Homebrew upgrades come from the tap formula, not from `pyproject.toml` alone.

### One-Time Tap Repo Setup

```bash
export GH_USER="binlecode"
export TAP_REPO="$GH_USER/homebrew-agtop"

brew tap-new "$TAP_REPO"
gh repo create "$TAP_REPO" --public --source "$(brew --repository "$TAP_REPO")" --push
```

### Release Flow (split CI/CD)

1. Update `pyproject.toml` (`[project].version`) and `CHANGELOG.md`, then commit.
   CI does not bump versions.
2. Push release tag via the helper script (recommended):
   `scripts/tag_release.sh`
   This fast-forwards local `main`, pushes `main`, creates `vX.Y.Z`, and pushes the tag.
   CI does not create tags.

```bash
export VERSION="0.1.9"
git add pyproject.toml CHANGELOG.md
git commit -m "Release v$VERSION"
scripts/tag_release.sh "$VERSION"
```

3. `.github/workflows/main-ci.yml` runs on `main` push:
   resolves Python version from `Formula/agtop.rb`, prepares `.ci-venv`, installs formula resource versions, then runs checks.
4. `.github/workflows/release-formula.yml` runs on `v*` tags:
   verifies tag/version match from the tag commit, updates `Formula/agtop.rb` tarball `url` + `sha256`, and commits formula sync to `main`.
   Formula sync is serialized and retried to avoid race-condition push failures.

5. Validate availability:

```bash
brew update
brew upgrade binlecode/agtop/agtop
brew info binlecode/agtop/agtop
```

### Release Checklist

1. Confirm working tree is clean:
   `git status --short`
2. Bump version and update changelog:
   edit `pyproject.toml` and `CHANGELOG.md`
3. Run required checks:
   `.venv/bin/python -m ruff check --fix .`
   `.venv/bin/python -m ruff format .`
   `.venv/bin/python -m agtop.agtop --help`
   `.venv/bin/pytest -q`
4. Create release commit and tag, then push both:
   `git add pyproject.toml CHANGELOG.md`
   `git commit -m "Release v$VERSION"`
   `scripts/tag_release.sh "$VERSION"`
5. Verify workflows:
   check `main-ci` and `release-formula` runs in GitHub Actions
6. Confirm formula points to the new tag and checksum:
   `Formula/agtop.rb` `url` and `sha256` (via CI sync commit)
7. Confirm install path:
   `brew update && brew upgrade binlecode/agtop/agtop && brew info binlecode/agtop/agtop`

## Architecture

| Module | Role |
| --- | --- |
| `agtop/agtop.py` | CLI entry point, argument parsing, terminal dashboard, main event loop |
| `agtop/sampler.py` | Unified sampler abstraction: `IOReportSampler` (primary) and `PowermetricsSampler` (fallback) |
| `agtop/ioreport.py` | IOReport + CoreFoundation ctypes bindings for in-process Apple Silicon metrics |
| `agtop/parsers.py` | Parses `powermetrics` plist payloads (used by fallback path) |
| `agtop/utils.py` | System integration: `powermetrics` subprocess management, `sysctl`/`system_profiler` calls |
| `agtop/soc_profiles.py` | SoC profiles (M1-M4 families) with power/bandwidth reference values |
| `agtop/power_scaling.py` | Power scaling logic: `auto` (rolling peak) vs `profile` (SoC reference) |
| `agtop/color_modes.py` | Terminal color detection and gradient/index mapping |
| `agtop/gradient.py` | Per-cell gradient rendering subclasses for `dashing` widgets |

## Compatibility Notes

- Chip families `M1` through `M4` are recognized directly.
- Unknown future Apple Silicon names fall back to tier defaults (`base`, `Pro`, `Max`, `Ultra`).
- IOReport backend requires macOS with `libIOReport.dylib` (available on all Apple Silicon Macs).
- The powermetrics fallback supports older macOS versions where IOReport may not be available.

Use `agtop` for install and runtime commands in this repository.
