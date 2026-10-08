"""
Script:      download_ctgov_study_documents.py
Description: Downloads the protocol and the SAP of each study you name from
             ClinicalTrials.gov. Without --accept, they go into your review folder
             outside the repo, so you can decide whether to use the study. With
             --accept, they are pinned under inputs/study_documents/ and recorded in
             the study's manifest.

             Each study is named by its NCT number, the National Clinical Trial
             number ClinicalTrials.gov gives every study, such as NCT05259917. A
             study's manifest is manifests/study_documents/<NCT number>.json. Before
             a file is pinned, its size must match the size ClinicalTrials.gov lists,
             and its manifest entry is written before the file gets its final name, so
             a pinned file is never on disk without a record.

             You name the studies by their NCT numbers on the command line. The
             script asks ClinicalTrials.gov for those studies only, in one request.

             For each study, the script downloads the protocol and the SAP, whichever
             the study posted, including a single file that combines the two. Other
             files posted, such as an informed consent form, are left alone.

             ClinicalTrials.gov gives each file's name, but not the web address to
             download it from. This script builds the address from the pattern in
             DOCUMENT_URL.

             Each file is saved in <folder>/<NCT number>/, under the file name
             ClinicalTrials.gov uses. <folder> is your local review folder, or
             inputs/study_documents/ if --accept is used. A pinned file's name has
             its spaces replaced by underscores, as CLAUDE.md requires.

             Your review folder is set by the CTGOV_REVIEW_DIR line in .env. It must
             be a full path to a folder outside the repo.

             A file that is already saved is not downloaded again, and the script
             reports that it skipped it. With --accept, a file already under inputs/
             is skipped only when its study's manifest records it. One that is not
             recorded is reported and left in place. A file the manifest records
             but that is missing from inputs/ is reported and not downloaded,
             because acquire_sources restores it against its recorded fingerprint.

             When one study or one file fails, the script reports the problem and
             carries on with the rest.

             The process uses the steps defined in main().

Inputs:      the NCT numbers typed on the command line
             .env at the repo root (read-only; only the CTGOV_REVIEW_DIR line, and
             only without --accept)
             the ClinicalTrials.gov API, and the server that holds the posted files
             (read-only)

Outputs:     Without --accept, the downloaded files in the review folder, one folder
             per study. Nothing in the repo is written.
             With --accept, the files under inputs/study_documents/<NCT number>/, and
             one manifest per study under manifests/study_documents/.
             The script prints each study, each file it downloads or skips, and each
             problem.

Usage:       download_ctgov_study_documents NCT05259917
                 download one study's protocol and SAP to the review folder
             download_ctgov_study_documents NCT05259917 NCT04573309
                 download several studies in one run
             download_ctgov_study_documents NCT05259917 --accept
                 pin the study's protocol and SAP, and record them in its manifest
             download_ctgov_study_documents NCT05259917 --quiet
                 print nothing; use the exit code

Exit codes:  0   SUCCEEDED  the command succeeded
             1   UNHANDLED-ERROR  Python stopped on an error that nothing handled
             2   COMMAND-LINE-REFUSED  the argument parser refused the command line
                 (this includes a value that is not NCT followed by eight digits)
             3   NOT-IN-REPO  the sdg package is not running from inside its repo
             4   ENV-FILE-MISSING  the .env file has not been created
             4   CTGOV-REVIEW-DIR-MISSING  .env has no review folder for
                 ClinicalTrials.gov downloads
             5   CTGOV-REVIEW-DIR-ESCAPED  the review folder in .env is in double
                 quotes, so its backslashes were read as escape codes
             5   CTGOV-REVIEW-DIR-INVALID  the review folder in .env is not a full
                 path outside the repo
             9   CTGOV-NO-ANSWER  ClinicalTrials.gov could not be reached or did
                 not answer in time
             9   DOWNLOAD-NO-ANSWER  a download's server could not be reached,
                 did not answer in time, or stopped part way
             10  DOWNLOAD-REFUSED  a download's server refused access to the
                 file
             11  CTGOV-ERROR-ANSWER  ClinicalTrials.gov answered with an error
             11  CTGOV-DOWNLOAD-ERROR-ANSWER  ClinicalTrials.gov's file server
                 answered with an error
             12  PINNED-FILE-NOT-DOWNLOADED  a pinned file has not been downloaded
                 (with --accept, a file the study's manifest records that is missing
                 from inputs/study_documents/)
             12  MANIFEST-MISSING  the manifests folder is missing or holds no
                 manifest (with --accept, when a study's manifest is read to
                 confirm a file already in inputs/study_documents/)
             13  CTGOV-DOWNLOAD-UNREADABLE  a downloaded file cannot be opened to
                 confirm its size or measure its fingerprint (the download is
                 deleted, or the message names it for removal by hand)
             13  MANIFEST-UNREADABLE  a manifest is on disk but cannot be opened
             14  CTGOV-REPLY-UNPARSEABLE  the answer from ClinicalTrials.gov is not
                 valid JSON
             14  MANIFEST-UNPARSEABLE  a manifest is not valid JSON
             15  MANIFEST-INVALID  a manifest's content breaks a requirement
             15  MANIFEST-LOCATION-OUTSIDE-INPUTS  a manifest records a location
                 that does not stay under inputs/ (with --accept, an entry in the
                 study's manifest)
             15  MANIFEST-URL-INVALID  a manifest entry's url is not one the
                 download library can use (here the address was built from
                 DOCUMENT_URL, not taken from a manifest)
             16  CTGOV-DOWNLOAD-SIZE-MISMATCH  a downloaded file's size differs
                 from the size ClinicalTrials.gov lists (the download is deleted,
                 or the message names it for removal by hand)
             16  FILE-UNRECORDED  a file under inputs/ is recorded by no manifest
                 (with --accept, a file already in inputs/study_documents/ that
                 its study's manifest does not record; it is left in place)
             17  CTGOV-STUDY-NOT-FOUND  an NCT number given is not on
                 ClinicalTrials.gov
             18  CTGOV-NO-STUDY-DOCUMENTS  a study has posted no protocol or SAP
             19  MANIFEST-ENTRY-EXISTS  a manifest already records the file, and
                 replacing it was not asked for (the download is deleted, or the
                 message names it for removal by hand)
             20  CTGOV-DOWNLOAD-NOT-PLACED  a downloaded file is recorded in its
                 manifest but could not be given its final name (the download is
                 deleted, or the message names it for removal by hand)
             20  DOWNLOAD-NOT-WRITTEN  a download, or its folder, could not be
                 written to disk
             20  MANIFEST-NOT-WRITTEN  a manifest, or its folder, could not be
                 written to disk (the download is deleted, or the message names it
                 for removal by hand)
             The wording above is copied from docs/exit_codes.csv. Every problem is
             reported. When there are several, the one listed first in PRECEDENCE
             below decides the exit number. A problem missing from PRECEDENCE still
             fails the run, with the highest exit number among the problems seen.

Date:        2026-10-06
Owner:       Jason Delosh
"""

import argparse
import re
import sys
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

from dotenv import dotenv_values

from sdg.exit_codes import fail, finish, problem_line
from sdg.sources.fetch_ctgov_study_records import CtgovError, fetch_study_records
from sdg.sources.fetch_file import FetchError, FetchErrorAnswerError, fetch
from sdg.sources.finalize_file import discard, place
from sdg.sources.fingerprint_file import Fingerprint, fingerprint
from sdg.sources.parse_ctgov_study_records import list_study_documents
from sdg.sources.read_manifests import (
    REPO_ROOT,
    STUDY_MANIFEST_DIR,
    ManifestError,
    ManifestNameError,
    NotInRepoError,
    manifests,
    require_repo,
)
from sdg.sources.write_manifests import write_entry

#######################################################################################
### Settings ###

# The address of the ClinicalTrials.gov API that study records are requested from.
API = "https://clinicaltrials.gov/api/v2/studies"

# The parts of each study record to ask for. NCTId matches each record to a number
# you typed. BriefTitle becomes the description of a new manifest. DocumentSection
# lists the files the sponsor posted.
FIELDS = "NCTId|BriefTitle|DocumentSection"

# The pattern of the web address a posted file is downloaded from. {folder} is the
# last two digits of the NCT number. No ClinicalTrials.gov page read so far publishes
# this pattern. It was confirmed on 2026-10-06, when both files posted for NCT05259917
# downloaded from addresses built this way, at the sizes the API lists.
DOCUMENT_URL = "https://cdn.clinicaltrials.gov/large-docs/{folder}/{nct_id}/{filename}"

# The study's own page on ClinicalTrials.gov, recorded as the source of its manifest.
STUDY_PAGE_URL = "https://clinicaltrials.gov/study/{nct_id}"

# Where --accept pins the files, written the way a manifest records a location.
PINNED_DIR = "inputs/study_documents"

# The review folder is read from the CTGOV_REVIEW_DIR line of .env at the repo root.
# .env is gitignored, so each machine sets its own folder and it is never committed.
ENV_FILE = REPO_ROOT / ".env"
REVIEW_DIR_SETTING = "CTGOV_REVIEW_DIR"

# An NCT number is NCT followed by eight digits.
NCT_PATTERN = re.compile(r"NCT\d{8}")

# When a run meets several problems, the first one in this list that happened decides
# the exit number. Problems with a manifest come first, because a manifest is the
# record of what is pinned. Failed downloads come next, because running again may fix
# them. A study with nothing to download comes last. A problem left off this list is
# caught at the end of main(), so a forgotten sub-code never ends a run as a success.
PRECEDENCE = (
    "MANIFEST-NOT-WRITTEN",
    "MANIFEST-MISSING",
    "MANIFEST-UNREADABLE",
    "MANIFEST-UNPARSEABLE",
    "MANIFEST-INVALID",
    "MANIFEST-LOCATION-OUTSIDE-INPUTS",
    "MANIFEST-ENTRY-EXISTS",
    "FILE-UNRECORDED",
    "PINNED-FILE-NOT-DOWNLOADED",
    "CTGOV-DOWNLOAD-NOT-PLACED",
    "CTGOV-DOWNLOAD-SIZE-MISMATCH",
    "CTGOV-DOWNLOAD-UNREADABLE",
    "DOWNLOAD-NO-ANSWER",
    "DOWNLOAD-REFUSED",
    "CTGOV-DOWNLOAD-ERROR-ANSWER",
    "MANIFEST-URL-INVALID",
    "DOWNLOAD-NOT-WRITTEN",
    "CTGOV-STUDY-NOT-FOUND",
    "CTGOV-NO-STUDY-DOCUMENTS",
)

#######################################################################################
### Failures ###

# Each failure has an exit number and a sub-code, both listed in docs/exit_codes.csv.


class ReviewDirError(Exception):
    """Raised when the review folder cannot be read from .env.

    Each of the four errors below is one reason it cannot be read.
    """

    exit_code: int
    sub_code: str


class EnvFileMissingError(ReviewDirError):
    """Raised when the repo has no .env file."""

    exit_code = 4
    sub_code = "ENV-FILE-MISSING"


class ReviewDirMissingError(ReviewDirError):
    """Raised when .env has no CTGOV_REVIEW_DIR line, or the line has no value."""

    exit_code = 4
    sub_code = "CTGOV-REVIEW-DIR-MISSING"


class ReviewDirEscapedError(ReviewDirError):
    """Raised when the review folder is in double quotes, and its backslashes were read
    as escape codes."""

    exit_code = 5
    sub_code = "CTGOV-REVIEW-DIR-ESCAPED"


class ReviewDirInvalidError(ReviewDirError):
    """Raised when the review folder is not a full path, or is inside the repo."""

    exit_code = 5
    sub_code = "CTGOV-REVIEW-DIR-INVALID"


class SizeMismatchError(Exception):
    """Raised when a downloaded file's size differs from the size ClinicalTrials.gov
    lists."""

    exit_code = 16
    sub_code = "CTGOV-DOWNLOAD-SIZE-MISMATCH"


#######################################################################################
### Reading the command line ###


def nct_number(text: str) -> str:
    """Confirm that a value typed on the command line is an NCT number.

    The argument parser runs this on each value, so a wrong value is refused before
    ClinicalTrials.gov is contacted. Lower-case letters are accepted and changed to
    upper case.

    Args:
        text: One value typed on the command line.

    Returns:
        The NCT number in upper case.

    Raises:
        argparse.ArgumentTypeError: The value is not NCT followed by eight digits.
    """
    number = text.strip().upper()
    if not NCT_PATTERN.fullmatch(number):
        raise argparse.ArgumentTypeError(
            f"{text} is not an NCT number, which is NCT followed by eight digits"
        )
    return number


#######################################################################################
### Reading the review folder ###


def read_review_dir(env_path: Path = ENV_FILE) -> Path:
    """Read the review folder from .env, and confirm it is a full path outside the repo.

    The folder does not have to exist yet, because fetch creates it on the first
    download.

    Args:
        env_path: The .env file to read.

    Returns:
        The review folder, as a full path.

    Raises:
        EnvFileMissingError: There is no .env file.
        ReviewDirMissingError: .env has no CTGOV_REVIEW_DIR line, or the line has no
            value.
        ReviewDirEscapedError: The value is in double quotes, and its backslashes
            were read as escape codes.
        ReviewDirInvalidError: The folder is not a full path, or it is inside the repo.
    """
    if not env_path.is_file():
        raise EnvFileMissingError(
            f"{env_path.name} does not exist at {env_path.parent}."
        )

    # python-dotenv reads .env the way other tools do. It accepts spaces around the =,
    # a line starting with spaces or with export, quotes around the value, and a
    # comment after it. When the setting appears on several lines, the last one wins.
    # A line with no = at all reads as None, and is treated like an empty value.
    settings = dotenv_values(env_path, encoding="utf-8")
    if REVIEW_DIR_SETTING not in settings:
        raise ReviewDirMissingError(
            f"{env_path.name} has no {REVIEW_DIR_SETTING} line."
        )
    value = (settings[REVIEW_DIR_SETTING] or "").strip()
    if not value:
        raise ReviewDirMissingError(
            f"the {REVIEW_DIR_SETTING} line in {env_path.name} has no value, or a "
            f"later {REVIEW_DIR_SETTING} line with no value replaces it."
        )

    # Inside double quotes, python-dotenv reads a backslash as the start of an escape
    # code, so \f in C:\Users\delos\for_review becomes a form feed. No folder name
    # holds such a character, so one in the value means the path was damaged this way.
    if any(ord(character) < 32 for character in value):
        raise ReviewDirEscapedError(
            f"the {REVIEW_DIR_SETTING} value in {env_path.name} is in double quotes, "
            "so its backslashes were read as escape codes. Write the path without "
            "quotes, or in single quotes."
        )

    folder = Path(value)
    if not folder.is_absolute():
        raise ReviewDirInvalidError(
            f"{REVIEW_DIR_SETTING} is {value}, which is not a full path."
        )
    # resolve() works out the real folder a path leads to. A path written with .. can
    # look as if it is outside the repo and still lead inside it, and this catches that.
    folder = folder.resolve()
    if folder.is_relative_to(REPO_ROOT.resolve()):
        raise ReviewDirInvalidError(
            f"{REVIEW_DIR_SETTING} is {folder}, which is inside the repo."
        )
    return folder


#######################################################################################
### Choosing which files to download ###


def protocol_and_sap(study: dict[str, Any]) -> list[dict[str, Any]]:
    """Keep the protocol and SAP from the files a study posted, and drop the rest.

    A study can post several files, such as a protocol, a SAP and an informed consent
    form. list_study_documents in parse_ctgov_study_records.py lists all of them.
    ClinicalTrials.gov marks each file as a protocol, a SAP, or both. A file is kept
    when it carries either mark, so a combined protocol and SAP file is kept too.

    Args:
        study: One study's record, from fetch_study_records in
            fetch_ctgov_study_records.py.

    Returns:
        The entries of the protocol and SAP files, or an empty list when there are none.
    """
    return [
        document
        for document in list_study_documents(study)
        if document.get("hasProtocol") or document.get("hasSap")
    ]


#######################################################################################
### Building a file's web address ###


def document_url(nct_id: str, document: dict[str, Any]) -> str:
    """Build the web address to the location of a file on ClinicalTrials.gov.

    Args:
        nct_id: The study's NCT number.
        document: One file's entry, from protocol_and_sap.

    Returns:
        The web address, following the pattern in DOCUMENT_URL.

    Raises:
        KeyError: The file's entry has no file name.
    """
    return DOCUMENT_URL.format(
        folder=nct_id[-2:], nct_id=nct_id, filename=document["filename"]
    )


#######################################################################################
### Naming a pinned file ###


def pinned_name(filename: str) -> str:
    """Give the name a file is pinned under in inputs/study_documents/.

    A pinned file keeps its publisher's name with spaces replaced by underscores, as
    CLAUDE.md requires. The download address keeps the original name, because that is
    the name ClinicalTrials.gov serves the file under.

    Args:
        filename: The file's name as ClinicalTrials.gov gives it, from protocol_and_sap.

    Returns:
        The name with every space replaced by an underscore.
    """
    return filename.replace(" ", "_")


#######################################################################################
### Confirming a download's size ###


def confirm_size(partial: Path, document: dict[str, Any]) -> None:
    """Confirm that a downloaded file is the size ClinicalTrials.gov lists for it.

    Args:
        partial: The downloaded file under its temporary name, from fetch.
        document: The file's entry, from protocol_and_sap, which holds the size
            ClinicalTrials.gov lists.

    Raises:
        SizeMismatchError: The two sizes differ.
    """
    size = partial.stat().st_size
    if size != document.get("size"):
        raise SizeMismatchError(
            f"{document['filename']} is {size} bytes, and ClinicalTrials.gov lists "
            f"{document.get('size')}."
        )


#######################################################################################
### Confirming that a pinned file is recorded ###


def recorded_in_manifest(nct_id: str, filename: str) -> bool:
    """Say whether a study's manifest records a file under inputs/study_documents/.

    The manifest is read through manifests in read_manifests.py, which reads it the
    same way every other command does.

    Args:
        nct_id: The study's NCT number, which is also its manifest's name.
        filename: The file's pinned name, from pinned_name.

    Returns:
        True when the study's manifest has an entry for the file. False when it has no
        such entry, or the study has no manifest.

    Raises:
        ManifestError: The manifests folder is missing, or the study's manifest cannot
            be opened or breaks a requirement. Each kind of ManifestError names which.
    """
    local = f"{PINNED_DIR}/{nct_id}/{filename}"
    # A study that has never been accepted has no manifest, which manifests reports as
    # a name it cannot find. Here that only means the file is not recorded.
    try:
        found = manifests(nct_id)
    except ManifestNameError:
        return False
    return any(entry.local == local for manifest in found for entry in manifest.entries)


#######################################################################################
### Removing a download that failed ###


def remove_download(partial: Path) -> str:
    """Delete a download that failed, and say whether it was deleted.

    A file that could not be opened may also refuse to be deleted, for the same reason,
    so a failed deletion is reported rather than raised.

    Args:
        partial: The downloaded file under its temporary name, from fetch.

    Returns:
        A phrase for the problem line: that the download was deleted, or that it must be
        removed by hand, with its path.
    """
    try:
        discard(partial)
    except OSError:
        return f"The download could not be deleted. Remove {partial} by hand."
    return "The download was deleted."


#######################################################################################
### Compiling a study's manifest information ###


def manifest_set_details(nct_id: str, study: dict[str, Any]) -> dict[str, Any]:
    """Build the study-level fields of a study's manifest.

    These are the set name, description, publisher, source and folder, which come
    before the list of files. write_entry uses them only when the study has no
    manifest yet.

    Args:
        nct_id: The study's NCT number.
        study: The study's record, from fetch_study_records in
            fetch_ctgov_study_records.py.

    Returns:
        The set name, description, publisher, source and folder of the manifest.
    """
    return {
        "set": nct_id,
        "description": study["protocolSection"]["identificationModule"].get(
            "briefTitle", ""
        ),
        "publisher": "ClinicalTrials.gov",
        "source": STUDY_PAGE_URL.format(nct_id=nct_id),
        "local_dir": f"{PINNED_DIR}/{nct_id}",
    }


def manifest_entry(
    nct_id: str, document: dict[str, Any], measured: Fingerprint
) -> dict[str, Any]:
    """Build a file's manifest entry from ClinicalTrials.gov's details and the file's
    fingerprint.

    Args:
        nct_id: The study's NCT number.
        document: The file's entry, from protocol_and_sap.
        measured: The file's size and sha256, from fingerprint in fingerprint_file.py.

    Returns:
        The entry, with the fields every manifest entry holds, plus the label and dates
        ClinicalTrials.gov gives the file.
    """
    filename = pinned_name(document["filename"])

    # The version is made from the two dates ClinicalTrials.gov gives the file. A date
    # it leaves out is left out here too, so the entry never records a missing date as
    # if it were a value.
    dates = []
    if document.get("date"):
        dates.append(f"dated {document['date']}")
    if document.get("uploadDate"):
        dates.append(f"uploaded {document['uploadDate']}")
    version = ", ".join(dates) or "no date given by ClinicalTrials.gov"

    return {
        "name": filename,
        "url": document_url(nct_id, document),
        "local": f"{PINNED_DIR}/{nct_id}/{filename}",
        "format": Path(filename).suffix.lstrip(".").upper(),
        "read_by": "both",
        "role": document.get("label", ""),
        "version": version,
        "retrieved": date.today().isoformat(),
        "bytes": measured.bytes,
        "sha256": measured.sha256,
    }


#######################################################################################
### Printing what happened ###


def make_reporter(quiet: bool) -> Callable[..., None]:
    """Build the function the run prints through, which prints nothing under --quiet.

    Passing this function around means nothing else has to remember to read the flag
    before printing. acquire_sources.py builds its printing function the same way.

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


def report(
    say: Callable[..., None],
    seen: dict[str, int],
    indent: str,
    sub_code: str,
    exit_code: int,
    message: object,
) -> None:
    """Print one problem, and keep its sub-code and exit number for the end of the run.

    Args:
        say: The printing function, from make_reporter.
        seen: The problems kept so far, by sub-code, which main uses at the end to
            choose the exit number.
        indent: The spaces put in front of the line, so the problem sits under the
            study or file it belongs to.
        sub_code: The problem's sub-code, as docs/exit_codes.csv lists it.
        exit_code: The exit number the sub-code carries.
        message: What went wrong.
    """
    say(indent + problem_line(sub_code, message))
    seen[sub_code] = exit_code


#######################################################################################
### Downloading the files ###


def main(argv: list[str] | None = None) -> int:
    """Download the protocol and SAP of each study given, and report what happened.

    The steps run in this order.
    - The folder is chosen.
        - Without --accept, read_review_dir reads the review folder from .env.
        - With --accept, the folder is inputs/study_documents/.
    - fetch_study_records fetches the records of all the NCT numbers given, in
      one request.
    - protocol_and_sap keeps each study's protocol and SAP files, and drops its other
      files.
    - A file already in the folder is skipped. With --accept, recorded_in_manifest
      first says whether the study's manifest records the file. A file on disk that
      is not recorded is reported instead of skipped, and a recorded file missing
      from disk is reported instead of downloaded.
    - fetch downloads each other file under a temporary name, from the address
      document_url builds.
    - With --accept, confirm_size confirms each file's size, fingerprint measures it,
      and write_entry writes the entry manifest_entry builds into the study's
      manifest. A file whose size does not match, that cannot be opened, or that
      cannot be recorded is deleted by remove_download.
    - place renames each file to its final name. With --accept, a file that cannot
      be renamed is already in its manifest, so it is reported, deleted by
      remove_download, and left for acquire_sources to download again.

    A failure before any download starts ends the run. A problem with one study or one
    file is reported, and the run carries on with the rest.

    Args:
        argv: The command-line arguments, or None to read the real ones.

    Returns:
        The exit code, as the header block lists them.
    """
    parser = argparse.ArgumentParser(
        description="Download the protocol and SAP of each study named, from "
        "ClinicalTrials.gov, into the review folder set in .env, or pin them with "
        "--accept."
    )
    parser.add_argument(
        "nct_ids",
        nargs="+",
        type=nct_number,
        metavar="NCT",
        help="one or more NCT numbers, such as NCT05259917",
    )
    parser.add_argument(
        "--accept",
        action="store_true",
        help="pin the files under inputs/study_documents/ and record them",
    )
    parser.add_argument(
        "--quiet", action="store_true", help="print nothing; use the exit code"
    )
    args = parser.parse_args(argv)

    say = make_reporter(args.quiet)
    # Each problem's sub-code and exit number are kept, so the worst problem can
    # decide the exit number at the end.
    seen: dict[str, int] = {}

    # require_repo confirms first that the package runs from inside its repo,
    # because .env and inputs/ are both found from the repo root.
    try:
        require_repo()
    except NotInRepoError as exc:
        return fail(say, exc.exit_code, exc.sub_code, exc)

    # A number typed twice is requested and downloaded only once. The order the
    # numbers were typed in is kept.
    nct_ids = list(dict.fromkeys(args.nct_ids))

    # Without a folder there is nowhere to save the files, and without the records
    # there is nothing to download. Either failure ends the run here.
    try:
        folder = REPO_ROOT / PINNED_DIR if args.accept else read_review_dir()
        studies = fetch_study_records(
            API, f"AREA[NCTId]({' OR '.join(nct_ids)})", FIELDS
        )
    except (ReviewDirError, CtgovError) as exc:
        return fail(say, exc.exit_code, exc.sub_code, exc)

    # ClinicalTrials.gov sends the records back in its own order, so each one is filed
    # under its NCT number and looked up by the number typed. A number ClinicalTrials.gov
    # does not know has no record, and is reported in the loop below.
    by_nct_id = {
        study["protocolSection"]["identificationModule"]["nctId"]: study
        for study in studies
    }

    downloaded = 0
    skipped = 0
    for nct_id in nct_ids:
        say(nct_id)

        study = by_nct_id.get(nct_id)
        if study is None:
            report(
                say,
                seen,
                "  ",
                "CTGOV-STUDY-NOT-FOUND",
                17,
                f"{nct_id} is not on ClinicalTrials.gov",
            )
            continue
        documents = protocol_and_sap(study)
        if not documents:
            report(
                say,
                seen,
                "  ",
                "CTGOV-NO-STUDY-DOCUMENTS",
                18,
                f"{nct_id} has posted no protocol or SAP",
            )
            continue

        for document in documents:
            # A pinned file is saved, recorded and looked up under its pinned name. A
            # review copy keeps the name ClinicalTrials.gov gives it, because it is not
            # pinned.
            filename = document["filename"]
            if args.accept:
                filename = pinned_name(filename)
            destination = folder / nct_id / filename

            # With --accept, whether the study's manifest records the file decides what
            # happens to it, together with whether the file is on disk.
            # - On disk and recorded, it is skipped as already saved.
            # - On disk and not recorded, it is reported and left in place, for a
            #   person to record or remove.
            # - Recorded but missing, it is reported and not downloaded, because
            #   acquire_sources restores a recorded file against its fingerprint, and
            #   a new entry for it would be refused.
            # - Neither, it is downloaded and recorded below.
            # Without --accept, a file already saved is skipped, because place()
            # refuses to replace a file that is already there.
            recorded = False
            if args.accept:
                try:
                    recorded = recorded_in_manifest(nct_id, filename)
                except ManifestError as exc:
                    report(
                        say,
                        seen,
                        "  ",
                        exc.sub_code,
                        exc.exit_code,
                        f"FAILED  {exc}",
                    )
                    continue
            if destination.exists():
                if args.accept and not recorded:
                    report(
                        say,
                        seen,
                        "  ",
                        "FILE-UNRECORDED",
                        16,
                        f"{filename} is already in {destination.parent}, and "
                        f"manifests/study_documents/{nct_id}.json does not "
                        "record it. It was left in place.",
                    )
                    continue
                say(f"  already saved  {filename}")
                skipped += 1
                continue
            if recorded:
                report(
                    say,
                    seen,
                    "  ",
                    "PINNED-FILE-NOT-DOWNLOADED",
                    12,
                    f"{filename} is recorded in manifests/study_documents/{nct_id}.json "
                    f"but is not in {destination.parent}. Run acquire_sources to "
                    "restore it.",
                )
                continue

            say(f"  downloading  {filename}")
            # A file that fails to download is reported, and the run moves on to the
            # next file. fetch removes its own partial download when it fails. An error
            # answer gets a sub-code of its own here, because the address was built
            # from DOCUMENT_URL rather than read from a manifest, so its fix differs.
            try:
                partial = fetch(document_url(nct_id, document), destination)
            except FetchErrorAnswerError as exc:
                report(
                    say,
                    seen,
                    "    ",
                    "CTGOV-DOWNLOAD-ERROR-ANSWER",
                    11,
                    f"FAILED  {exc}",
                )
                continue
            except FetchError as exc:
                report(say, seen, "    ", exc.sub_code, exc.exit_code, f"FAILED  {exc}")
                continue

            # With --accept, the file is confirmed and recorded before it gets its final
            # name. A file whose size does not match, whose manifest entry cannot be
            # written, or which cannot be opened to measure it, is deleted, so no
            # unrecorded file is left under inputs/. OSError here can only come from
            # opening the download, because write_entry turns its own disk
            # failures into kinds of ManifestError.
            if args.accept:
                try:
                    confirm_size(partial, document)
                    write_entry(
                        STUDY_MANIFEST_DIR / f"{nct_id}.json",
                        manifest_set_details(nct_id, study),
                        manifest_entry(nct_id, document, fingerprint(partial)),
                    )
                except (SizeMismatchError, ManifestError) as exc:
                    outcome = remove_download(partial)
                    report(
                        say,
                        seen,
                        "    ",
                        exc.sub_code,
                        exc.exit_code,
                        f"FAILED  {exc} {outcome}",
                    )
                    continue
                except OSError as exc:
                    outcome = remove_download(partial)
                    report(
                        say,
                        seen,
                        "    ",
                        "CTGOV-DOWNLOAD-UNREADABLE",
                        13,
                        f"FAILED  {filename} could not be opened ({exc}). {outcome}",
                    )
                    continue

            # A rename can fail when another program, such as antivirus software, is
            # holding the new file. With --accept the manifest already records the
            # file, so the problem says so and points to acquire_sources, which
            # downloads a recorded file that is missing. The run moves on to the next
            # file. Without --accept the failure is a plain download that could not
            # be written.
            try:
                place(partial)
            except OSError as exc:
                outcome = remove_download(partial)
                if args.accept:
                    report(
                        say,
                        seen,
                        "    ",
                        "CTGOV-DOWNLOAD-NOT-PLACED",
                        20,
                        f"FAILED  {filename} is recorded in manifests/study_documents/"
                        f"{nct_id}.json but could not be given its final name ({exc}). "
                        f"{outcome} Run acquire_sources to download it again.",
                    )
                else:
                    report(
                        say,
                        seen,
                        "    ",
                        "DOWNLOAD-NOT-WRITTEN",
                        20,
                        f"FAILED  {filename} could not be given its final name "
                        f"({exc}). {outcome}",
                    )
                continue
            downloaded += 1

    say()
    say(f"{downloaded} downloaded, {skipped} already saved, in {folder}")

    # The worst problem seen decides the exit number.
    for sub_code in PRECEDENCE:
        if sub_code in seen:
            return finish(say, seen[sub_code], sub_code)

    # A problem whose sub-code is missing from PRECEDENCE would otherwise fall through
    # to success. It still fails the run, with the highest exit number seen.
    if seen:
        sub_code = max(seen, key=lambda code: seen[code])
        return finish(say, seen[sub_code], sub_code)
    return 0


if __name__ == "__main__":
    sys.exit(main())
