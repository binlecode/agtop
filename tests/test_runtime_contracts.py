from agtop import utils


def _assert_percent_or_none(value):
    if value is None:
        return
    assert isinstance(value, int)
    assert 0 <= value <= 100


def _assert_non_negative_number(value):
    assert isinstance(value, (int, float))
    assert value >= 0


def test_ram_metrics_contract():
    ram_metrics = utils.get_ram_metrics_dict()

    required_keys = [
        "total_GB",
        "free_GB",
        "used_GB",
        "free_percent",
        "swap_total_GB",
        "swap_used_GB",
        "swap_free_GB",
        "swap_free_percent",
    ]
    for key in required_keys:
        assert key in ram_metrics

    _assert_non_negative_number(ram_metrics["total_GB"])
    _assert_non_negative_number(ram_metrics["free_GB"])
    _assert_non_negative_number(ram_metrics["used_GB"])
    _assert_percent_or_none(ram_metrics["free_percent"])
    _assert_non_negative_number(ram_metrics["swap_total_GB"])
    _assert_non_negative_number(ram_metrics["swap_used_GB"])
    _assert_non_negative_number(ram_metrics["swap_free_GB"])
    _assert_percent_or_none(ram_metrics["swap_free_percent"])

    assert ram_metrics["used_GB"] <= ram_metrics["total_GB"] + 0.5
    assert ram_metrics["free_GB"] <= ram_metrics["total_GB"] + 0.5
    assert ram_metrics["swap_used_GB"] <= ram_metrics["swap_total_GB"] + 0.5


def test_soc_info_contract():
    soc_info = utils.get_soc_info()

    required_keys = [
        "name",
        "core_count",
        "cpu_chart_ref_w",
        "gpu_chart_ref_w",
        "cpu_max_power",
        "gpu_max_power",
        "cpu_max_bw",
        "gpu_max_bw",
        "e_core_count",
        "p_core_count",
        "gpu_core_count",
    ]
    for key in required_keys:
        assert key in soc_info

    assert isinstance(soc_info["name"], str)
    assert soc_info["name"] != ""
    _assert_non_negative_number(soc_info["core_count"])
    _assert_non_negative_number(soc_info["cpu_chart_ref_w"])
    _assert_non_negative_number(soc_info["gpu_chart_ref_w"])
    _assert_non_negative_number(soc_info["cpu_max_power"])
    _assert_non_negative_number(soc_info["gpu_max_power"])
    _assert_non_negative_number(soc_info["cpu_max_bw"])
    _assert_non_negative_number(soc_info["gpu_max_bw"])
    _assert_non_negative_number(soc_info["e_core_count"])
    _assert_non_negative_number(soc_info["p_core_count"])
    assert soc_info["gpu_core_count"] == "?" or (
        isinstance(soc_info["gpu_core_count"], int) and soc_info["gpu_core_count"] >= 0
    )
