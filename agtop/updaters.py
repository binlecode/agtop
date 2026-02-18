"""Metric computation and widget update functions for the dashboard."""

import os
import re

import psutil

from .input import (
    SORT_CPU,
    SORT_MEMORY,
    SORT_PID,
    SORT_LABELS,
)
from .power_scaling import (
    DEFAULT_CPU_FLOOR_W,
    DEFAULT_GPU_FLOOR_W,
    clamp_percent,
    power_to_percent,
)


# --- Promoted helpers (private, module-level) ---


def _get_avg(values):
    """Return the arithmetic mean of a non-empty sequence."""
    return sum(values) / len(values)


def _get_metric_gbps(metric_map, metric_key, sample_interval):
    """Extract a bandwidth metric in GB/s from the raw sample dict."""
    if not isinstance(metric_map, dict):
        return 0.0
    try:
        metric_value = float(metric_map.get(metric_key, 0.0))
    except (TypeError, ValueError):
        return 0.0
    if metric_value < 0:
        return 0.0
    return metric_value / sample_interval


def _bandwidth_percent(value_gbps, reference_gbps):
    """Convert a bandwidth value to a percentage of the reference."""
    if reference_gbps <= 0:
        return 0
    return clamp_percent(value_gbps / reference_gbps * 100)


def _core_usage(system_core_usage, cpu_index, fallback_value):
    """Get core usage from psutil per-CPU list, falling back to IOReport value."""
    if (
        isinstance(cpu_index, int)
        and cpu_index >= 0
        and cpu_index < len(system_core_usage)
    ):
        return clamp_percent(system_core_usage[cpu_index])
    return clamp_percent(fallback_value)


def _update_sustained_counter(counter, is_active):
    """Increment counter if active, reset to 0 otherwise."""
    if is_active:
        return counter + 1
    return 0


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


def get_system_core_usage():
    """Read per-CPU usage percentages from psutil."""
    try:
        percpu = psutil.cpu_percent(interval=None, percpu=True)
    except Exception:
        return []
    return [clamp_percent(value) for value in percpu]


# --- Main update functions ---


def update_metrics(
    state, sample, config, system_core_usage, ram_metrics, process_metrics
):
    """Pure computation: update state from gathered OS data.

    Returns False if the sample timestamp has not advanced (stale frame).
    Mutates *state* in place.
    """
    (
        cpu_metrics_dict,
        gpu_metrics_dict,
        thermal_pressure,
        bandwidth_metrics,
        timestamp,
        cpu_temp_c,
        gpu_temp_c,
    ) = sample

    # 1. Timestamp check
    if timestamp <= state.last_timestamp:
        return False
    state.last_timestamp = timestamp

    # 2. Thermal pressure + alert flag
    state.thermal_pressure = thermal_pressure
    state.thermal_alert = thermal_pressure not in ("Nominal", "Unknown")

    # 3. Per-core activity
    state.e_core_activity = {
        core_index: _core_usage(
            system_core_usage,
            core_index,
            cpu_metrics_dict.get("E-Cluster" + str(core_index) + "_active", 0),
        )
        for core_index in cpu_metrics_dict["e_core"]
    }
    state.p_core_activity = {
        core_index: _core_usage(
            system_core_usage,
            core_index,
            cpu_metrics_dict.get("P-Cluster" + str(core_index) + "_active", 0),
        )
        for core_index in cpu_metrics_dict["p_core"]
    }

    # 4. E-CPU/P-CPU cluster usage from per-core averages
    state.ecpu_usage = (
        int(sum(state.e_core_activity.values()) / len(state.e_core_activity))
        if state.e_core_activity
        else clamp_percent(cpu_metrics_dict["E-Cluster_active"])
    )
    state.pcpu_usage = (
        int(sum(state.p_core_activity.values()) / len(state.p_core_activity))
        if state.p_core_activity
        else clamp_percent(cpu_metrics_dict["P-Cluster_active"])
    )
    state.ecpu_usage_peak = max(state.ecpu_usage_peak, state.ecpu_usage)
    state.pcpu_usage_peak = max(state.pcpu_usage_peak, state.pcpu_usage)
    state.avg_ecpu_usage_list.append(state.ecpu_usage)
    state.avg_pcpu_usage_list.append(state.pcpu_usage)

    # 5. Frequency and temperature
    state.ecpu_freq_mhz = cpu_metrics_dict["E-Cluster_freq_Mhz"]
    state.pcpu_freq_mhz = cpu_metrics_dict["P-Cluster_freq_Mhz"]
    state.gpu_freq_mhz = gpu_metrics_dict["freq_MHz"]
    state.cpu_temp_c = cpu_temp_c
    state.gpu_temp_c = gpu_temp_c

    # 6. GPU usage, peak, averaging
    state.gpu_usage = gpu_metrics_dict["active"]
    state.gpu_usage_peak = max(state.gpu_usage_peak, state.gpu_usage)
    state.avg_gpu_usage_list.append(state.gpu_usage)

    # 7. ANE usage
    state.ane_power_w = cpu_metrics_dict["ane_W"] / config.sample_interval
    state.ane_util_percent = clamp_percent(
        cpu_metrics_dict["ane_W"] / config.sample_interval / config.ane_max_power * 100
    )
    state.ane_usage_peak = max(state.ane_usage_peak, state.ane_util_percent)
    state.avg_ane_usage_list.append(state.ane_util_percent)

    # 8. RAM metrics
    state.ram_metrics_dict = ram_metrics
    state.ram_used_percent = clamp_percent(ram_metrics["used_percent"])
    state.ram_usage_peak = max(state.ram_usage_peak, state.ram_used_percent)
    state.avg_ram_usage_list.append(state.ram_used_percent)
    state.swap_used_history.append(
        max(0.0, float(ram_metrics.get("swap_used_GB", 0.0) or 0.0))
    )

    # 9. Per-core history buffer appends (only when cores are displayed)
    if config.show_cores:
        for core_count, i in enumerate(cpu_metrics_dict["e_core"]):
            if core_count < len(state.e_core_history_buffers):
                core_active = state.e_core_activity.get(
                    i, cpu_metrics_dict.get("E-Cluster" + str(i) + "_active", 0)
                )
                state.e_core_history_buffers[core_count].append(core_active)
        for core_count, i in enumerate(cpu_metrics_dict["p_core"]):
            if core_count < len(state.p_core_history_buffers):
                core_active = state.p_core_activity.get(
                    i, cpu_metrics_dict.get("P-Cluster" + str(i) + "_active", 0)
                )
                state.p_core_history_buffers[core_count].append(core_active)

    # 10. Process list + row percent computation
    state.cpu_processes = process_metrics.get("cpu", [])
    process_rows_percents = [None]
    for proc in state.cpu_processes[: config.process_display_count]:
        cpu_pct = max(0.0, float(proc.get("cpu_percent", 0.0) or 0.0))
        process_rows_percents.append(cpu_pct)
    if len(process_rows_percents) == 1:
        process_rows_percents.append(None)
    state.process_row_percents = process_rows_percents

    # 11. Bandwidth channels + totals, sustained counter
    state.bandwidth_available = bool(
        isinstance(bandwidth_metrics, dict)
        and bandwidth_metrics.get("_available", False)
    )
    if state.bandwidth_available:
        ecpu_read = _get_metric_gbps(
            bandwidth_metrics, "ECPU DCS RD", config.sample_interval
        )
        ecpu_write = _get_metric_gbps(
            bandwidth_metrics, "ECPU DCS WR", config.sample_interval
        )
        state.ecpu_bw_gbps = ecpu_read + ecpu_write
        state.ecpu_bw_percent = _bandwidth_percent(
            state.ecpu_bw_gbps, config.max_cpu_bw
        )

        pcpu_read = _get_metric_gbps(
            bandwidth_metrics, "PCPU DCS RD", config.sample_interval
        )
        pcpu_write = _get_metric_gbps(
            bandwidth_metrics, "PCPU DCS WR", config.sample_interval
        )
        state.pcpu_bw_gbps = pcpu_read + pcpu_write
        state.pcpu_bw_percent = _bandwidth_percent(
            state.pcpu_bw_gbps, config.max_cpu_bw
        )

        gpu_read = _get_metric_gbps(
            bandwidth_metrics, "GFX DCS RD", config.sample_interval
        )
        gpu_write = _get_metric_gbps(
            bandwidth_metrics, "GFX DCS WR", config.sample_interval
        )
        state.gpu_bw_gbps = gpu_read + gpu_write
        state.gpu_bw_percent = _bandwidth_percent(state.gpu_bw_gbps, config.max_gpu_bw)

        state.media_bw_gbps = _get_metric_gbps(
            bandwidth_metrics, "MEDIA DCS", config.sample_interval
        )
        state.media_bw_percent = _bandwidth_percent(
            state.media_bw_gbps, config.max_media_bw
        )

        state.total_bw_read_gbps = _get_metric_gbps(
            bandwidth_metrics, "DCS RD", config.sample_interval
        )
        state.total_bw_write_gbps = _get_metric_gbps(
            bandwidth_metrics, "DCS WR", config.sample_interval
        )
        state.total_bw_gbps = state.total_bw_read_gbps + state.total_bw_write_gbps
    else:
        state.ecpu_bw_gbps = 0.0
        state.pcpu_bw_gbps = 0.0
        state.gpu_bw_gbps = 0.0
        state.media_bw_gbps = 0.0
        state.ecpu_bw_percent = 0
        state.pcpu_bw_percent = 0
        state.gpu_bw_percent = 0
        state.media_bw_percent = 0
        state.total_bw_read_gbps = 0.0
        state.total_bw_write_gbps = 0.0
        state.total_bw_gbps = 0.0

    peak_bw_percent = max(
        state.ecpu_bw_percent,
        state.pcpu_bw_percent,
        state.gpu_bw_percent,
        state.media_bw_percent,
    )
    state.high_bw_counter = _update_sustained_counter(
        state.high_bw_counter,
        state.bandwidth_available and peak_bw_percent >= config.alert_bw_sat_percent,
    )
    state.bandwidth_alert = state.high_bw_counter >= config.alert_sustain_samples

    # 12. Power: cpu/gpu/package watts, peaks, percents, averages
    state.cpu_power_w = cpu_metrics_dict["cpu_W"] / config.sample_interval
    state.cpu_peak_power = max(state.cpu_peak_power, state.cpu_power_w)
    state.cpu_power_percent = power_to_percent(
        power_w=state.cpu_power_w,
        mode=config.power_scale,
        profile_ref_w=config.cpu_chart_ref_w,
        peak_w=state.cpu_peak_power,
        floor_w=DEFAULT_CPU_FLOOR_W,
    )
    state.avg_cpu_power_list.append(state.cpu_power_w)
    state.avg_cpu_power = _get_avg(state.avg_cpu_power_list)

    state.gpu_power_w = cpu_metrics_dict["gpu_W"] / config.sample_interval
    state.gpu_peak_power = max(state.gpu_peak_power, state.gpu_power_w)
    state.gpu_power_percent = power_to_percent(
        power_w=state.gpu_power_w,
        mode=config.power_scale,
        profile_ref_w=config.gpu_chart_ref_w,
        peak_w=state.gpu_peak_power,
        floor_w=DEFAULT_GPU_FLOOR_W,
    )
    state.avg_gpu_power_list.append(state.gpu_power_w)
    state.avg_gpu_power = _get_avg(state.avg_gpu_power_list)

    state.package_power_w = cpu_metrics_dict["package_W"] / config.sample_interval
    state.package_peak_power = max(state.package_peak_power, state.package_power_w)
    state.package_power_percent = clamp_percent(
        state.package_power_w / config.package_ref_w * 100
    )
    state.avg_package_power_list.append(state.package_power_w)
    state.avg_package_power = _get_avg(state.avg_package_power_list)

    state.high_package_power_counter = _update_sustained_counter(
        state.high_package_power_counter,
        state.package_power_percent >= config.alert_package_power_percent,
    )
    state.package_power_alert = (
        state.high_package_power_counter >= config.alert_sustain_samples
    )

    # Swap alert
    swap_history_points = config.alert_sustain_samples + 1
    swap_rise_gb = (
        max(0.0, state.swap_used_history[-1] - state.swap_used_history[0])
        if len(state.swap_used_history) > 1
        else 0.0
    )
    state.swap_alert = (
        ram_metrics.get("swap_total_GB", 0.0) >= 0.1
        and len(state.swap_used_history) >= swap_history_points
        and swap_rise_gb >= config.alert_swap_rise_gb
    )

    # 13. All alert flags + alerts_label string
    active_alerts = []
    if state.thermal_alert:
        active_alerts.append("THERMAL")
    if state.bandwidth_alert:
        active_alerts.append("BW>{}%".format(config.alert_bw_sat_percent))
    if state.swap_alert:
        active_alerts.append("SWAP+{0:.1f}G".format(swap_rise_gb))
    if state.package_power_alert:
        active_alerts.append("PKG>{}%".format(config.alert_package_power_percent))
    state.alerts_label = ", ".join(active_alerts) if active_alerts else "none"

    return True


def update_process_panel(state, widgets, config, interactive=None):
    """Update only the process list text and panel title from current state."""
    process_list = widgets["process_list"]
    if interactive is not None and interactive.sort_mode == SORT_MEMORY:
        process_rows = ["  PID NAME                      CPU%   *RSS"]
    elif interactive is not None and interactive.sort_mode == SORT_PID:
        process_rows = [" *PID NAME                      CPU%    RSS"]
    else:
        process_rows = ["  PID NAME                     *CPU%    RSS"]
    for proc in state.cpu_processes[: config.process_display_count]:
        cpu_pct = max(0.0, float(proc.get("cpu_percent", 0.0) or 0.0))
        process_rows.append(
            "{:>5} {:<24} {:>5.1f}% {:>5.1f}M".format(
                proc.get("pid", "?"),
                _process_display_name(proc.get("command")),
                cpu_pct,
                max(0.0, float(proc.get("rss_mb", 0.0) or 0.0)),
            )
        )
    if len(process_rows) == 1:
        process_rows.append("(no matching processes)")
    process_list.text = "\n".join(process_rows)
    if hasattr(process_list, "line_percents"):
        process_list.line_percents = state.process_row_percents

    process_panel = widgets["process_panel"]
    title_parts = []
    if interactive is not None and interactive.sort_mode != SORT_CPU:
        title_parts.append("sort: {}".format(SORT_LABELS[interactive.sort_mode]))
    if config.proc_filter_raw:
        filter_label = _shorten_process_command(config.proc_filter_raw, max_len=28)
        title_parts.append("filter: {}".format(filter_label))
    if title_parts:
        if not state.cpu_processes and config.proc_filter_raw:
            process_panel.title = "Processes: no match ({})".format(
                ", ".join(title_parts)
            )
        else:
            process_panel.title = "Processes ({})".format(", ".join(title_parts))
    else:
        process_panel.title = "Processes (PID command CPU% RSS)"


def update_widgets(state, widgets, config, interactive=None):
    """Write computed state values into widget objects. No computation."""
    cpu_temp_suffix = (
        " ({0:.0f}\u00b0C)".format(state.cpu_temp_c) if state.cpu_temp_c > 0 else ""
    )
    gpu_temp_suffix = (
        " ({0:.0f}\u00b0C)".format(state.gpu_temp_c) if state.gpu_temp_c > 0 else ""
    )

    # E-CPU gauge + chart
    cpu1_gauge = widgets["cpu1_gauge"]
    cpu1_gauge.title = "".join(
        [
            "E-CPU ",
            str(state.ecpu_usage),
            "% @",
            str(state.ecpu_freq_mhz),
            "MHz",
            cpu_temp_suffix,
        ]
    )
    cpu1_gauge.value = state.ecpu_usage

    ecpu_usage_chart = widgets["ecpu_usage_chart"]
    ecpu_usage_chart.title = "".join(
        [
            "E-CPU ",
            str(state.ecpu_usage),
            "% avg:",
            "{0:.1f}".format(_get_avg(state.avg_ecpu_usage_list)),
            " pk:",
            str(state.ecpu_usage_peak),
            "%",
        ]
    )
    ecpu_usage_chart.append(state.ecpu_usage)

    # P-CPU gauge + chart
    cpu2_gauge = widgets["cpu2_gauge"]
    cpu2_gauge.title = "".join(
        [
            "P-CPU ",
            str(state.pcpu_usage),
            "% @",
            str(state.pcpu_freq_mhz),
            "MHz",
            cpu_temp_suffix,
        ]
    )
    cpu2_gauge.value = state.pcpu_usage

    pcpu_usage_chart = widgets["pcpu_usage_chart"]
    pcpu_usage_chart.title = "".join(
        [
            "P-CPU ",
            str(state.pcpu_usage),
            "% avg:",
            "{0:.1f}".format(_get_avg(state.avg_pcpu_usage_list)),
            " pk:",
            str(state.pcpu_usage_peak),
            "%",
        ]
    )
    pcpu_usage_chart.append(state.pcpu_usage)

    # Per-core gauges and history charts
    if config.show_cores:
        e_core_gauges = widgets["e_core_gauges"]
        e_core_history_charts = widgets["e_core_history_charts"]
        # Iterate in insertion order (matches the sample's e_core list order)
        for core_count, i in enumerate(state.e_core_activity):
            core_active = state.e_core_activity.get(i, 0)
            if core_count < len(e_core_gauges):
                gauge = e_core_gauges[core_count]
                gauge.title = "".join(
                    [
                        "Core-" + str(i + 1) + " ",
                        str(core_active),
                        "%",
                    ]
                )
                gauge.value = core_active
            if core_count < len(e_core_history_charts):
                chart = e_core_history_charts[core_count]
                chart.title = "".join(
                    [
                        "E",
                        str(i + 1),
                        " ",
                        str(core_active),
                        "%",
                    ]
                )
                chart.append(core_active)

        p_core_gauges = widgets["p_core_gauges"]
        p_core_history_charts = widgets["p_core_history_charts"]
        for core_count, i in enumerate(state.p_core_activity):
            core_active = state.p_core_activity.get(i, 0)
            if core_count < len(p_core_gauges):
                gauge = p_core_gauges[core_count]
                gauge.title = "".join(
                    [
                        ("Core-" if config.p_core_count < 6 else "C-")
                        + str(i + 1)
                        + " ",
                        str(core_active),
                        "%",
                    ]
                )
                gauge.value = core_active
            if core_count < len(p_core_history_charts):
                chart = p_core_history_charts[core_count]
                chart.title = "".join(
                    [
                        "P",
                        str(i + 1),
                        " ",
                        str(core_active),
                        "%",
                    ]
                )
                chart.append(core_active)

    # GPU gauge + chart
    gpu_gauge = widgets["gpu_gauge"]
    gpu_gauge.title = "".join(
        [
            "GPU ",
            str(state.gpu_usage),
            "% @",
            str(state.gpu_freq_mhz),
            "MHz",
            gpu_temp_suffix,
        ]
    )
    gpu_gauge.value = state.gpu_usage

    gpu_usage_chart = widgets["gpu_usage_chart"]
    gpu_usage_chart.title = "".join(
        [
            "GPU ",
            str(state.gpu_usage),
            "% avg:",
            "{0:.1f}".format(_get_avg(state.avg_gpu_usage_list)),
            " pk:",
            str(state.gpu_usage_peak),
            "%",
        ]
    )
    gpu_usage_chart.append(state.gpu_usage)

    # ANE gauge + chart
    ane_gauge = widgets["ane_gauge"]
    ane_gauge.title = "".join(
        [
            "ANE ",
            str(state.ane_util_percent),
            "% @",
            "{0:.1f}".format(state.ane_power_w),
            "W",
        ]
    )
    ane_gauge.value = state.ane_util_percent

    ane_usage_chart = widgets["ane_usage_chart"]
    ane_usage_chart.title = "".join(
        [
            "ANE ",
            str(state.ane_util_percent),
            "% avg:",
            "{0:.1f}".format(_get_avg(state.avg_ane_usage_list)),
            " pk:",
            str(state.ane_usage_peak),
            "%",
        ]
    )
    ane_usage_chart.append(state.ane_util_percent)

    # RAM gauge + chart
    ram_gauge = widgets["ram_gauge"]
    ram = state.ram_metrics_dict
    if ram.get("swap_total_GB", 0.0) < 0.1:
        ram_gauge.title = "".join(
            [
                "RAM ",
                str(ram["used_GB"]),
                "/",
                str(ram["total_GB"]),
                "GB",
            ]
        )
    else:
        ram_gauge.title = "".join(
            [
                "RAM ",
                str(ram["used_GB"]),
                "/",
                str(ram["total_GB"]),
                "GB sw:",
                str(ram["swap_used_GB"]),
                "/",
                str(ram["swap_total_GB"]),
                "GB",
            ]
        )
    ram_gauge.value = ram["used_percent"]

    ram_usage_chart = widgets["ram_usage_chart"]
    ram_usage_chart.title = "".join(
        [
            "RAM ",
            str(state.ram_used_percent),
            "% avg:",
            "{0:.1f}".format(_get_avg(state.avg_ram_usage_list)),
            " pk:",
            str(state.ram_usage_peak),
            "%",
        ]
    )
    ram_usage_chart.append(state.ram_used_percent)

    update_process_panel(state, widgets, config, interactive)

    # Bandwidth gauges
    ecpu_bw_gauge = widgets["ecpu_bw_gauge"]
    pcpu_bw_gauge = widgets["pcpu_bw_gauge"]
    gpu_bw_gauge = widgets["gpu_bw_gauge"]
    media_bw_gauge = widgets["media_bw_gauge"]
    memory_bandwidth_panel = widgets["memory_bandwidth_panel"]

    if state.bandwidth_available:
        ecpu_bw_gauge.title = "".join(
            [
                "E-CPU B/W: ",
                "{0:.1f}".format(state.ecpu_bw_gbps),
                " GB/s (",
                str(state.ecpu_bw_percent),
                "%)",
            ]
        )
        ecpu_bw_gauge.value = state.ecpu_bw_percent

        pcpu_bw_gauge.title = "".join(
            [
                "P-CPU B/W: ",
                "{0:.1f}".format(state.pcpu_bw_gbps),
                " GB/s (",
                str(state.pcpu_bw_percent),
                "%)",
            ]
        )
        pcpu_bw_gauge.value = state.pcpu_bw_percent

        gpu_bw_gauge.title = "".join(
            [
                "GPU B/W: ",
                "{0:.1f}".format(state.gpu_bw_gbps),
                " GB/s (",
                str(state.gpu_bw_percent),
                "%)",
            ]
        )
        gpu_bw_gauge.value = state.gpu_bw_percent

        media_bw_gauge.title = "".join(
            [
                "Media B/W: ",
                "{0:.1f}".format(state.media_bw_gbps),
                " GB/s (",
                str(state.media_bw_percent),
                "%)",
            ]
        )
        media_bw_gauge.value = state.media_bw_percent

        memory_bandwidth_panel.title = "".join(
            [
                "Memory Bandwidth: ",
                "{0:.2f}".format(state.total_bw_gbps),
                " GB/s (R:",
                "{0:.2f}".format(state.total_bw_read_gbps),
                "/W:",
                "{0:.2f}".format(state.total_bw_write_gbps),
                ")",
            ]
        )
    else:
        ecpu_bw_gauge.title = "E-CPU B/W: N/A"
        pcpu_bw_gauge.title = "P-CPU B/W: N/A"
        gpu_bw_gauge.title = "GPU B/W: N/A"
        media_bw_gauge.title = "Media B/W: N/A"
        ecpu_bw_gauge.value = 0
        pcpu_bw_gauge.value = 0
        gpu_bw_gauge.value = 0
        media_bw_gauge.value = 0
        memory_bandwidth_panel.title = "Memory Bandwidth: N/A (counters unavailable)"

    # Power charts
    cpu_power_chart = widgets["cpu_power_chart"]
    cpu_power_chart.title = "".join(
        [
            "CPU: ",
            "{0:.2f}".format(state.cpu_power_w),
            "W (avg: ",
            "{0:.2f}".format(state.avg_cpu_power),
            "W peak: ",
            "{0:.2f}".format(state.cpu_peak_power),
            "W)",
        ]
    )
    cpu_power_chart.append(state.cpu_power_percent)

    gpu_power_chart = widgets["gpu_power_chart"]
    gpu_power_chart.title = "".join(
        [
            "GPU: ",
            "{0:.2f}".format(state.gpu_power_w),
            "W (avg: ",
            "{0:.2f}".format(state.avg_gpu_power),
            "W peak: ",
            "{0:.2f}".format(state.gpu_peak_power),
            "W)",
        ]
    )
    gpu_power_chart.append(state.gpu_power_percent)

    power_charts = widgets["power_charts"]
    power_charts.title = "".join(
        [
            "CPU+GPU+ANE Power: ",
            "{0:.2f}".format(state.package_power_w),
            "W (avg: ",
            "{0:.2f}".format(state.avg_package_power),
            "W peak: ",
            "{0:.2f}".format(state.package_peak_power),
            "W) thermal: ",
            state.thermal_pressure,
            " alerts: ",
            state.alerts_label,
        ]
    )


def apply_dynamic_colors(state, widgets, config, color_for_fn):
    """Apply dynamic color values to widgets based on current state.

    Separated so the caller can catch exceptions and fall back to static colors.
    """
    widgets["cpu1_gauge"].color = color_for_fn(state.ecpu_usage)
    widgets["cpu2_gauge"].color = color_for_fn(state.pcpu_usage)
    widgets["gpu_gauge"].color = color_for_fn(state.gpu_usage)
    widgets["ane_gauge"].color = color_for_fn(state.ane_util_percent)
    widgets["ecpu_usage_chart"].color = color_for_fn(state.ecpu_usage)
    widgets["pcpu_usage_chart"].color = color_for_fn(state.pcpu_usage)
    widgets["gpu_usage_chart"].color = color_for_fn(state.gpu_usage)
    widgets["ane_usage_chart"].color = color_for_fn(state.ane_util_percent)
    widgets["ram_gauge"].color = color_for_fn(state.ram_metrics_dict["used_percent"])
    widgets["ram_usage_chart"].color = color_for_fn(state.ram_used_percent)
    widgets["ecpu_bw_gauge"].color = color_for_fn(state.ecpu_bw_percent)
    widgets["pcpu_bw_gauge"].color = color_for_fn(state.pcpu_bw_percent)
    widgets["gpu_bw_gauge"].color = color_for_fn(state.gpu_bw_percent)
    widgets["media_bw_gauge"].color = color_for_fn(state.media_bw_percent)
    widgets["cpu_power_chart"].color = color_for_fn(state.cpu_power_percent)
    widgets["gpu_power_chart"].color = color_for_fn(state.gpu_power_percent)

    top_process_cpu = (
        max(0.0, float(state.cpu_processes[0].get("cpu_percent", 0.0) or 0.0))
        if state.cpu_processes
        else 0.0
    )
    widgets["process_list"].color = color_for_fn(top_process_cpu)
    widgets["process_list"].border_color = None

    e_core_gauges = widgets["e_core_gauges"]
    p_core_gauges = widgets["p_core_gauges"]
    for gauge in e_core_gauges + p_core_gauges:
        gauge.color = color_for_fn(gauge.value)
        if gauge in p_core_gauges:
            gauge.border_color = None
        else:
            gauge.border_color = gauge.color

    for idx, chart in enumerate(widgets["e_core_history_charts"]):
        history_val = (
            state.e_core_history_buffers[idx][-1]
            if state.e_core_history_buffers[idx]
            else 0
        )
        chart.color = color_for_fn(history_val)

    for idx, chart in enumerate(widgets["p_core_history_charts"]):
        history_val = (
            state.p_core_history_buffers[idx][-1]
            if state.p_core_history_buffers[idx]
            else 0
        )
        chart.color = color_for_fn(history_val)
