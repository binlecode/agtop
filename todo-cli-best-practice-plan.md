# CLI Best-Practice Refactor TODO (Pending Only)

## Goal
Complete CLI hygiene and packaging modernization while preserving current dashboard behavior and metric semantics.

## Execution Order
Work top-to-bottom. `P2` is now the highest pending priority and `P4` is lowest.

## P1: Runtime Failure and Cleanup Paths
- [x] Add explicit startup failure guidance for `powermetrics`:
  - [x] If binary is missing: explain that `powermetrics` is required on macOS and not available on this system.
  - [x] If permission is denied: explain that elevated privileges are required and suggest `sudo agtop`.
  - [x] If subprocess startup fails for other reasons: print actionable error details and exit non-zero.
- [x] Guarantee terminal/process cleanup in a single `finally` path:
  - [x] Always restore cursor visibility (emit `\033[?25h`) on every exit path, not only `KeyboardInterrupt`.
  - [x] Always terminate an active `powermetrics` subprocess during shutdown, with safe exception handling.
  - [x] Ensure cleanup runs for normal exit, argument/runtime exceptions, and `KeyboardInterrupt`.

## P2: Imports and Dependency UX
- [ ] Replace `from .utils import *` with explicit imports in `agtop/agtop.py`.
- [ ] Handle missing `dashing` dependency with a clear error message and non-zero exit code.

## P3: Packaging Migration
- [ ] Add `pyproject.toml` with setuptools build-system metadata and runtime dependencies.
- [ ] Keep compatibility with current installs during migration (`setup.py` can remain as shim while transitioning).

## P4: Tests and Validation
- [x] Add parser tests for defaults and flags (`--show_cores` behavior).
- [x] Add import-safety test (importing `agtop.agtop` must not parse CLI args or trigger side effects).
- [ ] Re-run:
  - [x] `.venv/bin/python -m agtop.agtop --help`
  - [x] `.venv/bin/pytest -q`
- [ ] Manual Apple Silicon runtime check:
  - [ ] `sudo agtop --interval 1 --avg 30 --power-scale profile`
