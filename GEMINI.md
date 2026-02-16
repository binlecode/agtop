# Project Context: agtop

## Overview
`agtop` is a Python-based CLI performance monitoring tool specifically designed for Apple Silicon (M1/M2/M3/M4 chips). It provides a terminal dashboard similar to `nvtop` or `htop`, displaying real-time metrics for:
-   **CPU/GPU Utilization:** Usage per cluster (E-core/P-core) and frequency.
-   **Memory:** RAM usage, swap usage, and memory bandwidth (where available).
-   **Power:** Package, CPU, GPU, and ANE (Apple Neural Engine) power consumption.
-   **Hardware Info:** SoC model, core counts, and thermal pressure.

The tool relies on macOS native `powermetrics` utility (requiring `sudo`) to gather low-level hardware statistics.

## Architecture
The project is structured as a standard Python package.

### Core Components
-   **Entry Point (`agtop/agtop.py`):** Handles argument parsing, the main event loop, and UI rendering using the `dashing` library. It coordinates data fetching and display updates.
-   **Data Acquisition (`agtop/utils.py` & `agtop/parsers.py`):**
    -   `utils.py`: Wraps system calls to `powermetrics`, `sysctl`, and `system_profiler`.
    -   `parsers.py`: Parses the complex text/plist output from `powermetrics` into structured dictionaries.
-   **Hardware Profiles (`agtop/soc_profiles.py`):** Defines `SocProfile` dataclasses containing reference values (TDP, max bandwidth) for various Apple Silicon chips (M1-M4 families). It includes fallback logic for unknown "Pro", "Max", or "Ultra" variants.
-   **Scaling Logic (`agtop/power_scaling.py`):** Utilities for normalizing power readings against reference values for visualization.

## Development Workflow

### Prerequisites
-   macOS with Apple Silicon.
-   Python 3.
-   `sudo` access (for `powermetrics`).

### Environment Setup
Always use the local virtual environment `.venv`.
```bash
# Install in editable mode
.venv/bin/pip install -e .
```

### Building and Running
To run the tool during development:
```bash
# Run directly from source (requires sudo)
sudo .venv/bin/python -m agtop.agtop

# Common flags
sudo .venv/bin/python -m agtop.agtop --interval 1 --color 2
```

To build the package:
```bash
.venv/bin/python -m build
```

### Testing
The project uses `pytest` for testing logic that doesn't require live hardware (e.g., parsers and profiles).
```bash
.venv/bin/pytest -q
```

## Key Files
-   `agtop/agtop.py`: Main application logic and UI layout.
-   `agtop/soc_profiles.py`: Database of chip specifications.
-   `agtop/parsers.py`: Logic for interpreting `powermetrics` output.
-   `pyproject.toml`: Package configuration and dependencies.
-   `AGENTS.md`: Specific guidelines for AI agents and contributors.

## Conventions
-   **Code Style:** Follow standard Python (PEP 8) with 4-space indentation.
-   **Imports:** Keep imports clean and organized.
-   **Safety:** `powermetrics` requires root; be extremely cautious when modifying code that executes system commands with `sudo`.
-   **Commits:** Use imperative mood (e.g., "Add support for M3 Max", "Fix parser regex").
