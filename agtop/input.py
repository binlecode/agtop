"""Interactive keyboard input handling for the dashboard."""

from dataclasses import dataclass

SORT_CPU = "cpu"
SORT_MEMORY = "memory"
SORT_PID = "pid"
SORT_LABELS = {SORT_CPU: "CPU%", SORT_MEMORY: "RSS", SORT_PID: "PID"}


@dataclass
class InteractiveState:
    """Mutable state for runtime keyboard interaction."""

    sort_mode: str = SORT_CPU
    quit_requested: bool = False


def handle_keypress(key, interactive):
    """Process a single keypress and mutate interactive state accordingly."""
    if not key:
        return

    ch = str(key)

    if ch == "q":
        interactive.quit_requested = True
    elif ch == "c":
        interactive.sort_mode = SORT_CPU
    elif ch == "m":
        interactive.sort_mode = SORT_MEMORY
    elif ch == "p":
        interactive.sort_mode = SORT_PID


def sort_processes(process_metrics, sort_mode, limit):
    """Return a sorted process list based on the active sort mode."""
    if sort_mode == SORT_MEMORY:
        return process_metrics.get("memory", [])[:limit]
    elif sort_mode == SORT_PID:
        cpu_list = list(process_metrics.get("cpu", []))
        cpu_list.sort(key=lambda proc: proc.get("pid", 0))
        return cpu_list[:limit]
    else:
        # Default: CPU sort (already sorted by get_top_processes)
        return process_metrics.get("cpu", [])[:limit]
