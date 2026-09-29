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

Usage:       find_unrecorded_files
                 list every unrecorded file
             find_unrecorded_files --quiet
                 print nothing; use the exit code

Exit codes:  0   SUCCEEDED  the command succeeded (every file under inputs/ is
                 recorded)
             1   UNHANDLED-ERROR  Python stopped on an error that nothing
                 handled
             2   COMMAND-LINE-REFUSED  the argument parser refused the command
                 line
             3   NOT-IN-REPO  the sdg package is not running from inside its
                 repo
             12  MANIFEST-MISSING  the manifests folder is missing or holds no
                 manifest
             13  MANIFEST-UNREADABLE  a manifest is on disk but cannot be opened
             14  MANIFEST-UNPARSEABLE  a manifest is not valid JSON
             15  MANIFEST-INVALID  a manifest's content breaks a requirement
             15  MANIFEST-LOCATION-OUTSIDE-INPUTS  a manifest records a
                 location that does not stay under inputs/
             16  FILE-UNRECORDED  a file under inputs/ is recorded by no
                 manifest
             The wording is the table in docs/exit_codes.csv.

Date:        2026-09-09
Owner:       Jason Delosh
"""

from __future__ import annotations

import argparse
import sys

# The manifests are read through the sdg package, so this script needs the
# editable install (pip install -e ., README.md step 4) the same as the
# pipeline does.
from sdg.exit_codes import fail, finish, problem_line
from sdg.sources import (
    ManifestError,
    NotInRepoError,
    manifests,
)
from sdg.sources.read_manifests import REPO_ROOT, Manifest

#######################################################################################
### Settings ###

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


#######################################################################################
### Find the unrecorded files ###


def unrecorded_files(found: list[Manifest]) -> list[str]:
    """Walk inputs/ and list the files no manifest entry records.

    The project's own files, meaning the READMEs and Excel's lock files, are left out.

    Args:
        found: The manifests, as the manifest reader, src/sdg/sources/read_manifests.py, hands them back.

    Returns:
        The repo-relative paths of the unrecorded files, sorted.
    """
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


#######################################################################################
### Command line ###


def main(argv: list[str] | None = None) -> int:
    """Read the manifests, walk inputs/, and print each unrecorded file, unless --quiet.

    Args:
        argv: The command-line arguments, or None to read the real ones.

    Returns:
        The exit code, as the header block lists them.
    """
    parser = argparse.ArgumentParser(
        description="List files under inputs/ that no manifest records."
    )
    parser.add_argument(
        "--quiet", action="store_true", help="print nothing; use the exit code"
    )
    args = parser.parse_args(argv)

    # The manifest reader, src/sdg/sources/read_manifests.py, confirms the sdg package is running from inside its repo before it
    # looks for any manifest, so the wrong install is reported as that.
    def say(message: str) -> None:
        """Print a line, unless --quiet was given."""
        if not args.quiet:
            print(message)

    # Each manifest error carries its own exit number and sub-code.
    try:
        found = manifests()
    except (NotInRepoError, ManifestError) as exc:
        return fail(say, exc.exit_code, exc.sub_code, exc)

    stray = unrecorded_files(found)

    for local in stray:
        say(problem_line("FILE-UNRECORDED", local))
    if not stray:
        return 0
    say(
        f"\n{len(stray)} file(s) no manifest records. They cannot be restored from a clone."
    )
    return finish(say, 16, "FILE-UNRECORDED")


if __name__ == "__main__":
    sys.exit(main())
