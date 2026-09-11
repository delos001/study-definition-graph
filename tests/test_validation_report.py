"""
Script:      test_validation_report.py
Description: Checks for the validation-record writer in tests/conftest.py. A
             record is the proof that the code was validated, so the writer
             itself has to be proven: above all, that it can never say PASS
             when pytest said the run failed.

             Each check builds a tiny throwaway test suite in a temporary
             folder (using pytest's own "pytester" helper), gives it a copy of
             tests/conftest.py, runs pytest on it as a separate process with
             --validation-report pointed at a temporary folder, and reads the
             CSV record that comes out. Nothing is written under
             tests/validation/.

Inputs:      tests/conftest.py   (read-only; copied into each throwaway suite)

Outputs:     Writes nothing to disk outside pytest's temporary folder.

Usage:       pytest tests/test_validation_report.py
                 run these checks
             pytest tests/test_validation_report.py -v
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

positive = pytest.mark.positive
negative = pytest.mark.negative
# Every check carries a @code line: its short, permanent id in
# tests/validation_inventory.csv, assigned once and never reused.
code = pytest.mark.code


#######################################################################################
### Shared staging ###
#
# One helper runs a throwaway suite with the real conftest beside it, and one reads
# the record back as rows.


def run_suite(pytester, test_source: str, *extra_args: str):
    """Run pytest on one throwaway test file, with the real conftest.py beside it.

    Args:
        pytester: pytest's helper for running a separate suite.
        test_source: The source of the one test file.
        *extra_args: Any further pytest arguments.

    Returns:
        pytest's result and the folder the record was written to.
    """
    pytester.makeconftest(CONFTEST_SOURCE)
    pytester.makepyfile(test_suite=textwrap.dedent(test_source))
    out = pytester.path / "records"
    result = pytester.runpytest_subprocess(
        "--validation-report", "--validation-report-dir", str(out), *extra_args
    )
    return result, out


def the_record(folder: Path) -> list[dict[str, str]]:
    """Read the one record the run wrote.

    Args:
        folder: Where the record was written.

    Returns:
        The record's rows, one per check, each a dict keyed by column name.
    """
    records = list(folder.glob("*.csv"))
    assert len(records) == 1, [r.name for r in records]
    with records[0].open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def row_for(rows: list[dict[str, str]], check_name: str) -> dict[str, str]:
    """Pick the one row for a named check.

    Args:
        rows: The record's rows.
        check_name: The check's function name.

    Returns:
        That check's row.
    """
    matches = [r for r in rows if r["check_name"] == check_name]
    assert len(matches) == 1, [r["check_name"] for r in rows]
    return matches[0]


#######################################################################################
### The record on a clean run ###


@code("TST0001")
@positive
def test_passing_run_is_recorded_as_pass(pytester):
    """A suite whose tests all pass gets a record saying PASS with pytest exit
    status 0, one row per check showing its code, kind and what it proves, and a
    skipped check shown as skipped with its reason."""
    result, out = run_suite(
        pytester,
        '''
        import pytest

        @pytest.mark.code("XYZ0001")
        @pytest.mark.positive
        def test_adds():
            """Two and two make four."""
            assert 2 + 2 == 4

        @pytest.mark.skipif(True, reason="not today")
        def test_left_out():
            """Never runs."""
        ''',
    )
    assert result.ret == 0
    rows = the_record(out)
    assert {r["run_verdict"] for r in rows} == {"PASS"}
    assert {r["pytest_exit_status"] for r in rows} == {"0"}
    assert {r["exit_meaning"] for r in rows} == {"all tests passed"}
    adds = row_for(rows, "test_adds")
    assert adds["check_name_code"] == "XYZ0001"
    assert adds["kind"] == "positive"
    assert adds["proves"] == "Two and two make four."
    assert adds["check_outcome"] == "passed"
    left_out = row_for(rows, "test_left_out")
    assert left_out["kind"] == "unmarked"
    assert left_out["check_outcome"] == "skipped"
    assert left_out["outcome_reason"] == "not today"


@code("TST0002")
@positive
def test_no_flag_writes_nothing(pytester):
    """Without --validation-report, a run writes no record at all, so development
    runs leave no trace."""
    pytester.makeconftest(CONFTEST_SOURCE)
    pytester.makepyfile(test_suite="def test_ok():\n    assert True\n")
    result = pytester.runpytest_subprocess()
    assert result.ret == 0
    # The copied conftest's default records folder is <suite>/validation.
    assert not (pytester.path / "validation").exists()


#######################################################################################
### The record on a failing run ###
#
# Each of these stages one way a run can fail that a naive tally of test results
# would miss, and asserts the record says FAIL because pytest's exit status did.


@code("TST0003")
@negative
def test_cleanup_failure_is_recorded_as_fail(pytester):
    """A test whose own checks pass but whose clean-up step throws is a failed
    run to pytest (exit 1). The record says FAIL, and that test's row says error
    with 'clean-up failed', never passed."""
    result, out = run_suite(
        pytester,
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
    rows = the_record(out)
    assert {r["run_verdict"] for r in rows} == {"FAIL"}
    assert {r["pytest_exit_status"] for r in rows} == {"1"}
    row = row_for(rows, "test_checks_pass_but_cleanup_fails")
    assert row["check_outcome"] == "error"
    assert row["outcome_reason"] == "clean-up failed"
    assert "passed" not in {r["check_outcome"] for r in rows}


@code("TST0004")
@negative
def test_failing_assertion_is_recorded_as_fail(pytester):
    """A test whose checks fail gives a FAIL record with that row marked failed and
    the assertion message as its reason."""
    result, out = run_suite(
        pytester,
        '''
        def test_wrong():
            """Claims two and two make five."""
            assert 2 + 2 == 5
        ''',
    )
    assert result.ret == 1
    rows = the_record(out)
    assert {r["run_verdict"] for r in rows} == {"FAIL"}
    row = row_for(rows, "test_wrong")
    assert row["proves"] == "Claims two and two make five."
    assert row["check_outcome"] == "failed"
    assert row["outcome_reason"].startswith("assert")


@code("TST0005")
@negative
def test_setup_failure_is_recorded_as_error(pytester):
    """A test whose set-up step throws never runs; the record says FAIL and the
    row says error."""
    result, out = run_suite(
        pytester,
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
    rows = the_record(out)
    assert {r["run_verdict"] for r in rows} == {"FAIL"}
    assert row_for(rows, "test_never_runs")["check_outcome"] == "error"


@code("TST0006")
@negative
def test_file_that_will_not_load_still_gets_a_fail_record(pytester):
    """When a test file cannot even be loaded (a syntax error), no test runs and
    pytest exits 2. A record is still written, says FAIL, and holds one row saying
    that no check ran, so a broken run cannot pass unnoticed by leaving no record
    behind."""
    result, out = run_suite(pytester, "def test_broken(:\n    pass\n")
    assert result.ret == 2
    rows = the_record(out)
    assert len(rows) == 1
    assert rows[0]["run_verdict"] == "FAIL"
    assert rows[0]["exit_meaning"] == "the run was interrupted"
    assert rows[0]["check_outcome"] == "none"
    assert rows[0]["outcome_reason"].startswith("no check ran")
    assert next(out.glob("*.csv")).name.startswith("run_")
