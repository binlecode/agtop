# TODO: Implement Native macOS Polling & Parity with mactop

This document outlines the concrete steps required to refactor `agtop` from relying on `psutil` to calling native macOS / Mach APIs directly via `ctypes`. This eliminates Python process-monitoring overhead, removes external dependencies, and adds missing network/disk I/O metrics.

---

## 1. Native API Bindings in `agtop/native_sys.py`

- [ ] **Define Swap Usage Structures (`vm.swapusage`)**
  - Implement the `XSWUsage` C-struct to query VM swap properties dynamically.
  - Bind `sysctlbyname` to parse `"vm.swapusage"` in-process.

- [ ] **Define Host Memory Structures (`host_statistics64`)**
  - Implement Mach VM statistics struct `VMStatistics64` (38 32-bit words).
  - Bind `mach_host_self()` and `host_statistics64` with flavor `HOST_VM_INFO64`.
  - Replicate Activity Monitor's RAM calculation algorithm:
    $$\text{Used RAM} = (\text{Internal} + \text{Wired} + \text{Compressed}) \times \text{Page Size}$$

- [ ] **Define Process Traversal Structures (`libproc.h`)**
  - Implement BSD process information structs: `ProcTaskInfo`, `BSDInfo`, and `ProcTaskAllInfo`.
  - Bind `/usr/lib/libSystem.B.dylib` methods:
    - `proc_listpids(type, typeinfo, buffer, buffersize)`
    - `proc_pidinfo(pid, flavor, arg, buffer, buffersize)`

- [ ] **Define Network Interface Structures (`getifaddrs`)**
  - Implement interface link structures: `SockAddr`, `IfData`, and `IfAddrs`.
  - Bind `getifaddrs` and `freeifaddrs` for socket connection traversals.

- [ ] **Define Disk Statistics (IOKit `IOBlockStorageDriver`)**
  - Add registry property search bindings to traverse device trees for disk operations.
  - Traverse IO Iterator to retrieve statistics dictionary containing `"Bytes Read"` and `"Bytes Written"`.

---

## 2. Refactor Metric Collections in `agtop/utils.py`

- [ ] **Implement `get_ram_metrics_dict` Refactoring**
  - Replace `psutil.virtual_memory()` and `psutil.swap_memory()` with `get_native_ram()` and `get_native_swap()`.
  - Format output metrics to match existing `agtop` schema.

- [ ] **Implement Process Polling Cache & Delta Calculators**
  - Create a module-level dictionary `_PROCESS_CPU_CACHE` storing `{pid: (total_ns, timestamp)}`.
  - Iterate active pids using `proc_listpids` and query their Task Stats via `proc_pidinfo`.
  - Compute precise process CPU utilization percentages using the timing differences.
  - Clean up stale dead PIDs from cache in each sweep.

- [ ] **Integrate Network and Disk Readers**
  - Expose aggregate metrics for network throughput and disk I/O.

---

## 3. UI and Rendering Integration

- [ ] **Create Network widget**
  - Display real-time input and output bandwidth values in the main TUI.

- [ ] **Create Disk widget**
  - Display aggregate reading and writing speeds in the layout.

---

## 4. Verification and Contract Testing

- [ ] **Create `tests/test_native_polling.py`**
  - Implement test contracts validating RAM calculations, process enumeration lists, and hardware interface structures.
  - Benchmark performance to verify target process polling latency remains under **1.5ms**.
