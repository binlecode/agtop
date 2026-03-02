# TODO: agtop Python API Level Support Refactor

## Vision
To survive and thrive alongside `mactop`, `agtop` must pivot its architecture to become the **Standard Python Hardware Profiling Library for Apple Silicon**. The TUI/CLI should become just *one* consumer of a robust, stable, and developer-friendly public Python API. 

This document outlines the exact implementation steps to build a high-level Python API tailored for Data Scientists, ML Engineers, and Backend Developers.

---

## Phase 1: Core API Facade & Data Structures
Currently, `sampler.py` returns a complex `SampleResult` NamedTuple heavily nested with dictionaries intended for the `dashing` UI. We need a clean, typed dataclass.

- [ ] **Create `agtop/models.py`**: Define clean, public-facing dataclasses.
  ```python
  from dataclasses import dataclass
  from typing import List, Optional

  @dataclass
  class SystemSnapshot:
      timestamp: float
      cpu_watts: float
      gpu_watts: float
      ane_watts: float
      package_watts: float
      cpu_temp_c: float
      gpu_temp_c: float
      ram_used_gb: float
      swap_used_gb: float
      thermal_state: str
      # ... plus detailed core frequencies if needed
  ```
- [ ] **Create `agtop/api.py`**: This will be the main entry point for developers.
- [ ] **Implement `agtop.Monitor` class**: A synchronous wrapper around `IOReportSampler`.
  ```python
  class Monitor:
      def __init__(self, interval_ms: int = 1000):
          # Initialize underlying sampler and utils
          pass
          
      def get_snapshot(self) -> SystemSnapshot:
          # Calls sampler.sample() and utils.get_ram_metrics_dict()
          # Maps internal dictionaries to the clean SystemSnapshot dataclass
          pass
  ```
- [ ] **Expose in `agtop/__init__.py`**:
  ```python
  from .api import Monitor, Profiler
  from .models import SystemSnapshot
  __all__ = ["Monitor", "Profiler", "SystemSnapshot"]
  ```

---

## Phase 2: The ML Benchmarking Context Manager
ML engineers need to wrap blocks of code (like PyTorch epochs) to measure power draw and energy consumption. This requires a threaded background collector.

- [ ] **Implement `agtop.Profiler` class in `api.py`**:
  ```python
  import threading
  import time

  class Profiler:
      def __init__(self, interval_ms: int = 100):
          self.interval = interval_ms / 1000.0
          self._monitor = Monitor(interval_ms)
          self._samples: List[SystemSnapshot] = []
          self._stop_event = threading.Event()
          self._thread = None

      def __enter__(self):
          self.start()
          return self

      def __exit__(self, exc_type, exc_val, exc_tb):
          self.stop()

      def start(self):
          self._samples.clear()
          self._stop_event.clear()
          self._thread = threading.Thread(target=self._run_loop, daemon=True)
          self._thread.start()

      def stop(self):
          self._stop_event.set()
          if self._thread:
              self._thread.join()

      def _run_loop(self):
          while not self._stop_event.is_set():
              self._samples.append(self._monitor.get_snapshot())
              time.sleep(self.interval) # Or use the sampler's blocking delay

      def get_summary(self) -> dict:
          # Calculate peak power, average power, total joules (avg_power * duration)
          pass
  ```

---

## Phase 3: Data Science Integrations (Pandas)
Data scientists need data in a format ready for Matplotlib, Seaborn, or Jupyter Notebooks.

- [ ] **Implement `to_pandas()` in `Profiler`**:
  ```python
  def to_pandas(self):
      """Exports collected samples to a Pandas DataFrame.
      Requires 'pandas' to be installed.
      """
      try:
          import pandas as pd
      except ImportError:
          raise ImportError("pandas is required for this feature: pip install pandas")
          
      # Convert List[SystemSnapshot] to a list of dicts, then to DataFrame
      df = pd.DataFrame([vars(s) for s in self._samples])
      # Set datetime index
      df['datetime'] = pd.to_datetime(df['timestamp'], unit='s')
      df.set_index('datetime', inplace=True)
      return df
  ```

---

## Phase 4: AsyncIO Support & Event Callbacks
For developers integrating `agtop` into FastAPI servers, Discord bots, or background daemons.

- [ ] **Implement Async support in `api.py`**:
  ```python
  import asyncio

  class AsyncMonitor(Monitor):
      async def get_snapshot_async(self) -> SystemSnapshot:
          # Run the blocking C-API calls in a ThreadPoolExecutor
          loop = asyncio.get_running_loop()
          return await loop.run_in_executor(None, self.get_snapshot)
  ```
- [ ] **Implement Threshold Callbacks in `Profiler`**:
  ```python
  def register_alert(self, metric: str, threshold: float, callback: callable):
      """
      Example: profiler.register_alert('cpu_temp_c', 95.0, lambda val: print("CPU overheating!"))
      """
      pass
  # Update `_run_loop` to check conditions and fire callbacks safely.
  ```

---

## Phase 5: Dogfooding (TUI Refactor)
To prove the API is robust, the internal CLI/TUI must be rewritten to consume it instead of calling `sampler.py` directly.

- [ ] **Refactor `agtop.py` (Main Loop)**:
  Replace direct `sampler.sample()` and `utils.get_soc_info()` calls with the new `agtop.Monitor` class.
- [ ] **Update Widget Data Bindings**:
  Update `dashing` widgets to read from `SystemSnapshot` dataclass attributes (e.g., `snapshot.cpu_watts`) instead of magic string dictionary keys (e.g., `metrics["cpu_W"]`).
- [ ] Ensure the CLI performance does not degrade during this refactor.

---

## Phase 6: Documentation & Examples
A public API is useless without documentation.

- [ ] **Create `examples/` directory**:
  - `examples/basic_monitor.py` (Simple while loop printing ANE/GPU power)
  - `examples/ml_pytorch_profiler.py` (Mock ML training loop using Context Manager)
  - `examples/jupyter_pandas_plot.ipynb` (Notebook showing `to_pandas().plot()`)
- [ ] **Update `README.md`**:
  Add a massive new section highlighting `agtop` as a Python Library, showing the `with agtop.Profiler():` snippet front and center.
- [ ] **Add Docstrings**: Ensure all public classes/methods in `models.py` and `api.py` have Sphinx/Google style docstrings.
