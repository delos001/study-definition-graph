"""
Script:      test_aspect_run_technical.py
Description: Checks for src/sdgval/aspect_run.py, the part every aspect's command
             shares to hold a run to one aspect of quality.

             Each check stages a tiny throwaway suite holding a technical check and
             an integrity check, with the staged_suite fixture in
             validation/conftest.py, commits it as a git repository, because a
             report is written only in one, runs the shared code on it as a
             separate process, and reads the report that comes out. The shared
             code runs pytest, which cannot be run a second time inside the pytest
             process running these checks, so a separate process is the only way
             to run it whole.

Inputs:      Nothing real. Each staged suite is written to pytest's own temporary
             folder.

Outputs:     Writes nothing to disk outside pytest's temporary folder.

Usage:       pytest validation/sdgval/test_aspect_run_technical.py
                 run these checks
             pytest validation/sdgval/test_aspect_run_technical.py -v
                 one line per check with its result

Exit codes:  pytest's own: 0 all passed, 1 some failed

Date:        2026-09-26
Owner:       Jason Delosh
"""

from __future__ import annotations

import sys

import pytest

positive = pytest.mark.positive
# Every check carries a @code line: its short, permanent id in
# validation/validation_inventory.csv, assigned once and never reused.
code = pytest.mark.code
# Every check carries an @objective line: what the check confirms about its category,
# one of the objectives validation/validation_inventory_dictionary.md defines.
objective = pytest.mark.objective
# Every check carries a @category line: what kind of thing the check confirms, one
# of the categories validation/validation_inventory_dictionary.md defines.
category = pytest.mark.category


#######################################################################################
### Shared staging ###
#
# One suite holds a technical check and an integrity check, so a report holding only
# one of them shows which aspect the run was held to.

MIXED_SUITE = '''
    import pytest

    @pytest.mark.code("XYZ0201")
    @pytest.mark.objective("functionality")
    def test_runs():
        """A technical check."""

    @pytest.mark.code("XYZ0202")
    @pytest.mark.objective("correctness")
    def test_holds():
        """An integrity check."""
    '''

# The shared code, called the way an aspect's command calls it, with the aspect given
# as the first argument and the person's arguments after it.
RUN_ONE_ASPECT = (
    "import sys\n"
    "from sdgval.aspect_run import run_aspect\n"
    "sys.exit(run_aspect(sys.argv[1], sys.argv[2:]))\n"
)


#######################################################################################
### Holding a run to the aspect it is given ###


@code("SA00495")
@category("repository")
@objective("functionality")
@positive
def test_the_run_is_held_to_the_aspect_it_is_given(staged_suite, pytester):
    """Given the integrity aspect, the shared code writes a report named for
    integrity, in a folder named integrity, whose rows are the integrity checks
    alone."""
    staged_suite.commit(MIXED_SUITE, aspect_conftest=False)
    result = pytester.run(
        sys.executable,
        "-c",
        RUN_ONE_ASPECT,
        "integrity",
        "--validation-report",
        "--validation-report-dir",
        str(staged_suite.report_dir),
    )
    assert result.ret == 0
    out = staged_suite.report_dir / "integrity"
    rows = staged_suite.report(out)
    assert {row["id"] for row in rows} == {"XYZ0202"}
    assert all(row["run_id"].startswith("integrity_") for row in rows)
