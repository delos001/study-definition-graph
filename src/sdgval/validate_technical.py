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
             --category, --id, --group, a test file or a list of test files. A run
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

Exit codes:  pytest's own, passed through: 0 all passed, 1 some failed, 2 the run
             was interrupted, 3 internal error, 4 bad command line, which
             includes a run given --aspect and a report refused on uncommitted
             changes, and 5 no check was collected.

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
        pytest's exit status for the run.
    """
    return run_aspect(ASPECT, sys.argv[1:] if argv is None else argv)


if __name__ == "__main__":
    sys.exit(main())
