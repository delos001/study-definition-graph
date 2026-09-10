"""
Script:      acquire_sources.py
Description: Acquires one or more needed source file(s) from their external location
             based on the respective manifest entry and URL.  The manifest must be
             current and accurate for this script to succeed.
             Ends with every entry's file present on disk and matching its entry.
             Only files not yet on disk are fetched; files already on disk are
             fingerprinted and compared, and one that no longer matches is reported
             and left alone for a person to decide.

             Each step is a function in the sdg package. This script runs them in order:
             - read manifest
             - fetch file from URL,
             - fingerprint,
             - compare to its manifest entry,
             - place it in the correct location (only if it matches the entry).

             A file already on disk is never replaced by this script.

Inputs:      manifests/*.json   (read-only)
             manifests/study_documents/*.json   (read-only)
             URL for each file named (read-only)

Outputs:     The files each entry names, under inputs/. Nothing
             existing is modified or deleted.

Usage:       python -m sdg.sources.acquire_sources
                 get whatever is missing
             python -m sdg.sources.acquire_sources --dry-run
                 list what would be fetched; no network, nothing written
             python -m sdg.sources.acquire_sources --set cdisc_usdm_v4
                 one manifest only
             python -m sdg.sources.acquire_sources --quiet
                 print nothing; use the exit code

Exit codes:  0  every entry's file is on disk and matches its entry
             1  a fetch failed, or what arrived did not match its entry
             2  a file already on disk does not match its entry; left alone
             3  no manifests found, or one could not be read
             6  the sdg package is not running from inside its repo

Date:        2026-09-08
Owner:       Jason Delosh
"""

from __future__ import annotations

import argparse
import sys

from .fetch_file import FetchError, fetch
from .finalize_file import discard, place
from .fingerprint_file import compare
from .read_manifests import ManifestError, NotInRepoError, manifests, require_repo

#######################################################################################
### Reporting ###


def make_reporter(quiet: bool):
    """Returns a print function that stays silent when --quiet was given.
    Passing the function around means nothing below has to remember to check
    the flag before printing."""

    def say(message: str = "") -> None:
        if not quiet:
            print(message)

    return say


#######################################################################################
### Acquire Sources ###


def main(argv: list[str] | None = None) -> int:
    """Runs the steps over every manifest entry and returns the exit code.
    `argv` is the command line, or None to read the real one.
    Problems are counted rather than raised, so one run reports the state of the whole
    corpus instead of stopping at the first bad file."""

    parser = argparse.ArgumentParser(
        description="Fetch every recorded source file not yet on disk, and check the ones that are."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="list what would be fetched; no network, nothing written",
    )
    parser.add_argument("--set", dest="only", help="one manifest only, by name")
    parser.add_argument(
        "--quiet", action="store_true", help="print nothing; use the exit code"
    )
    args = parser.parse_args(argv)

    say = make_reporter(args.quiet)

    # The repo check runs first, in every mode. Without it, a package installed
    # the wrong way would look for manifests in the wrong place and report the
    # wrong problem.
    try:
        require_repo()
        found = manifests(args.only)
    except NotInRepoError as exc:
        say(str(exc))
        return 6
    except ManifestError as exc:
        say(str(exc))
        return 3

    fetched = 0
    would_fetch = 0
    present = 0
    failures = 0
    disagreements = 0

    for manifest in found:
        say(manifest.name)

        for entry in manifest.entries:
            # A file already on disk is checked, never replaced. A mismatch is
            # a decision for a person, so it is reported and left alone.
            if entry.path.exists():
                result = compare(entry.path, entry)
                if result.matched:
                    present += 1
                else:
                    say(f"  MISMATCH  {entry.local}: {result.detail}; left alone")
                    disagreements += 1
                continue

            if args.dry_run:
                say(f"  would fetch  {entry.name}")
                would_fetch += 1
                continue

            say(f"  fetching     {entry.name}")
            try:
                partial = fetch(entry.url, entry.path)
            except FetchError as exc:
                say(f"    FAILED  {exc}")
                failures += 1
                continue

            # The download is compared under its temporary name, so a wrong
            # file never appears under a final name even for a moment.
            result = compare(partial, entry)
            if result.matched:
                place(partial)
                fetched += 1
            else:
                say(f"    DISCARDED  {result.detail}")
                discard(partial)
                failures += 1

    say()
    if args.dry_run:
        say(f"{would_fetch} to fetch, {present} present and matching")
    else:
        say(f"{fetched} fetched, {present} present and matching")
    if disagreements:
        say(
            f"{disagreements} file(s) on disk disagree with their entry. Delete deliberately, then re-run."
        )
    if failures:
        say(f"{failures} fetch(es) failed or did not match their entry.")

    # 1 outranks 2: a corpus with a file missing is worse than one whose files
    # are all present but one has changed, because the second at least has
    # known contents on disk.
    if failures:
        return 1
    if disagreements:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
