# TODO — Metric Coverage (first-principle use-case gaps)

Reviewed on 2026-06-29 against agtop's core use cases and the direct Apple-Silicon
peers ([asitop](https://github.com/tlkh/asitop),
[macmon](https://github.com/vladkens/macmon), [mactop](https://github.com/context-labs/mactop)).

**Summary:** agtop's sampling layer already captures more than its dashboard
displays. The highest-value gaps are *surfacing* problems (data is in
`SystemSnapshot` / `Profiler` but never rendered), not *sampling* problems. This
file tracks closing them, and records the deliberate scope boundaries so they are
not mistaken for oversights.

agtop's first-principle use cases:
1. **Live workload monitoring** — "is my GPU saturated / am I thermal-throttling /
   is the ANE engaged" while running ML inference, video encode, or compilation.
2. **Profiling a run** programmatically (`Monitor` / `Profiler` + pandas).
3. **Observability source** (`--json`, `--serve`).

---

## Tier 1 — critical, data already sampled, presentation-only lift

- [x] **Memory bandwidth chart + label.** *(done — see `bw-chart` / `bw-label`)*
  `SystemSnapshot.bandwidth_gbps` is sampled but used **only** to fire the `BW>%`
  alert (`agtop/tui/widgets.py:644-654`) — there is no bandwidth chart or readout.
  On unified-memory Apple Silicon, memory-bandwidth saturation is *the* bottleneck
  for LLM inference and is a headline metric in asitop and macmon. Today the user
  gets a `BW>85%` token but can never see the actual GB/s or its trend.
  - Added a `bw-chart` + `bw-label` mirroring the existing metric pattern
    (`Mem BW N GB/s  avg … · max … GB/s`), placed after RAM and hidden per-snapshot
    when `s.bandwidth_available` is false. Chart percent reuses the `BW>` alert
    normalisation (bandwidth vs summed CPU+GPU channel capacity).
  - Files touched: `agtop/tui/widgets.py` (`_bw_hist` / `_bw_gbps_hist` deques,
    compose, `update_metrics`, `_gbps_stats_suffix`), `agtop/tui/app.py` (help
    overlay), `docs/DESIGN-system.md` §5.3, `tests/test_dashboard_stats.py`.
  - Stretch (still open): per-channel breakdown (CPU / GPU / media / DCS).
    `SystemSnapshot` currently exposes only the aggregate total, so this needs a
    sampler change (`agtop/sampler.py`) — track separately, not required for the
    headline number.

- [x] **Total / package power headline.** *(done — see `pkgpwr-chart` / `pkgpwr-label`)*
  `package_watts` is computed and drives the `PKG>%` alert, but the dashboard shows
  only **CPU Power** and **GPU Power** as separate charts. There is no total-SoC
  figure — asitop's signature number. A user must mentally sum CPU+GPU+ANE and still
  miss other rails.
  - Added a "Package Power" label + chart after GPU Power (field already on the
    snapshot). Chart percent reuses the `PKG>` alert normalisation (vs `package_ref_w`).
  - Files touched: `agtop/tui/widgets.py` (`_pkgpwr_hist` / `_pkg_w_hist` deques,
    compose, `update_metrics`), `agtop/tui/app.py` (help overlay), `docs/DESIGN-system.md`.

---

## Tier 2 — medium value

- [x] **Session energy total in the TUI.** *(done — `energy` status-line token)*
  `Profiler` already returns `total_package_joules` / `total_cpu_joules` /
  `total_gpu_joules` (`agtop/api.py:177-179`), but the live TUI has no cumulative
  energy / Wh readout — the natural "what did this run cost" question for the
  monitoring use case. Math is trivial (∫ package_watts dt over the session).
  - Added an `energy` token to the status line (next to `span`), accumulating
    `package_watts × sample_interval` each frame in `_session_joules` and
    rendering via `_format_session_energy` (mWh below 0.1 Wh, else Wh).
  - Files touched: `agtop/tui/widgets.py` (`_session_joules`, `update_metrics`,
    `_compute_alerts`, `_format_session_energy`), `agtop/tui/app.py` (help
    overlay), `docs/DESIGN-system.md` §5.4, `tests/test_dashboard_metrics.py`.

---

## Deliberate scope boundaries (NOT gaps — documented to avoid re-litigation)

- **Network / disk I/O.** Present in mactop / btop, but those are `psutil`-based and
  orthogonal to agtop's IOReport-first SoC-power thesis. Conscious non-goal.
- **Per-process GPU / ANE / energy attribution.** macOS does not expose this
  unprivileged; no direct peer (asitop / macmon) does either.
- **GPU per-core metrics.** Hardware limitation — the GPU is a monolithic `GPUPH`
  channel under a unified clock domain (see `docs/DESIGN-system.md` §3.4).

---

## Recommended order

All three landed (Tier 1 memory bandwidth + package power headline, Tier 2
session energy) — pure presentation-layer additions, no new sampling or native
bindings. The only remaining open item is the **Tier 1 stretch**: per-channel
bandwidth breakdown (CPU / GPU / media / DCS), which *does* require a sampler
change since `SystemSnapshot` exposes only the aggregate total today.
