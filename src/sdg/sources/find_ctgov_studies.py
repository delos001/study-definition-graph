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

             The work is done by four steps in this folder, which this script calls
             in order:
             - narrow_ctgov_study_records.py reads the filters file, and later keeps
               the study records that pass the additional filters,
             - fetch_ctgov_study_records.py sends the query and collects the study
               records,
             - parse_ctgov_study_records.py pulls out the details of each candidate,
             - save_ctgov_search_records.py writes the search record.

Inputs:      src/sdg/sources/ctgov_study_filters.yml (read-only)
             the ClinicalTrials.gov API (read-only)

Outputs:     One search record per run, written to searches/ctgov/ and named by the
             date and time the run started. Prints how many studies
             ClinicalTrials.gov returned and how many were left after each filter.


Usage:       find_ctgov_studies
                 search ClinicalTrials.gov, apply the filters, save the search record
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
                 filter (the search record is still saved)
             20  CTGOV-RECORD-NOT-WRITTEN  the ClinicalTrials.gov search record, or
                 its folder, could not be written to disk
             The wording is the table in docs/exit_codes.csv.


Date:        2026-10-02
Owner:       Jason Delosh
"""

import argparse
import sys
from datetime import datetime

from sdg.exit_codes import fail
from sdg.sources.fetch_ctgov_study_records import CtgovError, fetch_ctgov_study_records
from sdg.sources.narrow_ctgov_study_records import (
    FiltersError,
    narrow_ctgov_study_records,
    read_filters,
)
from sdg.sources.parse_ctgov_study_records import describe_candidate
from sdg.sources.read_manifests import REPO_ROOT, NotInRepoError, require_repo
from sdg.sources.save_ctgov_search_records import (
    RecordNotWrittenError,
    save_ctgov_search_records,
)

#######################################################################################
### Settings ###

# Specifies the parts of each study requested by the script. Note that posted results
# are excluded because no filters read them and they increase reply size.
FIELDS = "ProtocolSection|DocumentSection|DerivedSection"

#######################################################################################
### Finding the studies ###

# The main() that runs the steps in order.


def main(argv: list[str] | None = None) -> int:
    """Run the steps of this script in order and report the results or the failure.

    Steps:
    - read_filters reads ctgov_study_filters.yml and confirms it is complete.
    - fetch_ctgov_study_records sends the search to ClinicalTrials.gov and collects
      every matching study record.
    - narrow_ctgov_study_records keeps the studies that pass every additional filter,
      and counts how many were left after each one.
    - describe_candidate gathers the details of each study that passed.
    - save_ctgov_search_records writes the search, the counts and the candidates to a
      file in searches/ctgov/.

    Any step that fails stops the run, and main() reports the failure with its exit
    number.

    Args:
        argv: The command-line arguments, or None to read the real ones.

    Returns:
        The exit code, as the header block lists them.
    """

    parser = argparse.ArgumentParser(
        description="List the studies on ClinicalTrials.gov that pass the filters in "
        "ctgov_study_filters.yml, and save a record of the search."
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

    # Each step raises one of the failures its own file lists. They are all caught
    # here and reported with their own exit number.
    try:
        filters = read_filters()
        studies = fetch_ctgov_study_records(filters["api"], filters["query"], FIELDS)
        candidates, remaining = narrow_ctgov_study_records(
            studies, filters["after_fetch"]
        )
        path = save_ctgov_search_records(
            filters,
            FIELDS,
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
    say(f"The record of this search is in {path.relative_to(REPO_ROOT)}.")

    # A run that leaves no candidates is still saved above, because its record shows
    # which filter removed the last of them.
    if not candidates:
        return fail(say, 17, "CTGOV-NO-CANDIDATES", "no study passed every filter.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
