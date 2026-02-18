"""Dashboard configuration and mutable state dataclasses."""

import re
from collections import deque
from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class DashboardConfig:
    """Immutable values computed once from args + soc_info_dict."""

    sample_interval: int
    avg_window: int
    usage_track_window: int
    core_history_window: int

    cpu_chart_ref_w: float
    gpu_chart_ref_w: float
    ane_max_power: float
    package_ref_w: float
    max_cpu_bw: float
    max_gpu_bw: float
    max_media_bw: float

    e_core_count: int
    p_core_count: int

    power_scale: str
    show_cores: bool

    alert_bw_sat_percent: int
    alert_package_power_percent: int
    alert_swap_rise_gb: float
    alert_sustain_samples: int

    process_display_count: int
    process_filter_pattern: Optional[object]  # compiled regex or None
    proc_filter_raw: str


@dataclass
class DashboardState:
    """All per-frame and accumulated mutable state."""

    # Current usage (0-100)
    ecpu_usage: int = 0
    pcpu_usage: int = 0
    gpu_usage: int = 0
    ane_util_percent: int = 0
    ram_used_percent: int = 0

    # Frequencies
    ecpu_freq_mhz: int = 0
    pcpu_freq_mhz: int = 0
    gpu_freq_mhz: int = 0

    # Temperatures
    cpu_temp_c: float = 0.0
    gpu_temp_c: float = 0.0

    # Per-core activity
    e_core_activity: dict = field(default_factory=dict)
    p_core_activity: dict = field(default_factory=dict)

    # Peaks
    ecpu_usage_peak: int = 0
    pcpu_usage_peak: int = 0
    gpu_usage_peak: int = 0
    ane_usage_peak: int = 0
    ram_usage_peak: int = 0
    cpu_peak_power: float = 0.0
    gpu_peak_power: float = 0.0
    package_peak_power: float = 0.0

    # Averaging deques (initialized by factory)
    avg_ecpu_usage_list: deque = field(default_factory=deque)
    avg_pcpu_usage_list: deque = field(default_factory=deque)
    avg_gpu_usage_list: deque = field(default_factory=deque)
    avg_ane_usage_list: deque = field(default_factory=deque)
    avg_ram_usage_list: deque = field(default_factory=deque)
    avg_cpu_power_list: deque = field(default_factory=deque)
    avg_gpu_power_list: deque = field(default_factory=deque)
    avg_package_power_list: deque = field(default_factory=deque)

    # Per-core history buffers (lists of deques)
    e_core_history_buffers: list = field(default_factory=list)
    p_core_history_buffers: list = field(default_factory=list)

    # Alert counters
    high_bw_counter: int = 0
    high_package_power_counter: int = 0
    swap_used_history: deque = field(default_factory=deque)

    # Power (current frame)
    cpu_power_w: float = 0.0
    gpu_power_w: float = 0.0
    package_power_w: float = 0.0
    cpu_power_percent: int = 0
    gpu_power_percent: int = 0
    package_power_percent: int = 0
    avg_cpu_power: float = 0.0
    avg_gpu_power: float = 0.0
    avg_package_power: float = 0.0
    ane_power_w: float = 0.0

    # Bandwidth
    bandwidth_available: bool = False
    ecpu_bw_gbps: float = 0.0
    pcpu_bw_gbps: float = 0.0
    gpu_bw_gbps: float = 0.0
    media_bw_gbps: float = 0.0
    ecpu_bw_percent: int = 0
    pcpu_bw_percent: int = 0
    gpu_bw_percent: int = 0
    media_bw_percent: int = 0
    total_bw_read_gbps: float = 0.0
    total_bw_write_gbps: float = 0.0
    total_bw_gbps: float = 0.0

    # RAM
    ram_metrics_dict: dict = field(default_factory=dict)

    # Thermal
    thermal_pressure: str = "Unknown"

    # Processes
    cpu_processes: list = field(default_factory=list)
    process_row_percents: list = field(default_factory=list)

    # Alerts
    thermal_alert: bool = False
    bandwidth_alert: bool = False
    swap_alert: bool = False
    package_power_alert: bool = False
    alerts_label: str = "none"

    # Timestamp
    last_timestamp: float = 0.0


def create_dashboard_config(args, soc_info_dict):
    """Build an immutable DashboardConfig from parsed CLI args and SoC info."""
    sample_interval = max(1, args.interval)
    avg_window = max(1, int(args.avg / sample_interval))
    usage_track_window = max(20, int(args.avg / sample_interval))
    core_history_window = max(20, int(args.avg / sample_interval))

    cpu_chart_ref_w = soc_info_dict["cpu_chart_ref_w"]
    gpu_chart_ref_w = soc_info_dict["gpu_chart_ref_w"]
    ane_max_power = 8.0
    package_ref_w = max(cpu_chart_ref_w + gpu_chart_ref_w + ane_max_power, 1.0)
    max_cpu_bw = max(float(soc_info_dict.get("cpu_max_bw", 0.0)), 1.0)
    max_gpu_bw = max(float(soc_info_dict.get("gpu_max_bw", 0.0)), 1.0)
    max_media_bw = max(max_cpu_bw, max_gpu_bw)

    e_core_count = max(0, int(soc_info_dict["e_core_count"]))
    p_core_count = max(0, int(soc_info_dict["p_core_count"]))

    process_filter_pattern = (
        re.compile(args.proc_filter, re.IGNORECASE) if args.proc_filter else None
    )

    return DashboardConfig(
        sample_interval=sample_interval,
        avg_window=avg_window,
        usage_track_window=usage_track_window,
        core_history_window=core_history_window,
        cpu_chart_ref_w=cpu_chart_ref_w,
        gpu_chart_ref_w=gpu_chart_ref_w,
        ane_max_power=ane_max_power,
        package_ref_w=package_ref_w,
        max_cpu_bw=max_cpu_bw,
        max_gpu_bw=max_gpu_bw,
        max_media_bw=max_media_bw,
        e_core_count=e_core_count,
        p_core_count=p_core_count,
        power_scale=args.power_scale,
        show_cores=args.show_cores,
        alert_bw_sat_percent=args.alert_bw_sat_percent,
        alert_package_power_percent=args.alert_package_power_percent,
        alert_swap_rise_gb=args.alert_swap_rise_gb,
        alert_sustain_samples=max(1, int(args.alert_sustain_samples)),
        process_display_count=8,
        process_filter_pattern=process_filter_pattern,
        proc_filter_raw=args.proc_filter or "",
    )


def create_dashboard_state(config):
    """Build a zeroed DashboardState with deque maxlens from config."""
    swap_history_points = config.alert_sustain_samples + 1
    return DashboardState(
        avg_ecpu_usage_list=deque([], maxlen=config.usage_track_window),
        avg_pcpu_usage_list=deque([], maxlen=config.usage_track_window),
        avg_gpu_usage_list=deque([], maxlen=config.usage_track_window),
        avg_ane_usage_list=deque([], maxlen=config.usage_track_window),
        avg_ram_usage_list=deque([], maxlen=config.usage_track_window),
        avg_cpu_power_list=deque([], maxlen=config.avg_window),
        avg_gpu_power_list=deque([], maxlen=config.avg_window),
        avg_package_power_list=deque([], maxlen=config.avg_window),
        e_core_history_buffers=[
            deque([], maxlen=config.core_history_window)
            for _ in range(config.e_core_count)
        ],
        p_core_history_buffers=[
            deque([], maxlen=config.core_history_window)
            for _ in range(config.p_core_count)
        ],
        swap_used_history=deque([], maxlen=swap_history_points),
    )
