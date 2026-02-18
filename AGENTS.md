# Repository Guidelines

## Project

**agtop** — performance monitoring CLI for Apple Silicon Macs. Hard fork of `tlkh/asitop`. Uses IOReport (in-process) for Apple Silicon power/frequency/residency metrics. Combines these with `psutil`, `sysctl`, and `system_profiler` into a real-time terminal dashboard showing CPU/GPU/ANE utilization, per-core frequency, memory/bandwidth, thermal state, and process info.

## Python Environment (Required)
- Always use the repository virtual environment at `.venv`.
- Prefer explicit executables over shell-global tools:
  - `.venv/bin/python`
  - `.venv/bin/pip`
  - `.venv/bin/pytest`
- Do not run `python`, `pip`, or `pytest` from the global environment for this repo.

## Build, Test, and Development Commands
- `.venv/bin/python -m pip install -e ".[dev]"`: install editable + dev deps (ruff).
- `.venv/bin/python -m agtop.agtop --help`: validate CLI parsing and flags.
- `agtop --interval 2 --avg 30`: run the tool locally.
- `.venv/bin/python -m build`: build source/wheel artifacts.
- `.venv/bin/pytest -q`: run automated tests.

## Architecture

| Module | Role |
|--------|------|
| `agtop/agtop.py` | CLI entry point (`cli()`), argument parsing, dashboard layout and main render loop |
| `agtop/sampler.py` | `IOReportSampler`: subscription lifecycle, delta computation, `SampleResult` conversion, DVFS table discovery via `ioreg` |
| `agtop/ioreport.py` | ctypes bindings to `libIOReport.dylib` and CoreFoundation (`IOReportSubscription`, `cfstr`, `cf_release`) |
| `agtop/smc.py` | SMC temperature reader: IOKit ctypes bindings to `AppleSMC`, key discovery, CPU/GPU die temperature reads |
| `agtop/utils.py` | System queries: `psutil` RAM/swap metrics, `sysctl`/`system_profiler` SoC info, `psutil` process collection |
| `agtop/soc_profiles.py` | 16 built-in M1–M4 SoC profiles with power/bandwidth reference values; tier fallbacks for unknown chips |
| `agtop/power_scaling.py` | Power chart scaling: `auto` mode (rolling peak x1.25) vs `profile` mode (SoC reference wattage) |
| `agtop/color_modes.py` | Terminal capability detection (mono/basic/256/truecolor) and percent-to-color-index mapping |
| `agtop/gradient.py` | Per-cell gradient rendering subclasses for `dashing` gauge/chart/text widgets |

**Data flow**: `ioreport.py` provides ctypes bindings for IOReport snapshots and deltas → `sampler.py` subscribes to Energy Model / CPU Stats / GPU Stats channels, computes deltas between consecutive snapshots, reads SMC die temperatures via `smc.py`, and converts raw items into a `SampleResult` (power in watts, frequency in MHz, activity in percent, temperatures in °C) using DVFS tables read from `ioreg` at startup → `agtop.py` merges `SampleResult` with `psutil` per-core CPU usage, `psutil` RAM/swap metrics, and `psutil` top processes from `utils.py` → renders via `dashing` widgets with optional gradient coloring from `color_modes.py` and `gradient.py`.

**SoC compatibility**: Explicit M1–M4 recognition (16 profiles). Unknown future chips fall back to tier defaults (base/Pro/Max/Ultra) using the latest known generation's reference values.

## Release Process

Releases are driven by `scripts/tag_release.sh [version]`. CI handles formula sync — never manually edit `Formula/agtop.rb` during releases. See `GUIDE-release-operations.md` for the full runbook.

## Coding Style & Naming Conventions
- Follow existing Python style: 4-space indentation, snake_case for functions/variables, short focused modules.
- Never use `from x import *`; always import explicitly.
- Keep parser keys and metric field names consistent with existing patterns (for example, `P-Cluster_active`, `gpu_W`).
- Prefer small, incremental changes in existing files over large refactors.
- No formatter/linter config is checked in; match surrounding code style when editing.

## Testing Guidelines
- Run `.venv/bin/pytest -q` for all code changes.
- Run a single test file: `.venv/bin/pytest tests/test_cli_contract.py -q`
- Run a single test function: `.venv/bin/pytest tests/test_cli_contract.py::test_name -q`
- Functional tests only: validate behavior through public/runtime entrypoints (for example CLI invocation, real file I/O paths, and end-to-end parse flows).
- Do not use mocks, fakes, monkeypatching, or fixture-based synthetic harnesses for new tests.
- Do not add unit tests that assert internal implementation details, helper math constants, or private function behavior in isolation.
- Do not add tests only to increase coverage numbers; each test must validate a production-relevant failure mode, regression risk, or external contract.
- Minimum checks before opening a PR:
  - `.venv/bin/python -m agtop.agtop --help`
  - `.venv/bin/pytest -q`
  - Run `agtop` on Apple Silicon and confirm gauges/charts update without crashes.
- For parser or metric changes, include a reproducible sample input/output note in the PR description.

## Commit & Pull Request Guidelines
- Use concise, imperative commit subjects (as seen in history), e.g. `Add support for M1 Ultra` or `agtop/utils.py: add bandwidth of M2`.
- Keep commits scoped to one logical change.
- Before every commit and before every push, always run:
  - `.venv/bin/ruff check --fix .`
  - `.venv/bin/ruff format .`
- PRs should include:
  - clear summary of behavior change,
  - tested macOS/chip details (for example, Ventura + M2),
  - commands used for validation,
  - screenshot or terminal capture for UI-visible changes.

## Security & Configuration Tips
- The IOReport backend runs unprivileged.
- Avoid introducing persistent privileged processes or unsafe temporary-file handling.
