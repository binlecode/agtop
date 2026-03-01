# TODO: Refactor agtop for Native API Efficiency

## Overview
While `agtop` successfully maps the complex `IOReport` and `SMC` APIs directly using Python `ctypes`, it currently falls back to slow shell commands (`os.popen` and `subprocess.run`) for basic system configuration. This introduces startup latency (e.g., ~0.2-0.3 seconds per shell call at init time) compared to native C-level calls that complete in microseconds.

This document outlines the gaps and provides the detailed `ctypes` implementation strategies to achieve native C-level performance in pure Python.

---

## Call-Site Classification

| Gap | Function(s) | When called | Impact |
|-----|------------|-------------|--------|
| Gap 1 | `get_cpu_info()`, `get_core_counts()`, `_get_core_counts()` | Startup only (once) | Startup latency |
| Gap 2 | `get_gpu_cores()` | Startup only (once) | Startup latency |
| Gap 3 | `_read_dvfs_tables()` | Startup only (once) | Startup latency |

Only Gaps 1–3 are worth replacing. `get_top_processes()` (psutil) runs every tick but is deferred — see note at end of document.

---

## Priority Order

Implement in this order: **Gap 2 → Gap 1 → Gap 3**

Gap 2 (`system_profiler`) has the highest single-call cost (~0.25 s). Gap 1 (sysctl) is simple and enables Gap 3. Gap 3 (DVFS) depends on the IOKit handle setup from Gap 2.

---

## Gap 1: Over-reliance on Subprocesses for `sysctl`

### Current State
In `agtop/utils.py` and `agtop/sampler.py`, the code calls `os.popen("sysctl -n <key>").read()` or `subprocess.run(["sysctl"...])` to fetch CPU info, core counts, and system profile strings.

### Implementation Plan
Create a new utility module (`agtop/native_sys.py`) that binds `sysctlbyname` directly from `libSystem.B.dylib`.

> **Note on handles**: `_libc` / `libSystem.B.dylib` is already loaded in `smc.py`. `native_sys.py` may load its own handle — dylib loads are OS-cached, so there is no double-load cost — but should not import from `smc.py` to avoid circular dependencies. `_cf` (CoreFoundation) is already set up in `ioreport.py`; `native_sys.py` handles its own CF handle the same way.

```python
import ctypes

_libc = ctypes.cdll.LoadLibrary("/usr/lib/libSystem.B.dylib")
_sysctlbyname = _libc.sysctlbyname
_sysctlbyname.argtypes = [
    ctypes.c_char_p, ctypes.c_void_p,
    ctypes.POINTER(ctypes.c_size_t), ctypes.c_void_p, ctypes.c_size_t,
]
_sysctlbyname.restype = ctypes.c_int

def get_sysctl_int(name: str):
    size = ctypes.c_size_t(8)
    val = ctypes.c_uint64(0)
    if _sysctlbyname(name.encode(), ctypes.byref(val), ctypes.byref(size), None, 0) == 0:
        if size.value == 4:
            return ctypes.c_uint32(val.value).value
        return val.value
    return None

def get_sysctl_string(name: str):
    size = ctypes.c_size_t(0)
    if _sysctlbyname(name.encode(), None, ctypes.byref(size), None, 0) == 0:
        buf = ctypes.create_string_buffer(size.value)
        if _sysctlbyname(name.encode(), buf, ctypes.byref(size), None, 0) == 0:
            return buf.value.decode("utf-8")
            # Note: ctypes.create_string_buffer.value already strips trailing nulls;
            # no .strip('\x00') needed.
    return None
```

**Replacement Targets:**
- `machdep.cpu.brand_string` → `get_sysctl_string("machdep.cpu.brand_string")`
- `machdep.cpu.core_count` → `get_sysctl_int("machdep.cpu.core_count")`
- `hw.perflevel0.logicalcpu` → `get_sysctl_int("hw.perflevel0.logicalcpu")`
- `hw.perflevel1.logicalcpu` → `get_sysctl_int("hw.perflevel1.logicalcpu")`

---

## Gap 2: Extracting GPU Core Counts via `system_profiler`

### Current State
`get_gpu_cores()` in `agtop/utils.py` runs `system_profiler -detailLevel basic SPDisplaysDataType`. This is extremely slow (~0.25 seconds) and blocks initialization.

### Implementation Plan
Use `IOKit` to query the `IORegistry` for the `AGXAccelerator` service, which holds the `gpu-core-count` property. Use `IOServiceGetMatchingService` (singular — returns first match directly, simpler than the iterator pattern used in `smc.py`).

> **Note on handles**: Load a local `_cf` and `_iokit` handle in `native_sys.py` — the same pattern as `ioreport.py` and `smc.py`. Use `kCFStringEncodingUTF8 = 0x08000100` (matches the named constant in `ioreport.py:17`).

```python
import ctypes

_iokit = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/IOKit.framework/IOKit")
_cf = ctypes.cdll.LoadLibrary(
    "/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation"
)

# IOKit bindings
_iokit.IOServiceMatching.restype = ctypes.c_void_p
_iokit.IOServiceMatching.argtypes = [ctypes.c_char_p]
_iokit.IOServiceGetMatchingService.restype = ctypes.c_uint32
_iokit.IOServiceGetMatchingService.argtypes = [ctypes.c_uint32, ctypes.c_void_p]
_iokit.IORegistryEntryCreateCFProperty.restype = ctypes.c_void_p
_iokit.IORegistryEntryCreateCFProperty.argtypes = [
    ctypes.c_uint32, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32
]
_iokit.IOObjectRelease.restype = ctypes.c_int
_iokit.IOObjectRelease.argtypes = [ctypes.c_uint32]

# CoreFoundation bindings
kCFStringEncodingUTF8 = 0x08000100
_cf.CFStringCreateWithCString.restype = ctypes.c_void_p
_cf.CFStringCreateWithCString.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint32]
_cf.CFNumberGetValue.restype = ctypes.c_bool
_cf.CFNumberGetValue.argtypes = [ctypes.c_void_p, ctypes.c_int32, ctypes.c_void_p]
_cf.CFRelease.argtypes = [ctypes.c_void_p]
_cf.CFRelease.restype = None

def get_gpu_cores_native() -> int:
    matching = _iokit.IOServiceMatching(b"AGXAccelerator")
    service = _iokit.IOServiceGetMatchingService(0, matching)  # kIOMasterPortDefault=0
    if not service:
        return 0
    prop_name_cf = _cf.CFStringCreateWithCString(None, b"gpu-core-count", kCFStringEncodingUTF8)
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
```

---

## Gap 3: Extracting DVFS tables via `ioreg` CLI

### Current State
`_read_dvfs_tables()` in `agtop/sampler.py` uses `subprocess.run(["ioreg", ...])` and parses the output using `plistlib`. Parsing XML plists from a stdout pipe is high-overhead at startup.

### Implementation Plan
Use `IOKit` directly to find the `pmgr` service and read `voltage-states*` properties as raw `CFData` byte buffers. The byte-unpacking logic (`struct.unpack_from("<II", ...)`) and table classification logic are preserved exactly from `sampler.py:_read_dvfs_tables()` — only the data acquisition layer changes. This skips the XML/plist layer entirely.

Additional bindings needed beyond Gap 2:
- `IOServiceGetMatchingServices` + `IOIteratorNext` (iterator pattern from `smc.py`)
- `IORegistryEntryCreateCFProperties` → returns `CFMutableDictionaryRef` via out-param
- `CFDictionaryGetCount` + `CFDictionaryGetKeysAndValues` for dictionary iteration
- `CFGetTypeID`, `CFStringGetTypeID`, `CFDataGetTypeID` for type-safe dispatch
- `CFStringGetCString` to read key names
- `CFDataGetBytePtr` + `CFDataGetLength` to get raw bytes

```python
def get_dvfs_tables_native() -> dict:
    # 1. Find pmgr service under AppleARMIODevice
    matching = _iokit.IOServiceMatching(b"AppleARMIODevice")
    iterator = ctypes.c_uint32()
    _iokit.IOServiceGetMatchingServices(0, matching, ctypes.byref(iterator))

    props_ref = ctypes.c_void_p()
    found = False
    service = _iokit.IOIteratorNext(iterator.value)
    while service:
        name_buf = ctypes.create_string_buffer(128)
        _iokit.IORegistryEntryGetName(service, name_buf)
        if name_buf.value == b"pmgr":
            # 2. IORegistryEntryCreateCFProperties -> CFMutableDictionaryRef
            _iokit.IORegistryEntryCreateCFProperties(service, ctypes.byref(props_ref), None, 0)
            _iokit.IOObjectRelease(service)
            found = True
            break
        _iokit.IOObjectRelease(service)
        service = _iokit.IOIteratorNext(iterator.value)
    _iokit.IOObjectRelease(iterator.value)

    if not found or not props_ref.value:
        return {"ecpu": [], "pcpu": [], "gpu": []}

    # 3. Iterate dictionary keys/values
    count = _cf.CFDictionaryGetCount(props_ref)
    keys_arr = (ctypes.c_void_p * count)()
    vals_arr = (ctypes.c_void_p * count)()
    _cf.CFDictionaryGetKeysAndValues(props_ref, keys_arr, vals_arr)

    cf_string_type = _cf.CFStringGetTypeID()
    cf_data_type = _cf.CFDataGetTypeID()

    tables = {}
    for i in range(count):
        key_ref = keys_arr[i]
        val_ref = vals_arr[i]
        if not key_ref or not val_ref:
            continue
        # 4. Type-check key (CFString) and value (CFData)
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
        # 5. Extract raw bytes from CFData
        length = _cf.CFDataGetLength(val_ref)
        if length < 8:
            continue
        ptr = _cf.CFDataGetBytePtr(val_ref)
        raw = (ctypes.c_char * length).from_address(ptr)[:]
        # 6. Unpack (same logic as current sampler.py)
        n_entries = length // 8
        freqs = []
        for j in range(n_entries):
            freq_hz, _voltage = struct.unpack_from("<II", raw, j * 8)
            freqs.append(freq_hz // 1_000_000)
        real_count = sum(1 for f in freqs if f > 50)
        if real_count >= max(1, len(freqs) // 2):
            tables[key_name] = freqs

    _cf.CFRelease(props_ref)

    # 7. Classify tables (same logic as current sampler.py)
    # ... (pcpu: most entries + highest max freq; ecpu: 5-12 entries; gpu: 10-20 entries)
    return _classify_dvfs_tables(tables)
```

---

## Gap 4 (Deferred): Process Polling Overhead (`psutil` vs Mach `libproc`)

`get_top_processes()` uses `psutil.process_iter()` and runs **every tick**. However, at ≥2 s intervals the per-tick psutil overhead is immeasurable in practice: psutil already wraps the same Mach `proc_pidinfo` calls internally, and implementing a replacement requires maintaining a `{pid: prev_cpu_ns}` delta map plus separate name lookups — high complexity for no measurable benefit at typical monitoring intervals.

**Decision**: Deferred indefinitely. Do not implement.
