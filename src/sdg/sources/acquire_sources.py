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

Exit codes:  0   SUCCEEDED  the command succeeded (every entry's file is on
                 disk and matches its entry)
             1   UNHANDLED-ERROR  Python stopped on an error that nothing
                 handled
             2   COMMAND-LINE-REFUSED  the argument parser refused the command
                 line
             3   NOT-IN-REPO  the sdg package is not running from inside its
                 repo
             9   DOWNLOAD-NO-ANSWER  a download's server could not be reached,
                 did not answer in time, or stopped part way
             10  DOWNLOAD-REFUSED  a download's server refused access to the
                 file
             11  DOWNLOAD-ERROR-ANSWER  a download's server answered with an
                 error
             12  MANIFEST-MISSING  the manifests folder is missing or holds no
                 manifest
             12  PINNED-FILE-NOT-DOWNLOADED  a pinned file has not been
                 downloaded (a dry run only; a real run fetches it)
             13  MANIFEST-UNREADABLE  a manifest is on disk but cannot be opened
             13  PINNED-FILE-UNREADABLE  a pinned file is on disk but cannot be
                 opened (left alone)
             14  MANIFEST-UNPARSEABLE  a manifest is not valid JSON
             15  MANIFEST-INVALID  a manifest's content breaks a requirement
             15  MANIFEST-LOCATION-OUTSIDE-INPUTS  a manifest records a
                 location that does not stay under inputs/
             15  MANIFEST-URL-INVALID  a manifest entry's url is not one the
                 download library can use
             16  PINNED-FILE-CHANGED  a pinned file on disk no longer matches
                 its manifest entry (left alone)
             16  DOWNLOAD-MISMATCH  a downloaded file does not match its
                 manifest entry (discarded)
             17  MANIFEST-NAME-NOT-FOUND  no manifest has the name given
             20  DOWNLOAD-NOT-WRITTEN  a download, or its folder, could not be
                 written to disk
             The wording is the table in docs/exit_codes.csv. Every problem is
             reported, and the exit number is the worst one seen, in the order
             of PRECEDENCE below, because a corpus with a file missing is worse
             than one whose files are all present but one has changed. So
             --dry-run --quiet answers whether the pinned files under inputs/
             are complete and intact from the exit number alone.

Date:        2026-09-08
Owner:       Jason Delosh
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable

from sdg.exit_codes import fail, finish, problem_line

from .fetch_file import FetchError, fetch
from .finalize_file import discard, place
from .fingerprint_file import compare
from .read_manifests import ManifestError, NotInRepoError, manifests

#######################################################################################
### Settings ###

# The order in which the problems a run found decide its exit number, worst first.
# A download that failed leaves a file missing, which is worse than a file that is
# present but changed, because the second at least has known contents on disk. In a
# dry run a file that would be fetched is a file missing.
PRECEDENCE = (
    "DOWNLOAD-NO-ANSWER",
    "DOWNLOAD-REFUSED",
    "DOWNLOAD-ERROR-ANSWER",
    "MANIFEST-URL-INVALID",
    "DOWNLOAD-NOT-WRITTEN",
    "DOWNLOAD-MISMATCH",
    "PINNED-FILE-NOT-DOWNLOADED",
    "PINNED-FILE-CHANGED",
    "PINNED-FILE-UNREADABLE",
)

#######################################################################################
### Reporting ###


def make_reporter(quiet: bool) -> Callable[..., None]:
    """Build the function the workflow prints through, silent when --quiet was given.

    Passing the function around means nothing below has to remember to read the flag
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
        description="Fetch every recorded source file not yet on disk, and confirm the ones that are."
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

    # The manifest reader, src/sdg/sources/read_manifests.py, confirms that the sdg
    # package is running from inside its repo before it looks for any manifest, so a
    # package installed the wrong way is reported as that and not as "no manifests
    # found". Each of its errors carries its own exit number and sub-code.
    try:
        found = manifests(args.only)
    except (NotInRepoError, ManifestError) as exc:
        return fail(say, exc.exit_code, exc.sub_code, exc)

    fetched = 0
    would_fetch = 0
    present = 0
    fetch_failures = 0
    wrong_downloads = 0
    mismatches = 0
    unreadable = 0
    # Each problem's sub-code, with the exit number it carries, so the worst can be
    # chosen once the run has seen them all.
    seen: dict[str, int] = {}

    for manifest in found:
        say(manifest.name)

        for entry in manifest.entries:
            # A file already on disk is confirmed, never replaced. A mismatch is
            # a decision for a person, so it is reported and left alone. So is
            # a path that cannot be read at all, such as a folder where a file
            # should be or a workbook Excel has locked. The run carries on, and
            # the exit number says a person has to look.
            if entry.path.exists():
                if entry.path.is_dir():
                    say(
                        "  "
                        + problem_line(
                            "PINNED-FILE-UNREADABLE",
                            f"{entry.local}: a folder, not a file; left alone",
                        )
                    )
                    seen["PINNED-FILE-UNREADABLE"] = 13
                    unreadable += 1
                    continue
                try:
                    result = compare(entry.path, entry)
                except OSError as exc:
                    say(
                        "  "
                        + problem_line(
                            "PINNED-FILE-UNREADABLE",
                            f"{entry.local}: {exc}; left alone",
                        )
                    )
                    seen["PINNED-FILE-UNREADABLE"] = 13
                    unreadable += 1
                    continue
                if result.matched:
                    present += 1
                else:
                    say(
                        "  "
                        + problem_line(
                            "PINNED-FILE-CHANGED",
                            f"{entry.local}: {result.detail}; left alone",
                        )
                    )
                    seen["PINNED-FILE-CHANGED"] = 16
                    mismatches += 1
                continue

            if args.dry_run:
                say(
                    "  "
                    + problem_line(
                        "PINNED-FILE-NOT-DOWNLOADED", f"would fetch {entry.name}"
                    )
                )
                seen["PINNED-FILE-NOT-DOWNLOADED"] = 12
                would_fetch += 1
                continue

            say(f"  fetching     {entry.name}")
            # A url that cannot be fetched is reported and counted, and the run goes on
            # to the next entry, so one dead address does not stop the rest. The kind
            # of error names the group of failure.
            try:
                partial = fetch(entry.url, entry.path)
            except FetchError as exc:
                say("    " + problem_line(exc.sub_code, f"FAILED  {exc}"))
                seen[exc.sub_code] = exc.exit_code
                fetch_failures += 1
                continue

            # The download is compared under its temporary name, so a wrong
            # file never appears under a final name even for a moment.
            result = compare(partial, entry)
            if result.matched:
                place(partial)
                fetched += 1
            else:
                say(
                    "    "
                    + problem_line("DOWNLOAD-MISMATCH", f"DISCARDED  {result.detail}")
                )
                seen["DOWNLOAD-MISMATCH"] = 16
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

    # The worst problem seen decides the exit number.
    for sub_code in PRECEDENCE:
        if sub_code in seen:
            return finish(say, seen[sub_code], sub_code)
    return 0


if __name__ == "__main__":
    sys.exit(main())
