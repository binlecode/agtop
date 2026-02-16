import re


def _to_float(value, default=0.0):
    try:
        if isinstance(value, str):
            normalized = value.strip()
            if normalized.endswith("%"):
                normalized = normalized[:-1].strip()
            if normalized == "":
                return float(default)
            return float(normalized)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _to_int(value, default=0):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return int(default)


def _normalize_ratio(value, default):
    ratio = _to_float(value, default=default)
    if ratio < 0.0:
        return 0.0
    if ratio > 1.0 and ratio <= 100.0:
        ratio = ratio / 100.0
    return min(1.0, ratio)


def _active_percent(idle_ratio, down_ratio=0.0):
    idle = _normalize_ratio(idle_ratio, default=1.0)
    down = _normalize_ratio(down_ratio, default=0.0)
    active = (1.0 - idle - down) * 100.0
    active = max(0.0, min(100.0, active))
    nearest_int = round(active)
    if abs(active - nearest_int) < 1e-6:
        active = float(nearest_int)
    return _to_int(active)


def parse_thermal_pressure(powermetrics_parse):
    if not isinstance(powermetrics_parse, dict):
        return "Unknown"
    return powermetrics_parse.get("thermal_pressure", "Unknown")


def parse_bandwidth_metrics(powermetrics_parse):
    required_fields = {
        "ECPU DCS RD": 0.0,
        "ECPU DCS WR": 0.0,
        "PCPU DCS RD": 0.0,
        "PCPU DCS WR": 0.0,
        "GFX DCS RD": 0.0,
        "GFX DCS WR": 0.0,
        "MEDIA DCS": 0.0,
        "DCS RD": 0.0,
        "DCS WR": 0.0,
        "_available": False,
    }
    if not isinstance(powermetrics_parse, dict):
        return dict(required_fields)

    counters_raw = powermetrics_parse.get("bandwidth_counters")
    counters = counters_raw if isinstance(counters_raw, (list, tuple)) else []
    if not isinstance(counters, (list, tuple)):
        counters = []

    bandwidth_metrics_dict = dict(required_fields)
    bandwidth_metrics_dict["_available"] = bool(isinstance(counters_raw, (list, tuple)))
    for metric_entry in counters:
        if not isinstance(metric_entry, dict):
            continue
        counter_name = metric_entry.get("name")
        if not isinstance(counter_name, str):
            continue
        bandwidth_metrics_dict[counter_name] = (
            _to_float(metric_entry.get("value")) / 1e9
        )

    def indexed_counter_sum(prefix, direction):
        pattern = re.compile(r"^{}\d+ DCS {}$".format(prefix, direction))
        return sum(
            value for key, value in bandwidth_metrics_dict.items() if pattern.match(key)
        )

    for prefix in ["ECPU", "PCPU", "VENC", "JPG"]:
        for direction in ["RD", "WR"]:
            aggregate_key = "{} DCS {}".format(prefix, direction)
            indexed_total = indexed_counter_sum(prefix, direction)
            bandwidth_metrics_dict[aggregate_key] = max(
                _to_float(bandwidth_metrics_dict.get(aggregate_key, 0.0)),
                _to_float(indexed_total),
            )

    media_rd_keys = [
        "ISP DCS RD",
        "STRM CODEC DCS RD",
        "PRORES DCS RD",
        "VDEC DCS RD",
        "VENC DCS RD",
        "JPG DCS RD",
    ]
    media_wr_keys = [
        "ISP DCS WR",
        "STRM CODEC DCS WR",
        "PRORES DCS WR",
        "VDEC DCS WR",
        "VENC DCS WR",
        "JPG DCS WR",
    ]
    media_rd = sum(
        _to_float(bandwidth_metrics_dict.get(key, 0.0)) for key in media_rd_keys
    )
    media_wr = sum(
        _to_float(bandwidth_metrics_dict.get(key, 0.0)) for key in media_wr_keys
    )
    bandwidth_metrics_dict["MEDIA DCS"] = media_rd + media_wr

    total_rd_fallback = (
        _to_float(bandwidth_metrics_dict.get("ECPU DCS RD", 0.0))
        + _to_float(bandwidth_metrics_dict.get("PCPU DCS RD", 0.0))
        + _to_float(bandwidth_metrics_dict.get("GFX DCS RD", 0.0))
        + media_rd
    )
    total_wr_fallback = (
        _to_float(bandwidth_metrics_dict.get("ECPU DCS WR", 0.0))
        + _to_float(bandwidth_metrics_dict.get("PCPU DCS WR", 0.0))
        + _to_float(bandwidth_metrics_dict.get("GFX DCS WR", 0.0))
        + media_wr
    )
    bandwidth_metrics_dict["DCS RD"] = max(
        _to_float(bandwidth_metrics_dict.get("DCS RD", 0.0)),
        total_rd_fallback,
    )
    bandwidth_metrics_dict["DCS WR"] = max(
        _to_float(bandwidth_metrics_dict.get("DCS WR", 0.0)),
        total_wr_fallback,
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

    cpu_metrics_raw = powermetrics_parse.get("processor", {})
    cpu_metrics = cpu_metrics_raw if isinstance(cpu_metrics_raw, dict) else {}
    clusters_raw = cpu_metrics.get("clusters", [])
    clusters = clusters_raw if isinstance(clusters_raw, (list, tuple)) else []
    e_cluster_active = []
    p_cluster_active = []
    e_cluster_freq = []
    p_cluster_freq = []
    e_core_active_values = []
    p_core_active_values = []

    for cluster in clusters:
        if not isinstance(cluster, dict):
            continue
        cluster_name = str(cluster.get("name", ""))
        if not cluster_name:
            continue
        is_e_cluster = cluster_name.startswith("E")
        is_p_cluster = cluster_name.startswith("P")
        cluster_prefix = (
            "E-Cluster" if is_e_cluster else "P-Cluster" if is_p_cluster else None
        )
        cluster_freq_mhz = _to_int(_to_float(cluster.get("freq_hz")) / 1e6)
        cluster_active = _active_percent(
            cluster.get("idle_ratio"), cluster.get("down_ratio", 0.0)
        )
        cpu_metric_dict[cluster_name + "_freq_Mhz"] = cluster_freq_mhz
        cpu_metric_dict[cluster_name + "_active"] = cluster_active

        if is_e_cluster:
            e_cluster_active.append(cluster_active)
            e_cluster_freq.append(cluster_freq_mhz)
        elif is_p_cluster:
            p_cluster_active.append(cluster_active)
            p_cluster_freq.append(cluster_freq_mhz)

        cpus_raw = cluster.get("cpus", [])
        cpus = cpus_raw if isinstance(cpus_raw, (list, tuple)) else []
        for cpu in cpus:
            if not isinstance(cpu, dict):
                continue
            if cluster_prefix is None:
                continue
            cpu_index = _to_int(cpu.get("cpu"), default=-1)
            if cpu_index < 0:
                continue
            cpu_freq_mhz = _to_int(_to_float(cpu.get("freq_hz")) / 1e6)
            cpu_active = _active_percent(
                cpu.get("idle_ratio"), cpu.get("down_ratio", 0.0)
            )
            cpu_metric_dict[cluster_prefix + str(cpu_index) + "_freq_Mhz"] = (
                cpu_freq_mhz
            )
            cpu_metric_dict[cluster_prefix + str(cpu_index) + "_active"] = cpu_active
            if is_e_cluster:
                cpu_metric_dict["e_core"].append(cpu_index)
                e_core_active_values.append(cpu_active)
            elif is_p_cluster:
                cpu_metric_dict["p_core"].append(cpu_index)
                p_core_active_values.append(cpu_active)

    if e_core_active_values:
        cpu_metric_dict["E-Cluster_active"] = _to_int(
            sum(e_core_active_values) / len(e_core_active_values)
        )
    elif e_cluster_active:
        cpu_metric_dict["E-Cluster_active"] = _to_int(
            sum(e_cluster_active) / len(e_cluster_active)
        )
    if p_core_active_values:
        cpu_metric_dict["P-Cluster_active"] = _to_int(
            sum(p_core_active_values) / len(p_core_active_values)
        )
    elif p_cluster_active:
        cpu_metric_dict["P-Cluster_active"] = _to_int(
            sum(p_cluster_active) / len(p_cluster_active)
        )
    if e_cluster_freq:
        cpu_metric_dict["E-Cluster_freq_Mhz"] = _to_int(max(e_cluster_freq))
    if p_cluster_freq:
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
        gpu_metrics_raw = powermetrics_parse.get("gpu", {})
        gpu_metrics = gpu_metrics_raw if isinstance(gpu_metrics_raw, dict) else {}
    freq_value = _to_float(gpu_metrics.get("freq_hz", 0.0))
    freq_mhz = _to_int(freq_value / 1e6) if freq_value > 100000 else _to_int(freq_value)
    gpu_metrics_dict = {
        "freq_MHz": freq_mhz,
        "active": _active_percent(gpu_metrics.get("idle_ratio")),
    }
    return gpu_metrics_dict
