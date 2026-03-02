"""Textual TUI application for agtop."""

import os
import re
import threading

from textual.app import App, ComposeResult
from textual import work
from textual.widgets import DataTable, Footer, Header, Input

from agtop.api import Monitor
from agtop.config import create_dashboard_config
from agtop.tui.widgets import HardwareDashboard, MetricsUpdated
from agtop.utils import get_ram_metrics_dict, get_soc_info, get_top_processes

SORT_CPU = "cpu"
SORT_MEMORY = "memory"
SORT_PID = "pid"
SORT_LABELS = {SORT_CPU: "CPU%", SORT_MEMORY: "RSS", SORT_PID: "PID"}

_SORT_CYCLE = [SORT_CPU, SORT_MEMORY, SORT_PID]


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


def _shorten_process_command(command, max_len=30):
    """Truncate a process command string with ellipsis if too long."""
    if command is None:
        return "?"
    command = str(command).strip()
    if not command:
        return "?"
    if len(command) <= max_len:
        return command
    return command[: max_len - 3] + "..."


def _process_display_name(command, max_len=24):
    """Extract a short display name from a process command string."""
    command = str(command or "").strip()
    if not command:
        return "?"
    app_match = re.search(r"([^/]+)\.app(?:/| |$)", command)
    if app_match:
        return _shorten_process_command(app_match.group(1), max_len=max_len)
    executable = command.split(" ", 1)[0]
    executable_name = os.path.basename(executable) or executable
    return _shorten_process_command(executable_name, max_len=max_len)


class AgtopApp(App):
    DEFAULT_CSS = """
    AgtopApp {
        layout: vertical;
    }
    HardwareDashboard {
        height: auto;
        layout: vertical;
        border: round $accent;
        padding: 0 1;
    }
    .metric-label {
        height: 1;
        color: $text-muted;
    }
    .metric-chart {
        height: 3;
        margin-bottom: 1;
    }
    .metric-pair {
        height: auto;
        layout: horizontal;
        margin-bottom: 1;
    }
    .metric-col {
        width: 1fr;
        layout: vertical;
        height: auto;
    }
    .metric-col .metric-chart {
        margin-bottom: 0;
    }
    .status-line {
        height: 1;
        color: $text-muted;
    }
    .core-row {
        height: auto;
    }
    #process-table {
        height: 1fr;
        border: round $accent;
    }
    """
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("p", "toggle_pause", "Pause"),
        ("s", "cycle_sort", "Sort"),
        ("space", "toggle_dashboard", "Collapse HW"),
        ("/", "toggle_filter", "Filter"),
    ]

    def __init__(self, args) -> None:
        super().__init__()
        self._config = create_dashboard_config(args, get_soc_info())
        self._stop_polling = threading.Event()
        self._sort_mode = SORT_CPU
        self._filter_regex = self._config.process_filter_pattern
        self._last_processes = {"cpu": [], "memory": []}

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield HardwareDashboard(config=self._config, id="hardware-dash")
        yield DataTable(id="process-table", zebra_stripes=True, cursor_type="row")
        filter_input = Input(placeholder="Regex filter...", id="filter-input")
        filter_input.display = False
        yield filter_input
        yield Footer()

    def on_mount(self) -> None:
        self._refresh_process_table()  # initialises columns without advancing sort
        self.poll_metrics()

    @work(thread=True, exclusive=True)
    def poll_metrics(self) -> None:
        monitor = Monitor(self._config.sample_interval, self._config.subsamples)
        try:
            while not self._stop_polling.is_set():
                snapshot = monitor.get_snapshot()
                ram = get_ram_metrics_dict()
                processes = get_top_processes(
                    limit=self._config.process_display_count,
                    proc_filter=self._filter_regex,
                )
                self.post_message(MetricsUpdated(snapshot, ram, processes))
        finally:
            monitor.close()

    def on_unmount(self) -> None:
        self._stop_polling.set()

    def on_metrics_updated(self, message: MetricsUpdated) -> None:
        self.query_one("#hardware-dash", HardwareDashboard).update_metrics(message)
        self._last_processes = message.processes
        self._refresh_process_table()

    def action_toggle_pause(self) -> None:
        if self._stop_polling.is_set():
            self._stop_polling.clear()
            self.poll_metrics()
        else:
            self._stop_polling.set()

    def action_cycle_sort(self) -> None:
        idx = (_SORT_CYCLE.index(self._sort_mode) + 1) % len(_SORT_CYCLE)
        self._sort_mode = _SORT_CYCLE[idx]
        self._refresh_process_table()

    def action_toggle_dashboard(self) -> None:
        dash = self.query_one("#hardware-dash", HardwareDashboard)
        dash.display = not dash.display

    def action_toggle_filter(self) -> None:
        inp = self.query_one("#filter-input", Input)
        if inp.display:
            inp.display = False
            self.set_focus(self.query_one("#process-table", DataTable))
        else:
            inp.display = True
            inp.focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "filter-input":
            val = event.value.strip()
            if val:
                try:
                    self._filter_regex = re.compile(val, re.IGNORECASE)
                except re.error:
                    pass
            else:
                self._filter_regex = self._config.process_filter_pattern
            event.input.display = False
            self.set_focus(self.query_one("#process-table", DataTable))
            # _filter_regex is read by the polling loop on each iteration;
            # no need to restart the worker.

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "filter-input":
            val = event.value.strip()
            if val:
                try:
                    self._filter_regex = re.compile(val, re.IGNORECASE)
                except re.error:
                    pass
            else:
                self._filter_regex = self._config.process_filter_pattern

    def _refresh_process_table(self) -> None:
        try:
            table = self.query_one("#process-table", DataTable)
        except Exception:
            return

        # Update columns
        table.clear(columns=True)
        cols = ["PID", "Command", "CPU%", "MEM (MB)", "Threads"]
        if self._sort_mode == SORT_PID:
            cols[0] = "*PID"
        elif self._sort_mode == SORT_CPU:
            cols[2] = "*CPU%"
        elif self._sort_mode == SORT_MEMORY:
            cols[3] = "*MEM (MB)"
        table.add_columns(*cols)

        sorted_procs = sort_processes(
            self._last_processes, self._sort_mode, self._config.process_display_count
        )
        for proc in sorted_procs:
            table.add_row(
                str(proc.get("pid", "")),
                _process_display_name(proc.get("command", ""), max_len=28),
                "{:.1f}".format(proc.get("cpu_percent", 0.0) or 0.0),
                "{:.1f}".format(proc.get("rss_mb", 0.0) or 0.0),
                str(proc.get("num_threads", "")),
            )
