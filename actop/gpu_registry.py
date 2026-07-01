"""Per-process GPU time via IOKit ctypes bindings.

Reads accumulated GPU-busy time per process from the IOKit accelerator
registry without requiring sudo. Each open Metal context shows up as an
`AGXDeviceUserClient` child of the chip's `IOAccelerator`-class service,
exposing `IOUserClientCreator` ("pid <N>, <name>") and an `AppUsage` array
with a monotonic `accumulatedGPUTime` nanosecond counter per command queue --
the GPU analogue of the `cpu_time_ns` counter `native_sys.py` reads for CPU.

Self-contained by design: loads its own IOKit/CoreFoundation bindings rather
than importing from `smc.py` or `ioreport.py`, matching this codebase's
convention of independent, non-cross-importing native ctypes modules.
"""

import ctypes
import re
import sys

_DARWIN = sys.platform == "darwin"

if _DARWIN:
    _iokit = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/IOKit.framework/IOKit")
    _cf = ctypes.cdll.LoadLibrary(
        "/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation"
    )

    kCFStringEncodingUTF8 = 0x08000100
    kCFNumberSInt64Type = 4

    _iokit.IOServiceMatching.restype = ctypes.c_void_p
    _iokit.IOServiceMatching.argtypes = [ctypes.c_char_p]

    _iokit.IOServiceGetMatchingServices.restype = ctypes.c_int
    _iokit.IOServiceGetMatchingServices.argtypes = [
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_uint32),
    ]

    _iokit.IOIteratorNext.restype = ctypes.c_uint32
    _iokit.IOIteratorNext.argtypes = [ctypes.c_uint32]

    _iokit.IOObjectRelease.restype = ctypes.c_int
    _iokit.IOObjectRelease.argtypes = [ctypes.c_uint32]

    _iokit.IORegistryEntryGetChildIterator.restype = ctypes.c_int
    _iokit.IORegistryEntryGetChildIterator.argtypes = [
        ctypes.c_uint32,
        ctypes.c_char_p,
        ctypes.POINTER(ctypes.c_uint32),
    ]

    _iokit.IORegistryEntryCreateCFProperty.restype = ctypes.c_void_p
    _iokit.IORegistryEntryCreateCFProperty.argtypes = [
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_uint32,
    ]

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

    _cf.CFRelease.restype = None
    _cf.CFRelease.argtypes = [ctypes.c_void_p]

    _cf.CFArrayGetCount.restype = ctypes.c_long
    _cf.CFArrayGetCount.argtypes = [ctypes.c_void_p]

    _cf.CFArrayGetValueAtIndex.restype = ctypes.c_void_p
    _cf.CFArrayGetValueAtIndex.argtypes = [ctypes.c_void_p, ctypes.c_long]

    _cf.CFDictionaryGetValue.restype = ctypes.c_void_p
    _cf.CFDictionaryGetValue.argtypes = [ctypes.c_void_p, ctypes.c_void_p]

    _cf.CFNumberGetValue.restype = ctypes.c_bool
    _cf.CFNumberGetValue.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]

_CREATOR_PID_RE = re.compile(r"pid (\d+)")


def _cfstr(s):
    return _cf.CFStringCreateWithCString(None, s.encode("utf-8"), kCFStringEncodingUTF8)


def _from_cfstr(ref):
    if not ref:
        return ""
    buf = ctypes.create_string_buffer(1024)
    if _cf.CFStringGetCString(ref, buf, 1024, kCFStringEncodingUTF8):
        return buf.value.decode("utf-8", errors="replace")
    return ""


def _cfnumber_to_int(ref):
    if not ref:
        return 0
    out = ctypes.c_int64(0)
    if _cf.CFNumberGetValue(ref, kCFNumberSInt64Type, ctypes.byref(out)):
        return out.value
    return 0


def _client_gpu_time_and_pid(client):
    """Read (pid, accumulated_ns) off one accelerator child entry.

    pid is None when the entry has no IOUserClientCreator (not a Metal
    client), or when its value doesn't parse -- callers skip those.
    """
    creator_key = _cfstr("IOUserClientCreator")
    creator_ref = _iokit.IORegistryEntryCreateCFProperty(client, creator_key, None, 0)
    _cf.CFRelease(creator_key)

    pid = None
    if creator_ref:
        match = _CREATOR_PID_RE.search(_from_cfstr(creator_ref))
        if match:
            pid = int(match.group(1))
        _cf.CFRelease(creator_ref)

    usage_key = _cfstr("AppUsage")
    usage_ref = _iokit.IORegistryEntryCreateCFProperty(client, usage_key, None, 0)
    _cf.CFRelease(usage_key)

    total_ns = 0
    if usage_ref:
        accum_key = _cfstr("accumulatedGPUTime")
        for i in range(_cf.CFArrayGetCount(usage_ref)):
            entry = _cf.CFArrayGetValueAtIndex(usage_ref, i)
            total_ns += _cfnumber_to_int(_cf.CFDictionaryGetValue(entry, accum_key))
        _cf.CFRelease(accum_key)
        _cf.CFRelease(usage_ref)

    return pid, total_ns


def get_gpu_time_by_pid():
    """pid -> cumulative accumulatedGPUTime (ns) right now.

    Sums across every live Metal client for that pid, across every matched
    GPU accelerator service (a multi-die chip like M1/M2 Ultra may expose
    more than one). No caching -- callers delta this against a previous
    poll themselves, the same way native_sys.get_native_processes() exposes
    raw cpu_time_ns for utils.py to delta.

    Returns {} if no GPU accelerator service is found, or on non-Darwin
    platforms where IOKit is unavailable.
    """
    result = {}
    if not _DARWIN:
        return result

    # IOServiceMatching(b"IOAccelerator") matches by class inheritance, so it
    # reaches the chip-specific subclass (e.g. AGXAcceleratorG16X) without a
    # per-chip table.
    matching = _iokit.IOServiceMatching(b"IOAccelerator")
    if not matching:
        return result

    accel_iter = ctypes.c_uint32()
    # IOServiceGetMatchingServices consumes the matching dict -- do not
    # CFRelease it.
    kr = _iokit.IOServiceGetMatchingServices(0, matching, ctypes.byref(accel_iter))
    if kr != 0:
        return result

    while True:
        accel = _iokit.IOIteratorNext(accel_iter.value)
        if accel == 0:
            break

        client_iter = ctypes.c_uint32()
        kr = _iokit.IORegistryEntryGetChildIterator(
            accel, b"IOService", ctypes.byref(client_iter)
        )
        if kr == 0:
            while True:
                client = _iokit.IOIteratorNext(client_iter.value)
                if client == 0:
                    break
                pid, gpu_ns = _client_gpu_time_and_pid(client)
                if pid is not None and gpu_ns > 0:
                    result[pid] = result.get(pid, 0) + gpu_ns
                _iokit.IOObjectRelease(client)
            _iokit.IOObjectRelease(client_iter.value)

        _iokit.IOObjectRelease(accel)

    _iokit.IOObjectRelease(accel_iter.value)
    return result
