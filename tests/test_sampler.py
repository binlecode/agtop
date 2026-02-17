import sys

import pytest

from agtop.sampler import SampleResult


def test_sample_result_unpacking():
    result = SampleResult(
        cpu_metrics={"cpu_W": 1.0},
        gpu_metrics={"freq_MHz": 500},
        thermal_pressure="Nominal",
        bandwidth_metrics={"_available": False},
        timestamp=1000.0,
    )
    cpu, gpu, thermal, bw, ts = result
    assert cpu == {"cpu_W": 1.0}
    assert gpu == {"freq_MHz": 500}
    assert thermal == "Nominal"
    assert bw == {"_available": False}
    assert ts == 1000.0


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")
def test_create_sampler_returns_sampler_and_backend():
    from agtop.sampler import create_sampler

    try:
        sampler, backend = create_sampler(1)
    except RuntimeError:
        pytest.skip("Neither IOReport nor powermetrics available")
    try:
        assert backend in ("ioreport", "powermetrics")
        assert hasattr(sampler, "sample")
        assert hasattr(sampler, "close")
    finally:
        sampler.close()
