# TODO: agtop Refactoring Plan

Derived from [ANALYSIS.md](./ANALYSIS.md). Focused on gap-filling the Apple
Silicon native monitoring mission — not duplicating what top/htop/btop already
do well.

---

## Phase 2: Temperature Metrics

**Goal:** Add CPU/GPU temperature display. Currently agtop shows thermal
pressure as "Unknown" (IOReport has no temperature channels). Actual die
temperatures are available via SMC (no sudo required).

### 2.1 SMC reader via IOKit

macmon uses IOKit's `AppleSMC` service to read temperature sensors:
- `Tp*` keys → P-core temperature
- `Te*` keys → E-core temperature
- `Tg*` keys → GPU temperature
- `PSTR` key → system power (float, watts)

**Approach:** Add `agtop/smc.py` using ctypes to call:
```
IOServiceMatching("AppleSMC") → matching dict
IOServiceGetMatchingServices → iterate to AppleSMCKeysEndpoint
IOServiceOpen(device, mach_task_self(), 0, &conn)
IOConnectCallStructMethod(conn, 2, &input, 80, &output, &80)
```
Use 80-byte KeyData struct with selectors: 9=ReadKeyInfo, 5=ReadBytes.
Temperature keys have type `"flt "` (4-byte IEEE float).

**Dynamic key discovery** (like macmon): enumerate all SMC keys, filter for
`data_type == "flt "` and `data_size == 4`, classify by prefix:
- `Tp*` / `Te*` → CPU sensors
- `Tg*` → GPU sensors

This avoids hardcoding chip-specific key lists and provides forward
compatibility with future chips.

**Fallback:** IOHIDSensors for M1 chips (macmon uses `pACC MTR Temp Sensor*`
and `GPU MTR Temp Sensor*` as HID fallback). Note: IOHID caps at ~80°C on
macOS 14+, so SMC is preferred.

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

**Goal:** Break the monolithic function into testable components.
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

Move the metric calculation lines into a pure function that takes the current
state + new sample and returns updated state. This becomes independently
testable.

### 3.3 Extract `update_widgets(state, widgets, args)` function

Move the widget property assignment lines into a function that reads from
`DashboardState` and writes to widget objects.

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

### 5.2 DRAM and GPU SRAM power

IOReport's `"Energy Model"` group includes `DRAM*` and `GPU SRAM*` channels.
macmon displays these. Add to the power panel as additional lines.

### 5.3 System power (SMC `PSTR`)

Total system power draw from the wall (or battery), not just CPU+GPU+ANE.
Available via SMC key `PSTR`. Add to power panel title. Depends on Phase 2
(SMC reader).

### 5.4 Responsive layout

Handle `SIGWINCH` (terminal resize). Rebuild widget tree with new dimensions.
Currently the layout is built once at startup and never adjusted.

### 5.5 Additional process columns

Add configurable columns. MVP set: MEM%, user. Use the already-collected
`memory_percent` field from `get_top_processes()`.

---

## Dependency Map

```
Phase 2 (Temperature)
  └── 2.1 smc.py (independent)
  └── 2.2 UI display (depends on 2.1)

Phase 3 (Refactor)
  ├── 3.1 DashboardState (independent)
  ├── 3.2 update_metrics (depends on 3.1)
  ├── 3.3 update_widgets (depends on 3.1)
  └── 3.4 slim _run_dashboard (depends on 3.2, 3.3)

Phase 4 (Interactivity)
  └── 4.1-4.4 all depend on Phase 3

Phase 5 (Polish)
  ├── 5.2, 5.3 depend on Phase 2 (SMC access)
  ├── 5.4 independent
  └── 5.5 independent
```

Phases 2, 3 can proceed in parallel. Phase 4 requires Phase 3.
Phase 5 items are independent and can be picked up opportunistically.
