import time
import os
import argparse
import re
from collections import deque
import psutil
from blessed import Terminal
from dashing import VSplit, HSplit, HGauge, HChart, VGauge, Text
from .utils import (
    clear_console,
    get_top_processes,
    get_ram_metrics_dict,
    get_soc_info,
    parse_powermetrics,
    run_powermetrics_process,
)
from .color_modes import (
    COLOR_MODE_BASIC,
    COLOR_MODE_MONO,
    COLOR_MODE_TRUECOLOR,
    COLOR_MODE_256,
    detect_color_mode,
    parse_color_mode_override,
    value_to_color_index,
)
from .power_scaling import (
    DEFAULT_CPU_FLOOR_W,
    DEFAULT_GPU_FLOOR_W,
    clamp_percent,
    power_to_percent,
)


def build_parser():
    parser = argparse.ArgumentParser(
        description="agtop: Performance monitoring CLI tool for Apple Silicon"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=1,
        help="Display interval and sampling interval for powermetrics (seconds)",
    )
    parser.add_argument(
        "--color", type=int, default=2, help="Choose display color (0~8)"
    )
    parser.add_argument(
        "--avg", type=int, default=30, help="Interval for averaged values (seconds)"
    )
    parser.add_argument(
        "--show_cores", action="store_true", help="Choose show cores mode"
    )
    parser.add_argument(
        "--core-view",
        choices=["gauge", "history", "both"],
        default="gauge",
        help="Per-core rendering mode for --show_cores: gauge, history, or both",
    )
    parser.add_argument(
        "--max_count",
        type=int,
        default=0,
        help="Max show count to restart powermetrics",
    )
    parser.add_argument(
        "--power-scale",
        choices=["auto", "profile"],
        default="auto",
        help="Power chart scaling mode: auto uses rolling peak, profile uses SoC reference",
    )
    parser.add_argument(
        "--proc-filter",
        type=_validate_proc_filter,
        default="",
        help='Regex filter for process panel command names (example: "python|ollama|vllm|docker|mlx")',
    )
    return parser


def _validate_proc_filter(value):
    if value in (None, ""):
        return ""
    try:
        re.compile(value, re.IGNORECASE)
    except re.error as error:
        raise argparse.ArgumentTypeError(
            "invalid --proc-filter regex: {}".format(error)
        ) from error
    return value


def _shorten_process_command(command, max_len=30):
    if command is None:
        return "?"
    command = str(command).strip()
    if not command:
        return "?"
    if len(command) <= max_len:
        return command
    return command[: max_len - 3] + "..."


def _process_display_name(command, max_len=18):
    command = str(command or "").strip()
    if not command:
        return "?"
    executable = command.split(" ", 1)[0]
    executable_name = os.path.basename(executable) or executable
    return _shorten_process_command(executable_name, max_len=max_len)


def _terminate_powermetrics_process(process):
    if process is None:
        return
    try:
        process.terminate()
    except Exception:
        pass


def _read_powermetrics_stderr(process):
    if process is None or process.poll() is None:
        return ""
    try:
        _, stderr_data = process.communicate(timeout=0.2)
    except Exception:
        return ""
    if not stderr_data:
        return ""
    try:
        return stderr_data.decode("utf-8", errors="replace").strip()
    except Exception:
        return str(stderr_data).strip()


def _build_powermetrics_start_error(stderr_text="", returncode=None):
    stderr_lower = stderr_text.lower()
    if "powermetrics" in stderr_lower and (
        "command not found" in stderr_lower or "no such file" in stderr_lower
    ):
        message = (
            "Failed to start powermetrics: the `powermetrics` binary was not found. "
            "agtop requires macOS with powermetrics available."
        )
    elif any(
        token in stderr_lower
        for token in [
            "a password is required",
            "terminal is required",
            "no tty present",
            "not in the sudoers",
            "permission denied",
            "operation not permitted",
        ]
    ):
        message = (
            "Failed to start powermetrics due to missing sudo privileges. "
            "Run `sudo agtop` and try again."
        )
    else:
        message = "Failed to start powermetrics subprocess."
        if returncode is not None:
            message = "{} Exit code: {}.".format(message, returncode)
    if stderr_text:
        message = "{} Details: {}".format(message, stderr_text)
    return message


def _start_powermetrics_process(timecode, sample_interval):
    def _spawn(include_extra_power_info):
        return run_powermetrics_process(
            timecode,
            interval=sample_interval * 1000,
            include_extra_power_info=include_extra_power_info,
        )

    try:
        process = _spawn(include_extra_power_info=True)
    except FileNotFoundError as e:
        missing_bin = str(e).lower()
        if "powermetrics" in missing_bin:
            raise RuntimeError(
                "Failed to start powermetrics: the `powermetrics` binary was not found. "
                "agtop requires macOS with powermetrics available."
            ) from e
        raise RuntimeError(
            "Failed to start powermetrics subprocess: {}".format(e)
        ) from e
    except PermissionError as e:
        raise RuntimeError(
            "Failed to start powermetrics due to missing sudo privileges. "
            "Run `sudo agtop` and try again."
        ) from e
    except OSError as e:
        raise RuntimeError(
            "Failed to start powermetrics subprocess: {}".format(e)
        ) from e

    time.sleep(0.15)
    if process.poll() is not None:
        stderr_text = _read_powermetrics_stderr(process)
        if (
            "show-extra-power-info" in stderr_text.lower()
            and "unrecognized" in stderr_text.lower()
        ):
            try:
                process = _spawn(include_extra_power_info=False)
            except Exception:
                process = None
            if process is None:
                raise RuntimeError(_build_powermetrics_start_error(stderr_text, None))
            time.sleep(0.15)
            if process.poll() is None:
                return process
            stderr_text = _read_powermetrics_stderr(process)
        raise RuntimeError(
            _build_powermetrics_start_error(stderr_text, process.returncode)
        )
    return process


def _run_dashboard(args, runtime_state):
    terminal = Terminal()
    raw_mode_override = os.getenv("AGTOP_COLOR_MODE")
    mode_override = parse_color_mode_override(raw_mode_override)
    normalized_raw_mode = (
        raw_mode_override.strip().lower() if raw_mode_override is not None else ""
    )
    if (
        raw_mode_override is not None
        and mode_override is None
        and normalized_raw_mode not in {"", "auto"}
    ):
        print(
            "Warning: invalid AGTOP_COLOR_MODE={!r}; using auto detection.".format(
                raw_mode_override
            )
        )
    color_mode = mode_override or detect_color_mode(os.environ, terminal)
    dynamic_color_enabled = color_mode in {
        COLOR_MODE_BASIC,
        COLOR_MODE_256,
        COLOR_MODE_TRUECOLOR,
    }
    gradient_override = os.getenv("AGTOP_EXPERIMENTAL_GRADIENT")
    if gradient_override is None:
        gradient_bars_enabled = dynamic_color_enabled
    else:
        gradient_bars_enabled = gradient_override.strip() == "1"
    GaugeClass = HGauge
    VGaugeClass = VGauge
    HChartClass = HChart
    if gradient_bars_enabled and dynamic_color_enabled:
        try:
            from .experimental_gradient import (
                GradientHGauge,
                GradientVGauge,
                GradientHChart,
            )

            GaugeClass = GradientHGauge
            VGaugeClass = GradientVGauge
            HChartClass = GradientHChart
        except Exception as e:
            print(
                "Warning: gradient renderer init failed: {}. Using default renderer.".format(
                    e
                )
            )
    base_color = 0 if color_mode == COLOR_MODE_MONO else args.color

    print("\nAGTOP - Performance monitoring CLI tool for Apple Silicon")
    print("Update with your package manager (for Homebrew: `brew upgrade agtop`)")
    print("Get help at `https://github.com/binlecode/agtop`")
    print("P.S. You are recommended to run AGTOP with `sudo agtop`\n")
    print("\n[1/3] Loading AGTOP\n")
    print("\033[?25l")
    runtime_state["cursor_hidden"] = True

    cpu1_gauge = GaugeClass(title="E-CPU Usage", val=0, color=base_color)
    cpu2_gauge = GaugeClass(title="P-CPU Usage", val=0, color=base_color)
    gpu_gauge = GaugeClass(title="GPU Usage", val=0, color=base_color)
    ane_gauge = GaugeClass(title="ANE", val=0, color=base_color)
    soc_info_dict = get_soc_info()
    sample_interval = max(1, args.interval)
    core_history_window = max(20, int(args.avg / sample_interval))
    usage_track_window = max(20, int(args.avg / sample_interval))

    ecpu_usage_chart = HChartClass(title="E-CPU Track", color=base_color)
    pcpu_usage_chart = HChartClass(title="P-CPU Track", color=base_color)
    gpu_usage_chart = HChartClass(title="GPU Track", color=base_color)
    ane_usage_chart = HChartClass(title="ANE Track", color=base_color)
    ram_usage_chart = HChartClass(title="RAM Track", color=base_color)

    e_core_count = max(0, int(soc_info_dict["e_core_count"]))
    e_core_gauges = [
        VGaugeClass(val=0, color=base_color, border_color=base_color)
        for _ in range(e_core_count)
    ]
    e_core_history_charts = [
        HChartClass(title="E{}".format(i + 1), color=base_color)
        for i in range(e_core_count)
    ]
    e_core_history_buffers = [
        deque([], maxlen=core_history_window) for _ in range(e_core_count)
    ]

    p_core_count = max(0, int(soc_info_dict["p_core_count"]))
    p_core_gauges_all = [
        VGaugeClass(val=0, color=base_color, border_color=base_color)
        for _ in range(p_core_count)
    ]
    p_core_gauges = p_core_gauges_all[:8]
    p_core_gauges_ext = p_core_gauges_all[8:]
    p_core_history_charts_all = [
        HChartClass(title="P{}".format(i + 1), color=base_color)
        for i in range(p_core_count)
    ]
    p_core_history_charts = p_core_history_charts_all[:8]
    p_core_history_charts_ext = p_core_history_charts_all[8:]
    p_core_history_buffers = [
        deque([], maxlen=core_history_window) for _ in range(p_core_count)
    ]

    p_core_gauge_split = []
    if p_core_gauges:
        p_core_gauge_split.append(HSplit(*p_core_gauges))
    if p_core_gauges_ext:
        p_core_gauge_split.append(HSplit(*p_core_gauges_ext))

    p_core_history_split = []
    if p_core_history_charts:
        p_core_history_split.append(HSplit(*p_core_history_charts))
    if p_core_history_charts_ext:
        p_core_history_split.append(HSplit(*p_core_history_charts_ext))

    show_core_gauges = args.show_cores and args.core_view in {"gauge", "both"}
    show_core_history = args.show_cores and args.core_view in {"history", "both"}

    if args.show_cores:
        processor_gauges = [HSplit(cpu1_gauge, ecpu_usage_chart)]
        if show_core_gauges and e_core_gauges:
            processor_gauges.append(HSplit(*e_core_gauges))
        if show_core_history and e_core_history_charts:
            processor_gauges.append(HSplit(*e_core_history_charts))
        processor_gauges.append(HSplit(cpu2_gauge, pcpu_usage_chart))
        if show_core_gauges:
            processor_gauges.extend(p_core_gauge_split)
        if show_core_history:
            processor_gauges.extend(p_core_history_split)
        processor_gauges.append(HSplit(gpu_gauge, gpu_usage_chart))
        processor_gauges.append(HSplit(ane_gauge, ane_usage_chart))
    else:
        processor_gauges = [
            HSplit(cpu1_gauge, ecpu_usage_chart),
            HSplit(cpu2_gauge, pcpu_usage_chart),
            HSplit(gpu_gauge, gpu_usage_chart),
            HSplit(ane_gauge, ane_usage_chart),
        ]
    processor_split = VSplit(
        *processor_gauges,
        title="Processor Utilization",
        border_color=base_color,
    )

    ram_gauge = GaugeClass(title="RAM Usage", val=0, color=base_color)
    ecpu_bw_gauge = GaugeClass(title="E-CPU B/W: N/A", val=0, color=base_color)
    pcpu_bw_gauge = GaugeClass(title="P-CPU B/W: N/A", val=0, color=base_color)
    gpu_bw_gauge = GaugeClass(title="GPU B/W: N/A", val=0, color=base_color)
    media_bw_gauge = GaugeClass(title="Media B/W: N/A", val=0, color=base_color)
    bandwidth_gauges = [ecpu_bw_gauge, pcpu_bw_gauge, gpu_bw_gauge, media_bw_gauge]
    bandwidth_rows = (
        [
            HSplit(
                ecpu_bw_gauge,
                pcpu_bw_gauge,
            ),
            HSplit(
                gpu_bw_gauge,
                media_bw_gauge,
            ),
        ]
        if args.show_cores
        else [
            HSplit(
                ecpu_bw_gauge,
                pcpu_bw_gauge,
                gpu_bw_gauge,
                media_bw_gauge,
            )
        ]
    )
    memory_bandwidth_panel = VSplit(
        *bandwidth_rows,
        border_color=base_color,
        title="Memory Bandwidth: N/A (counters unavailable)",
    )
    ram_usage_panel = HSplit(
        ram_gauge,
        ram_usage_chart,
    )
    memory_gauges = VSplit(
        ram_usage_panel,
        memory_bandwidth_panel,
        border_color=base_color,
        title="Memory",
    )

    cpu_power_chart = HChartClass(title="CPU Power", color=base_color)
    gpu_power_chart = HChartClass(title="GPU Power", color=base_color)
    power_charts = (
        VSplit(
            cpu_power_chart,
            gpu_power_chart,
            title="Power Chart",
            border_color=base_color,
        )
        if args.show_cores
        else HSplit(
            cpu_power_chart,
            gpu_power_chart,
            title="Power Chart",
            border_color=base_color,
        )
    )

    process_display_count = 8
    process_list = Text(
        "NAME                 CPU%   RSS\n(no data yet)",
        color=base_color,
        border_color=base_color,
    )
    process_panel = VSplit(
        process_list,
        border_color=base_color,
        title="Processes (top CPU)",
    )

    ui = (
        HSplit(
            processor_split,
            VSplit(
                memory_gauges,
                power_charts,
                process_panel,
            ),
        )
        if args.show_cores
        else VSplit(
            processor_split,
            memory_gauges,
            power_charts,
            process_panel,
        )
    )

    usage_gauges = ui.items[0]

    cpu_title = "".join(
        [
            soc_info_dict["name"],
            " (cores: ",
            str(soc_info_dict["e_core_count"]),
            "E+",
            str(soc_info_dict["p_core_count"]),
            "P+",
            str(soc_info_dict["gpu_core_count"]),
            "GPU)",
        ]
    )
    usage_gauges.title = cpu_title
    cpu_chart_ref_w = soc_info_dict["cpu_chart_ref_w"]
    gpu_chart_ref_w = soc_info_dict["gpu_chart_ref_w"]
    ane_max_power = 8.0
    max_cpu_bw = max(float(soc_info_dict.get("cpu_max_bw", 0.0)), 1.0)
    max_gpu_bw = max(float(soc_info_dict.get("gpu_max_bw", 0.0)), 1.0)
    max_media_bw = max(max_cpu_bw, max_gpu_bw)
    process_filter_pattern = (
        re.compile(args.proc_filter, re.IGNORECASE) if args.proc_filter else None
    )

    cpu_peak_power = 0
    gpu_peak_power = 0
    package_peak_power = 0
    ecpu_usage_peak = 0
    pcpu_usage_peak = 0
    gpu_usage_peak = 0
    ane_usage_peak = 0
    ram_usage_peak = 0

    print("\n[2/3] Starting powermetrics process\n")

    timecode = str(int(time.time()))

    powermetrics_process = _start_powermetrics_process(timecode, sample_interval)
    runtime_state["powermetrics_process"] = powermetrics_process

    print("\n[3/3] Waiting for first reading...\n")

    def get_reading(wait=0.1):
        ready = parse_powermetrics(timecode=timecode)
        while not ready:
            if powermetrics_process.poll() is not None:
                stderr_text = _read_powermetrics_stderr(powermetrics_process)
                raise RuntimeError(
                    _build_powermetrics_start_error(
                        stderr_text, powermetrics_process.returncode
                    )
                )
            time.sleep(wait)
            ready = parse_powermetrics(timecode=timecode)
        return ready

    ready = get_reading()
    last_timestamp = ready[-1]

    def get_avg(inlist):
        avg = sum(inlist) / len(inlist)
        return avg

    def get_metric_gbps(metric_map, metric_key):
        if not isinstance(metric_map, dict):
            return 0.0
        try:
            metric_value = float(metric_map.get(metric_key, 0.0))
        except (TypeError, ValueError):
            return 0.0
        if metric_value < 0:
            return 0.0
        return metric_value / sample_interval

    def bandwidth_percent(value_gbps, reference_gbps):
        if reference_gbps <= 0:
            return 0
        return clamp_percent(value_gbps / reference_gbps * 100)

    def get_system_core_usage():
        try:
            percpu = psutil.cpu_percent(interval=None, percpu=True)
        except Exception:
            return []
        return [clamp_percent(value) for value in percpu]

    avg_window = max(1, int(args.avg / sample_interval))
    avg_package_power_list = deque([], maxlen=avg_window)
    avg_cpu_power_list = deque([], maxlen=avg_window)
    avg_gpu_power_list = deque([], maxlen=avg_window)
    avg_ecpu_usage_list = deque([], maxlen=usage_track_window)
    avg_pcpu_usage_list = deque([], maxlen=usage_track_window)
    avg_gpu_usage_list = deque([], maxlen=usage_track_window)
    avg_ane_usage_list = deque([], maxlen=usage_track_window)
    avg_ram_usage_list = deque([], maxlen=usage_track_window)

    core_gauges = e_core_gauges + p_core_gauges + p_core_gauges_ext
    core_history_charts = e_core_history_charts + p_core_history_charts_all
    usage_track_charts = [
        ecpu_usage_chart,
        pcpu_usage_chart,
        gpu_usage_chart,
        ane_usage_chart,
        ram_usage_chart,
    ]

    def reset_static_colors(color_index):
        cpu1_gauge.color = color_index
        cpu2_gauge.color = color_index
        gpu_gauge.color = color_index
        ane_gauge.color = color_index
        ram_gauge.color = color_index
        for chart in usage_track_charts:
            chart.color = color_index
        for gauge in bandwidth_gauges:
            gauge.color = color_index
        cpu_power_chart.color = color_index
        gpu_power_chart.color = color_index
        processor_split.border_color = color_index
        memory_gauges.border_color = color_index
        memory_bandwidth_panel.border_color = color_index
        power_charts.border_color = color_index
        process_panel.border_color = color_index
        for gauge in core_gauges:
            gauge.color = color_index
            gauge.border_color = color_index
        for chart in core_history_charts:
            chart.color = color_index
        process_list.color = color_index
        process_list.border_color = color_index

    def color_for(percent):
        return value_to_color_index(
            percent=percent,
            mode=color_mode,
            terminal=terminal,
            seed_color=args.color,
        )

    if color_mode == COLOR_MODE_MONO:
        reset_static_colors(0)

    clear_console()
    get_system_core_usage()
    try:
        get_top_processes(
            limit=process_display_count, proc_filter=process_filter_pattern
        )
    except Exception:
        pass

    count = 0
    while True:
        if args.max_count > 0:
            if count >= args.max_count:
                count = 0
                _terminate_powermetrics_process(powermetrics_process)
                powermetrics_process = None
                runtime_state["powermetrics_process"] = None
                timecode = str(int(time.time()))
                powermetrics_process = _start_powermetrics_process(
                    timecode, sample_interval
                )
                runtime_state["powermetrics_process"] = powermetrics_process
            count += 1
        ready = parse_powermetrics(timecode=timecode)
        if not ready and powermetrics_process.poll() is not None:
            stderr_text = _read_powermetrics_stderr(powermetrics_process)
            raise RuntimeError(
                _build_powermetrics_start_error(
                    stderr_text, powermetrics_process.returncode
                )
            )
        if ready:
            (
                cpu_metrics_dict,
                gpu_metrics_dict,
                thermal_pressure,
                bandwidth_metrics,
                timestamp,
            ) = ready

            if timestamp > last_timestamp:
                last_timestamp = timestamp

                if thermal_pressure == "Nominal":
                    thermal_throttle = "no"
                else:
                    thermal_throttle = "yes"

                system_core_usage = get_system_core_usage()

                def core_usage(cpu_index, fallback_value):
                    if (
                        isinstance(cpu_index, int)
                        and cpu_index >= 0
                        and cpu_index < len(system_core_usage)
                    ):
                        return clamp_percent(system_core_usage[cpu_index])
                    return clamp_percent(fallback_value)

                e_core_activity = {
                    core_index: core_usage(
                        core_index,
                        cpu_metrics_dict.get(
                            "E-Cluster" + str(core_index) + "_active", 0
                        ),
                    )
                    for core_index in cpu_metrics_dict["e_core"]
                }
                p_core_activity = {
                    core_index: core_usage(
                        core_index,
                        cpu_metrics_dict.get(
                            "P-Cluster" + str(core_index) + "_active", 0
                        ),
                    )
                    for core_index in cpu_metrics_dict["p_core"]
                }
                ecpu_usage = (
                    int(sum(e_core_activity.values()) / len(e_core_activity))
                    if e_core_activity
                    else clamp_percent(cpu_metrics_dict["E-Cluster_active"])
                )
                pcpu_usage = (
                    int(sum(p_core_activity.values()) / len(p_core_activity))
                    if p_core_activity
                    else clamp_percent(cpu_metrics_dict["P-Cluster_active"])
                )

                cpu1_gauge.title = "".join(
                    [
                        "E-CPU Usage: ",
                        str(ecpu_usage),
                        "% @ ",
                        str(cpu_metrics_dict["E-Cluster_freq_Mhz"]),
                        " MHz",
                    ]
                )
                cpu1_gauge.value = ecpu_usage
                ecpu_usage_peak = max(ecpu_usage_peak, ecpu_usage)
                avg_ecpu_usage_list.append(ecpu_usage)
                ecpu_usage_chart.title = "".join(
                    [
                        "E-CPU Track: ",
                        str(ecpu_usage),
                        "% (avg: ",
                        "{0:.1f}".format(get_avg(avg_ecpu_usage_list)),
                        "% peak: ",
                        str(ecpu_usage_peak),
                        "%)",
                    ]
                )
                ecpu_usage_chart.append(ecpu_usage)

                cpu2_gauge.title = "".join(
                    [
                        "P-CPU Usage: ",
                        str(pcpu_usage),
                        "% @ ",
                        str(cpu_metrics_dict["P-Cluster_freq_Mhz"]),
                        " MHz",
                    ]
                )
                cpu2_gauge.value = pcpu_usage
                pcpu_usage_peak = max(pcpu_usage_peak, pcpu_usage)
                avg_pcpu_usage_list.append(pcpu_usage)
                pcpu_usage_chart.title = "".join(
                    [
                        "P-CPU Track: ",
                        str(pcpu_usage),
                        "% (avg: ",
                        "{0:.1f}".format(get_avg(avg_pcpu_usage_list)),
                        "% peak: ",
                        str(pcpu_usage_peak),
                        "%)",
                    ]
                )
                pcpu_usage_chart.append(pcpu_usage)

                if args.show_cores:
                    for core_count, i in enumerate(cpu_metrics_dict["e_core"]):
                        core_active = e_core_activity.get(
                            i, cpu_metrics_dict.get("E-Cluster" + str(i) + "_active", 0)
                        )
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
                            e_core_history_buffers[core_count].append(core_active)
                            chart.append(core_active)

                    for core_count, i in enumerate(cpu_metrics_dict["p_core"]):
                        core_active = p_core_activity.get(
                            i, cpu_metrics_dict.get("P-Cluster" + str(i) + "_active", 0)
                        )
                        if core_count < len(p_core_gauges_all):
                            gauge = p_core_gauges_all[core_count]
                            gauge.title = "".join(
                                [
                                    ("Core-" if p_core_count < 6 else "C-")
                                    + str(i + 1)
                                    + " ",
                                    str(core_active),
                                    "%",
                                ]
                            )
                            gauge.value = core_active
                        if core_count < len(p_core_history_charts_all):
                            chart = p_core_history_charts_all[core_count]
                            chart.title = "".join(
                                [
                                    "P",
                                    str(i + 1),
                                    " ",
                                    str(core_active),
                                    "%",
                                ]
                            )
                            p_core_history_buffers[core_count].append(core_active)
                            chart.append(core_active)

                gpu_gauge.title = "".join(
                    [
                        "GPU Usage: ",
                        str(gpu_metrics_dict["active"]),
                        "% @ ",
                        str(gpu_metrics_dict["freq_MHz"]),
                        " MHz",
                    ]
                )
                gpu_gauge.value = gpu_metrics_dict["active"]
                gpu_usage = gpu_metrics_dict["active"]
                gpu_usage_peak = max(gpu_usage_peak, gpu_usage)
                avg_gpu_usage_list.append(gpu_usage)
                gpu_usage_chart.title = "".join(
                    [
                        "GPU Track: ",
                        str(gpu_usage),
                        "% (avg: ",
                        "{0:.1f}".format(get_avg(avg_gpu_usage_list)),
                        "% peak: ",
                        str(gpu_usage_peak),
                        "%)",
                    ]
                )
                gpu_usage_chart.append(gpu_usage)

                ane_util_percent = clamp_percent(
                    cpu_metrics_dict["ane_W"] / sample_interval / ane_max_power * 100
                )
                ane_gauge.title = "".join(
                    [
                        "ANE Usage: ",
                        str(ane_util_percent),
                        "% @ ",
                        "{0:.1f}".format(cpu_metrics_dict["ane_W"] / sample_interval),
                        " W",
                    ]
                )
                ane_gauge.value = ane_util_percent
                ane_usage_peak = max(ane_usage_peak, ane_util_percent)
                avg_ane_usage_list.append(ane_util_percent)
                ane_usage_chart.title = "".join(
                    [
                        "ANE Track: ",
                        str(ane_util_percent),
                        "% (avg: ",
                        "{0:.1f}".format(get_avg(avg_ane_usage_list)),
                        "% peak: ",
                        str(ane_usage_peak),
                        "%)",
                    ]
                )
                ane_usage_chart.append(ane_util_percent)

                ram_metrics_dict = get_ram_metrics_dict()

                if ram_metrics_dict["swap_total_GB"] < 0.1:
                    ram_gauge.title = "".join(
                        [
                            "RAM Usage: ",
                            str(ram_metrics_dict["used_GB"]),
                            "/",
                            str(ram_metrics_dict["total_GB"]),
                            "GB - swap inactive",
                        ]
                    )
                else:
                    ram_gauge.title = "".join(
                        [
                            "RAM Usage: ",
                            str(ram_metrics_dict["used_GB"]),
                            "/",
                            str(ram_metrics_dict["total_GB"]),
                            "GB",
                            " - swap:",
                            str(ram_metrics_dict["swap_used_GB"]),
                            "/",
                            str(ram_metrics_dict["swap_total_GB"]),
                            "GB",
                        ]
                    )
                ram_gauge.value = ram_metrics_dict["free_percent"]
                ram_used_percent = clamp_percent(ram_metrics_dict["free_percent"])
                ram_usage_peak = max(ram_usage_peak, ram_used_percent)
                avg_ram_usage_list.append(ram_used_percent)
                ram_usage_chart.title = "".join(
                    [
                        "RAM Track: ",
                        str(ram_used_percent),
                        "% (avg: ",
                        "{0:.1f}".format(get_avg(avg_ram_usage_list)),
                        "% peak: ",
                        str(ram_usage_peak),
                        "%)",
                    ]
                )
                ram_usage_chart.append(ram_used_percent)

                process_metrics = {"cpu": [], "memory": []}
                try:
                    process_metrics = get_top_processes(
                        limit=process_display_count,
                        proc_filter=process_filter_pattern,
                    )
                except Exception:
                    pass
                cpu_processes = process_metrics.get("cpu", [])
                process_rows = ["NAME                 CPU%   RSS"]
                for proc in cpu_processes[:process_display_count]:
                    process_rows.append(
                        "{:<20} {:>5.1f}% {:>5.1f}M".format(
                            _process_display_name(proc.get("command")),
                            max(0.0, float(proc.get("cpu_percent", 0.0) or 0.0)),
                            max(0.0, float(proc.get("rss_mb", 0.0) or 0.0)),
                        )
                    )
                if len(process_rows) == 1:
                    process_rows.append("(no matching processes)")
                process_list.text = "\n".join(process_rows)

                if args.proc_filter:
                    filter_label = _shorten_process_command(
                        args.proc_filter, max_len=28
                    )
                    if not cpu_processes:
                        process_panel.title = "Processes: no match ({})".format(
                            filter_label
                        )
                    else:
                        process_panel.title = "Processes (filter: {})".format(
                            filter_label
                        )
                else:
                    process_panel.title = "Processes (PID command CPU% RSS)"

                bandwidth_available = bool(
                    isinstance(bandwidth_metrics, dict)
                    and bandwidth_metrics.get("_available", False)
                )
                if bandwidth_available:
                    ecpu_read_gbps = get_metric_gbps(bandwidth_metrics, "ECPU DCS RD")
                    ecpu_write_gbps = get_metric_gbps(bandwidth_metrics, "ECPU DCS WR")
                    ecpu_total_gbps = ecpu_read_gbps + ecpu_write_gbps
                    ecpu_bw_percent = bandwidth_percent(ecpu_total_gbps, max_cpu_bw)
                    ecpu_bw_gauge.title = "".join(
                        [
                            "E-CPU B/W: ",
                            "{0:.1f}".format(ecpu_total_gbps),
                            " GB/s (",
                            str(ecpu_bw_percent),
                            "%)",
                        ]
                    )
                    ecpu_bw_gauge.value = ecpu_bw_percent

                    pcpu_read_gbps = get_metric_gbps(bandwidth_metrics, "PCPU DCS RD")
                    pcpu_write_gbps = get_metric_gbps(bandwidth_metrics, "PCPU DCS WR")
                    pcpu_total_gbps = pcpu_read_gbps + pcpu_write_gbps
                    pcpu_bw_percent = bandwidth_percent(pcpu_total_gbps, max_cpu_bw)
                    pcpu_bw_gauge.title = "".join(
                        [
                            "P-CPU B/W: ",
                            "{0:.1f}".format(pcpu_total_gbps),
                            " GB/s (",
                            str(pcpu_bw_percent),
                            "%)",
                        ]
                    )
                    pcpu_bw_gauge.value = pcpu_bw_percent

                    gpu_read_gbps = get_metric_gbps(bandwidth_metrics, "GFX DCS RD")
                    gpu_write_gbps = get_metric_gbps(bandwidth_metrics, "GFX DCS WR")
                    gpu_total_gbps = gpu_read_gbps + gpu_write_gbps
                    gpu_bw_percent = bandwidth_percent(gpu_total_gbps, max_gpu_bw)
                    gpu_bw_gauge.title = "".join(
                        [
                            "GPU B/W: ",
                            "{0:.1f}".format(gpu_total_gbps),
                            " GB/s (",
                            str(gpu_bw_percent),
                            "%)",
                        ]
                    )
                    gpu_bw_gauge.value = gpu_bw_percent

                    media_total_gbps = get_metric_gbps(bandwidth_metrics, "MEDIA DCS")
                    media_bw_percent = bandwidth_percent(media_total_gbps, max_media_bw)
                    media_bw_gauge.title = "".join(
                        [
                            "Media B/W: ",
                            "{0:.1f}".format(media_total_gbps),
                            " GB/s (",
                            str(media_bw_percent),
                            "%)",
                        ]
                    )
                    media_bw_gauge.value = media_bw_percent

                    total_bw_read_gbps = get_metric_gbps(bandwidth_metrics, "DCS RD")
                    total_bw_write_gbps = get_metric_gbps(bandwidth_metrics, "DCS WR")
                    total_bw_gbps = total_bw_read_gbps + total_bw_write_gbps
                    memory_bandwidth_panel.title = "".join(
                        [
                            "Memory Bandwidth: ",
                            "{0:.2f}".format(total_bw_gbps),
                            " GB/s (R:",
                            "{0:.2f}".format(total_bw_read_gbps),
                            "/W:",
                            "{0:.2f}".format(total_bw_write_gbps),
                            ")",
                        ]
                    )
                else:
                    ecpu_bw_percent = 0
                    pcpu_bw_percent = 0
                    gpu_bw_percent = 0
                    media_bw_percent = 0
                    ecpu_bw_gauge.title = "E-CPU B/W: N/A"
                    pcpu_bw_gauge.title = "P-CPU B/W: N/A"
                    gpu_bw_gauge.title = "GPU B/W: N/A"
                    media_bw_gauge.title = "Media B/W: N/A"
                    ecpu_bw_gauge.value = 0
                    pcpu_bw_gauge.value = 0
                    gpu_bw_gauge.value = 0
                    media_bw_gauge.value = 0
                    memory_bandwidth_panel.title = (
                        "Memory Bandwidth: N/A (counters unavailable)"
                    )

                package_power_W = cpu_metrics_dict["package_W"] / sample_interval
                if package_power_W > package_peak_power:
                    package_peak_power = package_power_W
                avg_package_power_list.append(package_power_W)
                avg_package_power = get_avg(avg_package_power_list)
                power_charts.title = "".join(
                    [
                        "CPU+GPU+ANE Power: ",
                        "{0:.2f}".format(package_power_W),
                        "W (avg: ",
                        "{0:.2f}".format(avg_package_power),
                        "W peak: ",
                        "{0:.2f}".format(package_peak_power),
                        "W) throttle: ",
                        thermal_throttle,
                    ]
                )

                cpu_power_W = cpu_metrics_dict["cpu_W"] / sample_interval
                if cpu_power_W > cpu_peak_power:
                    cpu_peak_power = cpu_power_W
                cpu_power_percent = power_to_percent(
                    power_w=cpu_power_W,
                    mode=args.power_scale,
                    profile_ref_w=cpu_chart_ref_w,
                    peak_w=cpu_peak_power,
                    floor_w=DEFAULT_CPU_FLOOR_W,
                )
                avg_cpu_power_list.append(cpu_power_W)
                avg_cpu_power = get_avg(avg_cpu_power_list)
                cpu_power_chart.title = "".join(
                    [
                        "CPU: ",
                        "{0:.2f}".format(cpu_power_W),
                        "W (avg: ",
                        "{0:.2f}".format(avg_cpu_power),
                        "W peak: ",
                        "{0:.2f}".format(cpu_peak_power),
                        "W)",
                    ]
                )
                cpu_power_chart.append(cpu_power_percent)

                gpu_power_W = cpu_metrics_dict["gpu_W"] / sample_interval
                if gpu_power_W > gpu_peak_power:
                    gpu_peak_power = gpu_power_W
                gpu_power_percent = power_to_percent(
                    power_w=gpu_power_W,
                    mode=args.power_scale,
                    profile_ref_w=gpu_chart_ref_w,
                    peak_w=gpu_peak_power,
                    floor_w=DEFAULT_GPU_FLOOR_W,
                )
                avg_gpu_power_list.append(gpu_power_W)
                avg_gpu_power = get_avg(avg_gpu_power_list)
                gpu_power_chart.title = "".join(
                    [
                        "GPU: ",
                        "{0:.2f}".format(gpu_power_W),
                        "W (avg: ",
                        "{0:.2f}".format(avg_gpu_power),
                        "W peak: ",
                        "{0:.2f}".format(gpu_peak_power),
                        "W)",
                    ]
                )
                gpu_power_chart.append(gpu_power_percent)

                if dynamic_color_enabled:
                    try:
                        cpu1_gauge.color = color_for(ecpu_usage)
                        cpu2_gauge.color = color_for(pcpu_usage)
                        gpu_gauge.color = color_for(gpu_metrics_dict["active"])
                        ane_gauge.color = color_for(ane_util_percent)
                        ecpu_usage_chart.color = color_for(ecpu_usage)
                        pcpu_usage_chart.color = color_for(pcpu_usage)
                        gpu_usage_chart.color = color_for(gpu_usage)
                        ane_usage_chart.color = color_for(ane_util_percent)
                        ram_gauge.color = color_for(ram_metrics_dict["free_percent"])
                        ram_usage_chart.color = color_for(ram_used_percent)
                        ecpu_bw_gauge.color = color_for(ecpu_bw_percent)
                        pcpu_bw_gauge.color = color_for(pcpu_bw_percent)
                        gpu_bw_gauge.color = color_for(gpu_bw_percent)
                        media_bw_gauge.color = color_for(media_bw_percent)
                        cpu_power_chart.color = color_for(cpu_power_percent)
                        gpu_power_chart.color = color_for(gpu_power_percent)
                        top_process_cpu = (
                            max(
                                0.0,
                                float(cpu_processes[0].get("cpu_percent", 0.0) or 0.0),
                            )
                            if cpu_processes
                            else 0.0
                        )
                        process_list.color = color_for(top_process_cpu)
                        process_list.border_color = process_list.color
                        for gauge in core_gauges:
                            gauge.color = color_for(gauge.value)
                            gauge.border_color = gauge.color
                        for idx, chart in enumerate(e_core_history_charts):
                            history_val = (
                                e_core_history_buffers[idx][-1]
                                if e_core_history_buffers[idx]
                                else 0
                            )
                            chart.color = color_for(history_val)
                        for idx, chart in enumerate(p_core_history_charts_all):
                            history_val = (
                                p_core_history_buffers[idx][-1]
                                if p_core_history_buffers[idx]
                                else 0
                            )
                            chart.color = color_for(history_val)
                    except Exception:
                        dynamic_color_enabled = False
                        reset_static_colors(args.color)

            ui.display()

        time.sleep(sample_interval)


def main(args=None):
    if args is None:
        args = build_parser().parse_args()
    runtime_state = {"powermetrics_process": None, "cursor_hidden": False}
    try:
        _run_dashboard(args, runtime_state)
        return 0
    except KeyboardInterrupt:
        print("Stopping...")
        return 130
    finally:
        _terminate_powermetrics_process(runtime_state["powermetrics_process"])
        if runtime_state["cursor_hidden"]:
            print("\033[?25h")


def cli(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return main(args)
    except Exception as e:
        print(e)
        return 1


if __name__ == "__main__":
    raise SystemExit(cli())
