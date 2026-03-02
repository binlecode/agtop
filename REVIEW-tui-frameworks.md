# REVIEW: TUI Framework Evaluation for `agtop`

## 1. Context and Objective

In the `REVIEW-architecture-comparison.md`, it was identified that the reference Go implementation (`mactop`) holds a distinct advantage in UI richness, interactivity, and rendering concurrency. Specifically, `mactop` utilizes `gotui` to provide complex grid layouts, tabs, mouse support, and background goroutines that prevent the terminal UI from freezing during expensive system calls.

Currently, `agtop` uses a combination of `blessed` and `dashing` for its UI layer. While lightweight and functional, it lacks native reactive components, structured application state management, and built-in asynchronous UI updates required to achieve feature parity with `mactop`.

This document evaluates the top production-grade Terminal User Interface (TUI) libraries in the Python ecosystem to determine the best path forward for `agtop` to close this UX gap.

---

## 2. Core Requirements for `agtop`

To match or exceed `mactop`, the chosen Python TUI framework must support:
1. **Asynchronous/Concurrent Rendering:** The UI main loop must not block while hardware metrics are polled via `ctypes` or `sysctl`.
2. **Rich Interactive Widgets:** Native support for Data Tables (for process lists), Tabs (to split hardware vs. process views), and interactive charts/gauges.
3. **Mouse Support:** Users should be able to click tabs, select processes, or scroll without keyboard binding hacks.
4. **Adaptive Layouts:** A robust grid system that handles window resizing dynamically.
5. **Theming:** First-class TrueColor support and easy theme creation (e.g., Catppuccin support).

---

## 3. Top TUI Candidates Evaluated

### 1. Textual (Winner / Highly Recommended)
Built by Textualize (the creators of `Rich`), Textual is a Rapid Application Development framework for Python TUIs. It is currently the most advanced and actively maintained TUI framework in the Python ecosystem.

*   **Concurrency Model:** Textual is built entirely on `asyncio`. It uses a reactive message-passing architecture with `Workers` (background tasks). This is the exact conceptual equivalent of `mactop`'s goroutine/channel architecture. `agtop` can run `api.py` in a background worker, streaming `PowerMetrics` objects to the main UI thread safely.
*   **Styling & Layout:** It uses a CSS-like dialect (`.tcss`) for styling, padding, layouts, and colors, completely decoupling the UI logic from the presentation layer.
*   **Widgets:** Provides out-of-the-box `DataTable`, `TabbedContent`, `Sparkline`, and rich text components.
*   **Interactivity:** Full mouse support (hover, click, scroll) and robust keyboard focus management.
*   **Verdict:** **The clear choice.** Textual provides the exact feature set needed to make `agtop` look and feel like a native, premium dashboard application, easily surpassing `gotui` in developer ergonomics and aesthetics.

### 2. Urwid
Urwid is a classic, battle-tested console UI library used in many complex production CLI tools (e.g., `mitmproxy`).
*   **Pros:** Extremely fast screen redraws, handles high-frequency updates efficiently. Supports rich layouts and mouse events. Integrates well with external event loops (`asyncio`, `glib`).
*   **Cons:** The API is dated, highly verbose, and has a steep learning curve. It requires significant manual effort to build modern-looking widgets (gauges, sparklines) and lacks the CSS-like theming engine of Textual.
*   **Verdict:** Viable but archaic. It would take substantially more development time to achieve a modern aesthetic.

### 3. Prompt Toolkit
Famous for powering interactive REPLs (`ptpython`, `ipython`), Prompt Toolkit also includes a full-screen application framework.
*   **Pros:** Excellent cross-platform compatibility, raw performance, async support, and solid mouse handling.
*   **Cons:** Primarily optimized for complex text input and autocompletion rather than data-heavy monitoring dashboards. Building custom grids, tables, and hardware metric visualizations requires writing low-level layout rendering logic.
*   **Verdict:** Better suited for CLI prompts than full-screen system monitors.

### 4. Rich (Standalone)
`Rich` is the underlying rendering engine for Textual, but it can be used on its own (`rich.layout`, `rich.live`).
*   **Pros:** Beautiful rendering, TrueColor support, easy to construct static grids and panels.
*   **Cons:** `Rich` is strictly an output/formatting library. It does **not** handle input (mouse clicks, keyboard navigation, focus switching) or complex application state.
*   **Verdict:** Insufficient for the highly interactive, multi-tabbed UX required to beat `mactop`.

---

## 4. Proposed Migration Architecture (Textual + `agtop`)

If `agtop` migrates to Textual, the architecture would shift as follows:

1. **Application Loop:** Replace the blocking `blessed` `while True:` loop with `textual.app.App`.
2. **Data Polling (Workers):** Wrap the existing `agtop.api.Profiler` with a `@work(thread=True)` decorator. This worker will poll Apple's `libIOReport` and `sysctl` natively and emit custom `Messages` (e.g., `MetricsUpdated`) to the UI.
3. **Process List:** Replace manual string truncation and sorting with `textual.widgets.DataTable`. This instantly provides sticky headers, column sorting on click, and scrolling.
4. **Layout:** Use `TabbedContent` to separate concerns:
    *   **Tab 1 (Overview):** CPU/GPU Gauges, ANE metrics, Total RAM.
    *   **Tab 2 (Processes):** The `DataTable` of active processes.
    *   **Tab 3 (Config/Themes):** Interactive toggles for changing themes (Catppuccin, Nord, etc.) and power scaling profiles.

## 5. Conclusion

Adopting **Textual** is the definitive strategy to resolve the "UI Library & UX" and "Desktop Integration" gaps identified against `mactop`. It will allow `agtop` to leverage its superior low-level Python `ctypes` bindings while presenting a visually stunning, highly concurrent, and interactive terminal dashboard that rivals or exceeds compiled Go applications.