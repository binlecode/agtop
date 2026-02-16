# agtop

Apple GPU Top for Apple Silicon.

![](images/agtop.png)

## Project Status

`agtop` is an independent hard fork with its own release cycle and maintenance policy.

Origin attribution: this project is inspired by `tlkh/asitop` and is now refactored to a new utility as `binlecode/agtop`.

## Features

- CPU utilization gauges + history trackers (E/P clusters and per-core views).
- GPU utilization/frequency display + history trackers.
- ANE utilization estimation from power usage.
- RAM and swap usage display.
- Memory bandwidth panel (E-CPU, P-CPU, GPU, Media, total read/write).
- CPU/GPU power charts with profile-aware scaling.
- Apple Silicon profile defaults for current and future M-series tiers.

## Telemetry Model (What / How / Why)

`agtop` intentionally combines multiple macOS telemetry sources:

- CPU utilization:
  - Uses OS-level per-core CPU percentages (`psutil`, scheduler tick style).
  - Why: this aligns better with Activity Monitor / btop-style CPU load semantics.
- CPU frequencies, GPU utilization/frequency, ANE power, CPU/GPU/package power, thermal pressure, memory bandwidth:
  - Uses `powermetrics` plist output.
  - Why: Apple-specific accelerator and bandwidth counters are not fully exposed through generic cross-platform CPU APIs.
- Hardware profile metadata (chip family, reference scaling):
  - Uses `sysctl` / `system_profiler` plus built-in SoC profiles.

Practical result:
- `agtop` is best for Apple Silicon diagnosis where you want CPU load behavior comparable to common system monitors while still seeing Apple-only metrics (GPU/ANE/power/bandwidth) in one dashboard.

## Requirements

- Apple Silicon Mac.
- macOS with `powermetrics` available.
- `sudo` access (required by `powermetrics`).

## Install

This project uses the source repo itself as the tap remote (not a separate `homebrew-*` tap repo).
Run this one-time tap setup first:

```shell
brew tap --custom-remote binlecode/agtop https://github.com/binlecode/agtop.git
```

Then install:

```shell
brew install binlecode/agtop/agtop
```

## Upgrade / Uninstall

```shell
brew update
brew upgrade binlecode/agtop/agtop
brew uninstall binlecode/agtop/agtop
```

## Usage

```shell
agtop --help
sudo agtop
sudo agtop --interval 1 --avg 30 --power-scale profile
sudo agtop --show_cores --core-view both --interval 1 --avg 30 --power-scale profile
```

## Development

Install dev dependencies (local laptop, `.venv`):

```bash
.venv/bin/python -m pip install -e ".[dev]"
```

Run the CLI module directly in development:

```bash
.venv/bin/python -m agtop.agtop --help
sudo .venv/bin/python -m agtop.agtop --interval 1 --avg 30 --power-scale profile
sudo .venv/bin/python -m agtop.agtop --show_cores --core-view both --interval 1 --avg 30 --power-scale profile
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

Maintainer release topology:

- Source repo: `binlecode/agtop`
- Tap repo: `binlecode/homebrew-agtop`
- Tap name users run: `binlecode/agtop`
- Formula name: `agtop`

Homebrew upgrades come from the tap formula, not from `pyproject.toml` alone.

One-time setup (if the tap repo does not exist yet):

```bash
export GH_USER="binlecode"
export TAP_REPO="$GH_USER/homebrew-agtop"

brew tap-new "$TAP_REPO"
gh repo create "$TAP_REPO" --public --source "$(brew --repository "$TAP_REPO")" --push
```

Release flow (split CI/CD):

1. On your local laptop, update `pyproject.toml` (`[project].version`) and `CHANGELOG.md` using your local `.venv` workflow, then commit.
   CI does not bump versions.

2. Create a matching source tag and push commit + tag together.
   CI does not create tags.

```bash
export VERSION="0.1.5"
git add pyproject.toml CHANGELOG.md
git commit -m "Release v$VERSION"
git tag "v$VERSION"
git push origin main "v$VERSION"
```

3. GitHub Actions workflow `.github/workflows/main-ci.yml` runs on push to `main`:

- Resolves Python version from `Formula/agtop.rb` (`depends_on "python@X.Y"`).
- Creates an isolated CI virtualenv (`.ci-venv`) to mirror formula-style isolation.
- Installs formula resource versions into `.ci-venv` before running project checks.
- Runs CLI/help and test checks.

4. GitHub Actions workflow `.github/workflows/release-formula.yml` runs on tag push (`v*`):

- Verifies tag version matches `pyproject.toml` version.
- Updates `Formula/agtop.rb` `url` and `sha256` from the tag tarball.
- Commits and pushes formula sync back to `main` automatically.

5. Validate package availability:

```bash
brew update
brew upgrade binlecode/agtop/agtop
brew info binlecode/agtop/agtop
```

## Compatibility Notes

- Chip families `M1` through `M4` are recognized directly.
- Unknown future Apple Silicon names fall back to tier defaults (`base`, `Pro`, `Max`, `Ultra`).
- Available `powermetrics` fields vary by macOS and chip generation.
- Small differences versus other tools can still occur due to sampling window and source timing differences.

Use `agtop` for install and runtime commands in this repository.
