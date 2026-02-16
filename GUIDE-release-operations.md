# Release Operations Guide

This guide is the canonical runbook for releasing `agtop` and publishing formula updates.

## Purpose

- Keep release operations deterministic.
- Avoid duplicate/manual formula-sync commits (including Python resource updates).
- Define clear ownership between local scripts and CI workflows.

## Scope

This guide covers:

- Version bump and tagging
- CI/CD responsibilities
- Formula synchronization
- Homebrew Python packaging model (self-contained install behavior)
- Post-release verification
- Common failure playbooks

## Homebrew Packaging Model (Important)

`agtop` uses Homebrew's Python virtualenv formula pattern by design.

- Formula uses `include Language::Python::Virtualenv`.
- Formula depends on Homebrew Python (`depends_on "python@3.13"`).
- Install path uses `virtualenv_install_with_resources`, which creates `libexec` venv and pip-installs declared `resource` blocks.
- Result: brew upgrade logs that show `python3.13 -m venv ...` and `python3.13 -m pip ... blessed/dashing/psutil/wcwidth` are expected and correct.

This behavior is intentional for a self-contained CLI install and does not indicate a stale formula by itself.

## Components and Ownership

### Local Operator (Maintainer)

- Updates `pyproject.toml` version.
- Updates `CHANGELOG.md`.
- Runs local checks.
- Creates/pushes release tag using `scripts/tag_release.sh`.

### Script (`scripts/tag_release.sh`)

- Verifies clean working tree.
- Validates requested version matches `pyproject.toml`.
- Fast-forwards local `main` from `origin/main`.
- Pushes `main`.
- Creates and pushes tag `vX.Y.Z`.

It does **not** modify `Formula/agtop.rb`.

### CI Workflow (`.github/workflows/main-ci.yml`)

- Runs on `main` pushes.
- Resolves Python version from `Formula/agtop.rb`.
- Installs formula-style dependencies into isolated `.ci-venv`.
- Verifies formula resources match runtime dependency resolution in a separate clean venv.
- Runs lint/format check/help/tests.

### CI Workflow (`.github/workflows/release-formula.yml`)

- Runs on `v*` tag pushes.
- Supports manual `workflow_dispatch` with `tag_name` and `refresh_resources` toggle.
- Validates tag version against `pyproject.toml` from the tag commit.
- Computes tarball SHA256 for the tag.
- Updates `Formula/agtop.rb` `url` + `sha256`.
- Regenerates Python `resource` blocks from the release tarball dependency resolution by default.
- Pushes a formula-sync commit to `main`.
- Uses serialized concurrency + retry loop to reduce push-race failures.

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

## Happy Path (Standard Release)

1. Ensure clean working tree.

```bash
git status --short
```

2. Update release metadata.

- `pyproject.toml` `[project].version`
- `CHANGELOG.md` (move completed items from `Unreleased` to new version section)

3. Run required checks.

```bash
.venv/bin/python -m ruff check --fix .
.venv/bin/python -m ruff format .
.venv/bin/python -m agtop.agtop --help
.venv/bin/pytest -q
```

4. Commit release metadata.

```bash
export VERSION="0.1.8"
git add pyproject.toml CHANGELOG.md
git commit -m "Release v$VERSION"
```

5. Push via release helper.

```bash
scripts/tag_release.sh "$VERSION"
```

6. Monitor workflows.

```bash
gh run list -R binlecode/agtop --limit 10
```

7. Verify formula and install path.

```bash
sed -n '1,20p' Formula/agtop.rb
brew update
brew upgrade binlecode/agtop/agtop
brew info binlecode/agtop/agtop
```

## Do / Do Not

### Do

- Use `scripts/tag_release.sh` for release tags.
- Let `release-formula.yml` own formula sync commits.
- Verify `main-ci` and `release-formula` after each release.
- Treat venv/resource install lines in `brew upgrade` output as expected for this formula style.
- Keep `refresh_resources=true` for normal releases so resources stay aligned.

### Do Not

- Do not manually sync `Formula/agtop.rb` during normal releases.
- Do not push a release tag before version/changelog are committed.
- Do not force-push `main` during release windows.
- Do not disable resource refresh except for short-lived emergency reruns.

## Failure Playbooks

### 1) `scripts/tag_release.sh` fails on `git pull --ff-only`

Meaning: local `main` is behind/diverged.

Action:

```bash
git fetch origin
git checkout main
git pull --ff-only origin main
```

Then re-run `scripts/tag_release.sh`.

### 2) `release-formula` fails with tag/version mismatch

Meaning: tag `vX.Y.Z` does not match `pyproject.toml` version in tag commit.

Action:

- Fix version in source.
- Create a new release commit/tag (do not reuse old tag).

### 3) `release-formula` fails with push race

Expected to be rare due to retry/concurrency.

Action:

- Wait for in-progress workflow completion.
- Re-run failed job from GitHub Actions UI if needed.
- If still failing, manually inspect `main` head and workflow logs before retry.

### 4) Formula already up to date

Workflow may exit successfully with "already up to date".

Action:

- No manual action needed.
- Confirm formula content on `main`.

### 5) `main-ci` fails after formula-sync commit

Action:

- Inspect failed run logs:

```bash
gh run list -R binlecode/agtop --limit 10
gh run view -R binlecode/agtop <RUN_ID> --log-failed
```

- Fix issue on `main` in a follow-up commit.

Common cause:

- Formula resource drift check failed (missing/extra/version mismatch vs clean runtime dependency resolution).

Action:

- Re-run `release-formula` with resource refresh enabled or update formula resources.

### 6) Brew output still shows pip installing Python resources after release

Meaning:

- Formula is using `virtualenv_install_with_resources`, so resource installation is expected.

Action:

- Confirm formula install method and resources:

```bash
sed -n '1,80p' Formula/agtop.rb
brew deps --formula --include-requirements binlecode/agtop/agtop
```

- Do not treat these lines as a release failure by themselves.

### 7) Emergency manual rerun without resource refresh

Meaning:

- A release rerun is needed and dependency/resource refresh must be temporarily bypassed.

Action:

- Use `workflow_dispatch` and set `refresh_resources=false` only as a temporary workaround.
- Follow up with a normal run (`refresh_resources=true`) to restore full formula synchronization.

## Operational Quick Commands

```bash
# latest runs
gh run list -R binlecode/agtop --limit 12

# inspect one run
gh run view -R binlecode/agtop <RUN_ID>
gh run view -R binlecode/agtop <RUN_ID> --log-failed

# confirm release tag exists remotely
git ls-remote --tags origin "v*"
```

## Source of Truth

- Version: `pyproject.toml`
- Release notes: `CHANGELOG.md`
- Formula definition: `Formula/agtop.rb`
- Tag helper: `scripts/tag_release.sh`
- CI workflows: `.github/workflows/main-ci.yml`, `.github/workflows/release-formula.yml`
