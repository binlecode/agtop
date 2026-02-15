# GUIDE: Homebrew Bottling for `asitop`

This guide shows how to package and publish `asitop` as a Homebrew formula using common Homebrew practices for Python CLI tools.

## Scope

- Packaging and release workflow only.
- No runtime behavior changes for `asitop`.
- Pinned source tarball + pinned Python resources.

## Prerequisites

- macOS with Homebrew installed.
- GitHub CLI (`gh`) logged in.
- A GitHub repo where the formula will live (this guide assumes `binlecode/asitop`).

Run preflight checks:

```bash
brew --version
python3 --version
which powermetrics
sysctl -n machdep.cpu.brand_string
gh auth status
```

## Step 1: Set Release Variables

```bash
export GITHUB_USER="binlecode"
export SRC_REPO="$GITHUB_USER/asitop"
export VERSION="0.0.23"
export TARBALL_URL="https://github.com/$SRC_REPO/archive/refs/tags/v$VERSION.tar.gz"
```

## Step 2: Create/Publish Git Tag Release

Push your source changes first, then create release tag:

```bash
git push origin main
gh release create "v$VERSION" -R "$SRC_REPO" --target main --title "v$VERSION" --notes "Release v$VERSION"
```

## Step 3: Compute Tarball SHA256

```bash
curl -fL "$TARBALL_URL" -o "/tmp/asitop-v$VERSION.tar.gz"
shasum -a 256 "/tmp/asitop-v$VERSION.tar.gz"
```

Copy that SHA256 value for the formula.

## Step 4: Add/Update Formula in Repo Tap

Use `Formula/asitop.rb` in your repository (repo-as-tap layout).

Template:

```ruby
class Asitop < Formula
  include Language::Python::Virtualenv

  desc "Performance monitoring CLI tool for Apple Silicon"
  homepage "https://github.com/binlecode/asitop"
  url "https://github.com/binlecode/asitop/archive/refs/tags/v0.0.23.tar.gz"
  sha256 "<TARBALL_SHA256>"
  license "MIT"

  depends_on "python@3.13"

  resource "blessed" do
    url "https://files.pythonhosted.org/packages/dd/19/e926a0dbbf93c7aeb15d4dfff0d0e3de02653b3ba540b687307d0819c1ff/blessed-1.30.0.tar.gz"
    sha256 "4d547019d7b40fc5420ea2ba2bc180fdccc31d6715298e2b49ffa7b020d44667"
  end

  resource "dashing" do
    url "https://files.pythonhosted.org/packages/bd/01/1c966934ab5ebe5a8fa3012c5de32bfa86916dba0428bdc6cdfe9489f768/dashing-0.1.0.tar.gz"
    sha256 "2514608e0f29a775dbd1b1111561219ce83d53cfa4baa2fe4101fab84fd56f1b"
  end

  resource "psutil" do
    url "https://files.pythonhosted.org/packages/aa/c6/d1ddf4abb55e93cebc4f2ed8b5d6dbad109ecb8d63748dd2b20ab5e57ebe/psutil-7.2.2.tar.gz"
    sha256 "0746f5f8d406af344fd547f1c8daa5f5c33dbc293bb8d6a16d80b4bb88f59372"
  end

  resource "wcwidth" do
    url "https://files.pythonhosted.org/packages/35/a2/8e3becb46433538a38726c948d3399905a4c7cabd0df578ede5dc51f0ec2/wcwidth-0.6.0.tar.gz"
    sha256 "cdc4e4262d6ef9a1a57e018384cbeb1208d8abbc64176027e2c2455c81313159"
  end

  def install
    virtualenv_install_with_resources(using: "python@3.13")
  end

  test do
    output = shell_output("#{bin}/asitop --help")
    assert_match "Performance monitoring CLI tool for Apple Silicon", output
  end
end
```

Note: `using: "python@3.13"` avoids `FormulaUnknownPythonError` on some setups.

## Step 5: (Optional) Refresh Python Resources

When dependencies change:

```bash
export HOMEBREW_NO_INSTALL_FROM_API=1
brew update-python-resources binlecode/asitop/asitop --package-name asitop
```

Preview only:

```bash
brew update-python-resources --print-only binlecode/asitop/asitop --package-name asitop
```

## Step 6: Validate Locally

```bash
export HOMEBREW_NO_AUTO_UPDATE=1
export HOMEBREW_NO_INSTALL_FROM_API=1

brew install --build-from-source --verbose binlecode/asitop/asitop
brew test binlecode/asitop/asitop
brew audit --strict --online binlecode/asitop/asitop
```

Expected:

- Install succeeds.
- `brew test` runs `asitop --help`.
- `brew audit` exits cleanly.

## Step 7: Publish Formula Update

```bash
git add Formula/asitop.rb
git commit -m "Formula: bump asitop to v$VERSION"
git push origin main
```

## Step 8: End-User Install

If users install from your repo tap:

```bash
brew tap binlecode/asitop https://github.com/binlecode/asitop.git
brew install asitop
```

Or fully-qualified:

```bash
brew install binlecode/asitop/asitop
```

Run:

```bash
asitop --help
sudo asitop --interval 1 --avg 30 --power-scale profile
```

## Step 9: Ongoing Release Routine

For every new release:

1. Cut a new tag/release (for example `v0.0.24`).
2. Update formula `url` and `sha256`.
3. Refresh resources if dependencies changed.
4. Re-run install/test/audit.
5. Push formula update.

## Troubleshooting

- `gh` token invalid:
  - `gh auth logout -h github.com -u <user>`
  - `gh auth login --web`
- Git pushes using wrong credential helper:
  - `gh auth setup-git`
- Homebrew can’t infer Python in virtualenv:
  - Use `virtualenv_install_with_resources(using: "python@3.13")`
