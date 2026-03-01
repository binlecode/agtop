import ctypes

libc = ctypes.cdll.LoadLibrary("/usr/lib/libSystem.B.dylib")
sysctlbyname = libc.sysctlbyname


def get_sysctl_int(name):
    size = ctypes.c_size_t(8)
    val = ctypes.c_uint64(0)
    if (
        sysctlbyname(
            name.encode("utf-8"), ctypes.byref(val), ctypes.byref(size), None, 0
        )
        == 0
    ):
        return val.value
    return None


print(
    "GPU cores:",
    get_sysctl_int("hw.perflevel2.logicalcpu") or get_sysctl_int("hw.gpu.core_count"),
)

import os  # noqa: E402
import time  # noqa: E402

start = time.time()
print(
    "system_profiler cores:",
    int(
        os.popen(
            "system_profiler -detailLevel basic SPDisplaysDataType | grep 'Total Number of Cores'"
        )
        .read()
        .split(": ")[-1]
    ),
)
print(f"Time: {time.time() - start:.3f}s")
