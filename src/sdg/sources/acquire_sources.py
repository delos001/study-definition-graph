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

Usage:       acquire_sources
                 get whatever is missing
             acquire_sources --dry-run
                 list what would be fetched; no network, nothing written
             acquire_sources --set cdisc_usdm_v4
                 one manifest only
             acquire_sources --quiet
                 print nothing; use the exit code

Exit codes:  0   success (every entry's file is on disk and matches its entry)
             1   unhandled error, Python's own
             2   invalid command line, the argument parser's own
             3   a manifest is missing or cannot be read
             6   not running from inside the repo
             8   a pinned file has not been downloaded (a dry run only; a real
                 run fetches it)
             9   a pinned file on disk does not match its manifest entry
                 (left alone)
             11  a download failed
             12  a downloaded file does not match its manifest entry (discarded)
             13  a file on disk cannot be read (left alone)
             The numbers are the repo-wide table in
             validation/exit_codes.csv. Every problem is reported;
             the exit code is the worst one seen, in the order 11, 12, 8, 9,
             13, because a corpus with a file missing is worse than one whose
             files are all present but one has changed. So --dry-run --quiet
             answers whether the pinned files under inputs/ are complete and intact from the exit
             code alone.

Date:        2026-09-08
Owner:       Jason Delosh
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable

from .fetch_file import FetchError, fetch
from .finalize_file import discard, place
from .fingerprint_file import compare
from .read_manifests import ManifestError, NotInRepoError, manifests

#######################################################################################
### Reporting ###


def make_reporter(quiet: bool) -> Callable[..., None]:
    """Build the function the workflow prints through, silent when --quiet was given.

    Passing the function around means nothing below has to remember to check the flag
    before printing.

    Args:
        quiet: True when --quiet was given.

    Returns:
        A function that prints its message, or prints nothing when quiet.
    """

    def say(message: str = "") -> None:
        """Print the message, unless the run is quiet.

        Args:
            message: The line to print. Empty prints a blank line.
        """
        if not quiet:
            print(message)

    return say


#######################################################################################
### Acquire Sources ###


def main(argv: list[str] | None = None) -> int:
    """Run the steps over every manifest entry and give back the exit code.

    Problems are counted rather than raised, so one run reports the state of the whole
    corpus instead of stopping at the first bad file.

    Args:
        argv: The command-line arguments, or None to read the real ones.

    Returns:
        The exit code, as the header block lists them.
    """

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

    # The manifest reader, src/sdg/sources/read_manifests.py, checks that the sdg package is running from inside its repo
    # before it looks for any manifest, so a package installed the wrong way
    # is reported as that and not as "no manifests found".
    try:
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
    fetch_failures = 0
    wrong_downloads = 0
    mismatches = 0
    unreadable = 0

    for manifest in found:
        say(manifest.name)

        for entry in manifest.entries:
            # A file already on disk is checked, never replaced. A mismatch is
            # a decision for a person, so it is reported and left alone. So is
            # a path that cannot be read at all, a folder where a file should
            # be or a workbook Excel has locked: the run carries on and the
            # exit code says a person has to look.
            if entry.path.exists():
                if entry.path.is_dir():
                    say(
                        f"  CANNOT READ  {entry.local}: a folder, not a file; left alone"
                    )
                    unreadable += 1
                    continue
                try:
                    result = compare(entry.path, entry)
                except OSError as exc:
                    say(f"  CANNOT READ  {entry.local}: {exc}; left alone")
                    unreadable += 1
                    continue
                if result.matched:
                    present += 1
                else:
                    say(f"  MISMATCH  {entry.local}: {result.detail}; left alone")
                    mismatches += 1
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
                fetch_failures += 1
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
                wrong_downloads += 1

    say()
    if args.dry_run:
        say(f"{would_fetch} to fetch, {present} present and matching")
    else:
        say(f"{fetched} fetched, {present} present and matching")
    if mismatches or unreadable:
        say(
            f"{mismatches + unreadable} file(s) on disk disagree with their entry or cannot be read. Look, then delete deliberately and re-run."
        )
    if fetch_failures or wrong_downloads:
        say(
            f"{fetch_failures + wrong_downloads} fetch(es) failed or did not match their entry."
        )

    # One exit code per cause, the worst one seen. A corpus with a file missing
    # is worse than one whose files are all present but one has changed, because
    # the second at least has known contents on disk. In a dry run a file that
    # would be fetched is a file missing.
    if fetch_failures:
        return 11
    if wrong_downloads:
        return 12
    if would_fetch:
        return 8
    if mismatches:
        return 9
    if unreadable:
        return 13
    return 0


if __name__ == "__main__":
    sys.exit(main())
