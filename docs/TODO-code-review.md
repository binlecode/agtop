# Code Review — Bug-Fix Release Scope

Re-assessed against current source on 2026-06-28 and scoped for a **bug-fix release**. All fix and
hardening items have been resolved.

**Bug-fix release status: closed — no fix or hardening work remaining.**

---

## Completed in this release (fixes & hardening)

### [x] A1 — Delete dead BSD process structs · DONE
* **File:** `agtop/native_sys.py`
* Removed the unused `ProcBSDInfo`, `ProcTaskInfo`, `ProcTaskAllInfo` ctypes structs (never
  instantiated; `get_native_processes()` parses via verified offsets instead).
* **Hardening:** documented the `proc_pidinfo(PROC_PIDTASKALLINFO)` offset provenance
  (macOS Sonoma/Sequoia, version-sensitive) at the unpack site. The existing `ret >= 232` length
  check already bounds the buffer before unpacking, so no further guard is needed.

### [x] A2 — Remove `_read_dvfs_tables()` passthrough + fix stale docstring · DONE
* **Files:** `agtop/sampler.py`, `agtop/native_sys.py`
* Inlined the one-line wrapper (`__init__` now calls `get_dvfs_tables_native()` directly) and
  corrected the backwards docstring on `_classify_dvfs_tables` (no longer claims to "replicate"
  sampler logic; describes the actual heuristics).

### [x] A3 — Sleep guard in `Monitor.get_snapshot` · DONE
* **File:** `agtop/api.py`
* Added `time.sleep(0.01)` inside the `while sample is None` loop. Note the original "critical
  busy-loop" diagnosis was wrong (`prev_time` advances each iteration, so the loop self-terminates);
  the real benefit is avoiding a frame with an inflated `interval / elapsed_s` power scale.

**Validation:** `ruff check --fix .` clean · `ruff format .` clean ·
`python -m agtop.agtop --help` OK · `pytest -q` → 37 passed.
