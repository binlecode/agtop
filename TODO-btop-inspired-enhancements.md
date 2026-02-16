# TODO: btop-Inspired Enhancements for AI Engineers and Power Users

## Goal
Improve `agtop` from a real-time monitor into a diagnosis and benchmarking tool for AI workloads on Apple Silicon.

## Priority 1: Re-enable and surface memory bandwidth
- [ ] Re-enable `parse_bandwidth_metrics()` in runtime path.
  - File targets: `agtop/utils.py`, `agtop/agtop.py`
  - Include counters for E-CPU, P-CPU, GPU, Media, and total DCS read/write.
- [ ] Restore bandwidth gauges/charts in UI.
  - Show GB/s and profile-relative percent.
  - Keep layout usable in both `--show_cores` and default view.
- [ ] Add robust fallback for missing counters on different macOS/chip generations.
  - Missing fields must not crash UI.

Acceptance:
- Running `sudo agtop` shows live bandwidth values when available.
- Missing bandwidth fields degrade gracefully to zero/hidden values.

## Priority 2: Add per-core history charts
- [ ] Add rolling history buffers for each core activity percent.
- [ ] Add compact per-core history panel (sparklines/charts) alongside current per-core gauges.
- [ ] Optional mode: show either per-core gauge or per-core history to avoid screen clutter.

Acceptance:
- Users can identify core scheduling imbalance or bursty contention at a glance.
- No major terminal redraw regressions at 1s interval.

## Priority 3: Process visibility for root-cause analysis
- [ ] Add process panel (top CPU + memory consumers).
  - Fields: PID, command, CPU%, RSS.
- [ ] Add process filter flag for AI workflows.
  - Example: `--proc-filter "python|ollama|vllm|docker|mlx"`.

Acceptance:
- CPU/GPU/power spikes can be correlated to process-level culprits without leaving `agtop`.

## Priority 4: Session recording and post-run summary
- [ ] Add `--record <path>` output in `jsonl` (default) and optional CSV.
- [ ] Emit structured samples with timestamp, CPU/GPU/ANE power, utilization, RAM/swap, thermal pressure, bandwidth.
- [ ] Add end-of-run summary stats: avg, p50, p95, peak.

Acceptance:
- Users can compare model runs or commits using recorded metrics.
- Output is machine-readable and stable.

## Priority 5: Bottleneck signals and alerts
- [ ] Add lightweight alerts in title/status line:
  - thermal throttling,
  - sustained high bandwidth saturation,
  - rising swap usage,
  - sustained high package power.
- [ ] Add threshold flags so power users can tune noise level.

Acceptance:
- `agtop` proactively points to likely bottlenecks instead of only raw metrics.

## Priority 6: Command profiling mode
- [ ] Add `--profile-cmd "<command>"` mode.
  - Start command, monitor until exit, print/store run summary.
- [ ] Add markers in recording output: run start/stop, exit code, duration.

Acceptance:
- One command profiles AI benchmark runs end-to-end and produces comparable output.

## Implementation Notes
- Keep parser and UI resilient to schema drift in `powermetrics`.
- Favor optional panels/flags to preserve current default simplicity.
- Reuse existing power scaling (`--power-scale auto|profile`) for new charted metrics where applicable.

## Suggested Delivery Plan
- [ ] Milestone 1: Bandwidth re-enable + UI restore.
- [ ] Milestone 2: Per-core history panel.
- [ ] Milestone 3: Process panel + filter.
- [ ] Milestone 4: Recording + summary.
- [ ] Milestone 5: Alerts + profile command mode.
