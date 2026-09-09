"""
Script:      find_unrecorded_files.py
Description: Lists every file in a pinned folder that no manifest records, since
             such a file cannot be restored from a fresh clone.

             The pinned folders are gitignored, so only the manifests say what
             belongs in them. The manifests say where to look and what to ignore; the disk says
             what is there. A pinned folder is any top-level folder that some
             manifest's local_dir points into, today standards/ and data/. A
             recorded file is any entry's local path. Everything else found
             under those folders is reported, except the files the project
             writes itself: README.md, .gitkeep, and the ~$ lock files Excel
             leaves beside an open workbook.

             A .part file is reported, because it is an unfinished download
             that acquire_sources did not get to finish.

Inputs:      manifests/*.json, manifests/data_raw/*.json   (read-only)
             the pinned folders                            (read-only, names only)

Outputs:     Nothing on disk. Prints one repo-relative path per unrecorded
             file, or nothing when there are none.

Usage:       python scripts/find_unrecorded_files.py
                 list every unrecorded file
             python scripts/find_unrecorded_files.py --quiet
                 print nothing; use the exit code

Exit codes:  0  every file in the pinned folders is recorded
             1  at least one file is not
             3  no manifests found, or one could not be read
             6  the sdg package is not running from inside its repo

Date:        2026-09-09
Owner:       Jason Delosh
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# The manifests are read through the package, so this script needs the
# editable install (pip install -e ., README.md step 1b) the same as the
# pipeline does.
from sdg.sources import ManifestError, NotInRepoError, manifests, require_repo
from sdg.sources.read_manifests import REPO_ROOT

# Files the project writes into the pinned folders itself, and so are never
# recorded in a manifest. The Claude Code hook in .claude/hooks/ keeps the
# same short list; it cannot import this one because it must run before the
# package is installed.
OWN_FILES = ("README.md", ".gitkeep")

# Excel writes a ~$name.xlsx lock file beside any workbook that is open. It is
# not data and goes away when the workbook is closed.
LOCK_PREFIX = "~$"


def pinned_roots(found) -> set[Path]:
    """Gives back the top-level folders the manifests point into, as paths on
    this machine. Each manifest's local_dir starts with one of them."""
    roots = set()
    for manifest in found:
        if manifest.local_dir:
            roots.add(REPO_ROOT / Path(manifest.local_dir).parts[0])
    return roots


def unrecorded_files(found) -> list[str]:
    """Walks every pinned root and gives back the repo-relative paths of files
    no entry records, sorted, with the project's own files left out."""
    recorded = {entry.local for manifest in found for entry in manifest.entries}
    stray: list[str] = []

    for root in sorted(pinned_roots(found)):
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if path.name in OWN_FILES or path.name.startswith(LOCK_PREFIX):
                continue
            local = path.relative_to(REPO_ROOT).as_posix()
            if local not in recorded:
                stray.append(local)

    return sorted(stray)


def main(argv: list[str] | None = None) -> int:
    """Reads the manifests, walks the pinned folders, prints each unrecorded
    file unless --quiet, and gives back the exit code."""
    parser = argparse.ArgumentParser(description="List files in the pinned folders that no manifest records.")
    parser.add_argument("--quiet", action="store_true", help="print nothing; use the exit code")
    args = parser.parse_args(argv)

    try:
        require_repo()
        found = manifests()
    except NotInRepoError as exc:
        if not args.quiet:
            print(exc)
        return 6
    except ManifestError as exc:
        if not args.quiet:
            print(exc)
        return 3

    stray = unrecorded_files(found)

    if not args.quiet:
        for local in stray:
            print(local)
        if stray:
            print(f"\n{len(stray)} file(s) no manifest records. They cannot be restored from a clone.")

    return 1 if stray else 0


if __name__ == "__main__":
    sys.exit(main())
