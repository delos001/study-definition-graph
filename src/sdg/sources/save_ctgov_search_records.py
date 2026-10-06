"""
Script:      save_ctgov_search_records.py
Description: Writes the record of one search of ClinicalTrials.gov to searches/ctgov/,
             one file per search, named by the date and time the search started.

             A search record holds the query as sent, the parts of each study record
             asked for, the additional filters, how many studies ClinicalTrials.gov
             returned, how many were left after each additional filter, and the
             candidate studies.

             Studies on ClinicalTrials.gov are added and updated daily, so a later
             search cannot reproduce an earlier one, and the record is the only proof
             of what a search found. The records are committed for that reason.

Inputs:      the search's settings, counts and candidates, handed in by the caller

Outputs:     One JSON file in searches/ctgov/, and the folder if it did not exist.
             Hands back the path of the file written.

Usage:       This file is not run directly; other code imports it.
             from sdg.sources.save_ctgov_search_records import save_ctgov_search_records
                save_ctgov_search_records(filters, fields, returned, remaining,
                                          candidates, ran_at)   -> path of the file

Exit codes:  There are none, because this file is not run on its own. On a problem it stops
             and hands an error to the program using it, which decides what to
             do. The error carries the exit number and sub-code a command reports it
             with, from docs/exit_codes.csv. The error it can hand back:
             RecordNotWrittenError   the search record, or its folder, could not be
                                     written to disk

Date:        2026-10-06
Owner:       Jason Delosh
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .read_manifests import REPO_ROOT

#######################################################################################
### Settings ###

# Each search's record is saved in this folder, one file per search.  The records are
# committed because ClinicalTrials.gov changes daily and no later search can show what
# an earlier search found.
SEARCHES_DIR = REPO_ROOT / "searches" / "ctgov"

#######################################################################################
### Failures ###

# The failure carries an exit number and short name which are listed in
# docs/exit_codes.csv.


class RecordNotWrittenError(Exception):
    """Raised when the search record or its folder cannot be written to disk."""

    exit_code = 20
    sub_code = "CTGOV-RECORD-NOT-WRITTEN"


#######################################################################################
### Saving the search record ###

# Writes the query as sent, the date, the counts and the studies that passed.


def save_ctgov_search_records(
    filters: dict[str, Any],
    fields: str,
    returned: int,
    remaining: dict[str, int],
    candidates: list[dict[str, Any]],
    ran_at: datetime,
) -> Path:
    """Write down what one search asked for and found.

    The file is named by the date and time the search started, such as
    2026-10-05_143012.json. The time has no colons, because Windows does not allow
    them in a file name.

    Args:
      filters: The filters returned by read_filters in narrow_ctgov_study_records.py.
      fields: The parts of each study record the search asked for, as passed to
        fetch_ctgov_study_records.
      returned: How many studies fetch_ctgov_study_records returned.
      remaining: How many studies were left after each filter, from
        narrow_ctgov_study_records.
      candidates: One description per candidate study, from describe_candidate in
        parse_ctgov_study_records.py.
      ran_at: When the search started.

    Returns:
      The path of the file written.

    Raises:
      RecordNotWrittenError: The folder or file could not be written.
    """

    record = {
        "ran_at": ran_at.isoformat(timespec="seconds"),
        "api": filters["api"],
        "query": filters["query"],
        "fields": fields,
        "additional_filters": filters["after_fetch"],
        "returned": returned,
        "remaining_after": remaining,
        "candidates": candidates,
    }

    path = SEARCHES_DIR / f"{ran_at:%Y-%m-%d_%H%M%S}.json"

    # The filters file holds the SAP date as a date, which JSON cannot store, so
    # default=str writes it as text, such as 2020-01-01. A folder or file that cannot
    # be written becomes RecordNotWrittenError, so the program using this module can
    # report it.
    try:
        SEARCHES_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(record, indent=2, default=str) + "\n", encoding="utf-8"
        )

    except OSError as exc:
        raise RecordNotWrittenError(
            f"the search record could not be written to {path} ({exc})."
        ) from exc
    return path
