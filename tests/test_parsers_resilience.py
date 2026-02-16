from agtop.parsers import parse_cpu_metrics, parse_gpu_metrics, parse_thermal_pressure


def test_parse_cpu_metrics_missing_sections_returns_defaults():
    metrics = parse_cpu_metrics({})
    assert metrics["E-Cluster_active"] == 0
    assert metrics["P-Cluster_active"] == 0
    assert metrics["cpu_W"] == 0.0
    assert metrics["gpu_W"] == 0.0
    assert metrics["package_W"] == 0.0
    assert metrics["e_core"] == []
    assert metrics["p_core"] == []


def test_parse_cpu_metrics_partial_payload_does_not_raise():
    payload = {
        "processor": {
            "clusters": [
                {
                    "name": "E-Cluster",
                    "freq_hz": 2400000000,
                    "idle_ratio": 0.5,
                    "cpus": [{"cpu": 0, "freq_hz": 2000000000, "idle_ratio": 0.4}],
                }
            ],
            "cpu_energy": 25000,
        }
    }
    metrics = parse_cpu_metrics(payload)
    assert metrics["E-Cluster_active"] == 50
    assert metrics["P-Cluster_active"] == 0
    assert metrics["cpu_W"] == 25.0
    assert metrics["package_W"] >= metrics["cpu_W"]


def test_parse_gpu_metrics_missing_gpu_returns_defaults():
    metrics = parse_gpu_metrics({})
    assert metrics["freq_MHz"] == 0
    assert metrics["active"] == 0


def test_parse_thermal_pressure_missing_value_returns_unknown():
    assert parse_thermal_pressure({}) == "Unknown"
