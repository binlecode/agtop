# Design Comparison: agtop vs. Standard x-top Tools

Comparison of agtop's design choices against the four dominant terminal system
monitors: `top`, `htop`, `btop`, and `bottom (btm)`, from system-level
architecture down to implementation details.

---

## 1. System Architecture

### Data acquisition model

| Aspect | top | htop | btop | bottom | **agtop** |
|---|---|---|---|---|---|
| Process data | kernel (procfs / libproc) | kernel (procfs / libproc) | kernel (procfs / libproc) | kernel (procfs / sysctl) | `psutil` (Python wrapper over sysctl/libproc) |
| Hardware metrics | kernel counters | kernel counters | kernel counters + `/sys` | kernel counters + optional NVIDIA SMI | `powermetrics` subprocess (plist output) |
| Data flow | direct syscall | direct syscall | direct syscall | direct syscall | file-based IPC: powermetrics writes to `/tmp/agtop_powermetrics*`, main loop reads & parses |
| Requires root | No | No | No | No | **Yes** — `sudo powermetrics` is mandatory |
| Sampling | in-process timer | in-process timer | in-process timer | in-process timer | external process (`powermetrics -i <ms>`) writes continuously; main loop polls file |

**Key difference:** All four reference tools read metrics directly from the
kernel via syscalls or procfs. agtop runs an external `powermetrics` subprocess
that writes plist data to a temp file, which the main loop deserializes each
tick. This is architecturally unusual — it introduces a file-based IPC boundary
with retry logic (`parse_powermetrics` in `utils.py:17` tries the last two
null-separated chunks if the first parse fails).

Process metrics (PID, CPU%, RSS) come from `psutil.process_iter()` separately,
making them independent of the powermetrics data path.

### IOReport: the private API that powermetrics wraps

`powermetrics` is **not** the only way to get Apple Silicon metrics. It is
itself a wrapper around the `IOReport` private C library (`libIOReport.dylib`).
Several open-source tools call `IOReport` directly, achieving the same metrics
**without sudo** and **without subprocess overhead**:

- [macmon](https://github.com/vladkens/macmon) (Rust) — full implementation
- [socpowerbud](https://github.com/dehydratedpotato/socpowerbud) (Obj-C) — reverse-engineered from powermetrics
- [Stats](https://github.com/exelban/stats) (Swift) — uses SMC + IOKit for sensors

**IOReport API surface** (from macmon's `sources.rs`):

```c
// Channel setup
IOReportCopyChannelsInGroup(group, subgroup, 0, 0, 0) → CFDictionaryRef
IOReportMergeChannels(ch1, ch2, NULL)                  → void
IOReportCreateSubscription(NULL, channels, &sub, 0, NULL) → SubscriptionRef

// Sampling (in-process, ~1ms per call)
IOReportCreateSamples(subscription, channels, NULL)    → CFDictionaryRef
IOReportCreateSamplesDelta(sample1, sample2, NULL)     → CFDictionaryRef

// Reading results
IOReportChannelGetGroup(item)          → CFStringRef
IOReportChannelGetSubGroup(item)       → CFStringRef
IOReportChannelGetChannelName(item)    → CFStringRef
IOReportSimpleGetIntegerValue(item, 0) → int64
IOReportStateGetResidency(item, idx)   → int64  (for DVFS states)
```

**Channel groups that provide Apple Silicon metrics:**

| IOReport Group | Subgroup | Metrics | agtop equivalent |
|---|---|---|---|
| `"Energy Model"` | (none) | CPU/GPU/ANE/DRAM power (watts) | `cpu_W`, `gpu_W`, `ane_W`, `package_W` |
| `"CPU Stats"` | `"CPU Core Performance States"` | Per-core frequency & residency (DVFS) | `E-Cluster_freq_Mhz`, `P-Cluster_active` |
| `"GPU Stats"` | `"GPU Performance States"` | GPU frequency & residency | `freq_MHz`, `active` |

macmon's channel names within `"Energy Model"`:
- `"CPU Energy"` / `"DIE_*_CPU Energy"` (Ultra chips) → CPU power
- `"GPU Energy"` → GPU power
- `"ANE*"` → Neural Engine power
- `"DRAM*"` → memory controller power
- `"GPU SRAM*"` → GPU SRAM power

**Temperature** comes from two additional sources (not IOReport):
- **SMC** (System Management Controller): keys `Tp*` (P-core), `Te*` (E-core),
  `Tg*` (GPU), `PSTR` (system power). Available from macOS 14+.
- **IOHIDSensors**: `pACC MTR Temp Sensor*`, `eACC MTR Temp Sensor*`,
  `GPU MTR Temp Sensor*`. Older API, works on M1.

**Bandwidth counters** are available via IOReport but the specific channel
groups are less documented. `powermetrics` exposes them as `bandwidth_counters`
in the plist output; the IOReport equivalent requires subscribing to additional
undocumented channel groups.

### Cost comparison: powermetrics vs. IOReport direct

| Approach | sudo | IPC | Startup | Per-sample | Complexity |
|---|---|---|---|---|---|
| `powermetrics` subprocess + file | **Yes** | spawn + file + plist parse | ~500ms | ~10-50ms (file read + parse) | Moderate (subprocess lifecycle) |
| IOReport via ctypes (Python) | **No** | none (in-process FFI) | ~50ms (dlopen) | ~1-5ms | High (C FFI, CoreFoundation types) |
| IOReport via C extension (Python) | **No** | none (in-process) | ~10ms | ~1ms | High (build step, C code) |

agtop currently uses the heaviest approach. Migrating to IOReport would:
1. **Drop the sudo requirement** — the single biggest usability barrier
2. **Eliminate file IPC** — no temp files, no plist parsing, no retry logic
3. **Remove subprocess management** — no spawn/kill/restart lifecycle
4. **Enable sub-second sampling** — practical for responsive UI

### Lifecycle & process management

| Aspect | top/htop/btop/bottom | **agtop** |
|---|---|---|
| Startup | Single process, immediate display | Spawns `powermetrics` subprocess, 150ms delay for first sample, then enters loop |
| Shutdown | Exit | Must terminate child `powermetrics` process; cleanup in `finally` block (`agtop.py:1328`) |
| Crash recovery | N/A (single process) | Detects `powermetrics` exit via `process.poll()`, reads stderr, raises descriptive error (`agtop.py:740-746`) |
| Periodic restart | N/A | `--max_count` triggers periodic `powermetrics` restart to work around potential resource leaks (`agtop.py:727-738`) |

The `runtime_state` dict (`agtop.py:1320`) tracks the powermetrics subprocess
and cursor visibility state, serving as a poor-man's context object passed
through the finally block for cleanup.

---

## 2. Rendering Architecture

### Terminal control layer

| Aspect | top | htop | btop | bottom | **agtop** |
|---|---|---|---|---|---|
| Terminal library | termcap/ncurses | ncurses | custom C++ (direct escape codes) | crossterm (Rust) | `blessed` (Python) |
| Widget framework | none (printf) | custom ncurses panels | custom C++ widget tree | tui-rs / ratatui | `dashing` (Python) |
| Rendering strategy | full screen rewrite | differential ncurses update | differential + Braille | differential via ratatui | full screen rewrite: `print("\033[2J\033[H")` then `ui.display()` (`agtop.py:1309-1311`) |
| Double buffering | ncurses handles it | ncurses handles it | manual back buffer | ratatui handles it | none — writes directly to stdout |

**agtop's rendering pipeline:**
1. `blessed.Terminal` provides cursor addressing (`terminal.move(x, y)`)
2. `dashing` library provides widget classes: `HSplit`, `VSplit`, `HGauge`,
   `HChart`, `VGauge`, `Text`
3. Widgets are composed into a tree: `ui = VSplit(row1, row2, row3)` with nested
   `HSplit`/`VSplit` for columns/rows (`agtop.py:415-544`)
4. Each tick: update widget `.value`, `.title`, `.text` properties, then call
   `ui.display()` which walks the tree and prints
5. Before rendering, cursor is hidden (`\033[?25l`); restored in finally block

**Flicker concern:** The `\033[2J\033[H` full-clear approach (line 1310) causes
visible flicker on every frame. `htop`, `btop`, and `bottom` all use
differential rendering (only redraw changed cells) to avoid this. The
`use_full_clear_redraw` flag exists but even the non-clear path still
redisplays the entire widget tree each frame.

### Gradient rendering

The `gradient.py` module subclasses `dashing`'s `HGauge`,
`VGauge`, and `HChart` to add per-cell RGB coloring based on fill percentage.
It uses a `_GradientRendererMixin` that converts percent values to RGB via
`color_modes.value_to_rgb()` (a 4-stop linear interpolation: green -> yellow ->
orange -> red), then emits `terminal.color_rgb()` escape sequences per cell.

This is activated by default when `dynamic_color_enabled` is true
(`agtop.py:322-346`), and can be disabled via `AGTOP_GRADIENT=0`.

Reference tools approach this differently:
- `btop` does per-cell coloring natively with its custom C++ renderer
- `bottom` delegates to ratatui's style system
- `htop` uses ncurses color pairs (limited palette)

---

## 3. Color System

| Aspect | top | htop | btop | bottom | **agtop** |
|---|---|---|---|---|---|
| Color detection | TERM env | TERM + ncurses | TERM + env vars | crossterm auto-detect | `detect_color_mode()`: checks NO_COLOR, TERM=dumb, FORCE_COLOR, COLORTERM, `terminal.number_of_colors` |
| Color modes | mono | 4 schemes | 14 themes | 21 themes | 4 modes: mono, basic (8-color), xterm256, truecolor |
| Dynamic coloring | No | No (static per type) | Static theme colors | Static theme colors | **Yes**: gauge/chart colors change per-tick based on current value (`color_for(percent)` at `agtop.py:704-710`) |
| User config | No | F2 menu | Config file + runtime | Config file | `--color` flag (seed color 0-8) + `AGTOP_COLOR_MODE` env var |

**agtop's dynamic coloring** is distinctive: the `value_to_color_index()`
function (`color_modes.py:120`) maps the current metric percentage to a color
on every frame. When CPU usage rises, the gauge turns from green to yellow to
red in real time. This is more like a car dashboard warning system than the
static theming of htop/btop/bottom.

The implementation cascades through modes:
- `truecolor`: `value_to_rgb()` -> 4-stop linear interpolation -> `terminal.rgb_downconvert()`
- `xterm256`: same RGB path -> `terminal.rgb_downconvert()` (256-color approximation)
- `basic`: 3-threshold mapping (green < 50%, yellow < 75%, red >= 75%)
- `mono`: always color index 0

---

## 4. Process List

### Data collection

| Aspect | top/htop/btop/bottom | **agtop** |
|---|---|---|
| Collection method | kernel iteration (procfs or sysctl) | `psutil.process_iter(attrs=[...])` (`utils.py:238`) |
| CPU% calculation | kernel-level per-tick delta | `proc.cpu_percent(interval=None)` — returns delta since last call |
| Pre-warming | First sample immediately valid | First call returns 0% (no previous sample); explicit warm-up call at `agtop.py:718-722` |
| Filtering | Runtime interactive | Compile-time regex: `re.compile(proc_filter, re.IGNORECASE)` applied via `pattern.search(command)` (`utils.py:244`) |

**Process name resolution pipeline** (`agtop.py:167-178`):
1. `_normalize_process_command(cmdline, name)` joins `cmdline` list with spaces
   (`utils.py:217-226`), falls back to psutil's `name` attribute
2. `_process_display_name(command)` extracts display name:
   - First checks for `.app` bundle path via `re.search(r"([^/]+)\.app(?:/| |$)")` — macOS-specific
   - Falls back to `command.split(" ", 1)[0]` -> `os.path.basename()`
3. `_shorten_process_command(name, max_len=24)` truncates with `...`

**Comparison:** `htop` stores the raw `cmdline` array and renders basename vs.
full path on demand (toggled by `p` key). `btop` uses `/proc/[pid]/comm` for
the short name. Neither does app-bundle extraction. agtop's approach
destructively joins the cmdline early (`" ".join(cmdline)`), losing the
argument boundary information.

### Display format

| Aspect | top | htop | btop | bottom | **agtop** |
|---|---|---|---|---|---|
| Columns | 12+ | 60+ configurable | ~8 | 14 | 4: PID, Name, CPU%, RSS |
| Column config | `f` key | F2 > Columns | Config | Config | Hardcoded |
| Sort | Interactive | Interactive | Interactive | Interactive | Fixed (CPU% desc) |
| Row count | Terminal height | Terminal height | Terminal height | Terminal height | Hardcoded 8 (`process_display_count = 8`) |
| Format | printf/ncurses | ncurses columns | C++ formatted | ratatui table widget | Python `str.format()`: `"{:>5} {:<24} {:>5.1f}% {:>5.1f}M"` |
| Kill/signal | `k` | F9 | Enter menu | `dd` | Not supported |

Process data flow: `get_top_processes()` returns both `cpu`-sorted and
`memory`-sorted lists (`utils.py:270-280`), but only the CPU list is displayed
(`agtop.py:1022`). The memory-sorted list is collected but unused in the UI.

---

## 5. Layout & Widget Composition

### Layout structure

All four reference tools use a "summary header + process table" pattern at
minimum. `btop` and `bottom` extend this to multi-panel dashboards.

**agtop's layout** (`agtop.py:415-544`):
```
VSplit (root)
├── Row 1 - HSplit "Processors"
│   ├── VSplit "E-CPU"
│   │   ├── HSplit [E-CPU gauge, E-CPU track chart]
│   │   ├── HSplit [per-core VGauges]  (if --show_cores)
│   │   └── HSplit [per-core HCharts]  (if --show_cores)
│   └── VSplit "P-CPU"
│       ├── HSplit [P-CPU gauge, P-CPU track chart]
│       └── HSplit [per-core VGauges or HCharts]  (if --show_cores)
├── Row 2 - HSplit "Graphics & Memory"
│   ├── VSplit "GPU & ANE"
│   │   ├── HSplit [GPU gauge, GPU track chart]
│   │   └── HSplit [ANE gauge, ANE track chart]
│   └── VSplit "Memory"
│       ├── HSplit [RAM gauge, RAM track chart]
│       └── VSplit "Memory Bandwidth"
│           └── HSplit [E-CPU BW, P-CPU BW, GPU BW, Media BW]
└── Row 3 - HSplit "Power & Processes"
    ├── HSplit "Power Chart"
    │   ├── HChart "CPU Power"
    │   └── HChart "GPU Power"
    └── VSplit "Processes"
        └── Text (formatted process list)
```

**Comparison to reference tools:**
- `btop` has a similar 3-row dashboard but with configurable layout presets
  (cycled via `P` key) and widgets that adapt to terminal width
- `bottom` has expandable widgets (`e` key zooms any widget to full screen)
- `htop`'s layout is fixed (header + table) but columns are configurable
- agtop's layout is **fully hardcoded** — the widget tree is built once at
  startup and never restructured

### Widget state model

Reference tools maintain a clear separation between data model and view. agtop
mutates widget properties directly in the main loop:

```python
# agtop.py:810-824 — direct widget mutation each tick
cpu1_gauge.title = "E-CPU Usage: " + str(ecpu_usage) + "% @ " + str(freq) + " MHz"
cpu1_gauge.value = ecpu_usage
ecpu_usage_chart.title = "E-CPU Track: " + str(ecpu_usage) + "% (avg: ...)"
ecpu_usage_chart.append(ecpu_usage)
```

There is no intermediate data model — the `_run_dashboard()` function
(`agtop.py:298`) is a single ~1050-line function that owns all widget
references as local variables, builds the layout, enters the main loop, and
updates everything inline. This monolithic pattern contrasts with btop's C++
class-per-widget architecture or bottom's Rust module-per-widget design.

History tracking uses `collections.deque(maxlen=N)` for rolling averages
(`agtop.py:367-368`), matching how btop and bottom handle time windows. The
`get_avg()` helper computes the mean of the deque.

---

## 6. Alert System

| Aspect | top | htop | btop | bottom | **agtop** |
|---|---|---|---|---|---|
| Alerts | None | None | None | None | **4 alert types** |
| Configuration | N/A | N/A | N/A | N/A | CLI flags per alert |
| Display | N/A | N/A | N/A | N/A | In power panel title bar |

agtop is unique among all reference tools in having a built-in alert system
(`agtop.py:1180-1203`):
- **Thermal pressure** — triggers when `thermal_pressure != "Nominal"`
- **Bandwidth saturation** — sustained bandwidth above `--alert-bw-sat-percent`
- **Swap growth** — swap usage increase over rolling window exceeds `--alert-swap-rise-gb`
- **Package power** — sustained power above `--alert-package-power-percent`

Alerts use a sustained-counter pattern (`_update_sustained_counter` at line 150):
the counter increments each tick while the condition is true, resets to 0 when
false, and fires when it reaches `alert_sustain_samples`. This debounce
prevents transient spikes from triggering alerts.

No reference tool has anything equivalent. `btop` has color-coded thresholds
(red for high usage) which is visual-only. agtop's alert system is the closest
thing to what monitoring tools like Datadog or Prometheus alerting rules provide.

---

## 7. SoC-Aware Power Scaling

| Aspect | top/htop/btop/bottom | **agtop** |
|---|---|---|
| Power display | N/A | Watts (current, avg, peak) for CPU, GPU, package |
| Power gauge scaling | N/A | SoC-specific reference wattage per chip model |
| Chip profiles | N/A | 16 known profiles (M1 through M4 Ultra) with tier fallbacks |

`soc_profiles.py` defines `SocProfile` dataclasses with per-chip reference
values: `cpu_chart_ref_w`, `gpu_chart_ref_w`, `cpu_max_bw`, `gpu_max_bw`.
These scale the power and bandwidth gauges so that 100% on an M1 means
something different than 100% on an M4 Ultra.

`get_soc_profile()` (`soc_profiles.py:187`) resolves by exact name first, then
falls back to tier-based defaults (Ultra > Max > Pro > base) using regex
matching, then a generic profile. This means unknown future chips (M5, M6)
degrade gracefully to the closest tier estimate rather than failing.

`power_scaling.py` provides two scaling modes:
- `profile`: uses the SoC profile's reference wattage as 100%
- `auto`: uses `peak_observed * 1.25` as 100%, with a floor minimum

This is wholly unique to agtop — no other terminal monitor has chip-specific
power calibration.

---

## 8. Implementation Patterns

### Language & dependencies

| Aspect | top | htop | btop | bottom | **agtop** |
|---|---|---|---|---|---|
| Language | C | C | C++ | Rust | Python |
| Binary size | ~100KB | ~300KB | ~2MB | ~4MB | N/A (interpreted) |
| Dependencies | libc, ncurses | ncurses, libcap | none (self-contained) | crossterm, ratatui | psutil, blessed, dashing |
| Startup time | instant | instant | ~50ms | ~50ms | ~500ms+ (Python import + powermetrics spawn + 150ms sleep) |
| Memory overhead | ~2MB | ~5MB | ~10MB | ~15MB | ~30MB+ (Python runtime + psutil) |

Python's performance characteristics are acceptable here because agtop samples
at 1-second intervals — the per-frame cost is negligible relative to the sleep
time. The real bottleneck is powermetrics startup latency, not rendering.

### Code structure

| Module | Lines | Responsibility |
|---|---|---|
| `agtop.py` | ~1345 | CLI, layout, main loop, rendering (monolithic) |
| `utils.py` | ~281 | powermetrics spawning/parsing, process collection, system info |
| `parsers.py` | ~284 | plist data extraction (CPU, GPU, bandwidth, thermal) |
| `soc_profiles.py` | ~202 | SoC profile definitions and resolution |
| `color_modes.py` | ~153 | Color detection, RGB interpolation, mode dispatch |
| `power_scaling.py` | ~37 | Power-to-percent conversion |
| `gradient.py` | ~131 | Per-cell gradient rendering subclasses |

**Architectural contrast with reference tools:**

- `htop` (~15K lines C): clean separation — `Process.c`, `CRT.c` (rendering),
  `Panel.c` (widget), `ScreenManager.c` (layout), platform-specific backends
- `btop` (~10K lines C++): `btop_draw.cpp`, `btop_collect.cpp`,
  `btop_config.cpp`, `btop_theme.cpp` — each concern in its own file
- `bottom` (~20K lines Rust): `app/`, `canvas/`, `data_collection/`,
  `widgets/` — module-per-concern with clear trait boundaries
- **agtop**: `_run_dashboard()` is a single 1050-line function containing
  widget construction, layout composition, the main loop, all metric updates,
  alert evaluation, and color updates. The data collection (`utils.py`,
  `parsers.py`) is well-separated, but the rendering/update logic is monolithic.

### Error handling pattern

agtop uses a defensive approach throughout:
- `parsers.py`: every field extraction goes through `_to_float()` / `_to_int()`
  with defaults, so malformed powermetrics output degrades to zeros rather than
  crashing
- `utils.py:238-268`: process iteration catches 5 exception types per process
- `agtop.py:1020`: process collection failure is silently swallowed
- The powermetrics retry in `parse_powermetrics()` tries the second-to-last
  null-separated chunk if the last one fails (handles partial writes)

Reference tools are less defensive because they read from stable kernel APIs.
agtop's defensiveness is justified because `powermetrics` plist output is an
undocumented format that varies across macOS versions.

---

## 9. Summary: Gaps and Strengths

### Gaps (prioritized by user-impact)

1. **sudo requirement** — the single biggest usability barrier. Every reference
   tool runs unprivileged. The IOReport private API provides the same metrics
   without sudo (proven by macmon, socpowerbud). Migrating from powermetrics
   subprocess to IOReport via ctypes/C extension would eliminate this.
2. **Subprocess + file IPC overhead** — spawning powermetrics, writing plist to
   `/tmp`, parsing with retry logic, managing lifecycle (restart, kill, stderr
   handling). IOReport direct calls are ~1ms in-process vs. ~50ms file parse.
3. **No interactivity** — the largest UX gap vs. reference tools. Every tool
   supports runtime keyboard navigation, sort, and filter. Requires refactoring
   `_run_dashboard()` into an event-loop model with non-blocking input (blessed
   supports `terminal.inkey(timeout=0)`).
4. **Monolithic main function** — `_run_dashboard()` at ~1050 lines mixes
   layout, data, rendering, and alerting. Extract widget-update functions and a
   data-model layer to enable testability and future interactivity.
5. **Full-screen redraw** — causes flicker. Differential rendering (only
   update changed cells) is standard in htop/btop/bottom. Would require
   changes to the `dashing` library or a switch to a different widget framework.
6. **No temperature metrics** — macmon and Stats show CPU/GPU temperature via
   SMC (`Tp*`/`Te*`/`Tg*` keys) or IOHIDSensors. agtop shows thermal pressure
   (nominal/heavy) but not actual temperatures in degrees.
7. **Fixed layout** — no responsive reflow, no widget zoom/expand, no layout
   presets. Terminal resize is not handled gracefully.
8. **Process management** — kill/signal is expected by htop/btop/bottom users.
9. **Limited process columns** — 4 columns vs. 8-60 in reference tools.
   At minimum: MEM%, user, state.
10. **No theming** — even 2-3 presets would help. The dynamic color system is
    a strength but isn't a substitute for aesthetic choice.

### Strengths (unique to agtop)

1. **Apple Silicon-native metrics** — power consumption (watts), ANE
   utilization, per-cluster frequency, memory bandwidth per subsystem, thermal
   pressure. No other terminal tool surfaces these.
2. **SoC-aware scaling** — chip-specific power/bandwidth profiles with tier
   fallbacks for unknown future chips.
3. **Dynamic severity coloring** — gauges change color per-tick based on
   current value (green -> yellow -> orange -> red). More informative than
   static themes.
4. **Alert system** — sustained-counter debounced alerts for thermal,
   bandwidth, swap, and power. No reference tool has this.
5. **Gradient rendering** — per-cell RGB coloring in bar gauges and charts,
   giving a smooth visual gradient effect.
6. **.app bundle name extraction** — shows "Visual Studio Code" instead of
   "Electron". A macOS GUI convention, but pragmatically correct for a
   macOS-only tool.
