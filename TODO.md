# TODO: agtop Refactoring Plan

Derived from [ANALYSIS.md](./ANALYSIS.md). Focused on gap-filling the Apple
Silicon native monitoring mission — not duplicating what top/htop/btop already
do well.

---

## Phase 1: IOReport Migration (drop sudo, drop subprocess)

**Goal:** Replace `powermetrics` subprocess + file IPC with direct IOReport
calls. This is the highest-impact change: eliminates sudo, removes subprocess
lifecycle, and enables faster sampling.

### 1.1 Create `agtop/ioreport.py` — IOReport ctypes bindings

New module wrapping the private `libIOReport.dylib` via Python `ctypes`.

**Functions to bind:**
```
IOReportCopyChannelsInGroup(group, subgroup, 0, 0, 0) → CFDictionaryRef
IOReportMergeChannels(ch1, ch2, NULL)
IOReportCreateSubscription(NULL, channels, &sub, 0, NULL) → SubscriptionRef
IOReportCreateSamples(subscription, channels, NULL) → CFDictionaryRef
IOReportCreateSamplesDelta(sample1, sample2, NULL) → CFDictionaryRef
IOReportChannelGetGroup(item) → CFStringRef
IOReportChannelGetSubGroup(item) → CFStringRef
IOReportChannelGetChannelName(item) → CFStringRef
IOReportSimpleGetIntegerValue(item, 0) → int64
IOReportStateGetCount(item) → int32
IOReportStateGetNameForIndex(item, idx) → CFStringRef
IOReportStateGetResidency(item, idx) → int64
```

**CoreFoundation helpers needed** (via `ctypes.cdll.LoadLibrary`):
- `CFRelease`, `CFDictionaryGetCount`, `CFDictionaryCreateMutableCopy`
- `CFArrayGetCount`, `CFArrayGetValueAtIndex`
- `CFStringCreateWithCString`, `CFStringGetCString`
- `CFDictionaryGetValue`

**Reference implementation:** macmon's `sources.rs` lines 100-170 (IOReport
bindings) and lines 500-600 (channel setup + subscription).

**Files:**
- Create: `agtop/ioreport.py`
- Tests: `tests/test_ioreport.py`

**Risks:**
- Private API — no stability guarantee across macOS versions. Add version
  detection and graceful fallback to powermetrics if IOReport fails.
- ctypes + CoreFoundation is verbose. Consider `pyobjc-framework-IOKit` as
  alternative if ctypes becomes unwieldy.

### 1.2 Create `agtop/sampler.py` — unified metrics sampler

New module that replaces `parse_powermetrics()` and `run_powermetrics_process()`
from `utils.py`. Provides a clean interface for the main loop.

**Class design:**
```python
class Sampler:
    def __init__(self):
        # Subscribe to IOReport channels:
        #   ("Energy Model", None)        → power metrics
        #   ("CPU Stats", "CPU Core Performance States") → CPU freq/residency
        #   ("GPU Stats", "GPU Performance States")      → GPU freq/residency
        # Fallback: spawn powermetrics if IOReport unavailable

    def sample(self) -> SampleResult:
        # Take two IOReport snapshots, compute delta
        # Return structured metrics dict matching current format

    def close(self):
        # Release IOReport subscription (or kill powermetrics fallback)
```

**`SampleResult` fields** (matching current `parse_powermetrics` return tuple):
- `cpu_metrics`: E/P-Cluster active %, freq MHz, per-core active %, power W
- `gpu_metrics`: active %, freq MHz
- `thermal_pressure`: str
- `bandwidth_metrics`: dict of GB/s per subsystem
- `timestamp`: float

**Migration path:** `_run_dashboard()` currently calls `parse_powermetrics()`
at line 739. Replace with `sampler.sample()`. The return format stays the same
so the 250+ lines of widget-update code don't change.

**Files:**
- Create: `agtop/sampler.py`
- Modify: `agtop/agtop.py` (replace `parse_powermetrics` + process management)
- Modify: `agtop/utils.py` (deprecate `run_powermetrics_process`, `parse_powermetrics`)
- Tests: `tests/test_sampler.py`

### 1.3 Graceful fallback to powermetrics

Keep powermetrics as a fallback for:
- Older macOS versions where IOReport symbols differ
- Bandwidth counters (less documented in IOReport)
- Any IOReport initialization failure

**Logic:**
```python
try:
    sampler = IOReportSampler()
except (OSError, AttributeError):
    sampler = PowermetricsSampler(timecode, interval)
```

Print a one-line notice: `"Using powermetrics fallback (sudo required)"` or
`"Using IOReport (sudoless)"`.

### 1.4 Remove sudo requirement from CLI

Once IOReport is the primary path:
- Remove `sudo -n nice -n` prefix from powermetrics command (fallback only)
- Update startup messages in `_run_dashboard()` (line 354-355)
- Update `_build_powermetrics_start_error()` messages
- Update README and help text

---

## Phase 2: Temperature Metrics

**Goal:** Add CPU/GPU temperature display. Currently agtop shows thermal
pressure (nominal/heavy/critical) but not actual degrees.

### 2.1 SMC reader via IOKit

macmon uses IOKit's `AppleSMC` service to read temperature sensors:
- `Tp*` keys → P-core temperature
- `Te*` keys → E-core temperature
- `Tg*` keys → GPU temperature
- `PSTR` key → system power (float, watts)

**Approach:** Add `agtop/smc.py` using ctypes to call:
```
IOServiceMatching("AppleSMC") → matching dict
IOServiceGetMatchingService(kIOMasterPortDefault, matching) → service
```
Then use the SMC user client to read keys.

**Alternative:** `pyobjc-framework-IOKit` provides higher-level access.

**Fallback:** IOHIDSensors for M1 chips (macmon uses `pACC MTR Temp Sensor*`
and `GPU MTR Temp Sensor*` as HID fallback).

### 2.2 Display temperature in UI

- Add CPU/GPU temp to the existing gauge titles:
  `"E-CPU Usage: 45% @ 2064 MHz (52°C)"` (append to existing title string)
- Add thermal alerts when temp exceeds threshold (integrate with existing
  alert system)

**Files:**
- Create: `agtop/smc.py`
- Modify: `agtop/agtop.py` (gauge title formatting)
- Tests: `tests/test_smc.py`

---

## Phase 3: Extract Data Model from `_run_dashboard()`

**Goal:** Break the 1050-line monolithic function into testable components.
This is prerequisite for Phase 4 (interactivity) and general maintainability.

### 3.1 Extract `DashboardState` dataclass

Move all the scattered local variables into a structured state object:

```python
@dataclass
class DashboardState:
    # Metric values
    ecpu_usage: int = 0
    pcpu_usage: int = 0
    gpu_usage: int = 0
    ane_usage: int = 0
    ram_used_percent: int = 0

    # Power
    cpu_power_w: float = 0.0
    gpu_power_w: float = 0.0
    package_power_w: float = 0.0

    # Peaks & averages (replace scattered deque locals)
    ecpu_usage_peak: int = 0
    avg_ecpu_usage: deque = field(default_factory=lambda: deque(maxlen=30))
    # ... etc for all metrics

    # Alerts
    high_bw_counter: int = 0
    high_package_power_counter: int = 0
    thermal_pressure: str = "Unknown"

    # Processes
    cpu_processes: list = field(default_factory=list)
```

### 3.2 Extract `update_metrics(state, sample, args)` function

Move the ~200 lines of metric calculation (lines 756-1012) into a pure
function that takes the current state + new sample and returns updated state.
This becomes independently testable.

### 3.3 Extract `update_widgets(state, widgets, args)` function

Move the ~200 lines of widget property assignment (lines 801-1307) into a
function that reads from `DashboardState` and writes to widget objects.

### 3.4 Slim down `_run_dashboard()`

After extraction, the main function becomes:
```python
def _run_dashboard(args, runtime_state):
    widgets = build_widgets(args)
    state = DashboardState(...)
    sampler = Sampler()
    while True:
        sample = sampler.sample()
        if sample:
            state = update_metrics(state, sample, args)
            update_widgets(state, widgets, args)
        widgets.ui.display()
        time.sleep(interval)
```

**Files:**
- Create: `agtop/state.py` (DashboardState)
- Create: `agtop/updaters.py` (update_metrics, update_widgets)
- Modify: `agtop/agtop.py` (slim _run_dashboard)
- Tests: `tests/test_state.py`, `tests/test_updaters.py`

---

## Phase 4: Basic Interactivity

**Goal:** Add runtime keyboard input. MVP: sort toggle and process filter.
Not trying to match htop's full interactivity — just the essentials.

### 4.1 Non-blocking input loop

Replace `time.sleep(interval)` with a `blessed` input loop:

```python
with terminal.cbreak():
    while True:
        key = terminal.inkey(timeout=interval)
        if key:
            handle_keypress(key, state)
        sample = sampler.sample()
        # ...
```

### 4.2 Process sort toggle

- `c` key: sort by CPU% (default)
- `m` key: sort by memory (RSS)
- `p` key: sort by PID
- Display current sort in panel title: `"Processes (sort: CPU%)"`

Uses the already-collected `memory`-sorted list from `get_top_processes()`
(currently computed but unused).

### 4.3 Runtime process filter

- `/` key: enter filter mode (show input prompt at bottom of process panel)
- Type regex, `Enter` to apply, `Esc` to cancel
- Reuses existing `proc_filter` regex infrastructure

### 4.4 Quit key

- `q` key: clean exit (currently only Ctrl+C works)

**Files:**
- Modify: `agtop/agtop.py` (input loop in `_run_dashboard`)
- Create: `agtop/input.py` (keypress handling, filter input mode)
- Tests: `tests/test_input.py`

---

## Phase 5: Polish

Lower-priority improvements, each independently shippable.

### 5.1 DVFS frequency distribution

IOReport provides per-core DVFS residency (time spent at each frequency step).
macmon displays this. agtop currently shows only the average frequency. Add
optional DVFS breakdown in the per-core view (`--show_cores`).

### 5.2 DRAM and GPU SRAM power

IOReport's `"Energy Model"` group includes `DRAM*` and `GPU SRAM*` channels.
macmon displays these. Add to the power panel as additional lines.

### 5.3 System power (SMC `PSTR`)

Total system power draw from the wall (or battery), not just CPU+GPU+ANE.
Available via SMC key `PSTR`. Add to power panel title.

### 5.4 Responsive layout

Handle `SIGWINCH` (terminal resize). Rebuild widget tree with new dimensions.
Currently the layout is built once at startup and never adjusted.

### 5.5 Additional process columns

Add configurable columns. MVP set: MEM%, user. Use the already-collected
`memory_percent` field from `get_top_processes()`.

---

## Dependency Map

```
Phase 1 (IOReport)
  ├── 1.1 ioreport.py bindings
  ├── 1.2 sampler.py (depends on 1.1)
  ├── 1.3 fallback logic (depends on 1.2)
  └── 1.4 remove sudo (depends on 1.2)

Phase 2 (Temperature)
  └── 2.1 smc.py (independent of Phase 1)
  └── 2.2 UI display (depends on 2.1)

Phase 3 (Refactor)
  ├── 3.1 DashboardState (independent)
  ├── 3.2 update_metrics (depends on 3.1)
  ├── 3.3 update_widgets (depends on 3.1)
  └── 3.4 slim _run_dashboard (depends on 3.2, 3.3)

Phase 4 (Interactivity)
  └── 4.1-4.4 all depend on Phase 3

Phase 5 (Polish)
  ├── 5.1, 5.2, 5.3 depend on Phase 1 (IOReport access)
  ├── 5.4 independent
  └── 5.5 independent
```

Phases 1, 2, and 3 can proceed in parallel. Phase 4 requires Phase 3.
Phase 5 items are independent and can be picked up opportunistically.
