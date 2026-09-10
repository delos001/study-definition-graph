"""
Script:      fetch_file.py
Description: Downloads one file from one url to one destination.

             The url and destination are passed in as two values. For a pinned
             standard, they come from a manifest entry, read by read_manifests.py and
             handed over by acquire_sources.py.  For a new study, they come from the
             ClinicalTrials.gov registry response, and the entry is written after.

             A separate function fingerprints the download; acquire_sources decides
             from that whether to place or discard it. A download that fails part
             way is removed, so no half-file is left to be mistaken for a finished
             one.

             The bytes are written under a temporary name (destination plus .part).
             For example: inputs/standards/cdisc/usdm_v4/USDM-IG.pdf.part.
             The file is later renamed by the place step after the fingerprint has
             matched. A .part file left behind by an earlier run is overwritten,
             because a .part file is by definition unfinished.

             If a server answers that the file has moved, the download follows
             the new address, since ICH and GitHub both do this for some files.

             The file is written to disk piece by piece as it arrives, so a
             large PDF never sits in memory whole.

Inputs:      one url   (network, read-only)

Outputs:     the downloaded file at <destination>.part, and the destination's folder
             if it did not exist; nothing else on disk.
             Hands back the path of that temporary file.

Usage:       Not run directly; imported.
             from sdg.sources import fetch
                fetch(url, destination)   -> path of the .part file written

Exit codes:  None. Not run on its own, so no exit code. On a problem it stops
             and hands an error to the program using it, which decides what to
             do. The errors it can hand back:
             FetchError   the url could not be reached, answered with an error,
                          or the download stopped part way; the message names
                          the url and the cause

Date:        2026-09-08
Owner:       Jason Delosh
"""

from __future__ import annotations

from pathlib import Path

# httpx is the HTTP library declared in environment.yml. It is used here rather
# than the standard library's urllib because it streams a response in pieces
# with one call and follows redirects with one setting.
import httpx

#######################################################################################
### Settings ###

# A download is given up after this many seconds of silence from the server.
# The limit is generous because two of the pinned files are PDFs of several
# megabytes served by ICH, and a slow link must not be mistaken for a dead url.
TIMEOUT_SECONDS = 60.0

# A download is written under the destination name plus this suffix. The
# suffix marks the file as unfinished, so nothing else in the repo treats it as
# a pinned file.
PARTIAL_SUFFIX = ".part"


#######################################################################################
### Error Class ###


class FetchError(Exception):
    """Informs that a download did not complete.
    The message names the url and the cause:
    - the server could not be reached,
    - it answered with an error, or
    - the transfer stopped part way."""


#######################################################################################
### Fetch ###


def partial_path(destination: Path) -> Path:
    """Returns a temporary name given to the download: the destination + .part.
    It is a function so that the naming rule lives in one place: finalize_file.py uses
    it to find the file and 'tests' checks use it to find the file to check."""
    return destination.with_name(destination.name + PARTIAL_SUFFIX)


def fetch(url: str, destination: Path) -> Path:
    """Downloads the file from the specified 'url' and saves it in the specified
    destination folder under the temporary name (see partial_path). The folder is
    created if it does not exist.
    Returns the path of that temporary file.
    Raises FetchError if the download does not complete; in that case no temporary file
    is left behind."""
    partial = partial_path(destination)
    partial.parent.mkdir(parents=True, exist_ok=True)

    # Every way a download can fail is turned into one FetchError. The program
    # using this module treats them all the same way, by counting the failure
    # and moving on, so it needs one error type with the cause in the message.
    try:
        with httpx.stream(
            "GET", url, follow_redirects=True, timeout=TIMEOUT_SECONDS
        ) as response:
            response.raise_for_status()

            with partial.open("wb") as handle:
                for chunk in response.iter_bytes():
                    handle.write(chunk)

    except (httpx.HTTPError, OSError) as exc:
        # A half-written .part file would otherwise survive and confuse the
        # next run, so it is removed before the error is handed back.
        partial.unlink(missing_ok=True)
        raise FetchError(f"{url}\n  cause -> {exc}") from exc

    return partial
