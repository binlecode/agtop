# Release Operations Guide

This guide is the canonical runbook for releasing `agtop` and publishing formula updates.

## Purpose

- Keep release operations deterministic.
- Avoid duplicate/manual formula-sync commits.
- Define clear ownership between local scripts and CI workflows.

## Scope

This guide covers:

- Version bump and tagging
- CI/CD responsibilities
- Formula synchronization
- Post-release verification
- Common failure playbooks

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
- Runs lint/format check/help/tests.

### CI Workflow (`.github/workflows/release-formula.yml`)

- Runs on `v*` tag pushes.
- Validates tag version against `pyproject.toml` from the tag commit.
- Computes tarball SHA256 for the tag.
- Updates `Formula/agtop.rb` `url` + `sha256`.
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
         -> Formula/agtop.rb sync commit on main
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

### Do Not

- Do not manually sync `Formula/agtop.rb` during normal releases.
- Do not push a release tag before version/changelog are committed.
- Do not force-push `main` during release windows.

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

### 4) Formula already at target URL/SHA

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
