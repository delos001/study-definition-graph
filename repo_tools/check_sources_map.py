"""
Script:      check_sources_map.py
Description: Compares docs/sources_index.md with the manifests, so a pinned file
             cannot exist without the map saying it does.

             The map is what a session reads to find out which file answers
             which question. A file the manifests record but the map omits fails
             silently, because nobody asks for a file they do not know exists.
             That happened once: the map was rewritten in September and found to
             be missing USDM_API.yaml, which its manifest had recorded since
             August.

             Two things are compared, in both directions. Every file a manifest
             records is covered by a document heading in the map, and every
             location the map names is a folder some manifest records a file in.

             A heading may name a pattern rather than one file, because some
             groups hold the same shape of file per study or per subject area.
             The map already writes those as <study>.pdf and uml/*.png, and both
             forms are matched here, with <anything> read as a wildcard. One
             heading may also name two files joined by the word and.

Inputs:      docs/sources_index.md                              (read-only)
             manifests/*.json, manifests/study_documents/*.json (read-only, through
                                                                 the manifest reader)

Outputs:     Nothing on disk. Prints one line per disagreement, or nothing when
             the map and the manifests agree.

             This runs from the validation suite rather than the pre-commit
             hook. The hook keeps to tools that need only the standard library,
             so a commit works in a terminal where the sdg environment is not
             active, and this one reads the manifests through the package.

Usage:       python repo_tools/check_sources_map.py
                 report every disagreement
             python repo_tools/check_sources_map.py --quiet
                 print nothing; use the exit code. For hooks.

Exit codes:  0   success (the map and the manifests agree)
             1   unhandled error, Python's own
             2   invalid command line, the argument parser's own
             3   a manifest is missing or cannot be read
             6   not running from inside the repo
             13  a file on disk cannot be read (the sources map)
             35  a pinned file has no document heading in the sources map
             36  the sources map names a location no manifest records
             35 outranks 36, because a file nobody can find is worse than a
             heading pointing at an empty folder. Every problem is still named.
             The numbers are the repo-wide table in
             validation/exit_codes.csv.

Date:        2026-09-15
Owner:       Jason Delosh
"""

from __future__ import annotations

import argparse
import re
import sys
from fnmatch import fnmatch

from sdg.sources import ManifestError, NotInRepoError, manifests
from sdg.sources.read_manifests import REPO_ROOT, Manifest

#######################################################################################
### Settings ###

# The map this script checks. It is read as text rather than parsed as markdown,
# because only two kinds of line matter and both are written the same way every
# time.
MAP_FILE = REPO_ROOT / "docs" / "sources_index.md"

# A location line names the folder a group of pinned files lives in.
LOCATION_RE = re.compile(r"^- location: (\S+)")

# A document heading names the file or files a section is about.
HEADING_RE = re.compile(r"^### Document: (.+)$")

# A heading may name two files joined by this word, as USDM_API.json and
# USDM_API.yaml are.
JOINER = " and "

# A heading may stand for a whole group of files by writing the part that varies
# inside angle brackets, as <study>.pdf does. Read as a wildcard when matching.
PLACEHOLDER_RE = re.compile(r"<[^>]+>")


#######################################################################################
### Read the map ###


def map_patterns(text: str) -> list[str]:
    """Collect the file patterns the map's document headings name.

    Args:
        text: The map, as read from disk.

    Returns:
        One pattern per file a heading names, in the order the map lists them.
    """
    patterns: list[str] = []
    for line in text.splitlines():
        heading = HEADING_RE.match(line)
        if heading:
            patterns.extend(part.strip() for part in heading.group(1).split(JOINER))
    return patterns


def map_locations(text: str) -> list[str]:
    """Collect the folders the map's location lines name.

    Args:
        text: The map, as read from disk.

    Returns:
        One repo-relative folder per location line, in the order the map lists them.
    """
    found: list[str] = []
    for line in text.splitlines():
        location = LOCATION_RE.match(line)
        if location:
            found.append(location.group(1).rstrip("/"))
    return found


#######################################################################################
### Compare the map with the manifests ###


def covers(pattern: str, local: str) -> bool:
    """Say whether one document heading covers one recorded file.

    A heading names the file, not its whole path, except where the group keeps files
    in subfolders and the heading says so, as uml/*.png does. Both are matched against
    the end of the recorded path, and a part written in angle brackets stands for
    anything.

    Args:
        pattern: The heading, as the map writes it.
        local: The file's path from the repo root, as the manifest records it.

    Returns:
        Whether the heading covers the file.
    """
    wildcard = PLACEHOLDER_RE.sub("*", pattern)
    return fnmatch(local, f"*/{wildcard}") or fnmatch(local, wildcard)


def unmapped_files(found: list[Manifest], patterns: list[str]) -> list[str]:
    """List every recorded file that no document heading covers.

    Args:
        found: The manifests, as the manifest reader hands them back.
        patterns: The patterns the map's headings name.

    Returns:
        The repo-relative paths of the uncovered files, sorted.
    """
    missing = [
        entry.local
        for manifest in found
        for entry in manifest.entries
        if not any(covers(pattern, entry.local) for pattern in patterns)
    ]
    return sorted(missing)


def empty_locations(found: list[Manifest], locations: list[str]) -> list[str]:
    """List every location the map names that no manifest records a file in.

    Args:
        found: The manifests, as the manifest reader hands them back.
        locations: The folders the map's location lines name.

    Returns:
        The locations nothing is recorded under, in the order the map lists them.
    """
    recorded = [entry.local for manifest in found for entry in manifest.entries]
    empty = []
    for location in locations:
        prefix = PLACEHOLDER_RE.sub("*", location)
        if not any(fnmatch(local, f"{prefix}/*") for local in recorded):
            empty.append(location)
    return empty


#######################################################################################
### Command line ###


def main(argv: list[str] | None = None) -> int:
    """Read the map and the manifests, and report where they disagree.

    Args:
        argv: The command-line arguments, or None to read the real ones.

    Returns:
        The exit code, as the header block lists them.
    """
    parser = argparse.ArgumentParser(
        description="Check that docs/sources_index.md and the manifests agree."
    )
    parser.add_argument(
        "--quiet", action="store_true", help="print nothing; use the exit code"
    )
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

    try:
        text = MAP_FILE.read_text(encoding="utf-8")
    except OSError as exc:
        if not args.quiet:
            print(f"{MAP_FILE.name} cannot be read: {exc}")
        return 13

    missing = unmapped_files(found, map_patterns(text))
    empty = empty_locations(found, map_locations(text))

    if not args.quiet:
        for local in missing:
            print(
                f"{local} is recorded in a manifest but no heading in the map covers it"
            )
        for location in empty:
            print(f"the map names {location}, which no manifest records a file in")

    if missing:
        return 35
    if empty:
        return 36
    return 0


if __name__ == "__main__":
    sys.exit(main())
