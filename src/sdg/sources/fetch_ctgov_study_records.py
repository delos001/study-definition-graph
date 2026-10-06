"""
Script:      fetch_ctgov_study_records.py
Description: Sends a query to the ClinicalTrials.gov API and collects the study
             record of every study that matches it.

             A study record is the registry's block of details about one study. The
             caller chooses which parts of each record to ask for, so a search that
             filters on the protocol section and a download that only needs the
             document list each ask for what they read.

             ClinicalTrials.gov sends the records one page at a time, and this
             module collects every page.

             This module reads nothing on disk and writes nothing.

Inputs:      the ClinicalTrials.gov API (read-only)

Outputs:     Nothing on disk.
             Hands back the list of study records that matched the query.

Usage:       This file is not run directly; other code imports it.
             from sdg.sources.fetch_ctgov_study_records import fetch_ctgov_study_records
                fetch_ctgov_study_records(api, query, fields)   -> list of study records

Exit codes:  There are none, because this file is not run on its own. On a problem it stops
             and hands an error to the program using it, which decides what to
             do. Every error is a kind of CtgovError, carrying the exit number and
             sub-code a command reports it with, from docs/exit_codes.csv. The errors
             it can hand back:
             CtgovNoAnswerError          ClinicalTrials.gov could not be reached or
                                         did not answer in time
             CtgovBadAnswerError         ClinicalTrials.gov answered with an error
             CtgovReplyUnparseableError  the answer from ClinicalTrials.gov is not
                                         valid JSON

Date:        2026-10-06
Owner:       Jason Delosh
"""

from typing import Any

import httpx

#######################################################################################
### Settings ###

# ClinicalTrials.gov sends results in pages with a max of 1000 studies per page. The
# script collects all pages, so it needs to know the page size.
PAGE_SIZE = 1000

# After no response for this many seconds, the script gives up trying to get a reply
# from ClinicalTrials.gov.
TIMEOUT_SECONDS = 60.0

#######################################################################################
### Failures ###

# Each failure carries an exit number and short name which are listed in
# docs/exit_codes.csv.


# CTGov: The script can fail multiple ways when it asks ClinicalTrials.gov for studies.
class CtgovError(Exception):
    """Raised when the studies cannot be collected from ClinicalTrials.gov.

    The three failures below are each a reason the studies cannot be collected.
    """

    exit_code: int
    sub_code: str


# Each failure below is a kind of CtgovError.
class CtgovNoAnswerError(CtgovError):
    """Raised when ClinicalTrials.gov cannot be reached or does not answer in time."""

    exit_code = 9
    sub_code = "CTGOV-NO-ANSWER"


class CtgovBadAnswerError(CtgovError):
    """Raised when ClinicalTrials.gov answers with an error."""

    exit_code = 11
    sub_code = "CTGOV-ERROR-ANSWER"


class CtgovReplyUnparseableError(CtgovError):
    """Raised when the answer from ClinicalTrials.gov is not valid JSON."""

    exit_code = 14
    sub_code = "CTGOV-REPLY-UNPARSEABLE"


#######################################################################################
### Asking the API ###

# Sends the query to ClinicalTrials.gov and collects every page of the reply.


def fetch_ctgov_study_records(
    api: str, query: str, fields: str
) -> list[dict[str, Any]]:
    """Send the query to ClinicalTrials.gov and collect the study records from every page.

    ClinicalTrials.gov returns one page at a time and a maximum of 1000 studies per
    page. Every page (except the last) carries a token and the script uses that token
    to get the next page.

    Args:
      api: The api web address, such as the api entry in ctgov_study_filters.yml.
      query: The search, written in the API's query language, such as the query entry
        in ctgov_study_filters.yml.
      fields: The parts of each study record to ask for, joined by |, such as
        ProtocolSection|DocumentSection.

    Returns:
      A list of the study record of every study that matched the search.

    Raises:
      CtgovNoAnswerError: ClinicalTrials.gov cannot be reached or did not answer in time.
      CtgovBadAnswerError: ClinicalTrials.gov answers with an error.
      CtgovReplyUnparseableError: The answer from ClinicalTrials.gov is not valid JSON.
    """

    params: dict[str, str | int] = {
        "filter.advanced": query,
        "fields": fields,
        "pageSize": PAGE_SIZE,
    }

    studies: list[dict[str, Any]] = []
    # The loop asks for one page at a time, and stops at the page that carries no token for
    # the next page.
    while True:
        # A failure is converted into one of the failures listed above so the program
        # using this module can report it with its specific exit number.
        try:
            response = httpx.get(api, params=params, timeout=TIMEOUT_SECONDS)
            response.raise_for_status()

        except httpx.HTTPStatusError as exc:
            raise CtgovBadAnswerError(
                f"ClinicalTrials.gov answered with an error: {exc.response.status_code}. "
                f"{exc.response.text[:500]}"
            ) from exc

        except httpx.TransportError as exc:
            raise CtgovNoAnswerError(
                f"ClinicalTrials.gov could not be reached ({exc})."
            ) from exc

        try:
            page = response.json()

        except ValueError as exc:
            raise CtgovReplyUnparseableError(
                f"ClinicalTrials.gov sent an answer that is not valid JSON ({exc})."
            ) from exc

        studies.extend(page.get("studies", []))
        token = page.get("nextPageToken")
        if not token:
            return studies
        params["pageToken"] = token
