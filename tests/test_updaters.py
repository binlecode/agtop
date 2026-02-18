"""Cross-platform tests for update_metrics and update_widgets."""

import argparse
import time

from dashing import HGauge, HChart

from agtop.sampler import SampleResult
from agtop.state import create_dashboard_config, create_dashboard_state
from agtop.updaters import update_metrics, update_widgets


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


def _make_config(**overrides):
    return create_dashboard_config(_make_args(**overrides), _make_soc_info())


def _make_sample(
    ecpu_active=50,
    pcpu_active=60,
    gpu_active=30,
    cpu_w=10.0,
    gpu_w=8.0,
    ane_w=1.0,
    package_w=19.0,
    timestamp=None,
    thermal_pressure="Nominal",
    bandwidth_available=False,
):
    ts = timestamp if timestamp is not None else time.time()
    cpu_metrics = {
        "E-Cluster_active": ecpu_active,
        "E-Cluster_freq_Mhz": 2000,
        "P-Cluster_active": pcpu_active,
        "P-Cluster_freq_Mhz": 3200,
        "ane_W": ane_w,
        "cpu_W": cpu_w,
        "gpu_W": gpu_w,
        "package_W": package_w,
        "e_core": [4, 5, 6, 7],
        "p_core": [0, 1, 2, 3],
    }
    # Add per-core activity
    for i in [4, 5, 6, 7]:
        cpu_metrics["E-Cluster" + str(i) + "_active"] = ecpu_active
        cpu_metrics["E-Cluster" + str(i) + "_freq_Mhz"] = 2000
    for i in [0, 1, 2, 3]:
        cpu_metrics["P-Cluster" + str(i) + "_active"] = pcpu_active
        cpu_metrics["P-Cluster" + str(i) + "_freq_Mhz"] = 3200

    gpu_metrics = {"freq_MHz": 1400, "active": gpu_active}

    bw = {
        "ECPU DCS RD": 0.0,
        "ECPU DCS WR": 0.0,
        "PCPU DCS RD": 0.0,
        "PCPU DCS WR": 0.0,
        "GFX DCS RD": 0.0,
        "GFX DCS WR": 0.0,
        "MEDIA DCS": 0.0,
        "DCS RD": 0.0,
        "DCS WR": 0.0,
        "_available": bandwidth_available,
    }

    return SampleResult(
        cpu_metrics=cpu_metrics,
        gpu_metrics=gpu_metrics,
        thermal_pressure=thermal_pressure,
        bandwidth_metrics=bw,
        timestamp=ts,
        cpu_temp_c=45.0,
        gpu_temp_c=40.0,
    )


def _make_ram_metrics():
    return {
        "total_GB": 16.0,
        "free_GB": 8.0,
        "used_GB": 8.0,
        "used_percent": 50,
        "swap_total_GB": 2.0,
        "swap_used_GB": 0.5,
        "swap_free_GB": 1.5,
        "swap_used_percent": 25,
    }


def _make_process_metrics():
    return {
        "cpu": [
            {"pid": 100, "command": "python3", "cpu_percent": 25.0, "rss_mb": 200.0},
            {"pid": 200, "command": "node", "cpu_percent": 10.0, "rss_mb": 150.0},
        ],
        "memory": [],
    }


def test_update_metrics_basic_usage():
    config = _make_config()
    state = create_dashboard_state(config)
    sample = _make_sample(ecpu_active=45, pcpu_active=70, gpu_active=55)
    system_core_usage = [70, 70, 70, 70, 45, 45, 45, 45]  # P0-3 then E4-7

    result = update_metrics(
        state,
        sample,
        config,
        system_core_usage,
        _make_ram_metrics(),
        _make_process_metrics(),
    )

    assert result is True
    assert state.ecpu_usage == 45
    assert state.pcpu_usage == 70
    assert state.gpu_usage == 55


def test_update_metrics_peak_tracking():
    config = _make_config()
    state = create_dashboard_state(config)

    ts = time.time()
    sample1 = _make_sample(ecpu_active=30, gpu_active=40, timestamp=ts)
    update_metrics(
        state, sample1, config, [], _make_ram_metrics(), _make_process_metrics()
    )
    assert state.ecpu_usage_peak == 30
    assert state.gpu_usage_peak == 40

    sample2 = _make_sample(ecpu_active=80, gpu_active=90, timestamp=ts + 1)
    update_metrics(
        state, sample2, config, [], _make_ram_metrics(), _make_process_metrics()
    )
    assert state.ecpu_usage_peak == 80
    assert state.gpu_usage_peak == 90

    sample3 = _make_sample(ecpu_active=10, gpu_active=5, timestamp=ts + 2)
    update_metrics(
        state, sample3, config, [], _make_ram_metrics(), _make_process_metrics()
    )
    assert state.ecpu_usage_peak == 80  # peak doesn't decrease
    assert state.gpu_usage_peak == 90


def test_update_metrics_averaging():
    config = _make_config()
    state = create_dashboard_state(config)
    ts = time.time()

    for i in range(5):
        sample = _make_sample(ecpu_active=20 + i * 10, timestamp=ts + i)
        update_metrics(
            state, sample, config, [], _make_ram_metrics(), _make_process_metrics()
        )

    assert len(state.avg_ecpu_usage_list) == 5


def test_update_metrics_power():
    config = _make_config()
    state = create_dashboard_state(config)
    # cpu_W and gpu_W are energy values that get divided by sample_interval
    sample = _make_sample(cpu_w=20.0, gpu_w=16.0, package_w=36.0)

    update_metrics(
        state, sample, config, [], _make_ram_metrics(), _make_process_metrics()
    )

    assert state.cpu_power_w == 20.0 / config.sample_interval
    assert state.gpu_power_w == 16.0 / config.sample_interval
    assert state.package_power_w == 36.0 / config.sample_interval


def test_update_metrics_bandwidth():
    config = _make_config()
    state = create_dashboard_state(config)

    bw_sample = _make_sample(bandwidth_available=True)
    # Manually set some bandwidth values
    bw_sample.bandwidth_metrics["ECPU DCS RD"] = 10.0
    bw_sample.bandwidth_metrics["ECPU DCS WR"] = 5.0
    bw_sample.bandwidth_metrics["_available"] = True

    update_metrics(
        state, bw_sample, config, [], _make_ram_metrics(), _make_process_metrics()
    )

    assert state.bandwidth_available is True
    assert state.ecpu_bw_gbps == (10.0 + 5.0) / config.sample_interval


def test_update_metrics_timestamp_skip():
    config = _make_config()
    state = create_dashboard_state(config)

    ts = time.time()
    sample1 = _make_sample(ecpu_active=50, timestamp=ts)
    update_metrics(
        state, sample1, config, [], _make_ram_metrics(), _make_process_metrics()
    )
    assert state.ecpu_usage == 50

    # Same timestamp should be skipped
    sample2 = _make_sample(ecpu_active=99, timestamp=ts)
    result = update_metrics(
        state, sample2, config, [], _make_ram_metrics(), _make_process_metrics()
    )
    assert result is False
    assert state.ecpu_usage == 50  # unchanged


def test_update_metrics_alert_sustained():
    config = _make_config(alert_sustain_samples=3, alert_package_power_percent=50)
    state = create_dashboard_state(config)
    ts = time.time()

    # Package ref is 58W (30 cpu + 20 gpu + 8 ane). 50% threshold = 29W.
    # Send package_W = 70 (/ 2 interval = 35W) which is >50% of 58W.
    for i in range(4):
        sample = _make_sample(package_w=70.0, timestamp=ts + i)
        update_metrics(
            state, sample, config, [], _make_ram_metrics(), _make_process_metrics()
        )

    assert state.high_package_power_counter >= 3
    assert state.package_power_alert is True


def test_update_widgets_sets_values():
    config = _make_config()
    state = create_dashboard_state(config)
    ts = time.time()
    sample = _make_sample(ecpu_active=42, pcpu_active=65, gpu_active=33, timestamp=ts)
    update_metrics(
        state, sample, config, [], _make_ram_metrics(), _make_process_metrics()
    )

    widgets = {
        "cpu1_gauge": HGauge(title="", val=0, color=0),
        "cpu2_gauge": HGauge(title="", val=0, color=0),
        "gpu_gauge": HGauge(title="", val=0, color=0),
        "ane_gauge": HGauge(title="", val=0, color=0),
        "ram_gauge": HGauge(title="", val=0, color=0),
        "ecpu_usage_chart": HChart(title="", color=0),
        "pcpu_usage_chart": HChart(title="", color=0),
        "gpu_usage_chart": HChart(title="", color=0),
        "ane_usage_chart": HChart(title="", color=0),
        "ram_usage_chart": HChart(title="", color=0),
        "cpu_power_chart": HChart(title="", color=0),
        "gpu_power_chart": HChart(title="", color=0),
        "power_charts": HGauge(title="", val=0, color=0),
        "process_list": HGauge(title="", val=0, color=0),
        "process_panel": HGauge(title="", val=0, color=0),
        "ecpu_bw_gauge": HGauge(title="", val=0, color=0),
        "pcpu_bw_gauge": HGauge(title="", val=0, color=0),
        "gpu_bw_gauge": HGauge(title="", val=0, color=0),
        "media_bw_gauge": HGauge(title="", val=0, color=0),
        "memory_bandwidth_panel": HGauge(title="", val=0, color=0),
        "e_core_gauges": [HGauge(title="", val=0, color=0) for _ in range(4)],
        "p_core_gauges": [HGauge(title="", val=0, color=0) for _ in range(4)],
        "e_core_history_charts": [HChart(title="", color=0) for _ in range(4)],
        "p_core_history_charts": [HChart(title="", color=0) for _ in range(4)],
    }

    # process_list needs a text attribute
    widgets["process_list"].text = ""

    update_widgets(state, widgets, config)

    assert widgets["cpu1_gauge"].value == state.ecpu_usage
    assert widgets["cpu2_gauge"].value == state.pcpu_usage
    assert widgets["gpu_gauge"].value == state.gpu_usage
    assert (
        "42%" in widgets["cpu1_gauge"].title
        or str(state.ecpu_usage) in widgets["cpu1_gauge"].title
    )
    assert "Processes" in widgets["process_panel"].title
