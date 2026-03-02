import pytest

from agtop.api import Monitor

pytestmark = pytest.mark.local


def test_full_update_cycle_with_real_data():
    # 2. Initialize real sampler and fetch data
    monitor = Monitor(1.0, subsamples=1)
    try:
        # Get real sample
        snapshot = monitor.get_snapshot()

        assert snapshot is not None, "Sampler failed to produce real data"

        # State should be updated with actual real numbers
        assert snapshot.ecpu_util_pct >= 0
        assert snapshot.pcpu_util_pct >= 0
        assert snapshot.gpu_util_pct >= 0
        assert snapshot.ram_used_gb >= 0
        assert snapshot.cpu_watts >= 0.0

    finally:
        monitor.close()
