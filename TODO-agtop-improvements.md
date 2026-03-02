# TODO: agtop Improvements — Adaptive Layout & Native API Efficiency

**Context**: Gap analysis between agtop (Python/dashing) and mactop (Go/gotui) identified five TUI
adaptive layout deficiencies (Stream A) and three startup-latency subprocess bottlenecks (Stream B).
This document provides cost-benefit analysis, adoption rationale, and full implementation specs,
ordered by priority. Both streams are independent and can be implemented in parallel.

---

## Architectural Context (from `REVIEW-architecture-comparison.md`)

Before committing to any TUI gap closure, the broader score card must be considered:

| Axis | agtop | mactop |
|------|-------|--------|
| TUI library | `dashing` — simple gauges/charts, no grid, no mouse | `gotui` — rich grid, tabs, mouse, resize events |
| Data backend | `ctypes` + subprocess | `cgo` statically linked C/Obj-C |
| agtop unique wins | ANE wattage tracking, SoC-profile power scaling, Python ecosystem integration | — |
| mactop unique wins | Layout variants, Prometheus, JSON/CSV export, menubar, disk/net I/O | — |

**Implication for this TODO**: agtop's competitive moat is *not* TUI richness — it is ANE visibility,
SoC-aware power scaling, and Python hackability. Closing TUI gaps has real value for defensive quality
(no crashes, no torn output) but diminishing returns for feature parity. Investment above the
"defensive polish" line (Gaps 1–3) should be evaluated against time that could be spent on
agtop's unique strengths instead.

**Principle applied below**: Gaps 1–3 improve defensive quality with minimal code. Gaps 4–5 require
disproportionate effort to match a capability (layout system) where `dashing`'s architecture is
fundamentally less capable than `gotui`. These are explicitly deferred.

---

## Gap 1 — Minimum Terminal Size Guard
### Status: `TODO — 1 line change, no-brainer`

### Problem
When the terminal is very small (`w < 3` or `h < 3`), dashing's `Split._display()` performs
`item_width = tbox.w // len(items)`, producing 0-width or negative-width `TBox` values.
Widget code then calls `terminal.move(x, y)` and tries to print strings into 0-column space —
resulting in garbled/overlapping output that persists until the terminal is resized larger.

mactop guards this explicitly (`layout.go:74`):
```go
if termWidth > 2 && termHeight > 2 {
    grid.SetRect(1, 1, termWidth-1, termHeight-1)
}
```

### Cost
- **Code change**: 4 lines in `agtop/agtop.py` render block.
- **Risk**: Zero — the guard only skips `ui.display()` when the terminal is unusably tiny.
- **Test surface**: Existing `pytest -q` suite unaffected; validate by resizing terminal below 3 cols/rows.

### Benefit
- Prevents garbled/corrupt terminal output at extreme sizes.
- Defensive correctness — users who split panes or run in embedded terminals won't see corruption.

### Adoption Rationale
**Adopt unconditionally.** Effort is negligible; there is no scenario where skipping `ui.display()` on
a 1×1 terminal is wrong. The change is self-evidently correct and carries zero trade-offs.
Because agtop's differentiation is not in TUI richness, every TUI investment must clear a high
cost-justification bar — this one passes trivially.

### Implementation

**File**: `agtop/agtop.py`
**Insertion point**: Just before the render block at line ~620.

```python
# Before (line 620-622):
if use_full_clear_redraw or not first_frame_rendered:
    print("\033[2J\033[H", end="", flush=True)
ui.display()

# After:
if terminal.width > 2 and terminal.height > 2:
    if use_full_clear_redraw or not first_frame_rendered:
        print("\033[2J\033[H", end="", flush=True)
    ui.display()
    first_frame_rendered = True
```

Note: move `first_frame_rendered = True` inside the guard so it only trips after a successful render.

**Verification**: resize terminal to 2 cols × 2 rows while agtop is running — no output corruption.

---

## Gap 2 — Forced Full-Clear on Terminal Resize
### Status: `TODO — blessed already provides the mechanism; ~15 lines`

### Problem
agtop has no explicit resize event path. When the user resizes the terminal mid-session:
- dashing re-reads `t.width` / `t.height` fresh on the next `ui.display()` call (via
  `blessed.Terminal.width` → `fcntl.ioctl(TIOCGWINSZ)` — `blessed/terminal.py:528–543`)
- BUT the render loop is blocked inside `terminal.inkey(timeout=config.sample_interval)` for up to 2
  seconds; the resize isn't reflected until the next natural frame.
- More critically, when the terminal shrinks, residual output from the previous larger frame remains
  visible until a full-clear is issued — resulting in visual artifacts/torn UI.

mactop's flow: `ui.ResizeEvent → handleResizeEvent → updateLayout → drawScreen` (all under `renderMutex`).

**blessed already ships the mechanism**: `terminal.notify_on_resize()` context manager
(`blessed/terminal.py:1481–1495`) — enables in-band DEC mode 2048 resize notifications.
When active, resize events are delivered through `inkey()` as keystroke objects with
`key.name == 'RESIZE_EVENT'`. This is the blessed-recommended approach over raw SIGWINCH.

### Cost
- **Code changes**: ~15 lines across `agtop/input.py` and `agtop/agtop.py`.
- **Risk**: Low. `notify_on_resize()` is a well-documented blessed feature. The only terminal-specific
  risk is that very old terminals don't support DEC mode 2048 — but blessed degrades silently.
- **Timing**: At most 1 stale frame after resize (resize is detected in the keypress drain loop, which
  runs after the current `ui.display()` call; the full-clear fires on the *next* loop iteration).

### Benefit
- Eliminates visual artifacts (ghost text, misaligned gauges) after terminal resize.
- Zero-latency response: resize → full-clear within one sample interval (≤ `--interval` seconds).
- Improves UX for tmux/split-pane workflows where users resize frequently.

### Adoption Rationale
**Adopt.** The blessed API makes this nearly free. The 1-frame stale window is imperceptible at normal
sample intervals. The only argument against is that "it works eventually anyway" — but torn output
is a visible quality regression that's entirely avoidable.

From the architecture review: mactop's clean resize handling is enabled by `gotui`'s native event loop.
agtop cannot replicate that architecture without replacing `dashing`, but `blessed.notify_on_resize()`
gets 90% of the benefit at near-zero cost — the right trade-off given agtop's positioning.

### Implementation

**Step 1 — Add `resize_pending` flag to `InteractiveState`**
File: `agtop/input.py`, lines 11–16

```python
@dataclass
class InteractiveState:
    sort_mode: str = SORT_CPU
    quit_requested: bool = False
    resize_pending: bool = False   # NEW: set True when RESIZE_EVENT received
```

**Step 2 — Detect `RESIZE_EVENT` in keypress handler**
File: `agtop/input.py`, in `handle_keypress()` (lines 19–33)

```python
def handle_keypress(key, interactive):
    if not key:
        return
    ch = str(key)
    if getattr(key, "name", None) == "RESIZE_EVENT":   # NEW
        interactive.resize_pending = True               # NEW
        return                                          # NEW
    if ch == "q":
        ...
```

**Step 3 — Enable `notify_on_resize()` around the main loop**
File: `agtop/agtop.py`, line 580 — wrap the `cbreak()` body:

```python
with terminal.cbreak():
    with terminal.notify_on_resize():   # NEW: enables in-band resize events
        while True:
            ...
```

**Step 4 — Trigger full-clear on resize in render block**
File: `agtop/agtop.py`, render block (~line 620):

```python
# Determine if full clear is needed
needs_full_clear = (
    use_full_clear_redraw
    or not first_frame_rendered
    or interactive.resize_pending        # NEW
)
if interactive.resize_pending:           # NEW
    interactive.resize_pending = False   # NEW

if terminal.width > 2 and terminal.height > 2:  # Gap 1 guard
    if needs_full_clear:
        print("\033[2J\033[H", end="", flush=True)
    ui.display()
    first_frame_rendered = True
```

**Verification**:
1. Run `agtop` in a resizable terminal.
2. Drag to resize — output should snap cleanly within ≤1 sample interval, no ghost text.
3. Shrink below 3 cols — no crash (Gap 1 guard).

---

## Gap 3 — Adaptive Widget Title Truncation
### Status: `MEDIUM priority — adopt for longest titles only`

### Problem
Widget titles in agtop are updated every frame in `update_widgets()` (`agtop/updaters.py:408–749`).
Some titles can reach 100+ chars:

| Title (max length) | Widget | Source lines |
|--------------------|--------|--------------|
| `"CPU+GPU+ANE Power: {W}W (avg: {W}W peak: {W}W) thermal: {x} alerts: {n}"` ~100 chars | `power_charts` container | updaters.py:736–749 |
| `"Memory Bandwidth: {G} GB/s (R:{G}/W:{G})"` ~55 chars | `memory_bandwidth_panel` | updaters.py:684–693 |
| `"CPU: {W}W (avg: {W}W peak: {W}W)"` ~55 chars | `cpu_power_chart` | updaters.py:708–718 |
| `"GPU: {W}W (avg: {W}W peak: {W}W)"` ~55 chars | `gpu_power_chart` | updaters.py:722–732 |
| `"RAM {G}/{G}GB sw:{G}/{G}GB"` ~50 chars | `ram_gauge` | updaters.py:601–612 |

**Important nuance**: dashing's `_draw_title()` already clips the title string to `tbox.w` characters
(`title[:tbox.w]`). So rendering never overflows. The issue is *semantic* — a clipped long string like
`"CPU+GPU+ANE Power: 15."` loses the peak/thermal info, whereas a deliberately shortened form like
`"Pkg 15.3W pk:18W"` would preserve the most useful numbers.

mactop's approach: `isCompactLayout()` → switches full form to short form (`app.go:862–871`).

### Cost
- **Code changes**: ~30–50 lines in `agtop/updaters.py`.
- Terminal width must be passed into `update_widgets()` (currently `agtop/agtop.py:612`).
- Requires defining width thresholds (what triggers truncation) and short-form strings for each title.
- Each dynamic title needs a `narrow_title` variant that must be maintained alongside the full form.
- **Risk**: Moderate — every title format change is a potential regression; tests against title strings
  become fragile. Title string content is not currently covered by automated tests.

### Benefit
- Narrow terminal users (split panes, small monitors) see useful abbreviated info instead of clipped mid-word.
- Mainly affects 4 titles; the majority of gauge titles (E-CPU, P-CPU, GPU, ANE, RAM %) are short enough.

### Adoption Rationale
**Adopt selectively, only for the 4 longest titles.**
Full mactop-style layout-switching is premature (Gap 5). But the `power_charts` container title at
~100 chars and `memory_bandwidth_panel` at ~55 chars are genuinely poor experiences at narrow widths.
A lightweight width threshold approach (one `if narrow:` branch per title) keeps the scope minimal.

From the architecture review: agtop's users skew toward ML engineers running Python pipelines and
terminal power users who value information density. Both groups use split-pane workflows where narrow
terminals are common. Truncation polish is therefore more valuable for agtop's actual audience than
it would be for a general system monitor.

**Threshold recommendation**: `terminal.width < 100` → narrow form. This matches when a standard
80-wide terminal splits in half.

### Implementation

**Step 1 — Pass terminal width into `update_widgets()`**
File: `agtop/agtop.py`, call site ~line 612:

```python
# Before:
update_widgets(state, widgets, config, interactive)
# After:
update_widgets(state, widgets, config, interactive, term_width=terminal.width)
```

File: `agtop/updaters.py`, function signature:

```python
def update_widgets(state, widgets, config, interactive, term_width=200):
    narrow = term_width < 100
```

**Step 2 — Apply narrow forms to 4 titles**
File: `agtop/updaters.py`

```python
# power_charts container title (~line 740):
if narrow:
    power_charts_title = f"Pkg {pkg_w:.1f}W pk:{pkg_peak:.0f}W"
else:
    power_charts_title = f"CPU+GPU+ANE Power: {pkg_w:.1f}W (avg: {pkg_avg:.1f}W peak: {pkg_peak:.1f}W) thermal: {thermal_str} alerts: {alert_count}"

# cpu_power_chart title (~line 712):
if narrow:
    widgets.cpu_power_chart.title = f"CPU {cpu_w:.1f}W"
else:
    widgets.cpu_power_chart.title = f"CPU: {cpu_w:.1f}W (avg: {cpu_avg:.1f}W peak: {cpu_peak:.1f}W)"

# gpu_power_chart title (~line 726):
if narrow:
    widgets.gpu_power_chart.title = f"GPU {gpu_w:.1f}W"
else:
    widgets.gpu_power_chart.title = f"GPU: {gpu_w:.1f}W (avg: {gpu_avg:.1f}W peak: {gpu_peak:.1f}W)"

# memory_bandwidth_panel title (~line 688):
if narrow:
    widgets.memory_bandwidth_panel.title = f"BW: {total_bw:.0f} GB/s"
else:
    widgets.memory_bandwidth_panel.title = f"Memory Bandwidth: {total_bw:.1f} GB/s (R:{read_bw:.0f}/W:{write_bw:.0f})"
```

**Verification**:
- Run `agtop` in an 80-wide terminal — confirm narrow titles.
- Run at 120-wide — confirm full titles.
- Check that `pytest -q` passes (no tests assert exact title strings).

---

## Gap 4 — Terminal-Width-Aware History Buffer Sizing
### Status: `LOW priority — defer unless wide-terminal use case is confirmed`

### Problem
History deques in `DashboardState` have fixed `maxlen` values set at startup
(`state.py:190–211` via `create_dashboard_state()`):
- `usage_track_window = max(20, int(args.avg / args.interval))` — default: **20 points**
- `avg_window = max(1, int(args.avg / args.interval))` — default: **15 points**

dashing's `HChart._display()` renders datapoints from left (oldest) to right (newest), filling
`tbox.w` columns. If `len(datapoints) < tbox.w`, the chart pads with the last recorded value to fill
the remaining columns. On a wide terminal (e.g., 200 cols), each chart widget is ~50 cols wide,
but with only 20 history points, the leftmost 30 columns repeat the oldest sample — making the
chart appear stretched/blocky.

mactop: `numPoints = max(500, termWidth)` (`app.go:112–122`) — buffers sized to full terminal width.

### Cost
- **Medium-high**. Python `deque` has no `resize(maxlen)` method. On terminal resize, all deques must
  be re-created and populated by copying existing elements:
  ```python
  new_deque = deque(old_deque, maxlen=new_maxlen)
  ```
- This must happen on the resize event (Gap 2 prerequisite).
- Requires threading Gap 2's `resize_pending` signal through to a `on_resize_rebuffer()` call.
- The rebuffering is cheap (20 elements copied) but the wiring is non-trivial.
- **Risk**: Low for correctness (deque copy is safe), medium for complexity.

### Benefit
- Chart history fills the full chart width on wide terminals — smoother, more informative visuals.
- Mactop uses 500+ points; agtop's 20 default feels sparse at any terminal width.
- However: increasing `--avg` already increases `maxlen`. Users on wide terminals can use
  `--avg 120 --interval 1` to get 120 points without any code change.

### Adoption Rationale
**Defer.** The workaround (`--avg` flag) is adequate. The complexity of deque rebuffering on resize
is disproportionate to the visual benefit (blocky chart history vs smooth). Additionally, the
meaningful fix is likely just increasing the *minimum* from 20 to a larger fixed value (e.g., 200),
regardless of terminal width — this is a 1-line change in `state.py` with better bang-for-buck
than the full resize-aware solution.

**Simpler alternative (recommended if acting on this gap)**:
File `agtop/state.py`, `create_dashboard_config()`:
```python
# Before:
usage_track_window = max(20, int(avg / sample_interval))
# After:
usage_track_window = max(200, int(avg / sample_interval))
```
This gives 200 history points regardless of terminal size — covers the "sparse chart" complaint at
practically no cost. Terminal-width-aware dynamic resizing can be revisited if user demand emerges.

---

## Gap 5 — Runtime Layout Switching
### Status: `LOW priority — NOT recommended for current scope`

### Problem
agtop has a single fixed layout structure. Changing the layout requires restarting with different
CLI flags (`--show_cores`, `--core_view`). mactop offers 17 named layout variants (`LayoutDefault`
through `LayoutPico`) cycled with `l` at runtime.

### Cost
- **High**. Requires:
  1. Design and implement 2–4 alternative layout trees in `agtop/agtop.py`.
  2. Add `layout_mode` field to `InteractiveState` and `handle_keypress()`.
  3. Rebuild the `ui = VSplit(...)` tree on layout switch, which means `_build_ui()` must be
     callable at runtime, not just at startup.
  4. Re-wire all widget references in `widgets` dataclass when rebuilding.
  5. Persist layout choice across restarts (needs a config file or `~/.agtoprc`).
- **Risk**: High — rebuild-on-switch is the most complex change in this list. Every widget reference
  in `updaters.py` (400+ lines) must remain valid after the rebuild.

### Benefit
- Nice quality-of-life for users who want different views (compact vs detailed, core focus, etc.).
- However, agtop's CLI flag approach is already ergonomic for most workflows (alias in shell profile).
- The `--show_cores` / `--core_view` flags cover 80% of the layout variation users need.

### Adoption Rationale
**Do not adopt in current cycle.**

From the architecture review: mactop's 17 layout variants are enabled by `gotui`'s native grid
system with proportional row/col sizing. `dashing`'s equal-division splits lack the expressiveness
to cleanly define even 3–4 meaningfully different layouts without significant scaffolding.
More critically, the review establishes that agtop's competitive advantage is **ANE tracking,
SoC profiles, and Python hackability** — not TUI flexibility. Investing 200+ lines to close a
feature gap in an area where mactop has a fundamental structural advantage is a poor allocation
of effort compared to deepening agtop's unique capabilities.

If layout cycling is eventually desired, the minimum viable approach is a `--compact` CLI flag
(applies shortened titles + hides per-core gauges at startup) rather than runtime switching.
Runtime switching requires rebuilding the `ui = VSplit(...)` tree and re-wiring all widget
references in `updaters.py` — that is a full refactor, not an incremental improvement.

---

---

## Stream B — Native API Efficiency (from `TODO-refactor-syscalls.md`)

These gaps are **fully independent** from Stream A (TUI layout). They touch `utils.py` and `sampler.py`
at startup only and have zero interaction with the render loop changes in Stream A.

### Overview

agtop currently calls shell subprocesses for basic system configuration that could be resolved with
in-process C bindings. Each call adds 0.2–0.3 s of startup latency:

| Syscall Gap | Function | Cost | Shell command replaced |
|-------------|----------|------|----------------------|
| **B-1** | `get_cpu_info()`, `get_core_counts()` | Simple | `sysctl -n <key>` |
| **B-2** | `get_gpu_cores()` | **Highest** (~0.25 s) | `system_profiler SPDisplaysDataType` |
| **B-3** | `_read_dvfs_tables()` | Medium | `ioreg -r -c AppleARMIODevice` |
| **B-4** | `get_top_processes()` | Deferred | `psutil` (per-tick, immeasurable at ≥2 s) |

**Recommended implementation order: B-2 → B-1 → B-3**

---

### B-1: Replace `sysctl` subprocess with `sysctlbyname` ctypes binding

**File**: new `agtop/native_sys.py` + edits to `agtop/utils.py`

**Mechanism**: Bind `sysctlbyname` from `libSystem.B.dylib` (already loaded in `smc.py` — safe to
load a second handle in `native_sys.py` via OS dylib cache; no circular import).

```python
# agtop/native_sys.py (new)
import ctypes
import sys

if sys.platform == "darwin":
    _libc = ctypes.cdll.LoadLibrary("/usr/lib/libSystem.B.dylib")
    _sysctlbyname = _libc.sysctlbyname
    _sysctlbyname.argtypes = [
        ctypes.c_char_p, ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_size_t), ctypes.c_void_p, ctypes.c_size_t,
    ]
    _sysctlbyname.restype = ctypes.c_int

def get_sysctl_int(name: str):
    size = ctypes.c_size_t(8)
    val = ctypes.c_uint64(0)
    if _sysctlbyname(name.encode(), ctypes.byref(val), ctypes.byref(size), None, 0) == 0:
        if size.value == 4:
            return ctypes.c_uint32(val.value).value
        return val.value
    return None

def get_sysctl_string(name: str):
    size = ctypes.c_size_t(0)
    if _sysctlbyname(name.encode(), None, ctypes.byref(size), None, 0) == 0:
        buf = ctypes.create_string_buffer(size.value)
        if _sysctlbyname(name.encode(), buf, ctypes.byref(size), None, 0) == 0:
            return buf.value.decode("utf-8")
    return None
```

**Replacement targets in `agtop/utils.py`**:
- `machdep.cpu.brand_string` → `get_sysctl_string("machdep.cpu.brand_string")`
- `machdep.cpu.core_count` → `get_sysctl_int("machdep.cpu.core_count")`
- `hw.perflevel0.logicalcpu` → `get_sysctl_int("hw.perflevel0.logicalcpu")`
- `hw.perflevel1.logicalcpu` → `get_sysctl_int("hw.perflevel1.logicalcpu")`

**Cost**: ~50 lines in new `native_sys.py` + ~10 line edits in `utils.py`. Risk: Low (sysctl keys are stable).

---

### B-2: Replace `system_profiler` with IOKit `AGXAccelerator` property read

**File**: `agtop/native_sys.py` (additions) + `agtop/utils.py`

**Mechanism**: `IOServiceGetMatchingService(0, IOServiceMatching("AGXAccelerator"))` →
`IORegistryEntryCreateCFProperty(service, "gpu-core-count")` → `CFNumberGetValue`.
Uses `IOServiceGetMatchingService` (singular — simpler than iterator pattern in `smc.py`).

Load local `_iokit` and `_cf` handles in `native_sys.py` (same pattern as `ioreport.py` and `smc.py`).
Use `kCFStringEncodingUTF8 = 0x08000100` (matches `ioreport.py:17`).

**Key bindings needed**:
```python
_iokit.IOServiceMatching.restype = ctypes.c_void_p
_iokit.IOServiceGetMatchingService.restype = ctypes.c_uint32  # returns io_service_t
_iokit.IORegistryEntryCreateCFProperty.restype = ctypes.c_void_p
_iokit.IOObjectRelease.restype = ctypes.c_int
_cf.CFNumberGetValue.argtypes = [ctypes.c_void_p, ctypes.c_int32, ctypes.c_void_p]
# kCFNumberSInt32Type = 3
```

**Cost**: ~40 lines added to `native_sys.py` + 3 line edit in `utils.py:get_gpu_cores()`. Risk: Low.

---

### B-3: Replace `ioreg` DVFS table read with direct IOKit property iteration

**File**: `agtop/native_sys.py` (additions) + `agtop/sampler.py`

**Mechanism**: `IOServiceGetMatchingServices("AppleARMIODevice")` → iterate until `IORegistryEntryGetName == "pmgr"` → `IORegistryEntryCreateCFProperties` → walk CFDictionary for `voltage-states*` keys → read raw `CFData` bytes → unpack with `struct.unpack_from("<II", ...)`.

**All byte-unpacking and table-classification logic preserved from `sampler.py:_read_dvfs_tables()`** — only the data acquisition layer changes (skips XML/plist).

**Additional bindings needed** (beyond B-2):
- `IOServiceGetMatchingServices` + `IOIteratorNext` (iterator pattern from `smc.py`)
- `IORegistryEntryCreateCFProperties` (out-param `CFMutableDictionaryRef`)
- `CFDictionaryGetCount` + `CFDictionaryGetKeysAndValues`
- `CFGetTypeID`, `CFStringGetTypeID`, `CFDataGetTypeID`
- `CFStringGetCString`, `CFDataGetBytePtr`, `CFDataGetLength`

**Cost**: ~90 lines added to `native_sys.py` + edit to `sampler.py:_read_dvfs_tables()` call site. Risk: Medium (IOKit iteration is more complex; keep old subprocess path as fallback behind `try/except`).

---

### B-4: Process Polling (`psutil`) — Deferred Indefinitely

`get_top_processes()` via `psutil.process_iter()` runs every tick but overhead is immeasurable at ≥2 s
intervals since psutil already wraps the same Mach `proc_pidinfo` calls. Implementing a replacement
requires a `{pid: prev_cpu_ns}` delta map + separate name lookups — high complexity, no measurable
benefit. **Do not implement.**

---

## Combined Implementation Order & Effort Summary

Both streams are independent. Can be executed in parallel across contributors or sequentially.

| ID | Stream | Gap | Priority | Effort | Risk | Verdict |
|----|--------|-----|----------|--------|------|---------|
| **A-1** | TUI Layout | Min size guard | **High** | 4 lines | Zero | **Implement now** |
| **A-2** | TUI Layout | Resize full-clear | **High** | ~15 lines | Low | **Implement now** |
| **B-2** | Native API | GPU cores via IOKit | **High** | ~50 lines | Low | **Implement now** |
| **B-1** | Native API | sysctl ctypes | **High** | ~60 lines | Low | **Implement now** |
| **A-3** | TUI Layout | Adaptive title truncation | **Medium** | ~40 lines | Medium | Implement |
| **B-3** | Native API | DVFS via IOKit | **Medium** | ~90 lines | Medium | Implement (with fallback) |
| **A-4a** | TUI Layout | Raise history buffer min | **Low** | 1 line | Zero | Opportunistic |
| **A-4b** | TUI Layout | Terminal-width-aware buffers | Low | ~60 lines | Medium | Defer |
| **A-5** | TUI Layout | Runtime layout switching | Low | 200+ lines | High | Defer |
| **B-4** | Native API | Process polling (psutil) | — | 100+ lines | High | Defer indefinitely |

---

## Files Touched (A-1 + A-2 + A-3 + A-4a + B-1 + B-2 + B-3)

| File | Change |
|------|--------|
| `agtop/agtop.py` | `notify_on_resize()` wrap; pass `term_width`; size guard + resize flag |
| `agtop/input.py` | `resize_pending` field; RESIZE_EVENT detection in `handle_keypress` |
| `agtop/updaters.py` | `term_width` param; 4 narrow title branches |
| `agtop/state.py` | Raise `usage_track_window` minimum from 20 → 200 |
| `agtop/native_sys.py` | **New file**: `sysctlbyname`, `get_gpu_cores_native`, `get_dvfs_tables_native` |
| `agtop/utils.py` | Replace `sysctl` subprocess calls; replace `system_profiler` GPU call |
| `agtop/sampler.py` | Replace `ioreg` DVFS subprocess with `get_dvfs_tables_native()` (with fallback) |

---

## Pre-implementation Checklist

- [ ] Run `.venv/bin/pytest -q` baseline — all tests green before touching code
- [ ] **A-2**: Confirm `terminal.notify_on_resize()` exists in installed blessed:
  `.venv/bin/python -c "from blessed import Terminal; t = Terminal(); print(hasattr(t, 'notify_on_resize'))"`
- [ ] **A-2**: Read `agtop/input.py` to confirm `InteractiveState` field names before adding `resize_pending`
- [ ] **A-3**: Confirm `update_widgets()` call sites (should be only one in `agtop.py` ~line 612)
- [ ] **B-1/B-2/B-3**: Confirm `sys.platform == "darwin"` guard in `native_sys.py` — existing
  pattern established in `ioreport.py` and `smc.py`
- [ ] **B-3**: Keep `ioreg` subprocess as `except`-fallback in `_read_dvfs_tables()` for safety
- [ ] After all changes: `.venv/bin/ruff check --fix . && .venv/bin/ruff format .`
- [ ] Manual validation on Apple Silicon: `agtop --interval 2 --avg 30`
  - Resize terminal → clean snap redraw (A-2)
  - Shrink to <3 cols → no crash (A-1)
  - Startup time: before/after comparison with `time agtop --help` (B-1/B-2)
  - Verify DVFS frequency tables still load correctly (B-3)
