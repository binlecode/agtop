# GUIDE: Homebrew Release Flow for `agtop`

This is the minimal workflow to publish a new `agtop` version and make `brew upgrade agtop` work.

Project stance: `agtop` is maintained as an independent hard fork inspired by `asitop`.

## Key Rule

Homebrew upgrades from the tap formula version in `Formula/agtop.rb`, not from `setup.py` alone.

If users see:

```bash
Warning: binlecode/agtop/agtop <version> already installed
```

your tap formula was not bumped (or users have not run `brew update` yet).

## Prerequisites

- macOS + Homebrew
- `gh` logged in
- Repo: `binlecode/agtop`

Quick checks:

```bash
brew --version
gh auth status
```

## Release Checklist (Maintainer)

Set variables:

```bash
export VERSION="0.0.25"
export SRC_REPO="binlecode/agtop"
export TARBALL_URL="https://github.com/$SRC_REPO/archive/refs/tags/v$VERSION.tar.gz"
```

1. Push source changes (code + `setup.py` + `CHANGELOG.md`).

```bash
git push origin main
```

2. Create and push the release tag.

```bash
git tag "v$VERSION"
git push origin "v$VERSION"
```

3. Compute tag tarball SHA256.

```bash
curl -fL "$TARBALL_URL" | shasum -a 256
```

4. Update `Formula/agtop.rb`.

- `url` -> `.../v$VERSION.tar.gz`
- `sha256` -> value from step 3

5. Commit and push formula update.

```bash
git add Formula/agtop.rb
git commit -m "Formula: bump agtop to $VERSION"
git push origin main
```

## End-User Upgrade

```bash
brew update
brew upgrade agtop
brew info agtop
```

Verify `brew info agtop` shows the new stable version.

## First-Time Install

```bash
brew tap --custom-remote binlecode/agtop https://github.com/binlecode/agtop.git
brew install agtop
```

## Naming Rules

- In this project docs, use `agtop` for the tap formula and CLI command.
- Avoid mixing install guidance with upstream package names in user-facing instructions.
- Keep one origin attribution in `README.md` for license and provenance clarity.

## Quick Validation

```bash
agtop --help
sudo agtop --interval 1 --avg 30 --power-scale profile
```

## Troubleshooting

- `brew upgrade agtop` says `already installed`:
  - Confirm `Formula/agtop.rb` was pushed with the new `url` and `sha256`.
  - Run `brew update`, then retry `brew upgrade agtop`.
  - Check `brew info agtop`.

- `brew update` has ref errors like `refs/remotes/origin/main`:
  - Run `brew tap --repair` then `brew update-reset` and retry `brew update`.
  - If still broken, untap/retap the failing tap.

- Wrong tap name:
  - Use `binlecode/agtop` (not `binlecode/asitop`).
