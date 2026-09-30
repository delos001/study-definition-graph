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

Usage:       This file is not run directly; other code imports it.
             from sdg.sources import fetch
                fetch(url, destination)   -> path of the .part file written

Exit codes:  There are none, because this file is not run on its own. On a problem it stops
             and hands an error to the program using it, which decides what to
             do. Every error is a kind of FetchError, carrying the exit number and
             sub-code a command reports it with, from docs/exit_codes.csv, and a
             message naming the url and the cause. The errors it can hand back:
             FetchNoAnswerError    the server could not be reached, did not
                                   answer in time, or stopped part way
             FetchRefusedError     the server refused access to the file
             FetchErrorAnswerError the server answered with any other error
             FetchBadUrlError      the url is not one the Hypertext Transfer
                                   Protocol (HTTP) library can use
             FetchNotWrittenError  the download or its folder could not be
                                   written to disk

Date:        2026-09-08
Owner:       Jason Delosh
"""

from __future__ import annotations

import contextlib
from pathlib import Path

# httpx is the HTTP library declared in environment.yml. It is used here rather
# than the standard library's urllib because it streams a response in pieces
# with one call and follows redirects with one setting.
import httpx

#######################################################################################
### Settings ###

# A download is given up after this many seconds of silence from the server.
# The limit is generous because some of the pinned files are PDFs of several
# megabytes served by ICH, and a slow link must not be mistaken for a dead url.
TIMEOUT_SECONDS = 60.0

# A download is written under the destination name plus this suffix. The
# suffix marks the file as unfinished, so nothing else in the repo treats it as
# a pinned file.
PARTIAL_SUFFIX = ".part"


#######################################################################################
### Error Classes ###


class FetchError(Exception):
    """Raised when a download did not complete, and the base of every download error.

    The message names the url and the cause. Each kind carries the exit number and
    sub-code a command reports it with, from docs/exit_codes.csv.
    """

    exit_code = 9
    sub_code = "DOWNLOAD-NO-ANSWER"


class FetchNoAnswerError(FetchError):
    """Raised when the server could not be reached, did not answer in time, or stopped
    sending part way."""

    exit_code = 9
    sub_code = "DOWNLOAD-NO-ANSWER"


class FetchRefusedError(FetchError):
    """Raised when the server refused access to the file, with status 401 or 403."""

    exit_code = 10
    sub_code = "DOWNLOAD-REFUSED"


class FetchErrorAnswerError(FetchError):
    """Raised when the server answered with any other error status, such as 404 for
    a file that is not there."""

    exit_code = 11
    sub_code = "DOWNLOAD-ERROR-ANSWER"


class FetchBadUrlError(FetchError):
    """Raised when the url is not one the HTTP library can use."""

    exit_code = 15
    sub_code = "MANIFEST-URL-INVALID"


class FetchNotWrittenError(FetchError):
    """Raised when the download, or the folder it goes in, could not be written."""

    exit_code = 20
    sub_code = "DOWNLOAD-NOT-WRITTEN"


#######################################################################################
### Fetch ###


def partial_path(destination: Path) -> Path:
    """Give the temporary name a download is written under: the destination plus .part.

    The naming rule lives in this one function, so that finalize_file.py can find the
    file and the checks under validation/ can find the file to look at.

    Args:
        destination: Where the finished file will live.

    Returns:
        The same path with .part added to the name.
    """
    return destination.with_name(destination.name + PARTIAL_SUFFIX)


def fetch(url: str, destination: Path) -> Path:
    """Download one url to its destination, under the temporary .part name.

    The destination's folder is created when it does not exist. When the download fails,
    no temporary file is left behind.

    Args:
        url: Where to download from.
        destination: Where the finished file will live. The download is written beside
            it under the .part name.

    Returns:
        The path of the .part file that was written.

    Raises:
        FetchError: The download did not complete. The kind raised says why, as
            download_error() sorts it.
    """
    partial = partial_path(destination)

    # Every way a download can fail is turned into a kind of FetchError. The
    # program using this module counts each failure and moves on, so it needs one
    # family of errors, and the kind says which group of failure it reports.
    # Creating the folder sits inside the try for the same reason: a file where
    # the folder should be is a failure of this download, not of the whole run.
    # InvalidURL is named on its own because the HTTP library does not count it
    # among its HTTPError family.
    try:
        partial.parent.mkdir(parents=True, exist_ok=True)
        with httpx.stream(
            "GET", url, follow_redirects=True, timeout=TIMEOUT_SECONDS
        ) as response:
            response.raise_for_status()

            with partial.open("wb") as handle:
                for chunk in response.iter_bytes():
                    handle.write(chunk)

    except (httpx.HTTPError, httpx.InvalidURL, OSError) as exc:
        # A half-written .part file would otherwise survive and confuse the
        # next run, so it is removed before the error is handed back. The
        # removal is allowed to fail silently: when the folder could not be
        # created there is nothing to remove and the attempt itself can raise,
        # and the failure worth reporting is the download's, not the cleanup's.
        with contextlib.suppress(OSError):
            partial.unlink()
        raise download_error(exc)(f"{url}\n  cause -> {exc}") from exc

    return partial


def download_error(exc: Exception) -> type[FetchError]:
    """Sort a failed download into the kind of FetchError that names its group.

    The HTTP library's own errors are sorted by what the person reading the report
    has to do. A status of 401 or 403 means access was refused, and any other status
    is an error answer. So are too many redirects and an answer that cannot be
    decoded, because the server did answer. A url the library cannot use is a mistake
    in the manifest. A
    failure to write is a problem on this machine. Everything else, such as a refused
    connection, a timeout or a server that stopped part way, means no answer came.

    Args:
        exc: The error the download raised.

    Returns:
        The kind of FetchError to raise.
    """
    if isinstance(exc, httpx.HTTPStatusError):
        if exc.response.status_code in (401, 403):
            return FetchRefusedError
        return FetchErrorAnswerError
    if isinstance(exc, httpx.InvalidURL | httpx.UnsupportedProtocol):
        return FetchBadUrlError
    if isinstance(exc, httpx.TooManyRedirects | httpx.DecodingError):
        return FetchErrorAnswerError
    if isinstance(exc, OSError):
        return FetchNotWrittenError
    return FetchNoAnswerError
