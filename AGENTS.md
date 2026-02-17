# Repository Guidelines

## Project

**agtop** — performance monitoring CLI for Apple Silicon Macs. Hard fork of `tlkh/asitop`. Uses IOReport (in-process, no sudo) as the primary backend for Apple Silicon power/frequency/residency metrics, with `powermetrics` (privileged) as a fallback. Combines these with `psutil`, `sysctl`, and `system_profiler` into a real-time terminal dashboard showing CPU/GPU/ANE utilization, per-core frequency, memory/bandwidth, thermal state, and process info.

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
- `agtop --interval 1 --avg 30`: run the tool locally (IOReport backend, no sudo needed).
- `.venv/bin/python -m build`: build source/wheel artifacts.
- `.venv/bin/pytest -q`: run automated tests.

## Architecture

| Module | Role |
|--------|------|
| `agtop/agtop.py` | CLI entry point (`cli()`), argument parsing, terminal dashboard rendering, main event loop |
| `agtop/sampler.py` | Unified sampler abstraction: `IOReportSampler` (primary) and `PowermetricsSampler` (fallback), DVFS table discovery |
| `agtop/ioreport.py` | IOReport + CoreFoundation ctypes bindings for in-process Apple Silicon metrics |
| `agtop/parsers.py` | Parses `powermetrics` plist payloads (used by fallback path) |
| `agtop/utils.py` | System integration: `powermetrics` subprocess management, `sysctl`/`system_profiler` calls, process collection |
| `agtop/soc_profiles.py` | SoC profiles (M1–M4 families) with power/bandwidth reference values for scaling |
| `agtop/power_scaling.py` | Power scaling logic: `auto` (rolling peak) vs `profile` (SoC reference) |
| `agtop/color_modes.py` | Terminal color detection and gradient/index mapping |
| `agtop/gradient.py` | Per-cell gradient rendering subclasses for `dashing` widgets |

**Data flow**: `sampler.py` selects backend (IOReport or powermetrics) → backend produces `SampleResult` (cpu/gpu/thermal/bandwidth dicts) → `agtop.py` merges with `psutil`/`sysctl` data from `utils.py` → renders via `dashing` widgets.

**SoC compatibility**: Explicit M1–M4 recognition (16 profiles). Unknown future chips fall back to tier defaults (base/Pro/Max/Ultra). Powermetrics parser uses fallback logic (tries last 2 plist frames if current is corrupted).

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
- The default IOReport backend runs unprivileged (no sudo).
- The `powermetrics` fallback requires elevated privileges; review `sudo` usage carefully.
- Avoid introducing persistent privileged processes or unsafe temporary-file handling.
