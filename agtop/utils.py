import os
import re
import psutil
from .soc_profiles import get_soc_profile


def clear_console():
    command = "clear"
    os.system(command)


def convert_to_GB(value):
    return round(value / 1024 / 1024 / 1024, 1)


def get_ram_metrics_dict():
    vm = psutil.virtual_memory()
    total_bytes = vm.total
    used_bytes = vm.total - vm.available
    free_bytes = vm.available
    used_percent = (
        min(100, int(used_bytes / total_bytes * 100)) if total_bytes > 0 else 0
    )

    swap = psutil.swap_memory()
    if swap.total > 0:
        swap_used_percent = int(swap.used / swap.total * 100)
    else:
        swap_used_percent = None

    return {
        "total_GB": convert_to_GB(total_bytes),
        "free_GB": convert_to_GB(free_bytes),
        "used_GB": convert_to_GB(used_bytes),
        "used_percent": used_percent,
        "swap_total_GB": convert_to_GB(swap.total),
        "swap_used_GB": convert_to_GB(swap.used),
        "swap_free_GB": convert_to_GB(swap.total - swap.used),
        "swap_used_percent": swap_used_percent,
    }


def get_cpu_info():
    cpu_info_dict = {}
    data_fields = ["machdep.cpu.brand_string", "machdep.cpu.core_count"]
    for field in data_fields:
        try:
            value = os.popen("sysctl -n " + field).read().strip()
        except Exception:
            value = ""
        if value:
            cpu_info_dict[field] = value

    if "machdep.cpu.brand_string" not in cpu_info_dict:
        cpu_info = os.popen("sysctl -a | grep machdep.cpu").read()
        for line in cpu_info.split("\n"):
            if "machdep.cpu.brand_string" in line:
                cpu_info_dict["machdep.cpu.brand_string"] = line.split(":", 1)[
                    1
                ].strip()
            if "machdep.cpu.core_count" in line:
                cpu_info_dict["machdep.cpu.core_count"] = line.split(":", 1)[1].strip()
    return cpu_info_dict


def get_core_counts():
    cores_info_dict = {}
    for field in ["hw.perflevel0.logicalcpu", "hw.perflevel1.logicalcpu"]:
        try:
            value = os.popen("sysctl -n " + field).read().strip()
            if value:
                cores_info_dict[field] = int(value)
        except Exception:
            continue

    if not cores_info_dict:
        cores_info = os.popen("sysctl -a | grep hw.perflevel").read()
        for line in cores_info.split("\n"):
            if "hw.perflevel0.logicalcpu" in line:
                try:
                    cores_info_dict["hw.perflevel0.logicalcpu"] = int(
                        line.split(":", 1)[1].strip()
                    )
                except Exception:
                    pass
            if "hw.perflevel1.logicalcpu" in line:
                try:
                    cores_info_dict["hw.perflevel1.logicalcpu"] = int(
                        line.split(":", 1)[1].strip()
                    )
                except Exception:
                    pass
    return cores_info_dict


def get_gpu_cores():
    try:
        cores = os.popen(
            "system_profiler -detailLevel basic SPDisplaysDataType | grep 'Total Number of Cores'"
        ).read()
        cores = int(cores.split(": ")[-1])
    except Exception:
        cores = "?"
    return cores


def get_soc_info():
    cpu_info_dict = get_cpu_info()
    core_counts_dict = get_core_counts()
    name = cpu_info_dict.get("machdep.cpu.brand_string", "Apple Silicon")
    profile = get_soc_profile(name)
    e_core_count = int(core_counts_dict.get("hw.perflevel1.logicalcpu", 0))
    p_core_count = int(core_counts_dict.get("hw.perflevel0.logicalcpu", 0))
    core_count = int(cpu_info_dict.get("machdep.cpu.core_count", 0) or 0)
    if p_core_count == 0 and core_count > 0:
        p_core_count = core_count

    soc_info = {
        "name": profile.name,
        "core_count": core_count,
        "cpu_chart_ref_w": profile.cpu_chart_ref_w,
        "gpu_chart_ref_w": profile.gpu_chart_ref_w,
        "cpu_max_power": profile.cpu_chart_ref_w,
        "gpu_max_power": profile.gpu_chart_ref_w,
        "cpu_max_bw": profile.cpu_max_bw,
        "gpu_max_bw": profile.gpu_max_bw,
        "e_core_count": e_core_count,
        "p_core_count": p_core_count,
        "gpu_core_count": get_gpu_cores(),
    }
    return soc_info


def _normalize_process_command(cmdline, fallback_name):
    if isinstance(cmdline, (list, tuple)):
        command = " ".join(str(part) for part in cmdline if part)
    else:
        command = ""
    command = command.strip()
    if command:
        return command
    fallback = str(fallback_name or "").strip()
    return fallback if fallback else "?"


def get_top_processes(limit=3, proc_filter=None):
    pattern = None
    if proc_filter:
        if hasattr(proc_filter, "search"):
            pattern = proc_filter
        else:
            pattern = re.compile(str(proc_filter), re.IGNORECASE)

    entries = []
    for proc in psutil.process_iter(
        attrs=["pid", "name", "cmdline", "memory_info", "memory_percent"]
    ):
        try:
            info = proc.info
            command = _normalize_process_command(info.get("cmdline"), info.get("name"))
            if pattern and not pattern.search(command):
                continue
            cpu_percent = proc.cpu_percent(interval=None) or 0.0
            cpu_percent = max(0.0, float(cpu_percent))
            memory_info = info.get("memory_info")
            rss_bytes = getattr(memory_info, "rss", 0) if memory_info else 0
            rss_mb = max(0.0, float(rss_bytes) / 1024 / 1024)
            memory_percent = max(0.0, float(info.get("memory_percent") or 0.0))
            entries.append(
                {
                    "pid": int(info.get("pid") or 0),
                    "command": command,
                    "cpu_percent": round(cpu_percent, 1),
                    "rss_mb": round(rss_mb, 1),
                    "memory_percent": round(memory_percent, 1),
                }
            )
        except (
            psutil.NoSuchProcess,
            psutil.AccessDenied,
            psutil.ZombieProcess,
            ValueError,
            TypeError,
        ):
            continue

    top_cpu = sorted(
        entries,
        key=lambda item: (item["cpu_percent"], item["rss_mb"]),
        reverse=True,
    )[:limit]
    top_memory = sorted(
        entries,
        key=lambda item: (item["rss_mb"], item["memory_percent"]),
        reverse=True,
    )[:limit]
    return {"cpu": top_cpu, "memory": top_memory}
