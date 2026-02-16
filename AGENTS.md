# Repository Guidelines

## Python Environment (Required)
- Always use the repository virtual environment at `.venv`.
- Prefer explicit executables over shell-global tools:
  - `.venv/bin/python`
  - `.venv/bin/pip`
  - `.venv/bin/pytest`
- Do not run `python`, `pip`, or `pytest` from the global environment for this repo.

## Project Structure & Module Organization
`agtop` is a small Python CLI package.
- `agtop/agtop.py`: CLI entry point, argument parsing, and terminal dashboard rendering.
- `agtop/utils.py`: system calls (`powermetrics`, `sysctl`, `system_profiler`) and runtime helpers.
- `agtop/parsers.py`: parsing logic for `powermetrics` plist payloads.
- `tests/`: unit tests for SoC profiles, parser resilience, and scaling logic.
- `images/`: README/demo assets.
- `setup.py`: package metadata, dependencies, and `console_scripts` entry point (`agtop`).

## Build, Test, and Development Commands
- `.venv/bin/python -m pip install -e .`: install in editable mode for local development.
- `.venv/bin/python -m agtop.agtop --help`: validate CLI parsing and flags.
- `sudo agtop --interval 1 --avg 30`: run the tool locally (requires `sudo` for `powermetrics`).
- `.venv/bin/python setup.py sdist bdist_wheel`: build source/wheel artifacts.
- `.venv/bin/pytest -q`: run automated tests.

## Coding Style & Naming Conventions
- Follow existing Python style: 4-space indentation, snake_case for functions/variables, short focused modules.
- Keep parser keys and metric field names consistent with existing patterns (for example, `P-Cluster_active`, `gpu_W`).
- Prefer small, incremental changes in existing files over large refactors.
- No formatter/linter config is checked in; match surrounding code style when editing.

## Testing Guidelines
- Run `.venv/bin/pytest -q` for all code changes.
- Functional tests only: validate behavior through public/runtime entrypoints (for example CLI invocation, real file I/O paths, and end-to-end parse flows).
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
- PRs should include:
  - clear summary of behavior change,
  - tested macOS/chip details (for example, Ventura + M2),
  - commands used for validation,
  - screenshot or terminal capture for UI-visible changes.

## Security & Configuration Tips
- `powermetrics` requires elevated privileges; review `sudo` usage carefully.
- Avoid introducing persistent privileged processes or unsafe temporary-file handling.
