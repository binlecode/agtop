#!/usr/bin/env python3
"""Prepare an agtop release: bump version, sync changelog, update formula, run checks."""

from __future__ import annotations

import argparse
import datetime as dt
import re
import subprocess
import sys
from pathlib import Path

from update_formula import (
    SHA256_VALUE,
    normalize_version,
    tarball_url,
    update_formula_file,
    compute_sha256,
)

UNRELEASED_TEMPLATE = """## [Unreleased]

### Added
- No changes yet.

### Changed
- No changes yet.

### Fixed
- No changes yet.
"""

SETUP_VERSION_LINE = re.compile(r'^(\s*version\s*=\s*[\'"])([^\'"]+)([\'"],\s*)$', re.MULTILINE)


def update_setup_version(path: Path, version: str, dry_run: bool) -> str:
    content = path.read_text(encoding="utf-8")
    match = SETUP_VERSION_LINE.search(content)
    if not match:
        raise ValueError(f"Could not find version assignment in {path}")

    old_version = match.group(2)
    replacement = f"{match.group(1)}{version}{match.group(3)}"
    new_content = content[: match.start()] + replacement + content[match.end() :]

    if not dry_run:
        path.write_text(new_content, encoding="utf-8")

    return old_version


def sync_changelog(path: Path, version: str, date_str: str, dry_run: bool) -> bool:
    content = path.read_text(encoding="utf-8")
    release_heading = f"## [{version}] - {date_str}"
    existing_release = re.search(rf"^## \[{re.escape(version)}\](?: - .+)?$", content, re.MULTILINE)
    if existing_release:
        return False

    start = content.find("## [Unreleased]\n")
    if start == -1:
        raise ValueError("Could not find '## [Unreleased]' section")

    body_start = start + len("## [Unreleased]\n")
    next_heading = content.find("\n## [", body_start)
    if next_heading == -1:
        raise ValueError("Could not find section after 'Unreleased'")

    unreleased_body = content[body_start:next_heading].strip("\n")
    if not unreleased_body:
        unreleased_body = (
            "### Added\n- No changes yet.\n\n"
            "### Changed\n- No changes yet.\n\n"
            "### Fixed\n- No changes yet."
        )

    release_block = f"{release_heading}\n\n{unreleased_body}\n\n"
    new_content = (
        content[:start]
        + UNRELEASED_TEMPLATE
        + "\n"
        + release_block
        + content[next_heading + 1 :]
    )

    if not dry_run:
        path.write_text(new_content, encoding="utf-8")

    return True


def run_checks(repo_root: Path) -> None:
    py = repo_root / ".venv" / "bin" / "python"
    pytest = repo_root / ".venv" / "bin" / "pytest"

    if not py.exists() or not pytest.exists():
        raise RuntimeError("Missing .venv binaries. Create virtualenv first.")

    subprocess.run([str(py), "-m", "agtop.agtop", "--help"], check=True)
    subprocess.run([str(pytest), "-q"], check=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare a new agtop release")
    parser.add_argument("version", help="Release version (for example: 0.1.2 or v0.1.2)")
    parser.add_argument("--repo", default="binlecode/agtop", help="GitHub source repo")
    parser.add_argument("--setup", default="setup.py", help="Path to setup.py")
    parser.add_argument("--changelog", default="CHANGELOG.md", help="Path to CHANGELOG.md")
    parser.add_argument("--formula", default="Formula/agtop.rb", help="Path to formula file")
    parser.add_argument("--skip-formula", action="store_true", help="Skip formula update")
    parser.add_argument("--sha256", help="Explicit SHA256 for formula tarball")
    parser.add_argument("--skip-checks", action="store_true", help="Skip help/pytest checks")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing files")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    version = normalize_version(args.version)
    today = dt.date.today().isoformat()

    setup_path = Path(args.setup)
    changelog_path = Path(args.changelog)
    formula_path = Path(args.formula)

    try:
        old_setup_version = update_setup_version(setup_path, version, args.dry_run)
        changelog_created = sync_changelog(changelog_path, version, today, args.dry_run)

        if not args.skip_formula:
            url = tarball_url(args.repo, version)
            if args.sha256:
                sha256 = args.sha256.lower().strip()
                if not SHA256_VALUE.fullmatch(sha256):
                    raise ValueError("Invalid --sha256 value")
            else:
                sha256 = compute_sha256(url)
            old_url, old_sha = update_formula_file(formula_path, url, sha256, args.dry_run)
        else:
            url = "(skipped)"
            sha256 = "(skipped)"
            old_url = "(skipped)"
            old_sha = "(skipped)"
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    mode = "Would update" if args.dry_run else "Updated"
    print(f"{mode} setup version: {old_setup_version} -> {version}")
    print(
        f"{mode} changelog: {'added release section' if changelog_created else 'release section already exists'}"
    )
    if not args.skip_formula:
        print(f"{mode} formula url: {old_url} -> {url}")
        print(f"{mode} formula sha256: {old_sha} -> {sha256}")

    if not args.skip_checks and not args.dry_run:
        try:
            run_checks(Path(__file__).resolve().parent.parent)
            print("Validation checks passed: agtop --help, pytest -q")
        except Exception as exc:
            print(f"Validation failed: {exc}", file=sys.stderr)
            return 1

    if not args.dry_run:
        print("\nNext steps:")
        print(f"1. git add setup.py CHANGELOG.md {'Formula/agtop.rb' if not args.skip_formula else ''}")
        print(f"2. git commit -m \"Release v{version}\"")
        print(f"3. git tag v{version} && git push origin HEAD --tags")
        print("4. Verify with: brew update && brew upgrade binlecode/agtop/agtop")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
