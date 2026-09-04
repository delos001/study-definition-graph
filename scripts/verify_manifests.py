"""
Script:      verify_manifests.py
Description: Checks every pinned file against the checksum recorded for it in
             data/manifests/, and reports anything that has drifted.

             This exists because CLAUDE.md requires the recorded sha256 to be
             verified before a pinned file is parsed, and until now that check
             was only ever run by hand. A rule nobody can run is a rule nobody
             keeps.

             It also reports the reverse case: files sitting under data/raw/
             that no manifest records. Those are the dangerous ones. A file with
             a bad checksum announces itself; a file nobody wrote down looks
             exactly like a file that was properly pinned, and will not survive
             a fresh clone because data/ is gitignored.

Inputs:      data/manifests/*.json   (read-only)
             data/raw/**             (read-only, opened only to hash)

Outputs:     A report on stdout. Writes nothing to disk.

Usage:       python scripts/verify_manifests.py
                 check everything, print one line per set plus any problems
             python scripts/verify_manifests.py --verbose
                 also list every file that passed
             python scripts/verify_manifests.py --quiet
                 print nothing; use the exit code. For hooks and scripts.
             python scripts/verify_manifests.py --set raw_ich_m11
                 check one manifest only

Exit codes:  0  every recorded file is present and matches, no unrecorded files
             1  a recorded file is missing, or its checksum does not match
             2  a file under data/raw/ is not recorded in any manifest
             3  no manifests found, or one could not be parsed
             6  the sdg package is installed but not from inside its repo
                (installed without -e), so data/ cannot be found; the message
                gives the install command. Same meaning as in sdg.usdm_spec

             1 outranks 2 when both occur, because a corrupted pin is worse
             than an undocumented one.

Date:        2026-08-18
Owner:       Jason Delosh
"""

from __future__ import annotations

import argparse
import sys

# The manifest reading, entry checking and hashing live in sdg.pinned: the same
# code the pipeline runs before it reads any pinned file, so the check run by
# hand here is the check run automatically there. Needs the package installed
# editable (pip install -e ., README.md step 1b).
from sdg.pinned import (
    MANIFEST_DIR,
    RAW_DIR,
    REPO_ROOT,
    NotInRepoError,
    check_entry,
    load_manifests,
    require_repo,
)


### Constants ##################################################################

# Placeholder files that exist only to keep an empty directory in git. They are
# not data and are never recorded in a manifest, so they must not be reported
# as unrecorded.
IGNORED_NAMES = {".gitkeep"}

# Excel writes a "~$name.xlsx" lock file beside any workbook that is currently
# open, inside data/raw/ despite that tree being immutable. It is an editor
# artifact rather than data, it disappears when the workbook is closed, and
# read_xlsx.py already filters it for the same reason. Skipped here so a merely
# open spreadsheet does not fail the check.
IGNORED_PREFIXES = ("~$",)


### Checking ##################################################################


def find_unrecorded(recorded: set[str]) -> list[str]:
    """
    List files under data/raw/ that no manifest accounts for.

    Comparison is on posix-style relative paths because manifests are written
    with forward slashes and this repo runs on Windows, where Path renders
    backslashes. Normalising both sides to posix avoids every path in the
    corpus reporting as unrecorded.

    Returns paths sorted, so output is stable between runs and diffable.
    """
    if not RAW_DIR.exists():
        return []

    found = []
    for path in RAW_DIR.rglob("*"):
        if not path.is_file() or path.name in IGNORED_NAMES:
            continue
        if path.name.startswith(IGNORED_PREFIXES):
            continue

        relative = path.relative_to(REPO_ROOT).as_posix()
        if relative not in recorded:
            found.append(relative)

    return sorted(found)


### Entry point ################################################################


def main(argv: list[str] | None = None) -> int:
    """
    Takes the command-line arguments (None means sys.argv, as when run from a
    terminal), checks every manifest, prints a report, and produces the exit code.

    Output is organised by manifest so a failure can be traced to the set it
    belongs to, and therefore to the url it should be re-downloaded from.
    """
    # Manifest role names and file paths are plain ASCII, but the report is
    # printed alongside output from the other scripts, which force UTF-8 for the
    # same reason: a Windows console defaults to a legacy code page.
    sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        description="Verify pinned files against the checksums in data/manifests/."
    )
    parser.add_argument("--set", help="check one manifest only, e.g. raw_ich_m11")
    parser.add_argument("--verbose", action="store_true", help="list files that passed")
    parser.add_argument("--quiet", action="store_true", help="print nothing; use the exit code")
    args = parser.parse_args(argv)

    def say(line: str = "") -> None:
        """Print unless --quiet. Wrapped so no check has to test the flag."""
        if not args.quiet:
            print(line)

    # Checked before any path is used. Installed without -e, the manifests
    # folder is looked for in the wrong place and the run would report "no
    # manifests found", which sends the user to the wrong fix.
    try:
        require_repo()
    except NotInRepoError as exc:
        say(str(exc))
        return 6

    manifests, load_errors = load_manifests(args.set)

    if load_errors:
        for error in load_errors:
            say(f"MANIFEST UNREADABLE  {error}")

    if not manifests:
        say(f"No manifests found in {MANIFEST_DIR}.")
        return 3

    recorded_paths: set[str] = set()
    problems: list[str] = []
    total_ok = 0

    for manifest_path, manifest in manifests:
        entries = manifest.get("files", [])
        set_ok = 0
        set_problems: list[str] = []

        for entry in entries:
            status, detail = check_entry(entry)

            if entry.get("local"):
                recorded_paths.add(entry["local"])

            if status == "ok":
                set_ok += 1
                if args.verbose:
                    say(f"    ok        {detail}")
            else:
                set_problems.append(f"    {status.upper():9} {detail}")

        total_ok += set_ok
        marker = "OK  " if not set_problems else "FAIL"
        say(f"{marker}  {manifest_path.name:28} {set_ok}/{len(entries)} verified")

        for line in set_problems:
            say(line)
        problems.extend(set_problems)

    # Only meaningful across the whole corpus, so it is skipped when --set has
    # narrowed the run to one manifest; every other set's files would otherwise
    # be reported as unrecorded.
    unrecorded = [] if args.set else find_unrecorded(recorded_paths)

    say()
    say(f"{total_ok} file(s) verified, {len(problems)} problem(s), {len(unrecorded)} unrecorded.")

    if unrecorded:
        say()
        say("Present under data/raw/ but not in any manifest:")
        for path in unrecorded:
            say(f"    {path}")
        say()
        say("data/ is gitignored, so an unrecorded file cannot be restored from a")
        say("clean clone. Add it to a manifest or delete it.")

    if load_errors:
        return 3
    if problems:
        return 1
    if unrecorded:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
