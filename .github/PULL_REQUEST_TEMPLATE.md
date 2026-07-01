<!-- Keep the PR scoped to one logical change (see CLAUDE.md). -->

## Summary

<!-- What behavior changes, and why. -->

## Validation

<!-- Paste commands run + their results. For parser/metric changes, include a
     reproducible sample input/output note. -->

- [ ] `.venv/bin/ruff check --fix .` and `.venv/bin/ruff format .`
- [ ] `.venv/bin/python -m actop.actop --help`
- [ ] `.venv/bin/pytest -q`
- [ ] Ran `actop` on Apple Silicon — gauges/charts update without crashes
      (chip + macOS: ______)

## Tests

- [ ] New/changed tests are **functional** — they drive a public or runtime surface
      (CLI, `Monitor`/`Profiler`, `create_dashboard_config`, real export/format
      contracts, or a widget mounted via `App.run_test()`). No private-attr access,
      no mock-the-data/monkeypatch of the unit under test, no coverage-only tests
      (see CLAUDE.md "Testing Guidelines").

## UI-visible changes

<!-- Screenshot or terminal capture, if the change affects the TUI. Delete if N/A. -->
