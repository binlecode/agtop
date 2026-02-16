def _to_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _to_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _active_percent(idle_ratio):
    idle = _to_float(idle_ratio, default=1.0)
    active = (1.0 - idle) * 100.0
    return _to_int(max(0.0, min(100.0, active)))


def parse_thermal_pressure(powermetrics_parse):
    if not isinstance(powermetrics_parse, dict):
        return "Unknown"
    return powermetrics_parse.get("thermal_pressure", "Unknown")


def parse_bandwidth_metrics(powermetrics_parse):
    if not isinstance(powermetrics_parse, dict):
        return {}
    bandwidth_metrics = powermetrics_parse.get("bandwidth_counters", [])
    bandwidth_metrics_dict = {}
    data_fields = [
        "PCPU0 DCS RD",
        "PCPU0 DCS WR",
        "PCPU1 DCS RD",
        "PCPU1 DCS WR",
        "PCPU2 DCS RD",
        "PCPU2 DCS WR",
        "PCPU3 DCS RD",
        "PCPU3 DCS WR",
        "PCPU DCS RD",
        "PCPU DCS WR",
        "ECPU0 DCS RD",
        "ECPU0 DCS WR",
        "ECPU1 DCS RD",
        "ECPU1 DCS WR",
        "ECPU DCS RD",
        "ECPU DCS WR",
        "GFX DCS RD",
        "GFX DCS WR",
        "ISP DCS RD",
        "ISP DCS WR",
        "STRM CODEC DCS RD",
        "STRM CODEC DCS WR",
        "PRORES DCS RD",
        "PRORES DCS WR",
        "VDEC DCS RD",
        "VDEC DCS WR",
        "VENC0 DCS RD",
        "VENC0 DCS WR",
        "VENC1 DCS RD",
        "VENC1 DCS WR",
        "VENC2 DCS RD",
        "VENC2 DCS WR",
        "VENC3 DCS RD",
        "VENC3 DCS WR",
        "VENC DCS RD",
        "VENC DCS WR",
        "JPG0 DCS RD",
        "JPG0 DCS WR",
        "JPG1 DCS RD",
        "JPG1 DCS WR",
        "JPG2 DCS RD",
        "JPG2 DCS WR",
        "JPG3 DCS RD",
        "JPG3 DCS WR",
        "JPG DCS RD",
        "JPG DCS WR",
        "DCS RD",
        "DCS WR",
    ]
    for h in data_fields:
        bandwidth_metrics_dict[h] = 0.0
    for metric_entry in bandwidth_metrics:
        if metric_entry.get("name") in data_fields:
            bandwidth_metrics_dict[metric_entry["name"]] = (
                _to_float(metric_entry.get("value")) / 1e9
            )
    bandwidth_metrics_dict["PCPU DCS RD"] = (
        bandwidth_metrics_dict["PCPU DCS RD"]
        + bandwidth_metrics_dict["PCPU0 DCS RD"]
        + bandwidth_metrics_dict["PCPU1 DCS RD"]
        + bandwidth_metrics_dict["PCPU2 DCS RD"]
        + bandwidth_metrics_dict["PCPU3 DCS RD"]
    )
    bandwidth_metrics_dict["PCPU DCS WR"] = (
        bandwidth_metrics_dict["PCPU DCS WR"]
        + bandwidth_metrics_dict["PCPU0 DCS WR"]
        + bandwidth_metrics_dict["PCPU1 DCS WR"]
        + bandwidth_metrics_dict["PCPU2 DCS WR"]
        + bandwidth_metrics_dict["PCPU3 DCS WR"]
    )
    bandwidth_metrics_dict["JPG DCS RD"] = (
        bandwidth_metrics_dict["JPG DCS RD"]
        + bandwidth_metrics_dict["JPG0 DCS RD"]
        + bandwidth_metrics_dict["JPG1 DCS RD"]
        + bandwidth_metrics_dict["JPG2 DCS RD"]
        + bandwidth_metrics_dict["JPG3 DCS RD"]
    )
    bandwidth_metrics_dict["JPG DCS WR"] = (
        bandwidth_metrics_dict["JPG DCS WR"]
        + bandwidth_metrics_dict["JPG0 DCS WR"]
        + bandwidth_metrics_dict["JPG1 DCS WR"]
        + bandwidth_metrics_dict["JPG2 DCS WR"]
        + bandwidth_metrics_dict["JPG3 DCS WR"]
    )
    bandwidth_metrics_dict["VENC DCS RD"] = (
        bandwidth_metrics_dict["VENC DCS RD"]
        + bandwidth_metrics_dict["VENC0 DCS RD"]
        + bandwidth_metrics_dict["VENC1 DCS RD"]
        + bandwidth_metrics_dict["VENC2 DCS RD"]
        + bandwidth_metrics_dict["VENC3 DCS RD"]
    )
    bandwidth_metrics_dict["VENC DCS WR"] = (
        bandwidth_metrics_dict["VENC DCS WR"]
        + bandwidth_metrics_dict["VENC0 DCS WR"]
        + bandwidth_metrics_dict["VENC1 DCS WR"]
        + bandwidth_metrics_dict["VENC2 DCS WR"]
        + bandwidth_metrics_dict["VENC3 DCS WR"]
    )
    bandwidth_metrics_dict["MEDIA DCS"] = sum(
        [
            bandwidth_metrics_dict["ISP DCS RD"],
            bandwidth_metrics_dict["ISP DCS WR"],
            bandwidth_metrics_dict["STRM CODEC DCS RD"],
            bandwidth_metrics_dict["STRM CODEC DCS WR"],
            bandwidth_metrics_dict["PRORES DCS RD"],
            bandwidth_metrics_dict["PRORES DCS WR"],
            bandwidth_metrics_dict["VDEC DCS RD"],
            bandwidth_metrics_dict["VDEC DCS WR"],
            bandwidth_metrics_dict["VENC DCS RD"],
            bandwidth_metrics_dict["VENC DCS WR"],
            bandwidth_metrics_dict["JPG DCS RD"],
            bandwidth_metrics_dict["JPG DCS WR"],
        ]
    )
    return bandwidth_metrics_dict


def parse_cpu_metrics(powermetrics_parse):
    cpu_metric_dict = {
        "E-Cluster_active": 0,
        "E-Cluster_freq_Mhz": 0,
        "P-Cluster_active": 0,
        "P-Cluster_freq_Mhz": 0,
        "ane_W": 0.0,
        "cpu_W": 0.0,
        "gpu_W": 0.0,
        "package_W": 0.0,
        "e_core": [],
        "p_core": [],
    }
    if not isinstance(powermetrics_parse, dict):
        return cpu_metric_dict

    cpu_metrics = powermetrics_parse.get("processor", {})
    clusters = cpu_metrics.get("clusters", [])
    e_cluster_active = []
    p_cluster_active = []
    e_cluster_freq = []
    p_cluster_freq = []

    for cluster in clusters:
        cluster_name = str(cluster.get("name", ""))
        if not cluster_name:
            continue
        is_e_cluster = cluster_name.startswith("E")
        is_p_cluster = cluster_name.startswith("P")
        cluster_prefix = "E-Cluster" if is_e_cluster else "P-Cluster"
        cluster_freq_mhz = _to_int(_to_float(cluster.get("freq_hz")) / 1e6)
        cluster_active = _active_percent(cluster.get("idle_ratio"))
        cpu_metric_dict[cluster_name + "_freq_Mhz"] = cluster_freq_mhz
        cpu_metric_dict[cluster_name + "_active"] = cluster_active

        if is_e_cluster:
            e_cluster_active.append(cluster_active)
            e_cluster_freq.append(cluster_freq_mhz)
        elif is_p_cluster:
            p_cluster_active.append(cluster_active)
            p_cluster_freq.append(cluster_freq_mhz)

        for cpu in cluster.get("cpus", []):
            cpu_index = _to_int(cpu.get("cpu"), default=-1)
            if cpu_index < 0:
                continue
            cpu_freq_mhz = _to_int(_to_float(cpu.get("freq_hz")) / 1e6)
            cpu_active = _active_percent(cpu.get("idle_ratio"))
            cpu_metric_dict[cluster_prefix + str(cpu_index) + "_freq_Mhz"] = (
                cpu_freq_mhz
            )
            cpu_metric_dict[cluster_prefix + str(cpu_index) + "_active"] = cpu_active
            if is_e_cluster:
                cpu_metric_dict["e_core"].append(cpu_index)
            elif is_p_cluster:
                cpu_metric_dict["p_core"].append(cpu_index)

    if e_cluster_active:
        cpu_metric_dict["E-Cluster_active"] = _to_int(
            sum(e_cluster_active) / len(e_cluster_active)
        )
        cpu_metric_dict["E-Cluster_freq_Mhz"] = _to_int(max(e_cluster_freq))
    if p_cluster_active:
        cpu_metric_dict["P-Cluster_active"] = _to_int(
            sum(p_cluster_active) / len(p_cluster_active)
        )
        cpu_metric_dict["P-Cluster_freq_Mhz"] = _to_int(max(p_cluster_freq))

    cpu_metric_dict["e_core"] = sorted(set(cpu_metric_dict["e_core"]))
    cpu_metric_dict["p_core"] = sorted(set(cpu_metric_dict["p_core"]))

    ane_energy = _to_float(cpu_metrics.get("ane_energy", 0.0))
    cpu_energy = _to_float(cpu_metrics.get("cpu_energy", 0.0))
    gpu_energy = _to_float(cpu_metrics.get("gpu_energy", 0.0))
    package_energy = cpu_metrics.get("combined_power")
    if package_energy is None:
        package_energy = ane_energy + cpu_energy + gpu_energy
    package_energy = _to_float(package_energy, 0.0)

    cpu_metric_dict["ane_W"] = ane_energy / 1000.0
    cpu_metric_dict["cpu_W"] = cpu_energy / 1000.0
    cpu_metric_dict["gpu_W"] = gpu_energy / 1000.0
    cpu_metric_dict["package_W"] = package_energy / 1000.0
    return cpu_metric_dict


def parse_gpu_metrics(powermetrics_parse):
    gpu_metrics = {}
    if isinstance(powermetrics_parse, dict):
        gpu_metrics = powermetrics_parse.get("gpu", {})
    freq_value = _to_float(gpu_metrics.get("freq_hz", 0.0))
    freq_mhz = _to_int(freq_value / 1e6) if freq_value > 100000 else _to_int(freq_value)
    gpu_metrics_dict = {
        "freq_MHz": freq_mhz,
        "active": _active_percent(gpu_metrics.get("idle_ratio")),
    }
    return gpu_metrics_dict
