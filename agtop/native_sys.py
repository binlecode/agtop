"""Native system information via ctypes — no subprocess required.

Provides sysctl, IOKit GPU core count, and IOKit DVFS table reads using
direct C library bindings. All calls are startup-time only (called once
at sampler/utils initialisation).

Dylib handles are module-level singletons; the OS caches dylib loads so
loading the same path in multiple modules has no additional cost.

All public functions return None/0/{} on non-Darwin platforms so that
importing this module does not break CI or cross-platform tooling.
"""

import ctypes
import struct
import sys

_DARWIN = sys.platform == "darwin"

# ---------------------------------------------------------------------------
# libSystem (sysctl) — macOS only
# ---------------------------------------------------------------------------

if _DARWIN:
    _libc = ctypes.cdll.LoadLibrary("/usr/lib/libSystem.B.dylib")

    # ObjC runtime + Foundation (for NSProcessInfo.thermalState)
    _objc = ctypes.cdll.LoadLibrary("/usr/lib/libobjc.A.dylib")
    ctypes.cdll.LoadLibrary(
        "/System/Library/Frameworks/Foundation.framework/Foundation"
    )

    _objc.objc_getClass.restype = ctypes.c_void_p
    _objc.objc_getClass.argtypes = [ctypes.c_char_p]
    _objc.sel_registerName.restype = ctypes.c_void_p
    _objc.sel_registerName.argtypes = [ctypes.c_char_p]

    _send_ptr = ctypes.cast(_objc.objc_msgSend, ctypes.c_void_p).value
    _msg_send_obj = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(
        _send_ptr
    )
    _msg_send_int = ctypes.CFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_void_p)(
        _send_ptr
    )

    _cls_NSProcessInfo = _objc.objc_getClass(b"NSProcessInfo")
    _sel_processInfo = _objc.sel_registerName(b"processInfo")
    _sel_thermalState = _objc.sel_registerName(b"thermalState")

    _sysctlbyname = _libc.sysctlbyname
    _sysctlbyname.argtypes = [
        ctypes.c_char_p,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_size_t),
        ctypes.c_void_p,
        ctypes.c_size_t,
    ]
    _sysctlbyname.restype = ctypes.c_int

    # IOKit + CoreFoundation
    _iokit = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/IOKit.framework/IOKit")
    _cf = ctypes.cdll.LoadLibrary(
        "/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation"
    )

    kCFStringEncodingUTF8 = 0x08000100

    # IOKit
    _iokit.IOServiceMatching.restype = ctypes.c_void_p
    _iokit.IOServiceMatching.argtypes = [ctypes.c_char_p]

    _iokit.IOServiceGetMatchingService.restype = ctypes.c_uint32
    _iokit.IOServiceGetMatchingService.argtypes = [ctypes.c_uint32, ctypes.c_void_p]

    _iokit.IOServiceGetMatchingServices.restype = ctypes.c_int
    _iokit.IOServiceGetMatchingServices.argtypes = [
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_uint32),
    ]

    _iokit.IOIteratorNext.restype = ctypes.c_uint32
    _iokit.IOIteratorNext.argtypes = [ctypes.c_uint32]

    _iokit.IORegistryEntryGetName.restype = ctypes.c_int
    _iokit.IORegistryEntryGetName.argtypes = [ctypes.c_uint32, ctypes.c_char_p]

    _iokit.IORegistryEntryCreateCFProperty.restype = ctypes.c_void_p
    _iokit.IORegistryEntryCreateCFProperty.argtypes = [
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_uint32,
    ]

    _iokit.IORegistryEntryCreateCFProperties.restype = ctypes.c_int
    _iokit.IORegistryEntryCreateCFProperties.argtypes = [
        ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.c_void_p,
        ctypes.c_uint32,
    ]

    _iokit.IOObjectRelease.restype = ctypes.c_int
    _iokit.IOObjectRelease.argtypes = [ctypes.c_uint32]

    # CoreFoundation
    _cf.CFRelease.argtypes = [ctypes.c_void_p]
    _cf.CFRelease.restype = None

    _cf.CFStringCreateWithCString.restype = ctypes.c_void_p
    _cf.CFStringCreateWithCString.argtypes = [
        ctypes.c_void_p,
        ctypes.c_char_p,
        ctypes.c_uint32,
    ]

    _cf.CFStringGetCString.restype = ctypes.c_bool
    _cf.CFStringGetCString.argtypes = [
        ctypes.c_void_p,
        ctypes.c_char_p,
        ctypes.c_long,
        ctypes.c_uint32,
    ]

    _cf.CFNumberGetValue.restype = ctypes.c_bool
    _cf.CFNumberGetValue.argtypes = [ctypes.c_void_p, ctypes.c_int32, ctypes.c_void_p]

    _cf.CFDictionaryGetCount.restype = ctypes.c_long
    _cf.CFDictionaryGetCount.argtypes = [ctypes.c_void_p]

    _cf.CFDictionaryGetKeysAndValues.restype = None
    _cf.CFDictionaryGetKeysAndValues.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
    ]

    _cf.CFGetTypeID.restype = ctypes.c_ulong
    _cf.CFGetTypeID.argtypes = [ctypes.c_void_p]

    _cf.CFStringGetTypeID.restype = ctypes.c_ulong
    _cf.CFStringGetTypeID.argtypes = []

    _cf.CFDataGetTypeID.restype = ctypes.c_ulong
    _cf.CFDataGetTypeID.argtypes = []

    _cf.CFDataGetLength.restype = ctypes.c_long
    _cf.CFDataGetLength.argtypes = [ctypes.c_void_p]

    _cf.CFDataGetBytePtr.restype = ctypes.c_size_t
    _cf.CFDataGetBytePtr.argtypes = [ctypes.c_void_p]


_THERMAL_STATES = {0: "Nominal", 1: "Fair", 2: "Serious", 3: "Critical"}


# ---------------------------------------------------------------------------
# Thermal pressure (NSProcessInfo.thermalState)
# ---------------------------------------------------------------------------


def get_thermal_pressure() -> str:
    """Return macOS thermal pressure state via NSProcessInfo.

    Returns one of "Nominal", "Fair", "Serious", "Critical", or "Unknown".
    No sudo required; reads the same value the OS exposes to all processes.
    """
    if not _DARWIN:
        return "Unknown"
    try:
        process_info = _msg_send_obj(_cls_NSProcessInfo, _sel_processInfo)
        state = _msg_send_int(process_info, _sel_thermalState)
        return _THERMAL_STATES.get(state, "Unknown")
    except Exception:
        return "Unknown"


# ---------------------------------------------------------------------------
# sysctl helpers
# ---------------------------------------------------------------------------


def get_sysctl_int(name: str):
    """Return an integer sysctl value, or None on failure / non-Darwin."""
    if not _DARWIN:
        return None
    size = ctypes.c_size_t(8)
    val = ctypes.c_uint64(0)
    if (
        _sysctlbyname(name.encode(), ctypes.byref(val), ctypes.byref(size), None, 0)
        == 0
    ):
        if size.value == 4:
            return ctypes.c_uint32(val.value).value
        return val.value
    return None


def get_sysctl_string(name: str):
    """Return a string sysctl value, or None on failure / non-Darwin."""
    if not _DARWIN:
        return None
    size = ctypes.c_size_t(0)
    if _sysctlbyname(name.encode(), None, ctypes.byref(size), None, 0) == 0:
        buf = ctypes.create_string_buffer(size.value)
        if _sysctlbyname(name.encode(), buf, ctypes.byref(size), None, 0) == 0:
            return buf.value.decode("utf-8")
    return None


# ---------------------------------------------------------------------------
# GPU core count
# ---------------------------------------------------------------------------


def get_gpu_cores_native() -> int:
    """Return GPU core count from IORegistry AGXAccelerator, or 0 on failure."""
    if not _DARWIN:
        return 0
    matching = _iokit.IOServiceMatching(b"AGXAccelerator")
    service = _iokit.IOServiceGetMatchingService(0, matching)
    if not service:
        return 0
    prop_name_cf = _cf.CFStringCreateWithCString(
        None, b"gpu-core-count", kCFStringEncodingUTF8
    )
    cf_num = _iokit.IORegistryEntryCreateCFProperty(service, prop_name_cf, None, 0)
    cores = 0
    if cf_num:
        val = ctypes.c_int32(0)
        if _cf.CFNumberGetValue(cf_num, 3, ctypes.byref(val)):  # kCFNumberSInt32Type=3
            cores = val.value
        _cf.CFRelease(cf_num)
    _cf.CFRelease(prop_name_cf)
    _iokit.IOObjectRelease(service)
    return cores


# ---------------------------------------------------------------------------
# DVFS frequency tables
# ---------------------------------------------------------------------------


def get_dvfs_tables_native() -> dict:
    """Read DVFS frequency tables from IOKit pmgr device.

    Returns dict with keys 'ecpu', 'pcpu', 'gpu', each a list of
    MHz values in ascending frequency order (indexed by V-state or P-state).
    Returns {'ecpu': [], 'pcpu': [], 'gpu': []} on failure or non-Darwin.
    """
    if not _DARWIN:
        return {"ecpu": [], "pcpu": [], "gpu": []}

    matching = _iokit.IOServiceMatching(b"AppleARMIODevice")
    iterator = ctypes.c_uint32()
    ret = _iokit.IOServiceGetMatchingServices(0, matching, ctypes.byref(iterator))
    if ret != 0:
        return {"ecpu": [], "pcpu": [], "gpu": []}

    props_ref = ctypes.c_void_p()
    service = _iokit.IOIteratorNext(iterator.value)
    while service:
        name_buf = ctypes.create_string_buffer(128)
        _iokit.IORegistryEntryGetName(service, name_buf)
        if name_buf.value == b"pmgr":
            _iokit.IORegistryEntryCreateCFProperties(
                service, ctypes.byref(props_ref), None, 0
            )
            _iokit.IOObjectRelease(service)
            break
        _iokit.IOObjectRelease(service)
        service = _iokit.IOIteratorNext(iterator.value)
    _iokit.IOObjectRelease(iterator.value)

    if not props_ref.value:
        return {"ecpu": [], "pcpu": [], "gpu": []}

    count = _cf.CFDictionaryGetCount(props_ref)
    keys_arr = (ctypes.c_void_p * count)()
    vals_arr = (ctypes.c_void_p * count)()
    _cf.CFDictionaryGetKeysAndValues(
        props_ref,
        ctypes.cast(keys_arr, ctypes.c_void_p),
        ctypes.cast(vals_arr, ctypes.c_void_p),
    )

    cf_string_type = _cf.CFStringGetTypeID()
    cf_data_type = _cf.CFDataGetTypeID()

    tables = {}
    for i in range(count):
        key_ref = keys_arr[i]
        val_ref = vals_arr[i]
        if not key_ref or not val_ref:
            continue
        if _cf.CFGetTypeID(key_ref) != cf_string_type:
            continue
        if _cf.CFGetTypeID(val_ref) != cf_data_type:
            continue
        key_buf = ctypes.create_string_buffer(128)
        if not _cf.CFStringGetCString(key_ref, key_buf, 128, kCFStringEncodingUTF8):
            continue
        key_name = key_buf.value.decode("utf-8")
        if not key_name.startswith("voltage-states"):
            continue
        length = _cf.CFDataGetLength(val_ref)
        if length < 8:
            continue
        ptr = _cf.CFDataGetBytePtr(val_ref)
        raw = (ctypes.c_char * length).from_address(ptr)[:]
        n_entries = length // 8
        freqs = []
        for j in range(n_entries):
            freq_hz, _voltage = struct.unpack_from("<II", raw, j * 8)
            freqs.append(freq_hz // 1_000_000)
        real_count = sum(1 for f in freqs if f > 50)
        if real_count >= max(1, len(freqs) // 2):
            tables[key_name] = freqs

    _cf.CFRelease(props_ref)

    return _classify_dvfs_tables(tables)


def _classify_dvfs_tables(tables: dict) -> dict:
    """Classify raw voltage-states tables into ecpu/pcpu/gpu buckets.

    Replicates the classification logic from sampler.py:_read_dvfs_tables().
    """
    ecpu = []
    pcpu = []
    gpu = []

    candidates = sorted(tables.items())

    # P-core: highest max frequency (>2 GHz), most entries (>=15)
    best_pcpu_key = None
    best_pcpu_max = 0
    for key, freqs in candidates:
        max_freq = max(freqs) if freqs else 0
        if len(freqs) >= 15 and max_freq > best_pcpu_max:
            best_pcpu_max = max_freq
            best_pcpu_key = key
    if best_pcpu_key:
        pcpu = tables[best_pcpu_key]

    # E-core: small table (5-12 entries), not the pcpu table
    for key, freqs in candidates:
        if key == best_pcpu_key:
            continue
        if 5 <= len(freqs) <= 12:
            ecpu = freqs
            break

    # GPU: 10-20 entries, not pcpu or ecpu table, first match
    for key, freqs in candidates:
        if key == best_pcpu_key:
            continue
        if freqs is ecpu:
            continue
        if 10 <= len(freqs) <= 20:
            gpu = freqs
            break

    return {"ecpu": ecpu, "pcpu": pcpu, "gpu": gpu}
