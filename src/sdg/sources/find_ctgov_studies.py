"""
Script:      find_ctgov_studies.py
Description: Finds the studies on ClinicalTrials.gov based on filters specified in
             src/sdg/sources/ctgov_study_filters.yml.

             - the script sends the search criteria defined in the filters file to
               ClinicalTrials.gov and matching studies and associated details are
               returned via the API.
             - based on the returned study information, the script then applies
               additional filters that cannot be applied by the API;
               (defined in after_fetch section).
             - each run saves a record of the search sent to ClinicalTrials.gov,
               the date it ran, how many studies ClinicalTrials.gov returned, how
               many remained after each additional filter, and the final list of
               studies.
             - studies on ClinicalTrials.gov are added and updated daily so a later run
               cannot reproduce an earlier one, and the record is the only proof of what
               a run found.

Inputs:      src/sdg/sources/ctgov_study_filters.yml (read-only)
             the ClinicalTrials.gov API (read-only)

Outputs:     One run record per run, written to searches/ctgov/ and named by the
             date and time the run started. Prints how many studies
             ClinicalTrials.gov returned and how many were left after each filter.


Usage:       find_ctgov_studies
                 search ClinicalTrials.gov, apply the filters, save the run record
             find_ctgov_studies --quiet
                 print nothing; use the exit code


Exit codes:  0   SUCCEEDED  the command succeeded
             1   UNHANDLED-ERROR  Python stopped on an error that nothing handled
             2   COMMAND-LINE-REFUSED  the argument parser refused the command line
             3   NOT-IN-REPO  the sdg package is not running from inside its repo
             9   CTGOV-NO-ANSWER  ClinicalTrials.gov could not be reached or did
                 not answer in time
             11  CTGOV-ERROR-ANSWER  ClinicalTrials.gov answered with an error
             12  FILTERS-FILE-MISSING  the ClinicalTrials.gov filters file is
                 missing
             13  FILTERS-FILE-UNREADABLE  the ClinicalTrials.gov filters file is on
                 disk but cannot be opened
             14  FILTERS-FILE-UNPARSEABLE  the ClinicalTrials.gov filters file is
                 not valid YAML
             14  CTGOV-REPLY-UNPARSEABLE  the answer from ClinicalTrials.gov is not
                 valid JSON
             15  FILTERS-FILE-INVALID  the ClinicalTrials.gov filters file is
                 missing a setting the script needs, or has a filter the script
                 does not apply
             17  CTGOV-NO-CANDIDATES  no study on ClinicalTrials.gov passed every
                 filter (the run record is still saved)
             20  CTGOV-RECORD-NOT-WRITTEN  the ClinicalTrials.gov run record, or
                 its folder, could not be written to disk
             The wording is the table in docs/exit_codes.csv.


Date:        2026-10-02
Owner:       Jason Delosh
"""

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

import httpx
import yaml

from sdg.exit_codes import fail
from sdg.sources.read_manifests import REPO_ROOT, NotInRepoError, require_repo

#######################################################################################
### Settings ###

# The filters file sits in the same folder as this script, so the script finds it
# there, whatever folder the script is run from.
FILTERS_FILE = Path(__file__).with_name("ctgov_study_filters.yml")

# ClinicalTrials.gov sends results in pages with a max of 1000 studies per page. The
# script collects all pages, so it needs to know the page size.
PAGE_SIZE = 1000

# After no response for this many seconds, the script gives up trying to get a reply
# from ClinicalTrials.gov.
TIMEOUT_SECONDS = 60.0

# Specifies the parts of each study requested by the script. Note that posted results
# are excluded because no filters read them and they increase reply size.
FIELDS = "ProtocolSection|DocumentSection|DerivedSection"

# This is a list of filters in the filters file. Each name is used by one of the
# filter functions in "Applying additional filters" section.
# The script stops if the filters file has a field or list name that is not in this
# list because that means the filter file and the filter functions are out of sync.
# This script stops if a name on this list is not present in the filters file.
ADDITIONAL_FILTER_SETTINGS = (
    "separate_protocol_sap",
    "sap_dated_on_or_after",
    "min_countries",
    "condition_terms",
    "intervention_types_allowed",
    "intervention_types_required",
)

# Each run's record is saved in this folder, one file per run.  The records are
# committed because ClinicalTrials.gov changes daily and no later run can show what
# was an earlier run found
SEARCHES_DIR = REPO_ROOT / "searches" / "ctgov"

#######################################################################################
### Script failures ###

# Each failure carries an exit number and short name which are listed in
# docs/exit_codes.csv.


# Filters: Opening the filters file can fail in multiple ways.
class FiltersError(Exception):
    """Raised when the filters file cannot be used.

    The four failures below are each a reason the file cannot be used.
    """

    exit_code: int
    sub_code: str


# Each failure below is a type of FiltersError.
class FiltersMissingError(FiltersError):
    """Raised when the filters file is missing."""

    exit_code = 12
    sub_code = "FILTERS-FILE-MISSING"


class FiltersUnreadableError(FiltersError):
    """Raised when the filters file is on disk but cannot be read."""

    exit_code = 13
    sub_code = "FILTERS-FILE-UNREADABLE"


class FiltersUnparseableError(FiltersError):
    """Raised when the filters file is not a valid YAML and cannot be parsed."""

    exit_code = 14
    sub_code = "FILTERS-FILE-UNPARSEABLE"


class FiltersInvalidError(FiltersError):
    """Raised when the filters file is missing a setting the script needs."""

    exit_code = 15
    sub_code = "FILTERS-FILE-INVALID"


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


# Saving the run record can fail.
class RecordNotWrittenError(Exception):
    """Raised when the run record or its folder cannot be written to disk."""

    exit_code = 20
    sub_code = "CTGOV-RECORD-NOT-WRITTEN"


#######################################################################################
### Reading the filters ###

# Loads ctgov_study_filters.yml, which holds the query and the after-fetch rules.


def read_filters(path: Path = FILTERS_FILE) -> dict[str, Any]:
    """Read the filters file and confirm it holds the settings the script needs.

    Args:
      path: The filters file.

    Returns:
      The settings in the filters file including api, query and after_fetch specs.

    Raises:
      FiltersMissingError: The filters file is missing.
      FiltersUnreadableError: The filters file is on disk but cannot be read.
      FiltersUnparseableError: The filters file is not a valid YAML.
      FiltersInvalidError: The filters file is missing a setting the script needs, or
        its after_fetch section does not match ADDITIONAL_FILTER_SETTINGS.
    """

    # If a failure occurs, it is reported by main() with its specific exit number.
    try:
        text = path.read_text(encoding="utf-8")

    except FileNotFoundError as exc:
        raise FiltersMissingError(f"the filters file is missing at {path}.") from exc

    except OSError as exc:
        raise FiltersUnreadableError(
            f"the filters file at {path} cannot be read ({exc})."
        ) from exc

    try:
        filters = yaml.safe_load(text)

    except yaml.YAMLError as exc:
        raise FiltersUnparseableError(f"{path.name} is not valid YAML: {exc}") from exc

    # An empty filters file or one holding a plain list has no named setting to look up.
    if not isinstance(filters, dict):
        raise FiltersInvalidError(f"{path.name} holds no named settings.")

    missing = [name for name in ("api", "query", "after_fetch") if name not in filters]
    if missing:
        raise FiltersInvalidError(f"{path.name} is missing {', '.join(missing)}.")

    # The settings in the after_fetch section of the ctgov_study_filters.yml must match
    # the settings listed in the ADDITIONAL_FILTER_SETTINGS.
    additional_filters = filters["after_fetch"]
    if not isinstance(additional_filters, dict):
        raise FiltersInvalidError(f"{path.name} has no named settings in after_fetch.")
    unused = sorted(set(additional_filters) - set(ADDITIONAL_FILTER_SETTINGS))
    if unused:
        raise FiltersInvalidError(
            f"{path.name} has after_fetch settings no filter reads: {', '.join(unused)}."
        )
    absent = [
        name for name in ADDITIONAL_FILTER_SETTINGS if name not in additional_filters
    ]
    if absent:
        raise FiltersInvalidError(
            f"{path.name} is missing after_fetch settings: {', '.join(absent)}."
        )
    return filters


#######################################################################################
### Asking the API ###

# Sends the query to ClinicalTrials.gov and collects every page of the reply.


def fetch_studies(api: str, query: str) -> list[dict[str, Any]]:
    """Send the query to ClinicalTrials.gov and collect the studies from every page.

    ClinicalTrials.gov returns one page at a time and a maximum of 1000 studies per
    page. Every page (except the last) carries a token and the script uses that token
    to get the next page.

    Args:
      api: The api web address from ctgov_study_filters.yml.
      query: The query search from ctgov_study_filters.yml.

    Returns:
      A list of every study that matched the search.

    Raises:
      CtgovNoAnswerError: ClinicalTrials.gov cannot be reached or did not answer in time.
      CtgovBadAnswerError: ClinicalTrials.gov answers with an error.
      CtgovReplyUnparseableError: The answer from ClinicalTrials.gov is not valid JSON.
    """

    params: dict[str, str | int] = {
        "filter.advanced": query,
        "fields": FIELDS,
        "pageSize": PAGE_SIZE,
    }

    studies: list[dict[str, Any]] = []
    # The loop asks for one page at a time, and stops at the page that carries no token for
    # the next page.
    while True:
        # A failure is converted into one of the failures listed above so main() can
        # report it with its specific exit number.
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


#######################################################################################
### Reading a study record ###

# Each study from ClinicalTrials.gov is one large block of details.  The functions
# in this section parse needed information from that block.
# These are used by the additional filters and run record later.


def list_study_documents(study: dict[str, Any]) -> list[dict[str, Any]]:
    """List the documents associated with a study.

    Args:
        study: One study as ClinicalTrials.gov sent it.

    Returns:
        One entry per document, or an empty list when the study has none.
    """
    module = study.get("documentSection", {}).get("largeDocumentModule", {})
    return module.get("largeDocs", [])


def list_study_countries(study: dict[str, Any]) -> set[str]:
    """List the countries where the study has sites, each country once.

    Args:
        study: One study from ClinicalTrials.gov.

    Returns:
        The names of the countries, or an empty set when the study lists no sites.
    """
    module = study.get("protocolSection", {}).get("contactsLocationsModule", {})
    return {
        site["country"] for site in module.get("locations", []) if site.get("country")
    }


def describe_candidate(study: dict[str, Any]) -> dict[str, Any]:
    """Gather details a person needs to choose between candidate studies.

    Args:
        study: One study that passed every filter.

    Returns:
        The study's ID, title, lead sponsor, conditions, countries with sites,
        enrollment, and whether it posted an informed consent form (ICF).
    """

    protocol = study.get("protocolSection", {})
    identification = protocol.get("identificationModule", {})
    sponsors = protocol.get("sponsorCollaboratorsModule", {})
    return {
        "nct_id": identification.get("nctId"),
        "title": identification.get("briefTitle"),
        "sponsor": sponsors.get("leadSponsor", {}).get("name"),
        "conditions": protocol.get("conditionsModule", {}).get("conditions", []),
        "countries": sorted(list_study_countries(study)),
        "enrollment": protocol.get("designModule", {})
        .get("enrollmentInfo", {})
        .get("count"),
        "icf_posted": any(d.get("hasIcf") for d in list_study_documents(study)),
    }


#######################################################################################
### Applying additional filters ###

# Applies each filter (from ctgov_study_filters.yml) in turn, and counts how many
# studies each one removes.


def separate_protocol_sap(
    study: dict[str, Any], additional_filters: dict[str, Any]
) -> bool:
    """Select studies where the protocol and SAP are present and separate documents.

    ClinicalTrials.gov marks each file as a protocol, a SAP, or a combined file
    holding both. A combined file counts as neither.

    Args:
        study: One study from ClinicalTrials.gov.
        additional_filters: The after_fetch section of ctgov_study_filters.yml. This
            function reads its separate_protocol_sap value, which turns the
            filter on or off.

    Returns:
        True when the study has at least one protocol-only file and at least one
        SAP-only file, or when separate_protocol_sap is false.
    """

    if not additional_filters["separate_protocol_sap"]:
        return True
    documents = list_study_documents(study)
    protocol_only = any(d.get("hasProtocol") and not d.get("hasSap") for d in documents)
    sap_only = any(d.get("hasSap") and not d.get("hasProtocol") for d in documents)
    return protocol_only and sap_only


def recent_sap(study: dict[str, Any], additional_filters: dict[str, Any]) -> bool:
    """Select studies where the SAP document date is on or after the desired date.

    Only a SAP-only file counts, because a combined protocol and SAP file is not a
    separate SAP. A file with a missing or malformed date does not count.

    Args:
        study: One study from ClinicalTrials.gov.
        additional_filters: The after_fetch section of ctgov_study_filters.yml. This
            function reads its sap_dated_on_or_after date.

    Returns:
        True when at least one SAP-only file is dated on or after that date.
    """

    earliest = additional_filters["sap_dated_on_or_after"]
    for document in list_study_documents(study):
        if not document.get("hasSap") or document.get("hasProtocol"):
            continue

        # A date that is missing or not written as year-month-day makes fromisoformat
        # fail, and the document is passed over.
        try:
            if date.fromisoformat(document.get("date", "")) >= earliest:
                return True
        except ValueError:
            continue

    return False


def min_countries(study: dict[str, Any], additional_filters: dict[str, Any]) -> bool:
    """Select studies with sites in at least the desired number of countries.

    Each country is counted once, however many sites the study has in it.

    Args:
        study: One study from ClinicalTrials.gov.
        additional_filters: The after_fetch section of ctgov_study_filters.yml. This
            function reads its min_countries number.

    Returns:
        True when the study has sites in at least that many countries.
    """

    return len(list_study_countries(study)) >= additional_filters["min_countries"]


def condition_terms(study: dict[str, Any], additional_filters: dict[str, Any]) -> bool:
    """Select studies in the desired therapeutic areas, judged by their conditions.

    ClinicalTrials.gov tags each study's conditions with terms from Medical Subject
    Headings, the medical vocabulary of the United States National Library of Medicine.
    It also adds every broader term above them. For example, a study tagged Breast
    Neoplasms also carries Neoplasms. A study with no terms is dropped.

    Args:
        study: One study from ClinicalTrials.gov.
        additional_filters: The after_fetch section of ctgov_study_filters.yml. This
            function reads its condition_terms list.

    Returns:
        True when any of the study's terms, or any broader term above them, is on
        that list.
    """

    module = study.get("derivedSection", {}).get("conditionBrowseModule", {})
    tagged = module.get("meshes", []) + module.get("ancestors", [])
    terms = {entry["term"] for entry in tagged}
    return bool(terms & set(additional_filters["condition_terms"]))


def intervention_types(
    study: dict[str, Any], additional_filters: dict[str, Any]
) -> bool:
    """Select studies with the desired treatment types.

    ClinicalTrials.gov gives each treatment a type, such as DRUG, BIOLOGICAL or
    DEVICE. Sponsors enter placebo and standard care as OTHER. A study with no
    treatment listed, or a treatment with no type, is dropped.

    Args:
        study: One study from ClinicalTrials.gov.
        additional_filters: The after_fetch section of ctgov_study_filters.yml. This
            function reads its intervention_types_allowed and
            intervention_types_required lists.

    Returns:
        True when every treatment type is allowed and at least one is required.
    """
    module = study.get("protocolSection", {}).get("armsInterventionsModule", {})
    types = {treatment.get("type") for treatment in module.get("interventions", [])}
    allowed = set(additional_filters["intervention_types_allowed"])
    required = set(additional_filters["intervention_types_required"])
    return bool(types) and types <= allowed and bool(types & required)


#######################################################################################
### Run additional filters ###
# Run the filter functions above, in the order they are applied. The run record lists
# how many studies were left after each one, in this order.

# List the filter functions above that will be run.
FILTER_FUNCTIONS = (
    separate_protocol_sap,
    recent_sap,
    min_countries,
    condition_terms,
    intervention_types,
)


def run_additional_filters(
    studies: list[dict[str, Any]], additional_filters: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Obtain just the studies that meet the criteria defined by the additional filters.

    Each pass through the loop keeps only the studies the current filter says yes to,
    then writes down how many are left.

    Args:
        studies: The studies from fetch_studies function.
        additional_filters: All filter criteria present in the after_fetch section of
            ctgov_study_filters.yml. This function passes them to each filter function.

    Returns:
        Studies that meet the requirements of all specified filters.
        Count of studies left after each filter is applied, named by its function.
    """

    remaining: dict[str, int] = {}
    for keep in FILTER_FUNCTIONS:
        studies = [study for study in studies if keep(study, additional_filters)]
        # keep.__name__ is the function's own name (e.g.: min_countries) kept as a label.
        remaining[keep.__name__] = len(studies)
    return studies, remaining


#######################################################################################
### Saving the run record ###

# Writes the query as sent, the date, the counts and the studies that passed.


def save_run_record(
    filters: dict[str, Any],
    returned: int,
    remaining: dict[str, int],
    candidates: list[dict[str, Any]],
    ran_at: datetime,
) -> Path:
    """Write down what one run searched for and found.

    The file is named by the date and time the run started, such as
    2026-10-05_143012.json. The time has no colons, because Windows does not allow
    them in a file name.

    Args:
      filters: The filters returned by read_filters.
      returned: How many studies fetch_studies returned.
      remaining: How many studies were left after each filter from
        run_additional_filters.
      candidates: One description per candidate study, from describe_candidate.
      ran_at: When the run started.

    Returns:
      The path of the file written.

    Raises:
      RecordNotWrittenError: The folder or file could not be written.
    """

    record = {
        "ran_at": ran_at.isoformat(timespec="seconds"),
        "api": filters["api"],
        "query": filters["query"],
        "fields": FIELDS,
        "additional_filters": filters["after_fetch"],
        "returned": returned,
        "remaining_after": remaining,
        "candidates": candidates,
    }

    path = SEARCHES_DIR / f"{ran_at:%Y-%m-%d_%H%M%S}.json"

    # The filters file holds the SAP date as a date, which JSON cannot store, so
    # default=str writes it as text, such as 2020-01-01. A folder or file that cannot
    # be written becomes RecordNotWrittenError, so main() can report it.
    try:
        SEARCHES_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(record, indent=2, default=str) + "\n", encoding="utf-8"
        )

    except OSError as exc:
        raise RecordNotWrittenError(
            f"the run record could not be written to {path} ({exc})."
        ) from exc
    return path


#######################################################################################
### Finding the studies ###

# The main() that runs the sections above in order.


def main(argv: list[str] | None = None) -> int:
    """Run the steps of this script in order and report the results or the failure.

    Steps:
    - read_filters reads ctgov_study_filters.yml and confirms it is complete.
    - fetch_studies sends the search to ClinicalTrials.gov and collects every
      matching study.
    - run_additional_filters keeps the studies that pass every additional filter,
      and counts how many were left after each one.
    - describe_candidate gathers the details of each study that passed.
    - save_run_record writes the search, the counts and the candidates to a file
      in searches/ctgov/.

    Any step that fails stops the run, and main() reports the failure with its exit
    number.

    Args:
        argv: The command-line arguments, or None to read the real ones.

    Returns:
        The exit code, as the header block lists them.
    """

    parser = argparse.ArgumentParser(
        description="List the studies on ClinicalTrials.gov that pass the filters in "
        "ctgov_study_filters.yml, and save a record of the run."
    )

    parser.add_argument(
        "--quiet", action="store_true", help="print nothing; use the exit code"
    )

    args = parser.parse_args(argv)

    def say(message: str) -> None:
        """Print a line, unless --quiet was given."""
        if not args.quiet:
            print(message)

    # The time is noted first, so the record is named by when the run started.
    ran_at = datetime.now().astimezone()

    # The repo check runs before anything else, because the record is saved
    # inside the repo.
    try:
        require_repo()
    except NotInRepoError as exc:
        return fail(say, exc.exit_code, exc.sub_code, exc)

    # Each step raises one of the failures in the Script failures section. They are
    # all caught here and reported with their own exit number.
    try:
        filters = read_filters()
        studies = fetch_studies(filters["api"], filters["query"])
        candidates, remaining = run_additional_filters(studies, filters["after_fetch"])
        path = save_run_record(
            filters,
            len(studies),
            remaining,
            [describe_candidate(study) for study in candidates],
            ran_at,
        )
    except (FiltersError, CtgovError, RecordNotWrittenError) as exc:
        return fail(say, exc.exit_code, exc.sub_code, exc)

    say(f"ClinicalTrials.gov returned {len(studies)} studies.")
    for name, count in remaining.items():
        say(f"  {count} left after {name}")
    say(f"The record of this run is in {path.relative_to(REPO_ROOT)}.")

    # A run that leaves no candidates is still saved above, because its record shows
    # which filter removed the last of them.
    if not candidates:
        return fail(say, 17, "CTGOV-NO-CANDIDATES", "no study passed every filter.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
