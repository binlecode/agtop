---
name: run-actop
description: Launch and drive the actop TUI dashboard (Textual-based Apple Silicon performance monitor) via tmux send-keys/capture-pane. Covers the Homebrew-installed binary and the local dev .venv build, keybindings, the sampler-init ready marker, and how to confirm gauges/charts/process-table update live rather than just rendering a static frame.
---

# run-actop

actop is a Textual TUI — it takes over the terminal, so drive it inside
tmux rather than calling it directly with the Bash tool.

## Run (direct, for humans)

Homebrew install:

```bash
actop --show-processes
```

Local dev build (from repo root, uses the `.venv`):

```bash
.venv/bin/python -m actop.actop --show-processes
```

Press `q` to quit.

## Run (interactive, for agents)

Start inside a detached tmux session at a size wide enough for the
two-column layout (dashboard + process table):

```bash
tmux new-session -d -s actop_verify -x 200 -y 55 'actop --show-processes'
```

To exercise a local dev build instead of the installed binary, swap the
command: `'.venv/bin/python -m actop.actop --show-processes'` (run from
the repo root so the venv path resolves).

Poll for ready rather than a fixed sleep — sampler init takes ~2-3s and
shows a splash screen ("Initializing sampler…") until the dashboard
renders:

```bash
timeout 15 bash -c 'until tmux capture-pane -t actop_verify -p | grep -q "PWR\|E-CPU\|P-CPU"; do sleep 0.5; done'
tmux capture-pane -t actop_verify -p
```

Confirm it's actually live (not a frozen frame) — the session-energy
accumulator in the status line only increases while sampling runs:

```bash
tmux capture-pane -t actop_verify -p | grep -oE 'energy [0-9]+mWh'
sleep 6
tmux capture-pane -t actop_verify -p | grep -oE 'energy [0-9]+mWh'   # value should have increased
```

Exercise interactivity:

```bash
tmux send-keys -t actop_verify 's'   # cycle sort mode; the active sort column gets a leading *
tmux send-keys -t actop_verify 'p'   # toggle pause
tmux send-keys -t actop_verify 't'   # toggle the process table panel
tmux send-keys -t actop_verify '?'   # help overlay
tmux capture-pane -t actop_verify -p
```

Quit:

```bash
tmux send-keys -t actop_verify 'q'
tmux kill-session -t actop_verify 2>/dev/null || true
```

### Key reference

| Key | Action |
|---|---|
| `q` | Quit |
| `p` | Pause / resume sampling |
| `s` | Cycle sort mode (CPU% / PWR / Memory / PID) |
| `g` | Cycle chart glyph style (dots / block) |
| `t` | Toggle process table panel |
| `/` | Filter processes by regex |
| `?` | Help overlay |

### Useful launch flags

| Flag | Effect |
|---|---|
| `--show-processes` | Show the process table panel at startup (off by default) |
| `--no-show-residency` | Hide the per-cluster DVFS residency distribution rows (on by default) |
| `--interval N` | Display/sampling interval in seconds |
| `--power-scale {auto,profile}` | Power chart scaling mode |
| `--chart-glyph {dots,block}` | Chart glyph style |

## What "working" looks like

- No crash/traceback; the splash screen is replaced by live gauges within ~3s.
- CPU/GPU/ANE utilization, per-core panels, RAM, Mem BW, and CPU/GPU/Package power
  sparklines are populated with non-placeholder values.
- DVFS residency bars render for P-CPU/E-CPU/GPU, e.g.:
  `P-CPU  [░░░░░░░░░░░░░░░░]  idle97 low1 mid2 high0`.
- With `--show-processes`: the process table's `PWR` column is populated per row, and
  the border subtitle reads `Σ shown N.NW / pkg CPU+GPU M.MW · est CPU+GPU time share`
  (combined CPU+GPU attribution, shipped v1.2.0).
- The session-energy accumulator (`energy NmWh`) increases across successive polls.

## Notes

- Terminal size: use at least `-x 160 -y 40` — the two-column layout wraps badly
  narrower than that.
- No special environment setup, packages, or patches are needed on macOS
  (Apple Silicon) — actop is unprivileged, no sudo, no subprocess dependency.
