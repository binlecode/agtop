# REVIEW: Architecture and Feature Comparison (agtop vs mactop)

This document provides a detailed architectural breakdown of the reference `mactop` Go project and compares its feature set, design, and performance characteristics against the current `agtop` Python implementation.

## 1. Architectural Analysis of `mactop` (Go)

`mactop` is a highly optimized, compiled Go application that heavily leverages `cgo` (C/Objective-C interop) to achieve native-level performance and deep integration with macOS.

### Core Architectural Components

*   **Concurrency Model (Goroutines & Channels)**
    Unlike Python-based tools that often run in a synchronous event loop or rely on thread-pools, `mactop` embraces Go's concurrent design. The UI rendering runs on the main thread (managed by the `gotui` library), while data collection runs in parallel background goroutines (see `internal/app/metrics.go`). These background workers push data to the UI using Go channels (e.g., `cpuCh`, `gpuCh`, `processMetricsChan`), ensuring the terminal UI never freezes or lags during expensive system calls.
*   **Native C/Objective-C Bindings (`cgo`)**
    `mactop` bypasses command-line tools completely. It bundles `.c` and `.m` files directly inside the Go source tree and links against Apple's internal frameworks at compile time:
    *   **`ioreport.m`**: Directly binds to `<IOKit/IOKitLib.h>` and `libIOReport.dylib`. It natively subscribes to Energy and Performance states, calculates deltas in C, and passes a clean struct (`PowerMetrics`) back to Go space.
    *   **`smc.c` / `smc.h`**: Native Apple System Management Controller implementation to read die temperatures.
    *   **`processes.go`**: Utilizes the Mach kernel's `libproc.h` (`proc_listpids`, `proc_pidinfo`) natively, avoiding the overhead of external cross-platform libraries.
    *   **`native_stats.go`**: Uses `sysctlbyname` from `<sys/sysctl.h>` to instantly fetch memory, swap, and system configurations.
*   **UI & Rendering Engine**
    It uses the `gotui` (Go Terminal UI) library. This provides a rich, responsive grid layout system that handles window resizing, mouse events, and complex text overlays much faster than standard terminal string printing.
*   **Menubar Integration**
    A unique architectural feature of `mactop` is `menubar.m`, which imports `<AppKit/AppKit.h>`. It spawns a background thread running a native macOS `NSApplication` loop, allowing it to display real-time stats in the macOS top menu bar directly from the CLI binary.
*   **Extensibility & DevOps**
    It includes built-in endpoints for headless CI/CD operations (outputting JSON, YAML, CSV) and runs an embedded **Prometheus** metrics server (`github.com/prometheus/client_golang`) to expose hardware metrics to external scrapers.

---

## 2. Win-Score Card & Feature Comparison

While both tools aim to monitor Apple Silicon metrics via `IOReport`, their approaches, features, and target use cases differ significantly. Below is a head-to-head evaluation of their capabilities.

| Feature Category | `agtop` (Python) | `mactop` (Go) | Winner |
| :--- | :--- | :--- | :--- |
| **Language / Distribution** | Python via Homebrew (`brew tap`), `pip` | Compiled Go (single, standalone binary) | 🏆 **mactop** |
| **UI Library & UX** | `blessed` + `dashing` (gauges, charts, runtime sort/filter toggles) | `gotui` (rich grids, tabs, mouse support) | 🏆 **mactop** |
| **Low-Level API Efficiency** | `ctypes` binding `libIOReport`, `IOKit`, `sysctl` (Zero Subprocesses) | `cgo` (statically linked C/Objective-C) | 🤝 **Tie** |
| **Process Monitoring** | `psutil` (Python library overhead) | Native Mach `libproc` (C structs) | 🏆 **mactop** |
| **Hardware Data Coverage** | CPU, GPU, **ANE**, RAM, Swap, SMC Temps | CPU, GPU, RAM, Swap, **Net I/O, Disk I/O**, Temps | 🤝 **Tie** (ANE vs I/O) |
| **Peripheral Profiling** | None | USB, Displays, Thunderbolt, Storage | 🏆 **mactop** |
| **Power Scaling Intelligence**| Deep M1-M4 profiles (`soc_profiles.py`) | Dynamic scaling (recent peak observations) | 🏆 **agtop** |
| **Data Export / Headless** | Python API (`Profiler`, `to_pandas()`) | JSON, YAML, CSV, Prometheus Server | 🤝 **Tie** (Python API vs CLI exports) |
| **Desktop Integration** | Terminal only | Includes macOS Menubar app natively | 🏆 **mactop** |
| **Theming & Colors** | Adaptive TrueColor RGB gradients | Rich themes (Catppuccin) + Hex overrides | 🤝 **Tie** |
| **Extensibility / Hackability** | Dedicated `api.py` (sync/async/threaded profiling, alerts, DataFrames) | Requires Go/C knowledge to extend | 🏆 **agtop** |

### 🏆 Final Score
*   **mactop:** 5 Wins
*   **agtop:** 2 Wins
*   **Ties:** 4

### Verdict & Niche Breakdown

**`mactop` wins on broad DevOps features and UI richness.** Because it is a compiled Go binary using `cgo`, it boasts zero-dependency installation, much lower CPU overhead during process polling (due to native Mach calls vs `psutil`), and instantaneous startups. Its inclusion of network/disk I/O, a menubar app, rich interactive TUI features (mouse support, tabs), and a Prometheus server makes it a vastly superior tool for server monitoring, devops, and general power users.

**`agtop` has rapidly closed the gap in metrics fidelity and interactivity.**
With the `0.4.x` series, `agtop` has completely replaced all `powermetrics` subprocess calls with pure in-process `ctypes` bindings to `libIOReport`, `CoreFoundation`, `IOKit`, and `sysctl`, achieving near-native performance parity in hardware data collection without needing `sudo`. Furthermore, the addition of a `blessed` non-blocking input loop provides responsive runtime interactivity (e.g., toggling process sorts by CPU/Memory/PID and dynamic regex filtering).
1. **AI/ML Workloads:** `agtop` is one of the very few tools that specifically tracks and breaks out **ANE (Apple Neural Engine)** wattage, which is critical for ML engineers evaluating local CoreML models.
2. **Contextual Awareness:** `agtop`'s `soc_profiles.py` gives it a massive UX win for hardware awareness. When you run `agtop` on an M4 Max, the power charts scale precisely to the M4 Max's hardware limits out-of-the-box, giving the user immediate visual context on how hard they are pushing their specific chip.
3. **First-Class Python API:** `agtop` now exposes a robust public API (`agtop.api`) with synchronous (`Monitor`), asynchronous (`AsyncMonitor`), and threaded (`Profiler`) hardware metrics collection. This allows data scientists to seamlessly profile their model training loops, trigger custom callbacks on hardware thresholds, and export results directly to Pandas DataFrames (`to_pandas()`) for analysis—a massive advantage over standalone CLI binaries.