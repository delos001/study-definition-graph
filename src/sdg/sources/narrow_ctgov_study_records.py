"""
Script:      narrow_ctgov_study_records.py
Description: Reads src/sdg/sources/ctgov_study_filters.yml and keeps the study records
             that pass its additional filters, the rules under after_fetch that the
             ClinicalTrials.gov API cannot apply itself.

             - read_filters reads the filters file and confirms it holds every setting
               the filter functions need, no setting none of them reads, and a value
               of the right kind in each setting.
             - narrow_study_records runs the filter functions in order and counts
               how many records are left after each one.

             read_filters and the filter functions are kept in this one file,
             because ADDITIONAL_FILTER_SETTINGS is the table that confirms the
             filters file and the filter functions agree.

Inputs:      src/sdg/sources/ctgov_study_filters.yml (read-only)
             the study records from fetch_ctgov_study_records.py

Outputs:     Nothing on disk.
             read_filters hands back the settings in the filters file.
             narrow_study_records hands back the records that passed every
             filter, and how many were left after each one.

Usage:       This file is not run directly; other code imports it.
             from sdg.sources.narrow_ctgov_study_records import (
                 narrow_study_records, read_filters)
                read_filters()                                  -> the filters file's settings
                narrow_study_records(studies, after_fetch) -> (kept records, counts)

Exit codes:  There are none, because this file is not run on its own. On a problem it stops
             and hands an error to the program using it, which decides what to
             do. Every error is a kind of FiltersError, carrying the exit number and
             sub-code a command reports it with, from docs/exit_codes.csv. The errors
             it can hand back:
             FiltersMissingError      the filters file is missing
             FiltersUnreadableError   the filters file is on disk but cannot be read
             FiltersUnparseableError  the filters file is not valid YAML
             FiltersInvalidError      the filters file is missing a setting the
                                      filter functions need, has a setting none
                                      of them reads, or has a setting with a value
                                      of the wrong kind

Date:        2026-10-06
Owner:       Jason Delosh
"""

from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml

from .parse_ctgov_study_records import list_study_countries, list_study_documents

#######################################################################################
### Settings ###

# The filters file sits in the same folder as this script, so the script finds it
# there, whatever folder the script is run from.
FILTERS_FILE = Path(__file__).with_name("ctgov_study_filters.yml")


def _is_text_list(value: Any) -> bool:
    """Say whether a setting is a list whose items are all text.

    Args:
        value: One setting from the after_fetch section of ctgov_study_filters.yml.

    Returns:
        True when the setting is a list of text items.
    """
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


# This table names each setting in the after_fetch section of the filters file, the
# test its value must pass, and that test in plain words for the error message. Each
# setting is read by one of the filter functions in the "Applying additional filters"
# section.
# - The script stops if the filters file has a setting that is not in this table,
#   because that means the filters file and the filter functions are out of step.
# - The script stops if a setting in this table is not in the filters file.
# - The script stops if a setting's value fails its test, because a filter function
#   would otherwise stop on it part way through a run with a raw Python error.
#
# The YAML reader turns 2020-01-01 into a date, but "2020-01-01" in quotes stays text,
# and 2020-01-01 10:00 becomes a date and time. Only a plain date can be compared with
# the SAP dates. true is excluded from the whole numbers, because Python counts it as
# the number 1.
ADDITIONAL_FILTER_SETTINGS: dict[str, tuple[Callable[[Any], bool], str]] = {
    "separate_protocol_sap": (
        lambda value: isinstance(value, bool),
        "true or false",
    ),
    "sap_dated_on_or_after": (
        lambda value: isinstance(value, date) and not isinstance(value, datetime),
        "a date written as year-month-day, without quotes",
    ),
    "min_countries": (
        lambda value: isinstance(value, int) and not isinstance(value, bool),
        "a whole number",
    ),
    "condition_terms": (_is_text_list, "a list of terms"),
    "intervention_types_allowed": (_is_text_list, "a list of treatment types"),
    "intervention_types_required": (_is_text_list, "a list of treatment types"),
}

#######################################################################################
### Failures ###

# Each failure carries an exit number and short name which are listed in
# docs/exit_codes.csv.


# Reading the filters file can fail in several ways, from a missing file to a wrong
# setting, and each has its own error below.
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
    """Raised when the filters file is missing a setting the script needs, has a
    setting no filter reads, or has a setting with a value of the wrong kind."""

    exit_code = 15
    sub_code = "FILTERS-FILE-INVALID"


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
        FiltersInvalidError: The filters file is missing a setting the script needs, its
            after_fetch section does not match ADDITIONAL_FILTER_SETTINGS, or a setting has
            a value of the wrong kind, including an api that is not an https:// address
            and an empty query.
    """

    # If a failure occurs, it is reported by the program using this module with its
    # specific exit number.
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

    # api and query are sent to ClinicalTrials.gov as they are written. A mistake in
    # either is reported here with the setting's name, because once sent it would look
    # like ClinicalTrials.gov failing to answer.
    api, query = filters["api"], filters["query"]
    if not (isinstance(api, str) and api.startswith("https://")):
        raise FiltersInvalidError(
            f"{path.name}: api must be a web address starting with https://, "
            f"and it is {api!r}."
        )
    if not (isinstance(query, str) and query.strip()):
        raise FiltersInvalidError(
            f"{path.name}: query must be text that is not empty, and it is {query!r}."
        )

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

    # Each setting's value is tested here, so a wrong kind of value is reported with
    # the setting's name before ClinicalTrials.gov is asked anything.
    wrong = [
        f"{name} must be {meaning}, and it is {additional_filters[name]!r}"
        for name, (passes, meaning) in ADDITIONAL_FILTER_SETTINGS.items()
        if not passes(additional_filters[name])
    ]
    if wrong:
        raise FiltersInvalidError(
            f"{path.name} has after_fetch settings of the wrong kind: "
            f"{'; '.join(wrong)}."
        )
    return filters


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
        study: One study record from fetch_study_records in
            fetch_ctgov_study_records.py.
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
        study: One study record from fetch_study_records in
            fetch_ctgov_study_records.py.
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
        study: One study record from fetch_study_records in
            fetch_ctgov_study_records.py.
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
        study: One study record from fetch_study_records in
            fetch_ctgov_study_records.py.
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
        study: One study record from fetch_study_records in
            fetch_ctgov_study_records.py.
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
# Run the filter functions above, in the order they are applied. The search record lists
# how many studies were left after each one, in this order.

# List the filter functions above that will be run.
FILTER_FUNCTIONS = (
    separate_protocol_sap,
    recent_sap,
    min_countries,
    condition_terms,
    intervention_types,
)


def narrow_study_records(
    studies: list[dict[str, Any]], additional_filters: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Obtain just the studies that meet the criteria defined by the additional filters.

    Each pass through the loop keeps only the studies the current filter says yes to,
    then writes down how many are left.

    Args:
        studies: The study records returned by fetch_study_records in
            fetch_ctgov_study_records.py.
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
