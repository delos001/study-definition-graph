"""
Script:      test_validation_report.py
Description: Checks for the validation-record writer in tests/conftest.py. A
             record is the proof that a component was validated, so the writer
             itself has to be proven: above all, that it can never say PASS
             when pytest said the run failed.

             Each check builds a tiny throwaway test suite in a temporary
             folder (using pytest's own "pytester" helper), gives it a copy of
             tests/conftest.py, runs pytest on it as a separate process with
             --validation-report pointed at a temporary folder, and reads the
             record that comes out. Nothing is written under tests/validation/.

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

import textwrap
from pathlib import Path

import pytest

CONFTEST_SOURCE = (Path(__file__).resolve().parent / "conftest.py").read_text(encoding="utf-8")

positive = pytest.mark.positive
negative = pytest.mark.negative


#######################################################################################
### Helpers ###


def run_suite(pytester, test_source: str, *extra_args: str):
    """Takes the source of one throwaway test file and any extra pytest
    arguments, runs pytest on it in a separate process with the real conftest.py
    beside it, and produces (pytest's result, the folder records were written to)."""
    pytester.makeconftest(CONFTEST_SOURCE)
    pytester.makepyfile(test_suite=textwrap.dedent(test_source))
    out = pytester.path / "records"
    result = pytester.runpytest_subprocess(
        "--validation-report", "--validation-report-dir", str(out), *extra_args
    )
    return result, out


def the_record(folder: Path) -> str:
    """Takes the records folder and produces the text of the one record in it,
    failing if there is not exactly one."""
    records = list(folder.glob("*.md"))
    assert len(records) == 1, [r.name for r in records]
    return records[0].read_text(encoding="utf-8")


#######################################################################################
### The record on a clean run ###


@positive
def test_passing_run_is_recorded_as_pass(pytester):
    """A suite whose tests all pass gets a record saying PASS with pytest exit
    status 0, one row per test showing its kind and what it proves, and a
    skipped test shown as skipped with its reason."""
    result, out = run_suite(
        pytester,
        '''
        import pytest

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
    record = the_record(out)
    assert "**PASS**: pytest exit status 0 (all tests passed)" in record
    assert "1 passed, 0 failed, 0 error, 1 skipped" in record
    assert "| `test_adds` | positive | Two and two make four. | passed |" in record
    assert "| `test_left_out` | unmarked | Never runs. | skipped (not today) |" in record


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
    record = the_record(out)
    assert "**FAIL**: pytest exit status 1" in record
    assert "| `test_checks_pass_but_cleanup_fails` | unmarked | Passes, then its clean-up fails. | error (clean-up failed) |" in record
    assert "| passed |" not in record


@negative
def test_failing_assertion_is_recorded_as_fail(pytester):
    """A test whose checks fail gives a FAIL record with that row marked failed."""
    result, out = run_suite(
        pytester,
        '''
        def test_wrong():
            """Claims two and two make five."""
            assert 2 + 2 == 5
        ''',
    )
    assert result.ret == 1
    record = the_record(out)
    assert "**FAIL**: pytest exit status 1" in record
    assert "| `test_wrong` | unmarked | Claims two and two make five. | failed |" in record


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
    record = the_record(out)
    assert "**FAIL**: pytest exit status 1" in record
    assert "| `test_never_runs` | unmarked | Cannot start. | error |" in record


@negative
def test_file_that_will_not_load_still_gets_a_fail_record(pytester):
    """When a test file cannot even be loaded (a syntax error), no test runs and
    pytest exits 2. A record is still written, says FAIL, and says that no test
    outcomes were recorded, so a broken run cannot pass unnoticed by leaving no
    record behind."""
    result, out = run_suite(pytester, "def test_broken(:\n    pass\n")
    assert result.ret == 2
    record = the_record(out)
    assert "**FAIL**: pytest exit status 2 (the run was interrupted)" in record
    assert "No test outcomes were recorded" in record
    assert next(out.glob("*.md")).name.startswith("run_")
