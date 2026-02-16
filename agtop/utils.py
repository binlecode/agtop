import os
import glob
import subprocess
from subprocess import PIPE
import psutil
from .parsers import parse_cpu_metrics, parse_gpu_metrics, parse_thermal_pressure
from .soc_profiles import get_soc_profile
import plistlib


def parse_powermetrics(path="/tmp/agtop_powermetrics", timecode="0"):
    data = None
    try:
        with open(path + timecode, "rb") as fp:
            data = fp.read()
        data = data.split(b"\x00")
        powermetrics_parse = plistlib.loads(data[-1])
        thermal_pressure = parse_thermal_pressure(powermetrics_parse)
        cpu_metrics_dict = parse_cpu_metrics(powermetrics_parse)
        gpu_metrics_dict = parse_gpu_metrics(powermetrics_parse)
        # bandwidth_metrics = parse_bandwidth_metrics(powermetrics_parse)
        bandwidth_metrics = None
        timestamp = powermetrics_parse.get("timestamp", 0)
        return (
            cpu_metrics_dict,
            gpu_metrics_dict,
            thermal_pressure,
            bandwidth_metrics,
            timestamp,
        )
    except Exception:
        if data:
            if len(data) > 1:
                try:
                    powermetrics_parse = plistlib.loads(data[-2])
                    thermal_pressure = parse_thermal_pressure(powermetrics_parse)
                    cpu_metrics_dict = parse_cpu_metrics(powermetrics_parse)
                    gpu_metrics_dict = parse_gpu_metrics(powermetrics_parse)
                    # bandwidth_metrics = parse_bandwidth_metrics(powermetrics_parse)
                    bandwidth_metrics = None
                    timestamp = powermetrics_parse.get("timestamp", 0)
                    return (
                        cpu_metrics_dict,
                        gpu_metrics_dict,
                        thermal_pressure,
                        bandwidth_metrics,
                        timestamp,
                    )
                except Exception:
                    return False
        return False


def clear_console():
    command = "clear"
    os.system(command)


def convert_to_GB(value):
    return round(value / 1024 / 1024 / 1024, 1)


def run_powermetrics_process(timecode, nice=10, interval=1000):
    # ver, *_ = platform.mac_ver()
    # major_ver = int(ver.split(".")[0])
    for tmpf in glob.glob("/tmp/agtop_powermetrics*"):
        try:
            os.remove(tmpf)
        except (FileNotFoundError, PermissionError, IsADirectoryError):
            pass
    output_file_flag = "-o"
    command = " ".join(
        [
            "sudo nice -n",
            str(nice),
            "powermetrics",
            "--samplers cpu_power,gpu_power,thermal",
            output_file_flag,
            "/tmp/agtop_powermetrics" + timecode,
            "-f plist",
            "-i",
            str(interval),
        ]
    )
    process = subprocess.Popen(command.split(" "), stdin=PIPE, stdout=PIPE)
    return process


def get_ram_metrics_dict():
    ram_metrics = psutil.virtual_memory()
    swap_metrics = psutil.swap_memory()
    total_GB = convert_to_GB(ram_metrics.total)
    free_GB = convert_to_GB(ram_metrics.available)
    used_GB = convert_to_GB(ram_metrics.total - ram_metrics.available)
    swap_total_GB = convert_to_GB(swap_metrics.total)
    swap_used_GB = convert_to_GB(swap_metrics.used)
    swap_free_GB = convert_to_GB(swap_metrics.total - swap_metrics.used)
    if swap_total_GB > 0:
        swap_free_percent = int(100 - (swap_free_GB / swap_total_GB * 100))
    else:
        swap_free_percent = None
    ram_metrics_dict = {
        "total_GB": round(total_GB, 1),
        "free_GB": round(free_GB, 1),
        "used_GB": round(used_GB, 1),
        "free_percent": int(100 - (ram_metrics.available / ram_metrics.total * 100)),
        "swap_total_GB": swap_total_GB,
        "swap_used_GB": swap_used_GB,
        "swap_free_GB": swap_free_GB,
        "swap_free_percent": swap_free_percent,
    }
    return ram_metrics_dict


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
