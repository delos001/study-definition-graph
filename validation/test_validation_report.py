"""
Script:      test_validation_report.py
Description: Checks for the validation-report writer in validation/conftest.py. A
             report is the proof that the code was validated, so the writer
             itself has to be proven: above all, that it can never say PASS
             when pytest said the run failed.

             Each check builds a tiny throwaway test suite in a temporary
             folder (using pytest's own "pytester" helper), gives it a copy of
             validation/conftest.py, runs pytest on it as a separate process with
             --validation-report pointed at a temporary folder, and reads the
             CSV report that comes out. Nothing is written under
             validation/reports/.

Inputs:      validation/conftest.py   (read-only; copied into each throwaway suite)

Outputs:     Writes nothing to disk outside pytest's temporary folder.

Usage:       pytest validation/test_validation_report.py
                 run these checks
             pytest validation/test_validation_report.py -v
                 one line per check with its result

Exit codes:  pytest's own: 0 all passed, 1 some failed

Date:        2026-09-04
Owner:       Jason Delosh
"""

from __future__ import annotations

import csv
import textwrap
from pathlib import Path

import pytest

CONFTEST_SOURCE = (Path(__file__).resolve().parent / "conftest.py").read_text(
    encoding="utf-8"
)
REPO_TOOLS = Path(__file__).resolve().parents[1] / "repo_tools"

positive = pytest.mark.positive
negative = pytest.mark.negative
# Every check carries a @code line: its short, permanent id in
# validation/validation_inventory.csv, assigned once and never reused.
code = pytest.mark.code


#######################################################################################
### Shared staging ###
#
# One helper runs a throwaway suite with the real conftest beside it, and one reads
# the report back as rows.


def with_repo_tools(monkeypatch) -> None:
    """Put repo_tools/ on the import path of the throwaway suite's process.

    The copied conftest imports the inventory generator from there. The real run gets
    that path from pyproject.toml, which the throwaway suite does not read.

    Args:
        monkeypatch: pytest's patcher, which puts the variable back when the check ends.
    """
    monkeypatch.setenv("PYTHONPATH", str(REPO_TOOLS))


def run_suite(pytester, monkeypatch, test_source: str, *extra_args: str):
    """Run pytest on one throwaway test file, with the real conftest.py beside it.

    Args:
        pytester: pytest's helper for running a separate suite.
        monkeypatch: pytest's patcher, for the import path of the separate process.
        test_source: The source of the one test file.
        *extra_args: Any further pytest arguments.

    Returns:
        pytest's result and the folder the report was written to.
    """
    with_repo_tools(monkeypatch)
    pytester.makeconftest(CONFTEST_SOURCE)
    pytester.makepyfile(test_suite=textwrap.dedent(test_source))
    out = pytester.path / "reports_out"
    result = pytester.runpytest_subprocess(
        "--validation-report", "--validation-report-dir", str(out), *extra_args
    )
    return result, out


def the_report(folder: Path) -> list[dict[str, str]]:
    """Read the one report the run wrote.

    Args:
        folder: Where the report was written.

    Returns:
        The report's rows, one record per check, each a dict keyed by column name.
    """
    reports = list(folder.glob("*.csv"))
    assert len(reports) == 1, [r.name for r in reports]
    with reports[0].open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def row_for(rows: list[dict[str, str]], check_name: str) -> dict[str, str]:
    """Pick the one row for a named check.

    Args:
        rows: The report's rows.
        check_name: The check's function name.

    Returns:
        That check's row.
    """
    matches = [r for r in rows if r["check_name"] == check_name]
    assert len(matches) == 1, [r["check_name"] for r in rows]
    return matches[0]


#######################################################################################
### The report on a clean run ###


PASSING_SUITE = '''
    import pytest

    @pytest.mark.code("XYZ0001")
    @pytest.mark.positive
    def test_adds():
        """Two and two make four."""
        assert 2 + 2 == 4

    @pytest.mark.skipif(True, reason="not today")
    def test_left_out():
        """Never runs."""
    '''


@pytest.fixture
def passing(pytester, monkeypatch):
    """Run a suite whose one live check passes and whose other check is skipped, and
    hand back pytest's result and the report's rows."""
    result, out = run_suite(pytester, monkeypatch, PASSING_SUITE)
    return result, the_report(out)


@code("TST0001")
@positive
def test_passing_run_is_recorded_as_pass(passing):
    """A suite whose tests all pass gets a report saying PASS, with pytest's exit
    status 0 and its meaning on every row."""
    result, rows = passing
    assert result.ret == 0
    assert {r["run_verdict"] for r in rows} == {"PASS"}
    assert {r["pytest_exit_status"] for r in rows} == {"0"}
    assert {r["exit_meaning"] for r in rows} == {"all tests passed"}


@code("TST0007")
@positive
def test_a_passing_check_gets_a_row_with_its_details(passing):
    """A check that passed gets one row carrying its code, its kind, the sentence it
    proves and the outcome passed."""
    _, rows = passing
    adds = row_for(rows, "test_adds")
    assert adds["check_name_code"] == "XYZ0001"
    assert adds["kind"] == "positive"
    assert adds["proves"] == "Two and two make four."
    assert adds["check_outcome"] == "passed"


@code("TST0008")
@positive
def test_a_skipped_check_is_shown_as_skipped_with_its_reason(passing):
    """A check that was skipped gets a row saying skipped, with the skip's reason and,
    since it carries no marker, the kind unmarked."""
    _, rows = passing
    left_out = row_for(rows, "test_left_out")
    assert left_out["kind"] == "unmarked"
    assert left_out["check_outcome"] == "skipped"
    assert left_out["outcome_reason"] == "not today"


@code("TST0002")
@positive
def test_no_flag_writes_nothing(pytester, monkeypatch):
    """Without --validation-report, a run writes no report at all, so development
    runs leave no trace."""
    with_repo_tools(monkeypatch)
    pytester.makeconftest(CONFTEST_SOURCE)
    pytester.makepyfile(test_suite="def test_ok():\n    assert True\n")
    result = pytester.runpytest_subprocess()
    assert result.ret == 0
    # The copied conftest's default report folder is <suite>/reports, beside it.
    assert not (pytester.path / "reports").exists()


#######################################################################################
### The report on a failing run ###
#
# Each of these stages one way a run can fail that a naive tally of test results
# would miss, and asserts the report says FAIL because pytest's exit status did.


@code("TST0003")
@negative
def test_cleanup_failure_is_recorded_as_fail(pytester, monkeypatch):
    """A test whose own checks pass but whose clean-up step throws is a failed
    run to pytest (exit 1). The report says FAIL, and that test's row says error
    with 'clean-up failed', never passed."""
    result, out = run_suite(
        pytester,
        monkeypatch,
        '''
        import pytest

        @pytest.fixture
        def cleanup_breaks():
            yield
            raise RuntimeError("clean-up broke")

        def test_checks_pass_but_cleanup_fails(cleanup_breaks):
            """Passes, then its clean-up fails."""
            assert True
        ''',
    )
    assert result.ret == 1
    rows = the_report(out)
    assert {r["run_verdict"] for r in rows} == {"FAIL"}
    assert {r["pytest_exit_status"] for r in rows} == {"1"}
    row = row_for(rows, "test_checks_pass_but_cleanup_fails")
    assert row["check_outcome"] == "error"
    assert row["outcome_reason"] == "clean-up failed"
    assert "passed" not in {r["check_outcome"] for r in rows}


@code("TST0004")
@negative
def test_failing_assertion_is_recorded_as_fail(pytester, monkeypatch):
    """A test whose checks fail gives a FAIL report with that row marked failed and
    the assertion message as its reason."""
    result, out = run_suite(
        pytester,
        monkeypatch,
        '''
        def test_wrong():
            """Claims two and two make five."""
            assert 2 + 2 == 5
        ''',
    )
    assert result.ret == 1
    rows = the_report(out)
    assert {r["run_verdict"] for r in rows} == {"FAIL"}
    row = row_for(rows, "test_wrong")
    assert row["proves"] == "Claims two and two make five."
    assert row["check_outcome"] == "failed"
    assert row["outcome_reason"].startswith("assert")


@code("TST0005")
@negative
def test_setup_failure_is_recorded_as_error(pytester, monkeypatch):
    """A test whose set-up step throws never runs; the report says FAIL and the
    row says error."""
    result, out = run_suite(
        pytester,
        monkeypatch,
        '''
        import pytest

        @pytest.fixture
        def setup_breaks():
            raise RuntimeError("set-up broke")

        def test_never_runs(setup_breaks):
            """Cannot start."""
        ''',
    )
    assert result.ret == 1
    rows = the_report(out)
    assert {r["run_verdict"] for r in rows} == {"FAIL"}
    assert row_for(rows, "test_never_runs")["check_outcome"] == "error"


@code("TST0006")
@negative
def test_file_that_will_not_load_still_gets_a_fail_report(pytester, monkeypatch):
    """When a test file cannot even be loaded (a syntax error), no test runs and
    pytest exits 2. A report is still written, says FAIL, and holds one row saying
    that no check ran, so a broken run cannot pass unnoticed by leaving no report
    behind."""
    result, out = run_suite(pytester, monkeypatch, "def test_broken(:\n    pass\n")
    assert result.ret == 2
    rows = the_report(out)
    assert len(rows) == 1
    assert rows[0]["run_verdict"] == "FAIL"
    assert rows[0]["exit_meaning"] == "the run was interrupted"
    assert rows[0]["check_outcome"] == "none"
    assert rows[0]["outcome_reason"].startswith("no check ran")
    assert next(out.glob("*.csv")).name.startswith("run_")
