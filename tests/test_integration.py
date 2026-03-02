import argparse
import time
import pytest

from agtop.state import create_dashboard_config, create_dashboard_state
from agtop.sampler import create_sampler
from agtop.updaters import update_metrics, update_widgets
from agtop.utils import get_soc_info, get_ram_metrics_dict, get_top_processes
from dashing import HGauge, HChart

pytestmark = pytest.mark.local


def test_full_update_cycle_with_real_data():
    # 1. Initialize real configuration and state
    parser = argparse.ArgumentParser()
    args = parser.parse_args([])
    # set defaults manually since we aren't using the full CLI parser builder here
    args.interval = 1
    args.color = 2
    args.avg = 30
    args.show_cores = True
    args.core_view = "gauge"
    args.power_scale = "profile"
    args.proc_filter = ""
    args.alert_bw_sat_percent = 85
    args.alert_package_power_percent = 85
    args.alert_swap_rise_gb = 0.3
    args.alert_sustain_samples = 3
    args.subsamples = 1

    soc_info = get_soc_info()
    config = create_dashboard_config(args, soc_info)
    state = create_dashboard_state(config)

    # 2. Initialize real sampler and fetch data
    sampler, backend = create_sampler(1)
    try:
        # Prime the sampler
        sampler.sample()
        time.sleep(1.0)

        # Get real sample
        deadline = time.monotonic() + 5.0
        sample = None
        while sample is None and time.monotonic() < deadline:
            sample = sampler.sample()
            if sample is None:
                time.sleep(0.5)

        assert sample is not None, "Sampler failed to produce real data"

        # Get real peripheral metrics
        ram_metrics = get_ram_metrics_dict()
        proc_metrics = get_top_processes(limit=5)

        # 3. Update the state with real data
        # we need system_core_usage, which updaters expects
        # we can just extract it from the real sample!
        e_cores = sample.cpu_metrics.get("e_core", [])
        p_cores = sample.cpu_metrics.get("p_core", [])
        system_core_usage = []
        for c in p_cores:
            system_core_usage.append(sample.cpu_metrics.get(f"P-Cluster{c}_active", 0))
        for c in e_cores:
            system_core_usage.append(sample.cpu_metrics.get(f"E-Cluster{c}_active", 0))

        success = update_metrics(
            state, sample, config, system_core_usage, ram_metrics, proc_metrics
        )
        assert success is True

        # State should be updated with actual real numbers
        assert state.ecpu_usage >= 0
        assert state.pcpu_usage >= 0
        assert state.gpu_usage >= 0
        assert state.ram_used_percent >= 0
        assert state.cpu_power_w >= 0.0

        # 4. Update real UI widgets with the updated state
        # Create minimal real widgets
        widgets = {
            "cpu1_gauge": HGauge(title="E-CPU", val=0, color=2),
            "cpu2_gauge": HGauge(title="P-CPU", val=0, color=2),
            "gpu_gauge": HGauge(title="GPU", val=0, color=2),
            "ane_gauge": HGauge(title="ANE", val=0, color=2),
            "ram_gauge": HGauge(title="RAM", val=0, color=2),
            "ecpu_usage_chart": HChart(title="", color=2),
            "pcpu_usage_chart": HChart(title="", color=2),
            "gpu_usage_chart": HChart(title="", color=2),
            "ane_usage_chart": HChart(title="", color=2),
            "ram_usage_chart": HChart(title="", color=2),
            "cpu_power_chart": HChart(title="", color=2),
            "gpu_power_chart": HChart(title="", color=2),
            "power_charts": HGauge(title="Power", val=0, color=2),
            "process_list": HGauge(title="Processes", val=0, color=2),
            "process_panel": HGauge(title="Processes", val=0, color=2),
            "ecpu_bw_gauge": HGauge(title="E-BW", val=0, color=2),
            "pcpu_bw_gauge": HGauge(title="P-BW", val=0, color=2),
            "gpu_bw_gauge": HGauge(title="G-BW", val=0, color=2),
            "media_bw_gauge": HGauge(title="M-BW", val=0, color=2),
            "memory_bandwidth_panel": HGauge(title="Mem BW", val=0, color=2),
            "e_core_gauges": [
                HGauge(title="", val=0, color=2) for _ in range(config.e_core_count)
            ],
            "p_core_gauges": [
                HGauge(title="", val=0, color=2) for _ in range(config.p_core_count)
            ],
            "e_core_history_charts": [
                HChart(title="", color=2) for _ in range(config.e_core_count)
            ],
            "p_core_history_charts": [
                HChart(title="", color=2) for _ in range(config.p_core_count)
            ],
        }
        widgets["process_list"].text = ""

        update_widgets(state, widgets, config, term_width=120)

        # Assert widgets reflect the state
        assert widgets["cpu1_gauge"].value == state.ecpu_usage
        assert widgets["cpu2_gauge"].value == state.pcpu_usage
        assert widgets["gpu_gauge"].value == state.gpu_usage

    finally:
        sampler.close()
