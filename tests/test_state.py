"""Cross-platform tests for DashboardConfig and DashboardState factories."""

import argparse

from agtop.state import create_dashboard_config, create_dashboard_state


def _make_args(**overrides):
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
    return argparse.Namespace(**defaults)


def _make_soc_info(**overrides):
    defaults = {
        "name": "Apple M2",
        "cpu_chart_ref_w": 30.0,
        "gpu_chart_ref_w": 20.0,
        "cpu_max_bw": 100.0,
        "gpu_max_bw": 200.0,
        "e_core_count": 4,
        "p_core_count": 4,
        "gpu_core_count": 10,
    }
    defaults.update(overrides)
    return defaults


def test_create_dashboard_config_fields():
    args = _make_args()
    soc = _make_soc_info()
    config = create_dashboard_config(args, soc)

    assert config.sample_interval == 2
    assert config.avg_window == 15
    assert config.usage_track_window == 20  # max(20, 30/2=15) -> 20
    assert config.core_history_window == 20
    assert config.cpu_chart_ref_w == 30.0
    assert config.gpu_chart_ref_w == 20.0
    assert config.ane_max_power == 8.0
    assert config.package_ref_w == 30.0 + 20.0 + 8.0
    assert config.max_cpu_bw == 100.0
    assert config.max_gpu_bw == 200.0
    assert config.max_media_bw == 200.0
    assert config.e_core_count == 4
    assert config.p_core_count == 4
    assert config.power_scale == "profile"
    assert config.show_cores is True
    assert config.alert_bw_sat_percent == 85
    assert config.alert_package_power_percent == 85
    assert config.alert_swap_rise_gb == 0.3
    assert config.alert_sustain_samples == 3
    assert config.process_display_count == 8
    assert config.process_filter_pattern is None
    assert config.proc_filter_raw == ""


def test_config_clamps_sample_interval():
    args = _make_args(interval=0)
    config = create_dashboard_config(args, _make_soc_info())
    assert config.sample_interval == 1


def test_config_process_filter_compiled():
    args = _make_args(proc_filter="python")
    config = create_dashboard_config(args, _make_soc_info())
    assert config.process_filter_pattern is not None
    assert config.process_filter_pattern.search("Python3")


def test_config_process_filter_none_when_empty():
    args = _make_args(proc_filter="")
    config = create_dashboard_config(args, _make_soc_info())
    assert config.process_filter_pattern is None


def test_create_dashboard_state_deque_maxlens():
    args = _make_args(interval=2, avg=30, alert_sustain_samples=3)
    config = create_dashboard_config(args, _make_soc_info())
    state = create_dashboard_state(config)

    assert state.avg_ecpu_usage_list.maxlen == config.usage_track_window
    assert state.avg_pcpu_usage_list.maxlen == config.usage_track_window
    assert state.avg_gpu_usage_list.maxlen == config.usage_track_window
    assert state.avg_ane_usage_list.maxlen == config.usage_track_window
    assert state.avg_ram_usage_list.maxlen == config.usage_track_window
    assert state.avg_cpu_power_list.maxlen == config.avg_window
    assert state.avg_gpu_power_list.maxlen == config.avg_window
    assert state.avg_package_power_list.maxlen == config.avg_window
    assert state.swap_used_history.maxlen == config.alert_sustain_samples + 1
    assert len(state.e_core_history_buffers) == 4
    assert len(state.p_core_history_buffers) == 4
    for buf in state.e_core_history_buffers + state.p_core_history_buffers:
        assert buf.maxlen == config.core_history_window


def test_dashboard_state_defaults():
    args = _make_args()
    config = create_dashboard_config(args, _make_soc_info())
    state = create_dashboard_state(config)

    assert state.ecpu_usage == 0
    assert state.pcpu_usage == 0
    assert state.gpu_usage == 0
    assert state.ane_util_percent == 0
    assert state.ram_used_percent == 0
    assert state.cpu_peak_power == 0.0
    assert state.gpu_peak_power == 0.0
    assert state.package_peak_power == 0.0
    assert state.high_bw_counter == 0
    assert state.high_package_power_counter == 0
    assert state.thermal_alert is False
    assert state.bandwidth_alert is False
    assert state.swap_alert is False
    assert state.package_power_alert is False
    assert state.alerts_label == "none"
    assert state.last_timestamp == 0.0
