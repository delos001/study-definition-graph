"""
Script:      validate_technical.py
Description: Runs the technical checks, and with --validation-report writes the
             technical report. It is the one way to file a report on how the
             project's scripts run.

             Holding the run to the technical aspect is done by
             src/sdgval/aspect_run.py, which every aspect's command shares. This
             file names the aspect, and anything that concerns the technical aspect
             alone belongs here. With --validation-report, the report is written by
             src/sdgval/report.py. Without it, the run writes nothing, which is how
             the technical checks are run during development. Every other way of
             narrowing a run works as it does for pytest, such as --objective,
             --category, --id, --group, a check file or a list of check files. A run
             given --aspect is refused before any check runs.

Inputs:      validation/**/test_*.py (read-only; the checks it runs)

Outputs:     Nothing, unless --validation-report is given. Then two files in
             validation/reports/technical/, written by src/sdgval/report.py: the
             report, technical_<YYYY-MM-DD>_<commit>.csv, and beside it the run's
             own file, the same name ending _run.csv.

Usage:       validate_technical
                 run every technical check and write nothing
             validate_technical --validation-report
                 run every technical check and write the report
             validate_technical --objective functionality
                 run only the technical checks with that objective
             validate_technical --id SA00001,SA00002
                 run only the checks with those ids
             validate_technical validation/sdg/sources
                 run only the technical checks in that folder

Exit codes:  0   SUCCEEDED  the command succeeded
             1   UNHANDLED-ERROR  Python stopped on an error that nothing
                 handled
             1   PYTEST-INTERNAL-ERROR  pytest stopped on an error inside pytest
                 or one of the project's plugins
             2   COMMAND-LINE-REFUSED  the argument parser refused the command
                 line (pytest refused the command line, such as an option it
                 does not know)
             2   ASPECT-OPTION-GIVEN  an aspect's command was given --aspect
             3   UNCOMMITTED-CHANGES  a validation report was refused because
                 the working folder has changes that are not committed
             6   GIT-NOT-FOUND  git cannot be found on the path (a validation
                 report was asked for)
             7   GIT-FAILED  git was found but did not answer (a validation
                 report was asked for)
             12  GROUPS-FILE-MISSING  validation/validation_groups.yml, which
                 --group reads, is missing
             15  GROUP-MIXES-ASPECTS  a group in validation/validation_groups.yml
                 lists checks of more than one aspect
             15  GROUP-HAS-NO-IDS  a group in validation/validation_groups.yml
                 lists no ids
             16  GROUP-ID-UNKNOWN  a group in validation/validation_groups.yml
                 lists an id no check has
             17  SELECTION-MATCHES-NOTHING  the selection options leave no check
                 to run
             18  NO-CHECKS-COLLECTED  no check was collected
             21  CHECKS-FAILED  one or more validation checks failed (a check
                 whose set-up or clean-up broke counts as failed)
             23  RUN-INTERRUPTED  the check run was interrupted before every
                 check ran (it was stopped by hand, or a check file could not
                 be loaded)
             src/sdgval/aspect_run.py turns pytest's own exit status into these
             numbers and prints the exit line. A plain pytest run of the same
             checks keeps pytest's own numbers. The wording is the table in
             docs/exit_codes.csv.

Date:        2026-09-25
Owner:       Jason Delosh
"""

from __future__ import annotations

import sys

from sdgval.aspect_run import run_aspect

#######################################################################################
### Settings ###

# The aspect this command runs. The conformance and integrity commands differ here.
ASPECT = "technical"


#######################################################################################
### Running the checks ###


def main(argv: list[str] | None = None) -> int:
    """Run the technical checks, passing the person's arguments on.

    Args:
        argv: The command-line arguments, or None to read them from the command
            line.

    Returns:
        The repo's exit number for how the run ended, as the header lists them.
    """
    return run_aspect(ASPECT, sys.argv[1:] if argv is None else argv)


if __name__ == "__main__":
    sys.exit(main())
