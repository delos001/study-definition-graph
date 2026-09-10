"""
Script:      find_unrecorded_files.py
Description: Lists every file under inputs/ that no manifest records, since
             such a file cannot be restored from a fresh clone.

             inputs/ is gitignored and holds only pinned downloads, so the
             manifests say what belongs there and the disk says what is there.
             A recorded file is any manifest entry's local path. Everything
             else found under inputs/ is reported, except the files the
             project writes there itself: README.md, .gitkeep, and the ~$ lock
             files Excel leaves beside an open workbook.

             A .part file is reported, because it is an unfinished download
             that acquire_sources did not get to finish.

Inputs:      manifests/*.json, manifests/study_documents/*.json   (read-only)
             inputs/                                           (read-only, names only)

Outputs:     Nothing on disk. Prints one repo-relative path per unrecorded
             file, or nothing when there are none.

Usage:       python scripts/find_unrecorded_files.py
                 list every unrecorded file
             python scripts/find_unrecorded_files.py --quiet
                 print nothing; use the exit code

Exit codes:  0  every file under inputs/ is recorded
             1  at least one file is not
             3  no manifests found, or one could not be read
             6  the sdg package is not running from inside its repo

Date:        2026-09-09
Owner:       Jason Delosh
"""

from __future__ import annotations

import argparse
import sys

# The manifests are read through the package, so this script needs the
# editable install (pip install -e ., README.md step 1b) the same as the
# pipeline does.
from sdg.sources import ManifestError, NotInRepoError, manifests
from sdg.sources.read_manifests import REPO_ROOT

# The one folder that holds pinned files. The Claude Code hook in
# .claude/hooks/ refuses edits under the same folder; the two agree because
# there is only one name.
PINNED_DIR = REPO_ROOT / "inputs"

# Files the project writes into the pinned folder itself, and so are never
# recorded in a manifest.
OWN_FILES = ("README.md", ".gitkeep")

# Excel writes a ~$name.xlsx lock file beside any workbook that is open. It is
# not data and goes away when the workbook is closed.
LOCK_PREFIX = "~$"


def unrecorded_files(found) -> list[str]:
    """Walks inputs/ and gives back the repo-relative paths of files no entry
    records, sorted, with the project's own files left out."""
    recorded = {entry.local for manifest in found for entry in manifest.entries}
    stray: list[str] = []

    if not PINNED_DIR.is_dir():
        return stray

    for path in PINNED_DIR.rglob("*"):
        if not path.is_file():
            continue
        if path.name in OWN_FILES or path.name.startswith(LOCK_PREFIX):
            continue
        local = path.relative_to(REPO_ROOT).as_posix()
        if local not in recorded:
            stray.append(local)

    return sorted(stray)


def main(argv: list[str] | None = None) -> int:
    """Reads the manifests, walks inputs/, prints each unrecorded file unless
    --quiet, and gives back the exit code."""
    parser = argparse.ArgumentParser(description="List files under inputs/ that no manifest records.")
    parser.add_argument("--quiet", action="store_true", help="print nothing; use the exit code")
    args = parser.parse_args(argv)

    # The reader checks the package is running from inside its repo before it
    # looks for any manifest, so the wrong install is reported as that.
    try:
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
