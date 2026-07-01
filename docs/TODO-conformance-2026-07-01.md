# TODO — conformance audit (actop) · 2026-07-01

Scope: `actop/` (whole package, 16 files, ~4900 LOC)   ·   Import edges scanned: 47   ·   Prior report folded: none (first run)

## TL;DR — 5 real issues, ranked

1. **P0 — breaks CI now.** `gpu_registry.py:18-19` unguarded `ctypes.cdll.LoadLibrary` crashes `import actop` on non-Darwin; CI runs on `ubuntu-latest`. Introduced this session.
2. **P1 — same bug, not yet triggered.** `smc.py:16,59` and `ioreport.py:13,55` have the identical unguarded load, currently reached only via a lazy import — one careless module-scope import away from the same crash.
3. **P2 — DRY/divergence risk.** `tui/widgets.py:549`/`:819` duplicate the package-power-percent formula instead of sharing a helper (like `_bandwidth_percent` already does).
4. **P3 — cosmetic.** `sampler.py` CPU freq keys use `_Mhz`, GPU uses `_MHz` — inconsistent casing, not a functional bug.
5. **P3 — dead code.** `widgets.py:264` `_braille_spark` and `utils.py:106` `_normalize_process_command` — zero callers, delete both.

#1–2 share one root cause and one fix; that's this round's plan below.

## Inventory (read-confirmed, urgency-graded)

Grading: **P0** actively broken right now · **P1** same root cause, not yet triggered · **P2**
correctness-adjacent (DRY risk of divergence) · **P3** cosmetic / trivial cleanup, no runtime risk.

| urgency | rule | file:line | what | fix |
|---------|------|-----------|------|-----|
| **P0** | R6 | `actop/gpu_registry.py:18-19` | Unguarded `ctypes.cdll.LoadLibrary` at true module scope, actively reachable from `actop/__init__.py` (→ `api.py:9` → `utils.py:3` → here) — **crashes `import actop` on non-Darwin right now**, breaking CI's `ubuntu-latest` matrix (`.github/workflows/main-ci.yml:53`, `python -m actop.actop --help`, and likely pytest collection on every matrix Python version). Introduced this session, not pre-existing debt. | Guard the load under `if sys.platform == "darwin":`, mirroring `native_sys.py`'s pattern; public functions return `{}` on non-Darwin. |
| **P1** | R6 | `actop/smc.py:16,59` | Same unguarded-load pattern. Currently *latent* — only reached via a `LOCAL` (function-scoped) import in `sampler.py:26`, so it doesn't crash `import actop` today, but one careless module-scope import away from doing so (exactly what happened to gpu_registry.py). | Same guard, mirroring `native_sys.py`. |
| **P1** | R6 | `actop/ioreport.py:13,55` | Same unguarded-load pattern, same latent status (`sampler.py:25`, `LOCAL` import). | Same guard. |
| **P2** | R11 | `actop/tui/widgets.py:549` and `:819` | `pkg_pwr_pct`/`pkg_pct` both compute the identical formula `clamp_percent(s.package_watts / max(cfg.package_ref_w, 1.0) * 100)` inline instead of sharing a helper — the exact duplication the codebase already avoided for bandwidth via `_bandwidth_percent()` (`widgets.py:302`, called from both `:560` and `:811`). Risk: chart and alert threshold can silently diverge if only one call site is edited later. | Extract `_package_power_percent(snapshot, cfg)` mirroring `_bandwidth_percent`; call it from both `update_metrics` and `_compute_alerts`. |
| **P3** | R9 | `actop/sampler.py:252,255,257,258,284,289,300,305` vs `:310,311` | CPU raw-metric-dict frequency keys use `_Mhz` casing (`"E-Cluster_freq_Mhz"`, `"P-Cluster_max_freq_Mhz"`) while GPU keys use standard `_MHz` casing (`"freq_MHz"`, `"max_freq_MHz"`) — inconsistent unit-suffix casing across the two clusters. Confirmed **not** a functional bug: `_is_int_cpu_metric()` (`sampler.py:394-402`) and `api.py:27,35,50,51,53,54` correctly match the CPU casing, and the GPU averaging branch (`sampler.py:139`) and `api.py:52,55` correctly match the GPU casing — each half is internally self-consistent. | Standardize on `_MHz` for the CPU keys too; update the 8 CPU-side definition sites, `_is_int_cpu_metric`'s `endswith` check, and `api.py`'s 6 CPU-side lookups together in one pass. |
| **P3** | R10 | `actop/tui/widgets.py:264` | `_braille_spark(history, width_chars=8)` — zero callers anywhere in `actop/` or `tests/` (re-verified independently: only its own `def` line matches). | Delete. |
| **P3** | R10 | `actop/utils.py:106` | `_normalize_process_command(cmdline, fallback_name)` — zero callers anywhere in `actop/` or `tests/` (re-verified independently: only its own `def` line matches); equivalent logic is already inlined at `tui/app.py:290-298`. | Delete. |

**Cleared (read-confirmed, no violations):**
- **R1/R2/R3** (one-sided members, redundant state, premature abstraction) — none confirmed. `DashboardConfig`, `Monitor`/`Profiler`/`AsyncMonitor`, and the modal/factory patterns present are deliberate published seams, not premature wrappers.
- **R4/R5** (layer back-edges, underscore leaks) — none confirmed. Every `MODULE`-scope edge in the 47-edge map respects the native-infra → sampler → API → TUI order; the sole `PRIVATE`-tagged edge (`api.py:7` → `models._EMPTY_RESIDENCY`) is same-package, which is legal (R5 only fires on an `actop` ↔ `actop.tui` crossing). Both `__init__.py` files are compliant (root: version-resolution + re-export only; `tui/__init__.py`: empty).
- **R7** (optimistic flags) — none confirmed; state transitions in `sampler.py`/`tui/app.py`/`api.py` are ordered correctly.
- **R8** (backward-compat residue) — none confirmed; zero `_legacy`/`_compat`/`_old`/`deprecated` matches, no dual-format readers.
- **R10 dependency drift** — none confirmed; `rich` is already declared as a *direct* dependency in `pyproject.toml` with an inline comment explaining why (despite being pulled in transitively by `textual`) — the exact fix this rule looks for is already in place.
- **R12** (swallowed errors) — none confirmed across all 11 candidate `except` sites (`native_sys.py:220,496,522,574,648`; `utils.py:74`; `api.py:151`; `tui/app.py:460,487`; `tui/widgets.py:916`; `actop.py:227`). Every one degrades to a visible sentinel (`"Unknown"`, `0`/`0.0` with an explicit "visible unavailable, never a fabricated figure" comment, `""`, `[]`, or a printed error + exit code) or is an explicitly-documented fault-isolation boundary (`api.py:151`'s user-callback isolation).

## This round — fix the unguarded native ctypes loads (R6) — P0 + P1

This covers the only rows graded **P0**/**P1**: one is **actively breaking CI right now** on this
branch (not theoretical), and all three share one root cause — the highest-value target per the
audit's own prioritization rule (recurrence class over severity-by-count).

- [x] **R6 `actop/gpu_registry.py:18-19`** — add `import sys` and wrap the two `ctypes.cdll.LoadLibrary` calls (plus all dependent `argtypes`/`restype` setup) under `if sys.platform == "darwin":`, matching `native_sys.py`'s guard. `get_gpu_time_by_pid()` returns `{}` when the guard didn't fire. done_when: `pytest -q` green + `python3 -c "import actop"` no longer requires Darwin-only paths to succeed (verify by temporarily renaming `/System/Library/Frameworks/IOKit.framework` or reading the guard is present) + `tmp/edges.txt` unaffected (this is a within-file fix, not an edge change).
- [x] **R6 `actop/smc.py:16,59`** — same guard, same pattern. `SMCReader`'s public methods already document graceful-unavailability (`available` property, empty `TemperatureReading`) — extend that same contract to cover "not Darwin" as another unavailable case, not just "SMC service not found". done_when: `pytest -q` green.
- [x] **R6 `actop/ioreport.py:13,55`** — same guard. `IOReportSubscription`/`get_residencies` etc. are only ever constructed from `sampler.py` (Darwin-only call sites already), so the guard just needs to make *import* safe, not every function — `sampler.py`'s existing `LOCAL` import already defers the actual use to Darwin. done_when: `pytest -q` green.

No behavior change on Darwin (the guard is a no-op there); on non-Darwin, `import actop` and `python -m actop.actop --help` go from crashing to succeeding, matching `native_sys.py`'s already-documented cross-platform contract.

## Deferred backlog (P2 + P3 — 4 violations)

- **P2** R11 duplication: 1 (`_package_power_percent` extraction in `tui/widgets.py`)
- **P3** R9 naming drift: 1 (CPU `_Mhz` vs GPU `_MHz` casing in `sampler.py`, 8 CPU-side sites + `api.py` lookups — larger blast radius than a one-line fix, better as its own small PR)
- **P3** R10 dead code: 2 (`_braille_spark`, `_normalize_process_command` — trivial deletes, bundle with whichever PR touches those files next)
