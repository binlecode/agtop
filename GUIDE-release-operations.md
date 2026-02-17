# Release Operations Guide

This document serves two purposes:

1. **Tutorial** — explains the Homebrew packaging model, CI/CD component ownership, and end-to-end release flow so that new contributors (human or AI) can understand how releases work without reading CI workflow files.
2. **Runbook** — provides step-by-step release instructions, operational rules, and failure recovery playbooks for day-to-day release execution.

## Homebrew Packaging Model

`agtop` uses Homebrew's Python virtualenv formula pattern:

- Formula includes `Language::Python::Virtualenv` and depends on `python@3.13`.
- `virtualenv_install_with_resources` creates a `libexec` venv and pip-installs declared `resource` blocks (blessed, dashing, psutil, wcwidth).
- Brew upgrade logs showing `python3.13 -m venv` and `python3.13 -m pip` are expected — this is a self-contained CLI install, not a stale formula.

## Component Ownership

| Component | Responsibility |
| --- | --- |
| **Maintainer** | Bumps `pyproject.toml` version, updates `CHANGELOG.md`, runs local checks, triggers release |
| **`scripts/tag_release.sh`** | Verifies clean tree, validates version vs `pyproject.toml`, fast-forwards local `main`, pushes `main`, creates and pushes `vX.Y.Z` tag. Does **not** modify `Formula/agtop.rb` |
| **`main-ci.yml`** | Runs on `main` push. Resolves Python version from formula, installs formula-style deps, verifies resource alignment, runs lint/format/help/tests |
| **`release-formula.yml`** | Runs on `v*` tag push (or manual `workflow_dispatch`). Validates tag/version match, computes tarball SHA256, updates formula `url` + `sha256`, regenerates `resource` blocks, pushes formula-sync commit to `main`. Serialized concurrency + retry to avoid push races |

## End-to-End Flow

```text
local commit (version + changelog)
  -> scripts/tag_release.sh
    -> push main
    -> push tag vX.Y.Z
      -> main-ci (main push)
      -> release-formula (tag push)
         -> Formula/agtop.rb sync commit on main (url/sha/resources)
            -> main-ci (formula-sync push)
```

## Release Steps

### 1. Clean working tree

```bash
git status --short
```

### 2. Bump version and changelog

Edit `pyproject.toml` (`[project].version`) and `CHANGELOG.md` (move items from `Unreleased` to new version section with date).

### 3. Run checks

```bash
.venv/bin/python -m ruff check --fix .
.venv/bin/python -m ruff format .
.venv/bin/python -m agtop.agtop --help
.venv/bin/pytest -q
```

### 4. Commit and tag

```bash
git add pyproject.toml CHANGELOG.md
git commit -m "Release v$VERSION"
scripts/tag_release.sh "$VERSION"
```

### 5. Monitor CI

```bash
gh run list -R binlecode/agtop --limit 10
```

Wait for both `main-ci` and `release-formula` to complete successfully.

### 6. Verify

```bash
git pull --ff-only origin main          # pull formula-sync commit
sed -n '1,20p' Formula/agtop.rb        # confirm url + sha256
brew update && brew upgrade binlecode/agtop/agtop
brew info binlecode/agtop/agtop
```

## Rules

**Do:**
- Use `scripts/tag_release.sh` for all release tags.
- Let `release-formula.yml` own formula sync commits.
- Verify both CI workflows after each release.
- Keep `refresh_resources=true` (default) for normal releases.

**Do not:**
- Manually edit `Formula/agtop.rb` during releases.
- Push a tag before version/changelog are committed.
- Force-push `main` during release windows.
- Disable resource refresh except for emergency reruns.

## Failure Playbooks

### `tag_release.sh` fails on `git pull --ff-only`

Local `main` is behind or diverged.

```bash
git fetch origin && git checkout main && git pull --ff-only origin main
scripts/tag_release.sh "$VERSION"
```

### `release-formula` fails with tag/version mismatch

Tag `vX.Y.Z` does not match `pyproject.toml` in the tag commit. Fix the version, create a new commit and tag (do not reuse the old tag).

### `release-formula` fails with push race

Rare due to serialized concurrency. Wait for in-progress workflows to finish, then re-run the failed job from GitHub Actions UI.

### `main-ci` fails after formula-sync commit

Inspect logs, fix on `main` in a follow-up commit. If caused by resource drift, re-run `release-formula` with resource refresh enabled.

```bash
gh run view -R binlecode/agtop <RUN_ID> --log-failed
```

### Emergency rerun without resource refresh

Use `workflow_dispatch` with `refresh_resources=false` as a temporary workaround. Follow up with a normal run (`refresh_resources=true`) to restore full synchronization.

## Quick Reference

```bash
gh run list -R binlecode/agtop --limit 12          # recent CI runs
gh run view -R binlecode/agtop <RUN_ID>             # inspect run
gh run view -R binlecode/agtop <RUN_ID> --log-failed
git ls-remote --tags origin "v*"                     # remote tags
```

**Source of truth:** version in `pyproject.toml`, notes in `CHANGELOG.md`, formula in `Formula/agtop.rb`, tag helper in `scripts/tag_release.sh`, CI in `.github/workflows/`.
