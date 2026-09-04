"""
Script:      fetch_sources.py
Description: Downloads every pinned source file recorded in data/manifests/ to
             the local path that manifest names, and verifies each one against
             its recorded sha256 before putting it in place.

             This exists because data/ is gitignored. A fresh clone has the
             manifests and none of the files they describe, so the repo was
             unusable to anyone who had not downloaded the corpus by hand. The
             instructions for doing it lived in README.md as a shell loop, which
             nothing executes and therefore nothing tests.

             It also gives the manifest "url" field its first consumer in code.
             Every other manifest field is checked by verify_manifests.py; a
             wrong or dead url was undetectable until someone attempted a fresh
             clone, which is the worst moment to discover it.

             This script never overwrites a file that already exists. CLAUDE.md
             makes data/raw/ immutable, so a file already on disk whose hash
             disagrees with its manifest is a human decision, not something a
             download script should silently resolve. It is reported and left
             alone. Delete it deliberately, then re-run.

Inputs:      data/manifests/*.json   (read-only)
             The urls those manifests name (network, read-only)

Outputs:     The files named by each manifest's "local" field, written under
             data/raw/. Nothing else is written, and nothing existing is
             modified or deleted.

Usage:       python scripts/fetch_sources.py
                 download whatever is missing, verify everything present
             python scripts/fetch_sources.py --dry-run
                 list what would be downloaded; touches no network, writes nothing
             python scripts/fetch_sources.py --set raw_ich_m11
                 one manifest only
             python scripts/fetch_sources.py --quiet
                 print nothing; use the exit code. For hooks and scripts.

Exit codes:  0  every recorded file is present and matches its recorded sha256
             1  a download failed, or a downloaded file did not match its hash
             2  a file already on disk disagrees with its manifest; not touched
             3  no manifests found, or one could not be parsed

             1 outranks 2 when both occur, because a failed fetch leaves the
             corpus incomplete while a disagreeing file at least still has
             known contents.

Date:        2026-08-24
Owner:       Jason Delosh
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import httpx

# Imported rather than reimplemented. sdg.pinned owns how a manifest is located,
# parsed and hashed (the same code the pipeline uses to verify a pinned file
# before reading it), and a second copy of that knowledge here is exactly the
# drift this script was written to remove. Needs the package installed
# editable (pip install -e ., README.md step 1b).
from sdg.pinned import REPO_ROOT, load_manifests, sha256_of


### Constants ##################################################################

# Generous because two of the pinned files are multi-megabyte PDFs served by
# ICH, and one is a GitHub raw fetch. Long enough that a slow link is not
# mistaken for a dead url, short enough that a hung request still ends.
TIMEOUT_SECONDS = 60.0

# Downloads land here first and are only renamed into place after their hash is
# confirmed. The suffix keeps a partial or corrupt download from ever appearing
# under data/raw/ looking like a pinned file, which matters because
# verify_manifests.py treats anything unrecorded there as a problem.
PARTIAL_SUFFIX = ".part"


### Reporting ##################################################################


def make_reporter(quiet: bool):
    """
    Return a print function that honours --quiet.

    A function rather than a global flag so that nothing below has to remember
    to check the flag before printing. Matches the reporting approach in
    verify_manifests.py.
    """

    def say(message: str = "") -> None:
        if not quiet:
            print(message)

    return say


### Fetching ###################################################################


def download_to(url: str, target: Path, say) -> str | None:
    """
    Download one url and return the sha256 of what arrived, or None on failure.

    Writes to a sibling .part file and leaves it there for the caller to verify
    and rename. Streamed rather than read whole so that memory use stays flat
    regardless of file size, matching how verify_manifests.py hashes.

    Redirects are followed because ICH and GitHub both serve some of these urls
    through one, and a manifest records the address a human was given rather
    than the final location.
    """
    partial = target.with_name(target.name + PARTIAL_SUFFIX)
    partial.parent.mkdir(parents=True, exist_ok=True)

    # Network and filesystem failures are absorbed and turned into a None
    # return so that one dead url does not abandon the rest of the corpus. The
    # caller counts the failure and carries on to the next file.
    try:
        with httpx.stream(
            "GET", url, follow_redirects=True, timeout=TIMEOUT_SECONDS
        ) as response:
            response.raise_for_status()

            with partial.open("wb") as handle:
                for chunk in response.iter_bytes():
                    handle.write(chunk)

    except (httpx.HTTPError, OSError) as exc:
        say(f"    FAILED  {exc}")

        # A half-written .part would otherwise survive to confuse the next run.
        partial.unlink(missing_ok=True)
        return None

    return sha256_of(partial)


def place_or_discard(target: Path, recorded_hash: str, actual_hash: str, say) -> bool:
    """
    Rename a verified download into place, or delete it and report. True on success.

    The hash is checked before the file reaches its final name, so a corrupt or
    silently replaced download never lands under data/raw/ at all. That is the
    whole reason for the .part dance: data/raw/ is supposed to contain only
    files whose contents are known.
    """
    partial = target.with_name(target.name + PARTIAL_SUFFIX)

    if actual_hash != recorded_hash:
        say(f"    HASH MISMATCH  expected {recorded_hash[:12]}, got {actual_hash[:12]}")
        partial.unlink(missing_ok=True)
        return False

    partial.replace(target)
    return True


### Entry point ################################################################


def main() -> int:
    """
    Walk every manifest, fetch what is missing, verify what is present.

    Returns the process exit code. Problems are counted rather than raised so
    that the run reports the state of the whole corpus in one pass instead of
    stopping at the first bad file.
    """
    parser = argparse.ArgumentParser(
        description="Download the pinned source files recorded in data/manifests/."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="list what would be downloaded; no network, nothing written",
    )
    parser.add_argument("--set", dest="only", help="one manifest only, by filename stem")
    parser.add_argument("--quiet", action="store_true", help="print nothing; use the exit code")
    args = parser.parse_args()

    say = make_reporter(args.quiet)

    manifests, load_errors = load_manifests(args.only)

    for error in load_errors:
        say(f"manifest error: {error}")

    # An unparseable manifest is fatal in the same way it is for
    # verify_manifests.py: every file location downstream of it is unknown, so
    # reporting a clean run would be a lie.
    if load_errors:
        return 3

    if not manifests:
        say(f"no manifests found matching --set {args.only}" if args.only else "no manifests found")
        return 3

    downloaded = 0
    already_present = 0
    would_download = 0
    failures = 0
    disagreements = 0

    for path, manifest in manifests:
        say(f"{path.stem}")

        for entry in manifest.get("files", []):
            local = entry.get("local")
            url = entry.get("url")
            recorded_hash = entry.get("sha256")
            name = entry.get("name") or (Path(local).name if local else "?")

            # A manifest entry missing any of these cannot be acted on. Counted
            # as a disagreement rather than skipped silently, because a manifest
            # that cannot describe its own file is a defect in the manifest.
            if not (local and url and recorded_hash):
                say(f"  {name}: manifest entry has no local, url or sha256")
                disagreements += 1
                continue

            target = REPO_ROOT / local

            if target.exists():
                # Present already. Verified rather than assumed correct, so that
                # one command answers both "do I have everything" and "is what I
                # have still what was pinned".
                if sha256_of(target) == recorded_hash:
                    already_present += 1
                    continue

                say(f"  {name}: on disk but does not match its manifest, left alone")
                disagreements += 1
                continue

            if args.dry_run:
                say(f"  would fetch  {name}")
                would_download += 1
                continue

            say(f"  fetching     {name}")
            actual_hash = download_to(url, target, say)

            if actual_hash is None:
                failures += 1
                continue

            if place_or_discard(target, recorded_hash, actual_hash, say):
                downloaded += 1
            else:
                failures += 1

    say()

    if args.dry_run:
        say(f"{would_download} to fetch, {already_present} already present and matching")
    else:
        say(f"{downloaded} downloaded, {already_present} already present and matching")

    if disagreements:
        say(f"{disagreements} file(s) disagree with their manifest. Delete deliberately, then re-run.")

    if failures:
        say(f"{failures} download(s) failed or did not match their recorded hash.")

    # 1 outranks 2: an incomplete corpus is worse than one whose contents are
    # known but unexpected. Documented in the header so a caller reading only
    # the exit code knows which condition it saw.
    if failures:
        return 1

    if disagreements:
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
