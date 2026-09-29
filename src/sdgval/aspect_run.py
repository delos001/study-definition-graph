"""
Script:      aspect_run.py
Description: Holds one pytest run to one aspect of quality. It is the part every
             aspect's command shares, such as src/sdgval/validate_technical.py, and
             it holds nothing that belongs to any one aspect. What an aspect reads,
             records or validates lives in that aspect's own module.

             It hands pytest the person's arguments with --aspect and the command's
             aspect added, so only that aspect's checks run. It leaves the aspect in
             pytest's stash, where src/sdgval/report.py reads it to name the report
             and src/sdgval/select_checks.py reads it to word its refusals.
             A run given --aspect by the person is refused before any check runs,
             because the aspect is the command's own and a second one would mix
             aspects in one report.

             When pytest has finished, it turns pytest's exit status into the
             repo's own number from docs/exit_codes.csv, so an aspect's command
             means the same by a number as every other script. pytest's usage
             error, 4, covers every refusal this package makes, so each refusal
             leaves its cause in pytest's stash, and the number is chosen by that
             cause. A plain pytest run is not changed and keeps pytest's numbers.

Inputs:      validation/**/test_*.py (read-only; the checks the run collects)

Outputs:     Nothing of its own. The report, when one is asked for, is written by
             src/sdgval/report.py. run_aspect() hands back the exit number.

Usage:       run_aspect("technical", ["--validation-report"])
                 called from an aspect's command, with the person's arguments

Exit codes:  None of its own. run_aspect() hands back the number an aspect's
             command exits with, and that command's header lists the numbers, as
             src/sdgval/validate_technical.py does.

Date:        2026-09-26
Owner:       Jason Delosh
"""

from __future__ import annotations

import pytest

from sdgval.select_checks import REFUSAL, RUN_ASPECT, Refusal, refuse, wanted

#######################################################################################
### Settings ###

# The repo's number for each way pytest can end a run. An internal error in pytest is
# an unhandled error, and a command line pytest refused is an invalid command line, so
# those two take Python's own numbers. Every number is a row of docs/exit_codes.csv.
PYTEST_EXITS: dict[int, int] = {
    pytest.ExitCode.OK: 0,
    pytest.ExitCode.TESTS_FAILED: 52,
    pytest.ExitCode.INTERRUPTED: 53,
    pytest.ExitCode.INTERNAL_ERROR: 1,
    pytest.ExitCode.USAGE_ERROR: 2,
    pytest.ExitCode.NO_TESTS_COLLECTED: 54,
}

# The repo's number for each refusal the validation package makes before any check
# runs. pytest reports every one of them as its usage error, 4, and the cause each
# refusal leaves behind is what tells them apart.
REFUSAL_EXITS = {
    Refusal.GROUPS_FILE_MISSING: 13,
    Refusal.NO_CHECK_COLLECTED: 54,
    Refusal.ASPECT_GIVEN: 55,
    Refusal.NOTHING_SELECTED: 56,
    Refusal.UNCOMMITTED_CHANGES: 57,
    Refusal.GIT_SILENT: 58,
    Refusal.GROUP_OF_MIXED_ASPECTS: 59,
    Refusal.GROUP_WITHOUT_IDS: 60,
    Refusal.GROUP_WITH_UNKNOWN_ID: 61,
}


#######################################################################################
### Naming the report and refusing a second aspect ###


class AspectRun:
    """A pytest plugin, handed to one run, that holds the run to one aspect.

    It tells the report writer the aspect, so the report's name starts with it, and
    it refuses any aspect the person named. The refusal is raised inside pytest as its
    usage error, so nothing runs, the same way the report writer refuses a report on
    uncommitted changes. It keeps pytest's configuration, so the cause of a refusal
    can be read once the run has ended.
    """

    def __init__(self, aspect: str) -> None:
        """Hold the aspect the run is kept to.

        Args:
            aspect: The aspect of quality, such as technical.
        """
        self.aspect = aspect
        self.config: pytest.Config | None = None

    def pytest_configure(self, config: pytest.Config) -> None:
        """Leave the aspect in pytest's stash, for the report writer and the refusals.

        Args:
            config: pytest's configuration for the run.
        """
        self.config = config
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
            refuse(
                session.config,
                Refusal.ASPECT_GIVEN,
                f"validate_{self.aspect} already runs only {self.aspect} checks, so "
                "it does not accept --aspect. Run it without --aspect.",
            )

    def refusal(self) -> Refusal | None:
        """Say why the run was refused, when a refusal of this package stopped it.

        Returns:
            The cause the refusal left in pytest's stash, or None when there was no
            such refusal, or pytest stopped before it read its configuration.
        """
        if self.config is None:
            return None
        return self.config.stash.get(REFUSAL, None)


#######################################################################################
### Running the checks ###


def exit_number(status: int, refusal: Refusal | None) -> int:
    """Turn pytest's exit status into the repo's own number for the same cause.

    Args:
        status: pytest's exit status for the run.
        refusal: The cause a refusal of this package left, or None.

    Returns:
        The number from docs/exit_codes.csv. A number pytest does not define comes
        only from a check or plugin that ends the run with a number of its own, which
        nothing in this project does, so it is handed back as an unhandled error.
    """
    if status == pytest.ExitCode.USAGE_ERROR and refusal is not None:
        return REFUSAL_EXITS[refusal]
    return PYTEST_EXITS.get(status, 1)


def run_aspect(aspect: str, args: list[str]) -> int:
    """Run one aspect's checks, passing the person's arguments on.

    Args:
        aspect: The aspect of quality the run is kept to.
        args: The arguments the person typed after the command.

    Returns:
        The repo's exit number for how the run ended.
    """
    plugin = AspectRun(aspect)
    status = int(pytest.main(["--aspect", aspect, *args], plugins=[plugin]))
    return exit_number(status, plugin.refusal())
