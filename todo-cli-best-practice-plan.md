# CLI Best-Practice Refactor TODO (Pending Only)

## Goal
Complete CLI hygiene and packaging modernization while preserving current dashboard behavior and metric semantics.

## Execution Order
Work top-to-bottom. `P0` is highest priority and blocking; `P4` is lowest.

## P0 (Blocking): CLI Entrypoint Safety
- [x] Add `build_parser()` in `agtop/agtop.py` and move all argument definitions into it.
- [x] Remove module-level `parse_args()`; parse only inside runtime entrypoints.
- [x] Change `--show_cores` from `type=bool` to `action="store_true"`.
- [x] Add `cli(argv=None) -> int` wrapper for import-safe execution and testability.
- [x] Update `console_scripts` entrypoint to call `agtop.agtop:cli`.

## P1: Runtime Failure and Cleanup Paths
- [ ] Add explicit guidance when `powermetrics` cannot start (missing binary, missing sudo permission, or subprocess failure).
- [ ] Ensure cursor restore and subprocess termination happen in a `finally` cleanup path, not only on `KeyboardInterrupt`.

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
