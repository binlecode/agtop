# TODO — `actop` rename + `*top`-driven differentiation roadmap

Status: **planned (rename happening soon).** This is the single source of truth for
(A) the `agtop → actop` rename and (B) the mission-specific feature roadmap that
justifies staying a `*top`.

## Mission (first principles)

> **The complete, sudoless Apple-Silicon `*top` — it shows what no other monitor does.**

`actop` stays a live terminal monitor you *watch* (the `*top` use case). It wins not by
leaving the category but by **covering the whole chip and surfacing decision-grade
signals the others can't** — per-process power, bandwidth saturation, throttle state,
DVFS residency — all **in-process and without `sudo`**. The Python API
(`Monitor`/`Profiler`, `to_pandas()`) stays as the programmable layer underneath, not
the headline.

Positioning line: *"the Apple-Silicon `*top` that answers the questions the others
can't — which process is drawing the watts, am I memory-bandwidth-bound, am I being
throttled right now."*

---

# Part A — Rename `agtop → actop`

### Why
- `agtop` = "Apple **G**PU top" — **too narrow** (we monitor CPU/GPU/ANE/mem/power/thermal).
- `actop` = "Apple **C**hip top" — whole-chip, on-mission; plus a second reading **AC = power**.
- Keeps the `a_top` lineage and brand cadence (one-letter evolution `g → c`).
- **Namespaces are clear:** PyPI `actop` free, Homebrew core `actop` free, GitHub
  `binlecode/actop` free (only a dead 0★ `dlhx5326/actop`, last pushed 2019 — non-blocking).
- Fixes the real blocker: PyPI `agtop` is squatted by an unrelated tool, so
  `pip install agtop` is impossible. `pip install actop` / `pipx install actop` becomes ours.
- `atop` (1k★ Linux monitor) adjacency is **unchanged** — `agtop` and `actop` are both
  `atop`+one consonant, equidistant; no *new* confusion risk. Accepted.

### Rename surfaces (checklist)
- [ ] **GitHub repo**: rename `binlecode/agtop → binlecode/actop` (GitHub auto-redirects old URLs/clones). Update repo description/topics to the new name.
- [ ] **Python package**: `agtop/ → actop/`; update `pyproject.toml` `[project].name`, `[project.urls]`, and `[project.scripts]` (`actop = "actop.actop:cli"`).
- [ ] **Internal imports / module paths**: `agtop.*` → `actop.*` across the package and `tests/` (`agtop/agtop.py:cli` → `actop/actop.py:cli`, `__init__`, `api.py`, `tui/`, etc.).
- [ ] **CLI command**: primary command becomes `actop`. **Keep `agtop` as a deprecated alias** console-script for ~1–2 releases so existing tap users aren't broken (prints a one-line "renamed to actop" notice).
- [ ] **Homebrew**: `Formula/agtop.rb → Formula/actop.rb`, `class Agtop → Actop`, new `url` (new repo tag); update tap install docs. Consider keeping an `agtop` formula shim that depends on `actop` for one cycle.
- [ ] **CI**: update `.github/workflows/release-formula.yml`, `main-ci.yml`, `scripts/tag_release.sh`, and `docs/GUIDE-cicd-release.md` (formula filename, class, repo refs).
- [ ] **PyPI publish (now possible)**: set up publishing for `actop` — prefer **PyPI Trusted Publishing (GitHub OIDC)** over a long-lived token; wire a publish step into the tag release flow. This delivers the frictionless `pipx install actop` / `uv tool install actop`.
- [ ] **README**: title, tagline/positioning (whole-chip mission), install commands (add `pipx`/`uv install actop` + brew), name-origin note ("Apple Chip top" + AC/power), badges, hero alt text.
- [ ] **Docs + project memory**: sweep `docs/` for `agtop`; update `CLAUDE.md` (project overview + module paths), and the `agtop-name-origin` memory note. `AGENTS.md` is a symlink to `CLAUDE.md` (no change needed beyond content).
- [ ] **Assets**: optionally rename `images/agtop*.png → actop*.png` and update references.

### Sequencing
1. Rename GitHub repo (redirects keep old links alive).
2. Code/package rename + `agtop` alias + tests green (`ruff` + `pytest`).
3. Formula/CI/tag-script updates.
4. Cut the rename release (suggest **v0.10.0** to signal the change).
5. Set up + verify PyPI Trusted Publishing; publish `actop`.
6. Update README/docs/positioning; announce.

### Risks / notes
- In-flight `0.9.x` releases: finish the rename on a clean tree; don't interleave with a release.
- Tap users: GitHub redirect + the `agtop` formula/command shim cover the transition; document the one-time `brew uninstall agtop && brew install …/actop` if needed.
- One-way-ish door (PyPI name, brew formula) — do it deliberately, all at once.

---

# Part B — `*top`-driven feature differentiation (the white space)

Each item: **what · why it's white space · data/module to build on · effort · acceptance.**
Everything below is feasible on the existing **sudoless in-process** stack.

## Tier 1 — headline differentiators (build on what exists; ship these as "why actop")

### 1. Per-process power / energy attribution ⭐ *the flagship*
- **What**: an **Energy/Power column** in the process table — "which process is drawing the watts."
- **Why white space**: asitop/mactop/macmon/silitop show *system-total* power and a CPU%/RSS process list; **none attributes power/energy per process**. This is Activity Monitor's "Energy Impact," but in a sudoless TUI — nobody does it.
- **Build on**: `native_sys.py` (already does native proc introspection via `proc_taskallinfo`) → add `task_power_info` / rusage energy counters; surface through `utils.py` process collection → `models.py` (`ProcessInfo` energy field) → `tui/widgets.py` process rows; include in `export.py`.
- **Effort**: M–L (native struct work; per-process *CPU* energy is readily available, per-process *GPU* is the stretch in Tier 2).
- **Acceptance**: process table shows a per-process energy/power figure that tracks a known busy process (e.g. an inference run) and sums sanely toward package power.

### 2. Bandwidth as % of SoC peak + saturation indicator ⭐ *the LLM answer*
- **What**: render memory bandwidth not just as GB/s but as **% of this chip's theoretical peak**, with a saturation/`MEM-BOUND` indicator.
- **Why white space**: most tools omit bandwidth entirely; none frames it as the *"am I memory-bandwidth-bound?"* decision metric that governs LLM inference.
- **Build on**: existing `bandwidth_gbps` (sampler/models) ÷ reference peak bandwidth in `soc_profiles.py` (add a `peak_bandwidth_gbps` field per profile if not present); display in `tui/widgets.py`; reuse the alert path for a `MEM-BOUND` state.
- **Effort**: S–M (data already sampled).
- **Acceptance**: on a bandwidth-heavy workload, the % climbs toward 100% of the SoC's known peak and the saturation indicator fires.

### 3. Thermal-throttle indicator
- **What**: an explicit **`THROTTLING`** state — "GPU/CPU capped at N% of max frequency right now," not just a temperature number.
- **Why white space**: everyone shows temps; **nobody clearly says you're being throttled** and by how much.
- **Build on**: per-core/GPU current frequency (sampler/models) vs max freq from `soc_profiles.py`; correlate with die temps from `smc.py`; surface via the existing alert/status path in `tui/widgets.py`.
- **Effort**: S–M.
- **Acceptance**: under sustained load that induces throttling, the indicator reflects the frequency cap; clears when thermals recover.

## Tier 2 — deep-silicon signals (unique to in-process IOReport; harder)

### 4. DVFS P-state residency distribution
- **What**: per-cluster **time-in-each-frequency-state** histogram (how the silicon actually behaved, not just instantaneous freq).
- **Why white space**: only your in-process IOReport access makes this cheap; powermetrics-based tools (asitop/silitop) can't easily match it.
- **Build on**: the **DVFS table discovery already in `sampler.py`** + residency data in `ioreport.py`; new compact widget in `tui/widgets.py`.
- **Effort**: M.
- **Acceptance**: residency distribution shifts toward high-freq states under load and idle states at rest.

### 5. Per-process GPU / ANE attribution (stretch)
- **What**: extend #1 to GPU/ANE share per process.
- **Why white space + caveat**: nobody does it; macOS exposes per-process GPU only partially → expect **approximate** attribution. Ship clearly labeled as estimated.
- **Effort**: L (research-y).

## Tier 3 — completeness parity (secondary; NOT white space)
Network I/O, disk I/O, fan RPM, SSD/battery temps. mactop/silitop already have these — they're *parity*, not differentiation. Add only after Tier 1–2; don't let them displace the wins.

## Supporting (keep, don't headline)
- **Python API** (`api.py` `Monitor`/`Profiler`, `to_pandas()`) and **exports** (`export.py` NDJSON/Prometheus) stay — they *feed* the differentiators (e.g. per-process energy in exports, workload correlation via an optional `Profiler.mark()`).

## Explicit non-goals (scope discipline)
- **Stay a terminal `*top`** — no menu-bar app, no web UI.
- **Silicon-focused** — we instrument the *chip*, not the whole box; Tier-3 system metrics are parity-only.
- Not a capture/replay oscilloscope (that was the abandoned `siliscope` direction) — `actop` is a live monitor.

## Update the comparison table
Add rows to README `## Where agtop fits` for the white-space metrics so the table reads
as "things **only actop** has": **per-process power/energy**, **bandwidth % of peak**,
**throttle state**, **DVFS residency**.

---

# References (prior art)

- **[plasma-umass/scalene](https://github.com/plasma-umass/scalene)** (13.5k★) — Python CPU+GPU+memory+**energy** profiler; bar for per-process energy reporting (feature #1, #5).
- **macOS "Energy Impact"** (Activity Monitor) + `task_power_info` / `proc_pid_rusage` — the per-process energy precedent and the API to read it (#1).
- **[jetperch/pyjoulescope_ui](https://github.com/jetperch/pyjoulescope_ui)** (106★) — power/energy UX, marker stats; reference for presenting watts/energy (#1, #2).
- **Peers / coverage benchmarks**: [Atoptool/atop], [aristocratos/btop], [Syllo/nvtop] (now Apple-aware), macmon, mactop, silitop — for parity scope (Tier 3) and positioning.
- **[google/perfetto](https://github.com/google/perfetto)** + **NVTX / torch.profiler** — marks/annotations model, *if* the optional `Profiler.mark()` workload-correlation is pursued.

# Suggested overall order
1. **Rename to `actop`** (Part A) — clears install friction + sets the brand.
2. Ship **Tier 1** (#1–#3) under the new name as the launch story ("the `*top` that shows what others don't").
3. Then **Tier 2** (#4–#5); **Tier 3** only as parity demand arises.
