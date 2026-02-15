# GUIDE: Homebrew Release Flow for `silitop`

This is the minimal workflow to publish a new `silitop` version and make `brew upgrade silitop` work.

## Key Rule

Homebrew upgrades from the tap formula version in `Formula/silitop.rb`, not from `setup.py` alone.

If users see:

```bash
Warning: binlecode/silitop/silitop <version> already installed
```

your tap formula was not bumped (or users have not run `brew update` yet).

## Prerequisites

- macOS + Homebrew
- `gh` logged in
- Repo: `binlecode/silitop`

Quick checks:

```bash
brew --version
gh auth status
```

## Release Checklist (Maintainer)

Set variables:

```bash
export VERSION="0.0.25"
export SRC_REPO="binlecode/silitop"
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

4. Update `Formula/silitop.rb`.

- `url` -> `.../v$VERSION.tar.gz`
- `sha256` -> value from step 3

5. Commit and push formula update.

```bash
git add Formula/silitop.rb
git commit -m "Formula: bump silitop to $VERSION"
git push origin main
```

## End-User Upgrade

```bash
brew update
brew upgrade silitop
brew info silitop
```

Verify `brew info silitop` shows the new stable version.

## First-Time Install

```bash
brew tap --custom-remote binlecode/silitop https://github.com/binlecode/silitop.git
brew install silitop
```

## Quick Validation

```bash
silitop --help
sudo silitop --interval 1 --avg 30 --power-scale profile
```

## Troubleshooting

- `brew upgrade silitop` says `already installed`:
  - Confirm `Formula/silitop.rb` was pushed with the new `url` and `sha256`.
  - Run `brew update`, then retry `brew upgrade silitop`.
  - Check `brew info silitop`.

- `brew update` has ref errors like `refs/remotes/origin/main`:
  - Run `brew tap --repair` then `brew update-reset` and retry `brew update`.
  - If still broken, untap/retap the failing tap.

- Wrong tap name:
  - Use `binlecode/silitop` (not `binlecode/asitop`).
