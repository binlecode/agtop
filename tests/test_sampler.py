import time

import pytest

from agtop.sampler import SampleResult, create_sampler

pytestmark = pytest.mark.local


def test_create_sampler_returns_sampler_and_backend():
    sampler, backend = create_sampler(1)
    try:
        assert backend == "ioreport"
        assert hasattr(sampler, "sample")
        assert hasattr(sampler, "close")
    finally:
        sampler.close()


def test_sampler_sample_returns_valid_metrics():
    sampler, _ = create_sampler(1)
    try:
        # First call primes the delta (returns None)
        first = sampler.sample()
        assert first is None

        time.sleep(1)

        # Retry until a valid result or timeout
        result = None
        deadline = time.monotonic() + 5.0
        while result is None and time.monotonic() < deadline:
            result = sampler.sample()
            if result is None:
                time.sleep(0.5)

        assert result is not None, "Sampler did not produce a reading within timeout"
        assert isinstance(result, SampleResult)

        cpu = result.cpu_metrics
        gpu = result.gpu_metrics
        thermal = result.thermal_pressure
        bw = result.bandwidth_metrics
        ts = result.timestamp

        # CPU metrics contract — keys consumed by agtop.py
        assert isinstance(cpu, dict)
        for key in [
            "E-Cluster_active",
            "E-Cluster_freq_Mhz",
            "P-Cluster_active",
            "P-Cluster_freq_Mhz",
            "ane_W",
            "cpu_W",
            "gpu_W",
            "package_W",
            "e_core",
            "p_core",
        ]:
            assert key in cpu, "Missing CPU metric key: {}".format(key)
        assert isinstance(cpu["e_core"], list)
        assert isinstance(cpu["p_core"], list)
        assert cpu["cpu_W"] >= 0
        assert cpu["gpu_W"] >= 0
        assert cpu["ane_W"] >= 0
        assert cpu["package_W"] >= 0

        # GPU metrics contract
        assert isinstance(gpu, dict)
        assert "freq_MHz" in gpu
        assert "active" in gpu
        assert isinstance(gpu["active"], int)
        assert 0 <= gpu["active"] <= 100

        # Thermal pressure
        assert isinstance(thermal, str)

        # Bandwidth metrics contract
        assert isinstance(bw, dict)
        assert "_available" in bw
        assert isinstance(bw["_available"], bool)

        # Timestamp
        assert isinstance(ts, (int, float))
        assert ts > 0
    finally:
        sampler.close()
