"""
Script:      validate_technical.py
Description: Runs the technical checks, and with --validation-report writes the
             technical report. It is the one way to file a report on how the
             project's scripts run.

             It hands pytest the person's arguments with --aspect technical added,
             so only technical checks run. With --validation-report, the report is
             written by src/sdgval/report.py. Without it, the run writes nothing,
             which is how the technical checks are run during development. Every
             other way of narrowing a run works as it does for pytest, such as
             --objective, --category, --id, --group, a test file or a list of test
             files.

             A run given --aspect is refused before any check runs, because the
             aspect is this command's own and a second one would mix aspects in
             one report.

Inputs:      validation/**/test_*.py (read-only; the checks it runs)

Outputs:     Nothing, unless --validation-report is given. Then one report in
             validation/reports/, written by src/sdgval/report.py and named
             technical_<YYYY-MM-DD>_<commit>.csv.

Usage:       validate_technical
                 run every technical check and write nothing
             validate_technical --validation-report
                 run every technical check and write the report
             validate_technical --objective functionality
                 run only the technical checks with that objective
             validate_technical --id SA00106,SA00283
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

import pytest

from sdgval.report import REPORT_ASPECT
from sdgval.select_checks import wanted

#######################################################################################
### Settings ###

# The aspect this command runs. The conformance and integrity commands differ here.
ASPECT = "technical"


#######################################################################################
### Naming the report and refusing a second aspect ###


class AspectRun:
    """A pytest plugin, handed to this run alone, that holds the run to its aspect.

    It tells the report writer the aspect, so the report's name starts with it, and
    it refuses any aspect but its own. The refusal is raised inside pytest as its
    usage error, so the run ends with pytest's own exit status 4 and nothing runs,
    the same way the report writer refuses a report on uncommitted changes.
    """

    def pytest_configure(self, config: pytest.Config) -> None:
        """Leave the aspect in pytest's stash, where the report writer reads it.

        Args:
            config: pytest's configuration for the run.
        """
        config.stash[REPORT_ASPECT] = ASPECT

    def pytest_sessionstart(self, session: pytest.Session) -> None:
        """Refuse the run when the person named an aspect of their own.

        Args:
            session: The pytest run.

        Raises:
            pytest.UsageError: The run holds an aspect other than this command's.
        """
        aspects = wanted(session.config, "aspect")
        if aspects != [ASPECT]:
            raise pytest.UsageError(
                f"validate_{ASPECT} runs only {ASPECT} checks, and --aspect was "
                f"given as well, naming {', '.join(aspects)}. Run it without "
                "--aspect."
            )


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
    args = sys.argv[1:] if argv is None else argv
    return int(
        pytest.main(
            ["--aspect", ASPECT, *args],
            plugins=[AspectRun()],
        )
    )


if __name__ == "__main__":
    sys.exit(main())
