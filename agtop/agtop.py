import time
import os
import argparse
import re
from importlib.metadata import version as _pkg_version
from blessed import Terminal
from dashing import VSplit, HSplit, HGauge, HChart, VGauge, Text
from .utils import (
    clear_console,
    get_top_processes,
    get_ram_metrics_dict,
    get_soc_info,
)
from .sampler import create_sampler
from .color_modes import (
    COLOR_MODE_BASIC,
    COLOR_MODE_MONO,
    COLOR_MODE_TRUECOLOR,
    COLOR_MODE_256,
    detect_color_mode,
    parse_color_mode_override,
    value_to_color_index,
)
from .input import (
    InteractiveState,
    SORT_MEMORY,
    handle_keypress,
    sort_processes,
)
from .state import create_dashboard_config, create_dashboard_state
from .updaters import (
    get_system_core_usage,
    update_metrics,
    update_widgets,
    apply_dynamic_colors,
)


def build_parser():
    parser = argparse.ArgumentParser(
        description="agtop: Performance monitoring CLI tool for Apple Silicon"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=2,
        help="Display and sampling interval in seconds",
    )
    parser.add_argument(
        "--color", type=int, default=2, help="Choose display color (0~8)"
    )
    parser.add_argument(
        "--avg", type=int, default=30, help="Interval for averaged values (seconds)"
    )
    parser.add_argument(
        "--subsamples",
        type=_validate_subsamples,
        default=1,
        help="Number of internal sampler deltas per interval (>=1)",
    )
    parser.add_argument(
        "--show_cores",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable per-core panels (disable with --no-show_cores)",
    )
    parser.add_argument(
        "--core-view",
        choices=["gauge", "history", "both"],
        default="gauge",
        help="Per-core rendering mode for --show_cores: gauge, history, or both",
    )
    parser.add_argument(
        "--power-scale",
        choices=["auto", "profile"],
        default="profile",
        help="Power chart scaling mode: profile uses SoC reference, auto uses rolling peak",
    )
    parser.add_argument(
        "--proc-filter",
        type=_validate_proc_filter,
        default="",
        help='Regex filter for process panel command names (example: "python|ollama|vllm|docker|mlx")',
    )
    parser.add_argument(
        "--alert-bw-sat-percent",
        type=_validate_percent_threshold,
        default=85,
        help="Bandwidth saturation alert threshold percent (1-100)",
    )
    parser.add_argument(
        "--alert-package-power-percent",
        type=_validate_percent_threshold,
        default=85,
        help="Package power alert threshold percent (1-100, profile-relative)",
    )
    parser.add_argument(
        "--alert-swap-rise-gb",
        type=_validate_swap_rise_gb,
        default=0.3,
        help="Alert when swap rises by at least this many GB over sustained samples",
    )
    parser.add_argument(
        "--alert-sustain-samples",
        type=_validate_sustain_samples,
        default=3,
        help="Consecutive samples required for sustained alerts",
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


def _validate_percent_threshold(value):
    try:
        threshold = int(value)
    except (TypeError, ValueError) as error:
        raise argparse.ArgumentTypeError("threshold must be an integer") from error
    if threshold < 1 or threshold > 100:
        raise argparse.ArgumentTypeError("threshold must be in the range 1-100")
    return threshold


def _validate_swap_rise_gb(value):
    try:
        swap_rise = float(value)
    except (TypeError, ValueError) as error:
        raise argparse.ArgumentTypeError(
            "swap rise threshold must be a number"
        ) from error
    if swap_rise < 0:
        raise argparse.ArgumentTypeError("swap rise threshold must be >= 0")
    return swap_rise


def _validate_sustain_samples(value):
    try:
        samples = int(value)
    except (TypeError, ValueError) as error:
        raise argparse.ArgumentTypeError(
            "sustain samples must be an integer"
        ) from error
    if samples < 1:
        raise argparse.ArgumentTypeError("sustain samples must be >= 1")
    return samples


def _validate_subsamples(value):
    try:
        subsamples = int(value)
    except (TypeError, ValueError) as error:
        raise argparse.ArgumentTypeError("subsamples must be an integer") from error
    if subsamples < 1:
        raise argparse.ArgumentTypeError("subsamples must be >= 1")
    return subsamples


def _recompute_process_row_percents(state, config, sort_mode):
    """Recompute process_row_percents based on the active sort mode."""
    rows = [None]
    for proc in state.cpu_processes[: config.process_display_count]:
        if sort_mode == SORT_MEMORY:
            pct = max(0.0, float(proc.get("memory_percent", 0.0) or 0.0))
        else:
            pct = max(0.0, float(proc.get("cpu_percent", 0.0) or 0.0))
        rows.append(pct)
    if len(rows) == 1:
        rows.append(None)
    state.process_row_percents = rows


def _supports_cursor_addressing(terminal):
    try:
        return bool(terminal.move(0, 0))
    except Exception:
        return False


def _run_dashboard(args, runtime_state):
    terminal = Terminal()
    use_full_clear_redraw = not _supports_cursor_addressing(terminal)
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
    gradient_override = os.getenv("AGTOP_GRADIENT") or os.getenv(
        "AGTOP_EXPERIMENTAL_GRADIENT"
    )
    if gradient_override is None:
        gradient_bars_enabled = dynamic_color_enabled
    else:
        gradient_bars_enabled = gradient_override.strip() != "0"
    GaugeClass = HGauge
    VGaugeClass = VGauge
    HChartClass = HChart
    TextClass = Text
    if gradient_bars_enabled and dynamic_color_enabled:
        try:
            from .gradient import (
                GradientHGauge,
                GradientVGauge,
                GradientHChart,
                GradientText,
            )

            GaugeClass = GradientHGauge
            VGaugeClass = GradientVGauge
            HChartClass = GradientHChart
            TextClass = GradientText
        except Exception as e:
            print(
                "Warning: gradient renderer init failed: {}. Using default renderer.".format(
                    e
                )
            )
    base_color = 0 if color_mode == COLOR_MODE_MONO else args.color

    try:
        _version = _pkg_version("agtop")
    except Exception:
        _version = "dev"
    print(
        "AGTOP v{} - Performance monitoring CLI tool for Apple Silicon".format(
            _version
        ),
        flush=True,
    )
    print(
        "Update with your package manager (for Homebrew: `brew upgrade agtop`)",
        flush=True,
    )
    print("Get help at `https://github.com/binlecode/agtop`", flush=True)
    print("", flush=True)
    print("\033[?25l", end="", flush=True)
    runtime_state["cursor_hidden"] = True
    print("[1/3] Loading AGTOP ...", flush=True)

    soc_info_dict = get_soc_info()
    config = create_dashboard_config(args, soc_info_dict)

    cpu1_gauge = GaugeClass(title="E-CPU", val=0, color=base_color)
    cpu2_gauge = GaugeClass(title="P-CPU", val=0, color=base_color)
    gpu_gauge = GaugeClass(title="GPU", val=0, color=base_color)
    ane_gauge = GaugeClass(title="ANE", val=0, color=base_color)

    ecpu_usage_chart = HChartClass(title="E-CPU", color=base_color)
    pcpu_usage_chart = HChartClass(title="P-CPU", color=base_color)
    gpu_usage_chart = HChartClass(title="GPU", color=base_color)
    ane_usage_chart = HChartClass(title="ANE", color=base_color)
    ram_usage_chart = HChartClass(title="RAM", color=base_color)

    e_core_gauges = [
        VGaugeClass(val=0, color=base_color, border_color=base_color)
        for _ in range(config.e_core_count)
    ]
    e_core_history_charts = [
        HChartClass(title="E{}".format(i + 1), color=base_color)
        for i in range(config.e_core_count)
    ]

    p_core_gauges_all = [
        VGaugeClass(val=0, color=base_color, border_color=None)
        for _ in range(config.p_core_count)
    ]
    p_core_history_charts_all = [
        HChartClass(title="P{}".format(i + 1), color=base_color)
        for i in range(config.p_core_count)
    ]

    p_core_items_per_row = 4
    p_core_gauge_split = [
        HSplit(*p_core_gauges_all[i : i + p_core_items_per_row])
        for i in range(0, len(p_core_gauges_all), p_core_items_per_row)
    ]
    p_core_history_split = [
        HSplit(*p_core_history_charts_all[i : i + p_core_items_per_row])
        for i in range(0, len(p_core_history_charts_all), p_core_items_per_row)
    ]

    show_core_gauges = args.show_cores and args.core_view in {"gauge", "both"}
    show_core_history = args.show_cores and args.core_view in {"history", "both"}

    # === Row 1: Processor Utilization (E-CPU | P-CPU) ===
    ecpu_elements = [HSplit(cpu1_gauge, ecpu_usage_chart)]
    if args.show_cores:
        if show_core_gauges and e_core_gauges:
            ecpu_elements.append(HSplit(*e_core_gauges))
        if show_core_history and e_core_history_charts:
            ecpu_elements.append(HSplit(*e_core_history_charts))

    ecpu_block = VSplit(
        *ecpu_elements,
        title="E-CPU",
        border_color=base_color,
    )

    pcpu_elements = [HSplit(cpu2_gauge, pcpu_usage_chart)]
    if args.show_cores:
        if show_core_gauges:
            pcpu_elements.extend(p_core_gauge_split)
        render_p_core_history_rows = show_core_history and not show_core_gauges
        if render_p_core_history_rows:
            pcpu_elements.extend(p_core_history_split)

    pcpu_block = VSplit(
        *pcpu_elements,
        title="P-CPU",
        border_color=base_color,
    )

    row1 = HSplit(
        ecpu_block,
        pcpu_block,
        title="Processors",
        border_color=base_color,
    )

    # === Row 2: GPU/ANE and Memory ===
    gpu_ane_block = VSplit(
        HSplit(gpu_gauge, gpu_usage_chart),
        HSplit(ane_gauge, ane_usage_chart),
        title="GPU & ANE",
        border_color=base_color,
    )

    ram_gauge = GaugeClass(title="RAM", val=0, color=base_color)
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

    row2 = HSplit(
        gpu_ane_block,
        memory_gauges,
        title="Graphics & Memory",
        border_color=base_color,
    )

    # === Row 3: Power and Processes ===
    cpu_power_chart = HChartClass(title="CPU Power", color=base_color)
    gpu_power_chart = HChartClass(title="GPU Power", color=base_color)
    power_charts = HSplit(
        cpu_power_chart,
        gpu_power_chart,
        title="Power Chart",
        border_color=base_color,
    )

    process_list = TextClass(
        "  PID NAME                      CPU%    RSS\n(no data yet)",
        color=base_color,
        border_color=base_color,
    )
    process_panel = VSplit(
        process_list,
        border_color=base_color,
        title="Processes (top CPU)",
    )

    row3 = HSplit(
        power_charts,
        process_panel,
        title="Power & Processes",
        border_color=base_color,
    )

    ui = VSplit(
        row1,
        row2,
        row3,
        border_color=base_color,
    )

    usage_gauges = ui

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

    # Build widgets dict for updaters
    widgets = {
        "cpu1_gauge": cpu1_gauge,
        "cpu2_gauge": cpu2_gauge,
        "gpu_gauge": gpu_gauge,
        "ane_gauge": ane_gauge,
        "ram_gauge": ram_gauge,
        "ecpu_usage_chart": ecpu_usage_chart,
        "pcpu_usage_chart": pcpu_usage_chart,
        "gpu_usage_chart": gpu_usage_chart,
        "ane_usage_chart": ane_usage_chart,
        "ram_usage_chart": ram_usage_chart,
        "cpu_power_chart": cpu_power_chart,
        "gpu_power_chart": gpu_power_chart,
        "power_charts": power_charts,
        "process_list": process_list,
        "process_panel": process_panel,
        "ecpu_bw_gauge": ecpu_bw_gauge,
        "pcpu_bw_gauge": pcpu_bw_gauge,
        "gpu_bw_gauge": gpu_bw_gauge,
        "media_bw_gauge": media_bw_gauge,
        "memory_bandwidth_panel": memory_bandwidth_panel,
        "e_core_gauges": e_core_gauges,
        "p_core_gauges": p_core_gauges_all,
        "e_core_history_charts": e_core_history_charts,
        "p_core_history_charts": p_core_history_charts_all,
    }

    sampler, backend_name = create_sampler(config.sample_interval, args.subsamples)
    sampler_manages_timing = bool(getattr(sampler, "manages_timing", False))
    runtime_state["sampler"] = sampler
    print("[2/3] Backend: {} ...".format(backend_name), flush=True)

    print("[3/3] Waiting for first reading ...", flush=True)
    print("", flush=True)

    sampler.sample()  # prime first snapshot (IOReport needs two for delta)
    if not sampler_manages_timing:
        time.sleep(config.sample_interval)

    first_reading_timeout_s = max(8.0, float(config.sample_interval) * 4.0)
    start_wait = time.time()
    ready = sampler.sample()
    while ready is None:
        if time.time() - start_wait >= first_reading_timeout_s:
            raise RuntimeError(
                "Timed out waiting for first reading from {} backend.".format(
                    backend_name
                )
            )
        if not sampler_manages_timing:
            time.sleep(0.5)
        ready = sampler.sample()

    state = create_dashboard_state(config)
    state.last_timestamp = ready.timestamp
    interactive = InteractiveState()

    core_gauges = e_core_gauges + p_core_gauges_all
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

        ui.border_color = color_index
        row1.border_color = color_index
        row2.border_color = color_index
        row3.border_color = color_index
        ecpu_block.border_color = color_index
        pcpu_block.border_color = color_index
        gpu_ane_block.border_color = color_index

        memory_gauges.border_color = color_index
        memory_bandwidth_panel.border_color = color_index
        power_charts.border_color = color_index
        process_panel.border_color = color_index
        for gauge in core_gauges:
            gauge.color = color_index
            if gauge in p_core_gauges_all:
                gauge.border_color = None
            else:
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
            limit=config.process_display_count,
            proc_filter=config.process_filter_pattern,
        )
    except Exception:
        pass

    first_frame_rendered = False
    with terminal.cbreak():
        while True:
            ready = sampler.sample()
            if ready is not None:
                if ready.timestamp > state.last_timestamp:
                    system_core_usage = get_system_core_usage()
                    ram_metrics = get_ram_metrics_dict()
                    process_metrics = {"cpu": [], "memory": []}
                    try:
                        process_metrics = get_top_processes(
                            limit=config.process_display_count,
                            proc_filter=config.process_filter_pattern,
                        )
                    except Exception:
                        pass

                    update_metrics(
                        state,
                        ready,
                        config,
                        system_core_usage,
                        ram_metrics,
                        process_metrics,
                    )
                    state.cpu_processes = sort_processes(
                        process_metrics,
                        interactive.sort_mode,
                        config.process_display_count,
                    )
                    _recompute_process_row_percents(
                        state, config, interactive.sort_mode
                    )
                    update_widgets(state, widgets, config, interactive)
                    if dynamic_color_enabled:
                        try:
                            apply_dynamic_colors(state, widgets, config, color_for)
                        except Exception:
                            dynamic_color_enabled = False
                            reset_static_colors(args.color)

                if use_full_clear_redraw or not first_frame_rendered:
                    print("\033[2J\033[H", end="", flush=True)
                ui.display()
                first_frame_rendered = True

            if not sampler_manages_timing:
                timeout = config.sample_interval
            else:
                timeout = 0
            key = terminal.inkey(timeout=timeout)
            while key:
                handle_keypress(key, interactive)
                if interactive.quit_requested:
                    return
                key = terminal.inkey(timeout=0)


def main(args=None):
    if args is None:
        args = build_parser().parse_args()
    runtime_state = {"sampler": None, "cursor_hidden": False}
    try:
        _run_dashboard(args, runtime_state)
        return 0
    except KeyboardInterrupt:
        print("Stopping...")
        return 130
    finally:
        sampler = runtime_state.get("sampler")
        if sampler is not None:
            sampler.close()
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
