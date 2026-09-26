"""
Script:      aspect_run.py
Description: Holds one pytest run to one aspect of quality. It is the part every
             aspect's command shares, such as src/sdgval/validate_technical.py, and
             it holds nothing that belongs to any one aspect. What an aspect reads,
             records or checks lives in that aspect's own module.

             It hands pytest the person's arguments with --aspect and the command's
             aspect added, so only that aspect's checks run. It leaves the aspect in
             pytest's stash, where src/sdgval/report.py reads it to name the report
             and src/sdgval/select_checks.py reads it to word its refusals.
             A run given --aspect by the person is refused before any check runs,
             because the aspect is the command's own and a second one would mix
             aspects in one report.

Inputs:      validation/**/test_*.py (read-only; the checks the run collects)

Outputs:     Nothing of its own. The report, when one is asked for, is written by
             src/sdgval/report.py.

Usage:       run_aspect("technical", ["--validation-report"])
                 called from an aspect's command, with the person's arguments

Exit codes:  pytest's own, passed through: 0 all passed, 1 some failed, 2 the run
             was interrupted, 3 internal error, 4 bad command line, which
             includes a run given --aspect, and 5 no check was collected.

Date:        2026-09-26
Owner:       Jason Delosh
"""

from __future__ import annotations

import pytest

from sdgval.select_checks import RUN_ASPECT, wanted

#######################################################################################
### Naming the report and refusing a second aspect ###


class AspectRun:
    """A pytest plugin, handed to one run, that holds the run to one aspect.

    It tells the report writer the aspect, so the report's name starts with it, and
    it refuses any aspect the person named. The refusal is raised inside pytest as its
    usage error, so the run ends with pytest's own exit status 4 and nothing runs,
    the same way the report writer refuses a report on uncommitted changes.
    """

    def __init__(self, aspect: str) -> None:
        """Hold the aspect the run is kept to.

        Args:
            aspect: The aspect of quality, such as technical.
        """
        self.aspect = aspect

    def pytest_configure(self, config: pytest.Config) -> None:
        """Leave the aspect in pytest's stash, for the report writer and the refusals.

        Args:
            config: pytest's configuration for the run.
        """
        config.stash[RUN_ASPECT] = self.aspect

    def pytest_sessionstart(self, session: pytest.Session) -> None:
        """Refuse the run when the person named an aspect of their own.

        Args:
            session: The pytest run.

        Raises:
            pytest.UsageError: The run holds an aspect other than the command's.
        """
        aspects = wanted(session.config, "aspect")
        if aspects != [self.aspect]:
            raise pytest.UsageError(
                f"validate_{self.aspect} already runs only {self.aspect} checks, so "
                "it does not accept --aspect. Run it without --aspect."
            )


#######################################################################################
### Running the checks ###


def run_aspect(aspect: str, args: list[str]) -> int:
    """Run one aspect's checks, passing the person's arguments on.

    Args:
        aspect: The aspect of quality the run is kept to.
        args: The arguments the person typed after the command.

    Returns:
        pytest's exit status for the run.
    """
    return int(pytest.main(["--aspect", aspect, *args], plugins=[AspectRun(aspect)]))
