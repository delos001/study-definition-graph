"""
Script:      narrow_ctgov_study_records.py
Description: Reads src/sdg/sources/ctgov_study_filters.yml and keeps the study records
             that pass its additional filters, the rules under after_fetch that the
             ClinicalTrials.gov API cannot apply itself.

             - read_filters reads the filters file and confirms it holds every setting
               the filter functions need, and no setting none of them reads.
             - narrow_ctgov_study_records runs the filter functions in order and counts
               how many records are left after each one.

             The filters file and the filter functions are kept in one file, because
             ADDITIONAL_FILTER_SETTINGS is the list that confirms the two agree.

Inputs:      src/sdg/sources/ctgov_study_filters.yml (read-only)
             the study records from fetch_ctgov_study_records.py

Outputs:     Nothing on disk.
             read_filters hands back the settings in the filters file.
             narrow_ctgov_study_records hands back the records that passed every
             filter, and how many were left after each one.

Usage:       This file is not run directly; other code imports it.
             from sdg.sources.narrow_ctgov_study_records import (
                 narrow_ctgov_study_records, read_filters)
                read_filters()                                  -> the filters file's settings
                narrow_ctgov_study_records(studies, after_fetch) -> (kept records, counts)

Exit codes:  There are none, because this file is not run on its own. On a problem it stops
             and hands an error to the program using it, which decides what to
             do. Every error is a kind of FiltersError, carrying the exit number and
             sub-code a command reports it with, from docs/exit_codes.csv. The errors
             it can hand back:
             FiltersMissingError      the filters file is missing
             FiltersUnreadableError   the filters file is on disk but cannot be read
             FiltersUnparseableError  the filters file is not valid YAML
             FiltersInvalidError      the filters file is missing a setting the
                                      filter functions need, or has a setting none
                                      of them reads

Date:        2026-10-06
Owner:       Jason Delosh
"""

from datetime import date
from pathlib import Path
from typing import Any

import yaml

from .parse_ctgov_study_records import list_study_countries, list_study_documents

#######################################################################################
### Settings ###

# The filters file sits in the same folder as this script, so the script finds it
# there, whatever folder the script is run from.
FILTERS_FILE = Path(__file__).with_name("ctgov_study_filters.yml")

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

#######################################################################################
### Failures ###

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


def narrow_ctgov_study_records(
    studies: list[dict[str, Any]], additional_filters: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Obtain just the studies that meet the criteria defined by the additional filters.

    Each pass through the loop keeps only the studies the current filter says yes to,
    then writes down how many are left.

    Args:
        studies: The study records returned by fetch_ctgov_study_records in
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
