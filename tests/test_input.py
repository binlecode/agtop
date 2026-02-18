"""Functional tests for the interactive input module."""

import argparse

from blessed import Terminal
from blessed.keyboard import Keystroke

from agtop.input import (
    SORT_CPU,
    SORT_MEMORY,
    SORT_PID,
    InteractiveState,
    handle_keypress,
    sort_processes,
)
from agtop.state import create_dashboard_config


def _make_key(char="", name=None):
    """Build a real blessed Keystroke."""
    return Keystroke(ucs=char, code=0, name=name)


def _make_config(**overrides):
    defaults = {
        "interval": 2,
        "color": 2,
        "avg": 30,
        "show_cores": True,
        "core_view": "gauge",
        "power_scale": "profile",
        "proc_filter": "",
        "alert_bw_sat_percent": 85,
        "alert_package_power_percent": 85,
        "alert_swap_rise_gb": 0.3,
        "alert_sustain_samples": 3,
        "subsamples": 1,
    }
    defaults.update(overrides)
    soc = {
        "name": "Apple M2",
        "cpu_chart_ref_w": 30.0,
        "gpu_chart_ref_w": 20.0,
        "cpu_max_bw": 100.0,
        "gpu_max_bw": 200.0,
        "e_core_count": 4,
        "p_core_count": 4,
        "gpu_core_count": 10,
    }
    return create_dashboard_config(argparse.Namespace(**defaults), soc)


_terminal = Terminal()


# --- Sort mode keys ---


def test_key_c_sets_sort_cpu():
    interactive = InteractiveState(sort_mode=SORT_MEMORY)
    handle_keypress(_make_key("c"), interactive)
    assert interactive.sort_mode == SORT_CPU


def test_key_m_sets_sort_memory():
    interactive = InteractiveState()
    handle_keypress(_make_key("m"), interactive)
    assert interactive.sort_mode == SORT_MEMORY


def test_key_p_sets_sort_pid():
    interactive = InteractiveState()
    handle_keypress(_make_key("p"), interactive)
    assert interactive.sort_mode == SORT_PID


# --- Quit ---


def test_key_q_sets_quit():
    interactive = InteractiveState()
    handle_keypress(_make_key("q"), interactive)
    assert interactive.quit_requested is True


# --- Unrecognized keys are ignored ---


def test_unrecognized_key_is_noop():
    interactive = InteractiveState()
    handle_keypress(_make_key("x"), interactive)
    assert interactive.sort_mode == SORT_CPU
    assert interactive.quit_requested is False


def test_empty_key_is_noop():
    interactive = InteractiveState()
    handle_keypress(_make_key(""), interactive)
    assert interactive.sort_mode == SORT_CPU
    assert interactive.quit_requested is False


# --- sort_processes ---


def test_sort_processes_cpu():
    metrics = {
        "cpu": [
            {"pid": 1, "cpu_percent": 50.0},
            {"pid": 2, "cpu_percent": 30.0},
        ],
        "memory": [
            {"pid": 2, "rss_mb": 500.0},
            {"pid": 1, "rss_mb": 100.0},
        ],
    }
    result = sort_processes(metrics, SORT_CPU, 10)
    assert result[0]["pid"] == 1
    assert result[1]["pid"] == 2


def test_sort_processes_memory():
    metrics = {
        "cpu": [
            {"pid": 1, "cpu_percent": 50.0},
            {"pid": 2, "cpu_percent": 30.0},
        ],
        "memory": [
            {"pid": 2, "rss_mb": 500.0},
            {"pid": 1, "rss_mb": 100.0},
        ],
    }
    result = sort_processes(metrics, SORT_MEMORY, 10)
    assert result[0]["pid"] == 2


def test_sort_processes_pid():
    # PIDs 9 and 10 distinguish numeric from lexicographic sort:
    # lexicographic "10" < "9", numeric 9 < 10
    metrics = {
        "cpu": [
            {"pid": 100, "cpu_percent": 50.0},
            {"pid": 9, "cpu_percent": 30.0},
            {"pid": 10, "cpu_percent": 10.0},
        ],
        "memory": [],
    }
    result = sort_processes(metrics, SORT_PID, 10)
    assert [p["pid"] for p in result] == [9, 10, 100]


def test_sort_processes_pid_does_not_mutate_original():
    cpu_list = [
        {"pid": 300, "cpu_percent": 50.0},
        {"pid": 100, "cpu_percent": 30.0},
    ]
    metrics = {"cpu": cpu_list, "memory": []}
    sort_processes(metrics, SORT_PID, 10)
    # Original list should keep its original order
    assert cpu_list[0]["pid"] == 300
    assert cpu_list[1]["pid"] == 100


def test_sort_processes_respects_limit():
    metrics = {
        "cpu": [{"pid": i, "cpu_percent": float(100 - i)} for i in range(10)],
        "memory": [],
    }
    result = sort_processes(metrics, SORT_CPU, 3)
    assert len(result) == 3


def test_sort_processes_empty_metrics():
    result = sort_processes({}, SORT_CPU, 10)
    assert result == []
    result = sort_processes({"cpu": [], "memory": []}, SORT_MEMORY, 10)
    assert result == []
