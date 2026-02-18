# TODO: agtop Roadmap

Focused on gap-filling the Apple Silicon native monitoring mission — not
duplicating what top/htop/btop already do well.

---

## Phase 4: Basic Interactivity

**Priority: High**

**Goal:** Add runtime keyboard input. MVP: sort toggle, process filter, quit key.

### 4.1 Non-blocking input loop

Replace `time.sleep(interval)` with a `blessed` input loop using
`terminal.inkey(timeout=interval)`.

### 4.2 Process sort toggle

- `c` key: sort by CPU% (default)
- `m` key: sort by memory (RSS)
- `p` key: sort by PID
- Display current sort in panel title: `"Processes (sort: CPU%)"`

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

### 5.1 System power (SMC `PSTR`)

**Priority: Medium** — uses existing SMC reader from `agtop/smc.py`.

Total system power draw from the wall (or battery), not just CPU+GPU+ANE.
Available via SMC key `PSTR`. Add to power panel title.

### 5.2 DRAM and GPU SRAM power

**Priority: Medium** — independent.

IOReport's `"Energy Model"` group includes `DRAM*` and `GPU SRAM*` channels.
macmon displays these. Add to the power panel as additional lines.

### 5.3 Thermal pressure

**Priority: Low** — independent of temperature display.

`thermal_pressure` in `sampler.py` is still hardcoded to `"Unknown"`.
Thermal pressure is the OS-level throttling state (`Nominal`/`Fair`/`Serious`/
`Critical`), distinct from die temperature. Options:
- `sysctl -n kern.thermalmonitor` (returns 0/1 — coarse)
- `NSProcessInfo.thermalState` via PyObjC (accurate, but adds dependency)

### 5.4 Responsive layout

**Priority: Low** — independent.

Handle `SIGWINCH` (terminal resize). Rebuild widget tree with new dimensions.
Currently the layout is built once at startup and never adjusted.

### 5.5 Additional process columns

**Priority: Low** — independent.

Add configurable columns. MVP set: MEM%, user. Use the already-collected
`memory_percent` field from `get_top_processes()`.

---

## Dependency Map

```
Phase 4 (Interactivity)
  └── 4.1-4.4 (no blockers — Phase 3 refactor is complete)

Phase 5 (Polish)
  ├── 5.1 system power (uses existing smc.py)
  ├── 5.2 DRAM/SRAM power (independent)
  ├── 5.3 thermal pressure (independent)
  ├── 5.4 responsive layout (independent)
  └── 5.5 process columns (independent)
```

Phase 4 is the next milestone.
Phase 5 items are independent and can be picked up opportunistically.
