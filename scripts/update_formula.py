#!/usr/bin/env python3
"""Update Homebrew formula url/sha256 for a tagged agtop release."""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

URL_LINE = re.compile(r'^(  url ")([^"]+)(")$', re.MULTILINE)
SHA_LINE = re.compile(r'^(  sha256 ")([0-9a-f]{64})(")$', re.MULTILINE)
SHA256_VALUE = re.compile(r'^[0-9a-f]{64}$')


def normalize_version(version: str) -> str:
    return version[1:] if version.startswith("v") else version


def tarball_url(repo: str, version: str) -> str:
    return f"https://github.com/{repo}/archive/refs/tags/v{version}.tar.gz"


def compute_sha256(url: str) -> str:
    digest = hashlib.sha256()
    with urlopen(url) as response:  # nosec B310: trusted release URL built from args
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _replace_line(content: str, pattern: re.Pattern[str], new_value: str, label: str) -> tuple[str, str]:
    match = pattern.search(content)
    if not match:
        raise ValueError(f"Could not find {label} line in formula")

    old_value = match.group(2)
    new_line = f"{match.group(1)}{new_value}{match.group(3)}"
    new_content = content[: match.start()] + new_line + content[match.end() :]
    return new_content, old_value


def update_formula_file(formula_path: Path, url: str, sha256: str, dry_run: bool) -> tuple[str, str]:
    content = formula_path.read_text(encoding="utf-8")
    content, old_url = _replace_line(content, URL_LINE, url, "url")
    content, old_sha = _replace_line(content, SHA_LINE, sha256, "sha256")

    if not dry_run:
        formula_path.write_text(content, encoding="utf-8")

    return old_url, old_sha


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Update Formula/agtop.rb release URL and checksum")
    parser.add_argument("version", help="Release version (for example: 0.1.2 or v0.1.2)")
    parser.add_argument("--repo", default="binlecode/agtop", help="GitHub source repo")
    parser.add_argument("--formula", default="Formula/agtop.rb", help="Path to formula file")
    parser.add_argument("--sha256", help="Use an explicit SHA256 instead of downloading tarball")
    parser.add_argument("--dry-run", action="store_true", help="Print updates without writing files")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    version = normalize_version(args.version)
    formula_path = Path(args.formula)

    if not formula_path.exists():
        print(f"Formula not found: {formula_path}", file=sys.stderr)
        return 1

    url = tarball_url(args.repo, version)

    if args.sha256:
        sha256 = args.sha256.lower().strip()
        if not SHA256_VALUE.fullmatch(sha256):
            print("Invalid --sha256; expected 64 lowercase hex characters", file=sys.stderr)
            return 1
    else:
        try:
            sha256 = compute_sha256(url)
        except HTTPError as exc:
            print(f"Failed to download tarball (HTTP {exc.code}): {url}", file=sys.stderr)
            return 1
        except URLError as exc:
            print(f"Failed to download tarball ({exc.reason}): {url}", file=sys.stderr)
            return 1

    try:
        old_url, old_sha = update_formula_file(formula_path, url, sha256, args.dry_run)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    action = "Would update" if args.dry_run else "Updated"
    print(f"{action} {formula_path}")
    print(f"  url:    {old_url} -> {url}")
    print(f"  sha256: {old_sha} -> {sha256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
