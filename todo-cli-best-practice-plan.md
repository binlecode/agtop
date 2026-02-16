# CLI Best-Practice Refactor TODO

## Goal
Improve `agtop` into a cleaner, testable, CLI-friendly all-in-one utility structure while preserving current behavior and output.

## Phase 1: CLI Entrypoint Hygiene
- [ ] Move argument parser creation into a function (for example `build_parser()`).
- [ ] Stop parsing args at import time; parse only inside `main()` or `cli()`.
- [ ] Replace `type=bool` flag handling for `--show_cores` with `action="store_true"`.
- [ ] Add a small `cli()` wrapper that returns process exit code and is safe for imports/tests.

## Phase 2: Import and Module Boundaries
- [ ] Replace wildcard import in `agtop/agtop.py` (`from .utils import *`) with explicit imports.
- [ ] Keep UI/render loop logic in `agtop/agtop.py` and isolate system/process helpers in `agtop/utils.py`.
- [ ] Ensure pure functions (parsing/scaling/profile resolution) stay side-effect free.

## Phase 3: Error Handling and UX
- [ ] Add clear runtime error messaging for missing `dashing` dependency.
- [ ] Add explicit guidance when `powermetrics` or `sudo` permissions are unavailable.
- [ ] Ensure graceful shutdown path consistently restores terminal cursor state.

## Phase 4: Packaging Modernization
- [ ] Add `pyproject.toml` with build-system metadata and project dependencies.
- [ ] Keep `console_scripts` entrypoint for `agtop`.
- [ ] Keep backward compatibility with current install workflows during migration.

## Phase 5: Tests and Validation
- [ ] Add tests for parser-building and CLI argument defaults/flags.
- [ ] Add tests for import safety (module import should not parse args or start side effects).
- [ ] Re-run full test suite and smoke checks:
  - [ ] `.venv/bin/python -m agtop.agtop --help`
  - [ ] `.venv/bin/python -m pytest -q`
  - [ ] `sudo agtop --interval 1 --avg 30 --power-scale profile` (manual runtime check on Apple Silicon)

## Non-Goals
- [ ] Do not change dashboard visual design or metric semantics in this refactor.
- [ ] Do not remove current compatibility fallbacks for unknown Apple Silicon names.
