# TODO: AGTOP Hard-Fork Migration Status

## Goal

Project identity, module names, commands, and docs are standardized on `agtop`.

Constraint:
- Legacy identifiers are removed from repository content, except one origin attribution mention in `README.md`.

## 1. Branch and Scope Lock

- [x] Create dedicated branch: `rename-package-to-agtop`.
- [x] Keep this migration isolated from unrelated feature work.
- [x] Keep commits scoped by area (module rename, docs/metadata, release).

## 2. Core Package Rename

- [x] Rename package directory to `agtop/`.
- [x] Rename CLI module file to `agtop/agtop.py`.
- [x] Update internal imports to `agtop.*`.
- [x] Update module paths in tests to `agtop.*`.
- [x] Update runtime temp file prefix to `/tmp/agtop_powermetrics*`.

## 3. CLI and Runtime String Cleanup

- [x] Replace banner text with `AGTOP`.
- [x] Replace runtime help/update strings and links with `agtop` references.
- [x] Ensure CLI examples only use `agtop`.

## 4. Packaging and Project Metadata

- [x] `setup.py` package name set to `agtop`.
- [x] `setup.py` URL set to `https://github.com/binlecode/agtop`.
- [x] `console_scripts` entrypoint set to `agtop = agtop.agtop:main`.
- [x] Legacy console alias removed.
- [x] Keywords and metadata normalized to `agtop`.
- [x] Package discovery still works after folder rename.

## 5. Homebrew Formula + Tap Naming

- [x] Formula path/name is `Formula/agtop.rb`.
- [x] Formula class is `Agtop`.
- [x] Formula URLs point to `binlecode/agtop`.
- [x] Formula install path expects `agtop` binary only.
- [x] Formula test invokes `agtop --help`.

## 6. Docs and Operational Files

- [x] `README.md` keeps one origin attribution mention and otherwise uses `agtop`.
- [x] `CHANGELOG.md` references `binlecode/agtop` and includes migration entry.
- [x] `GUIDE-homebrew-bottling.md` uses `agtop` naming.
- [x] `AGENTS.md`, `GEMINI.md`, and local TODO docs updated to `agtop` paths/commands.
- [x] Image assets renamed to `images/agtop.*` and links updated.

## 7. Repository and Remote Hygiene

- [x] Confirm primary remote:
  - [x] `origin -> git@github.com-binlecode:binlecode/agtop.git`
- [x] Legacy secondary remote removed.
- [ ] Confirm GitHub repository description includes origin attribution.

## 8. Strict String-Policy Validation

- [x] Ran repository scan for legacy identifiers.
- [x] Verified only the single permitted origin mention remains in `README.md`.

## 9. Functional Validation

- [x] CLI help:

```bash
.venv/bin/python -m agtop.agtop --help
```

- [x] Tests:

```bash
.venv/bin/pytest -q
```

- [ ] Runtime smoke check on Apple Silicon:

```bash
sudo agtop --interval 1 --avg 30
```

- [x] Confirm no runtime references to legacy identifiers in source.

## 10. Release and Distribution

- [x] Bumped package version for the breaking rename (`0.1.0`).
- [ ] Tag release in `binlecode/agtop` (for example `v0.1.0`).
- [ ] Update `Formula/agtop.rb` URL + SHA for new tag tarball.
- [ ] Push formula update.
- [ ] Verify install/upgrade:

```bash
brew update
brew install agtop
brew upgrade agtop
brew info agtop
```

## 11. Commit Plan

- [ ] Commit 1: package/module rename + import fixes.
- [ ] Commit 2: metadata/docs normalization.
- [ ] Commit 3: formula + release bump.
- [ ] Final verification commit only if needed for straggler cleanup.
