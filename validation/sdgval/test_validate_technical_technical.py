"""
Script:      test_validate_technical_technical.py
Description: Checks for src/sdgval/validate_technical.py, the command that runs the
             technical checks and writes the technical report.

             Each check stages a tiny throwaway suite holding technical checks and
             an integrity check, with the staged_suite fixture in
             validation/conftest.py, runs the command on it as a separate process,
             and reads the report that comes out. The command runs pytest, which
             cannot be run a second time inside the pytest process running these
             checks, so a separate process is the only way to run it whole.

Inputs:      Nothing real. Each staged suite is written to pytest's own temporary
             folder.

Outputs:     Writes nothing to disk outside pytest's temporary folder.

Usage:       pytest validation/sdgval/test_validate_technical_technical.py
                 run these checks
             pytest validation/sdgval/test_validate_technical_technical.py -v
                 one line per check with its result

Exit codes:  pytest's own: 0 all passed, 1 some failed

Date:        2026-09-25
Owner:       Jason Delosh
"""

from __future__ import annotations

import json
import sys

import pytest

positive = pytest.mark.positive
negative = pytest.mark.negative
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
# One suite holds two technical checks and one integrity check, so a report that
# holds only the technical rows shows the command kept to its aspect.

MIXED_SUITE = '''
    import pytest

    @pytest.mark.code("XYZ0101")
    @pytest.mark.objective("functionality")
    def test_runs():
        """A technical check."""

    @pytest.mark.code("XYZ0102")
    @pytest.mark.objective("correctness")
    def test_holds():
        """An integrity check."""

    @pytest.mark.code("XYZ0103")
    @pytest.mark.objective("functionality")
    def test_also_runs():
        """A second technical check."""
    '''


def run_command(staged_suite, pytester, *args, report=True):
    """Write the mixed suite and run the command on it in a separate process.

    Args:
        staged_suite: The throwaway suite to write.
        pytester: pytest's helper for running a separate process.
        *args: The arguments a person would type after the command.
        report: Whether --validation-report is given.

    Returns:
        The result of the run and the technical folder inside the report folder,
        where the report is written.
    """
    staged_suite.write(MIXED_SUITE)
    if report:
        args = ("--validation-report", *args)
    result = pytester.run(
        sys.executable,
        "-m",
        "sdgval.validate_technical",
        "--validation-report-dir",
        str(staged_suite.report_dir),
        *args,
    )
    return result, staged_suite.report_dir / "technical"


#######################################################################################
### Running the technical checks ###


@code("SA00481")
@category("repository")
@objective("functionality")
@positive
def test_the_report_holds_only_the_technical_checks(staged_suite, pytester):
    """Run on a suite holding technical checks and an integrity check, the command
    exits 0 and writes a report whose rows are the technical checks alone."""
    result, out = run_command(staged_suite, pytester)
    assert result.ret == 0
    ids = {row["id"] for row in staged_suite.report(out)}
    assert ids == {"XYZ0101", "XYZ0103"}


@code("SA00482")
@category("repository")
@objective("functionality")
@positive
def test_options_after_the_command_narrow_the_run(staged_suite, pytester):
    """An option typed after the command, such as --id, narrows the run the way it
    narrows pytest, so the report holds only the checks it selects."""
    result, out = run_command(staged_suite, pytester, "--id", "XYZ0103")
    assert result.ret == 0
    ids = {row["id"] for row in staged_suite.report(out)}
    assert ids == {"XYZ0103"}


@code("SA00486")
@category("repository")
@objective("functionality")
@positive
def test_without_the_report_flag_the_checks_run_and_nothing_is_written(
    staged_suite, pytester
):
    """Without --validation-report, the command runs the technical checks, exits 0
    and writes no report, so a development run leaves no record."""
    result, out = run_command(staged_suite, pytester, "-v", report=False)
    assert result.ret == 0
    assert "test_runs PASSED" in result.stdout.str()
    assert not out.exists()


@code("SA00484")
@category("repository")
@objective("functionality")
@positive
def test_the_report_is_named_for_its_aspect(staged_suite, pytester):
    """The report's file name starts with technical, and every row's run_id is that
    name without .csv, so a report copied out of its folder still says which aspect
    it covers."""
    result, out = run_command(staged_suite, pytester)
    assert result.ret == 0
    (report,) = (p for p in out.glob("*.csv") if not p.stem.endswith("_run"))
    assert report.name.startswith("technical_")
    assert {row["run_id"] for row in staged_suite.report(out)} == {report.stem}


@code("SA00487")
@category("repository")
@objective("functionality")
@positive
def test_the_report_is_written_in_the_technical_folder(staged_suite, pytester):
    """The report and the run's own file are written in a folder named technical
    inside the report folder, and nothing is written in the report folder itself, so
    each aspect's reports are kept apart."""
    result, _ = run_command(staged_suite, pytester)
    assert result.ret == 0
    assert len(list((staged_suite.report_dir / "technical").glob("*.csv"))) == 2
    assert not list(staged_suite.report_dir.glob("*.csv"))


@code("SA00490")
@category("repository")
@objective("functionality")
@positive
def test_each_way_of_narrowing_the_run_has_its_own_column(staged_suite, pytester):
    """In the run's own file, each way the run was narrowed is written in its own
    selection column, a list as JSON, and a way that was not used leaves its column
    empty."""
    result, out = run_command(staged_suite, pytester, "--id", "XYZ0103")
    assert result.ret == 0
    run = staged_suite.run_details(out)
    assert json.loads(run["selection_aspect"]) == ["technical"]
    assert json.loads(run["selection_id"]) == ["XYZ0103"]
    assert run["selection_objective"] == ""
    assert run["selection_keyword"] == ""


#######################################################################################
### Refusing a second aspect ###


@code("SA00483")
@category("repository")
@objective("functionality")
@negative
def test_a_run_given_an_aspect_is_refused_before_any_check_runs(staged_suite, pytester):
    """A run given --aspect stops with pytest's usage error, exit 4, before any check
    runs, the message says the command runs only technical checks and to run it
    without --aspect, and no report is written."""
    result, out = run_command(staged_suite, pytester, "--aspect", "integrity")
    printed = result.stdout.str() + result.stderr.str()
    assert result.ret == 4
    assert "validate_technical runs only technical checks" in printed
    assert "Run it without --aspect." in printed
    assert "test_holds" not in result.stdout.str()
    assert not out.exists()
