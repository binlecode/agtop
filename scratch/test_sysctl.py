import ctypes

libc = ctypes.cdll.LoadLibrary("/usr/lib/libSystem.B.dylib")

# size_t size;
# sysctlbyname(const char *name, void *oldp, size_t *oldlenp, void *newp, size_t newlen);
sysctlbyname = libc.sysctlbyname
sysctlbyname.argtypes = [
    ctypes.c_char_p,
    ctypes.c_void_p,
    ctypes.POINTER(ctypes.c_size_t),
    ctypes.c_void_p,
    ctypes.c_size_t,
]
sysctlbyname.restype = ctypes.c_int


def get_sysctl_int(name):
    size = ctypes.c_size_t(8)
    val = ctypes.c_uint64(0)
    if (
        sysctlbyname(
            name.encode("utf-8"), ctypes.byref(val), ctypes.byref(size), None, 0
        )
        == 0
    ):
        if size.value == 4:
            return ctypes.c_uint32(val.value).value
        return val.value
    return None


def get_sysctl_string(name):
    size = ctypes.c_size_t(0)
    if sysctlbyname(name.encode("utf-8"), None, ctypes.byref(size), None, 0) == 0:
        buf = ctypes.create_string_buffer(size.value)
        if sysctlbyname(name.encode("utf-8"), buf, ctypes.byref(size), None, 0) == 0:
            return buf.value.decode("utf-8")
    return None


print("Brand:", get_sysctl_string("machdep.cpu.brand_string"))
print("Cores:", get_sysctl_int("machdep.cpu.core_count"))
print("P-Cores:", get_sysctl_int("hw.perflevel0.logicalcpu"))
print("E-Cores:", get_sysctl_int("hw.perflevel1.logicalcpu"))
