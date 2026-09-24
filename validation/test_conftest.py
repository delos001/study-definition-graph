"""
Script:      test_conftest.py
Description: Checks for validation/conftest.py: the validation-report writer, and
             the gate that skips a check whose pinned files are not downloaded
             or have changed. A report is the proof that the code was
             validated, so the writer itself has to be proven: above all, that
             it can never say PASS when pytest said the run failed.

             Each check builds a tiny throwaway test suite in a temporary
             folder, using pytest's own pytester helper, and gives it a copy of
             validation/conftest.py. It then runs pytest on that suite as a
             separate process, with --validation-report pointed at a temporary
             folder, and reads the CSV report that comes out. Nothing is written under
             validation/reports/.

Inputs:      validation/conftest.py   (read-only; copied into each throwaway suite)

Outputs:     Writes nothing to disk outside pytest's temporary folder.

Usage:       pytest validation/test_conftest.py
                 run these checks
             pytest validation/test_conftest.py -v
                 one line per check with its result

Exit codes:  pytest's own: 0 all passed, 1 some failed

Date:        2026-09-04
Owner:       Jason Delosh
"""

from __future__ import annotations

import csv
import hashlib
import subprocess
import textwrap
from pathlib import Path

import pytest

CONFTEST_SOURCE = (Path(__file__).resolve().parent / "conftest.py").read_text(
    encoding="utf-8"
)
REPO_ROOT = Path(__file__).resolve().parents[1]

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
# One helper runs a throwaway suite with the real validation/conftest.py beside it, and one reads
# the report back as rows.


def with_repo_root(monkeypatch) -> None:
    """Put the repo root on the import path of the throwaway suite's process.

    The copied conftest imports the selection plugin, validation/select_checks.py,
    by its dotted name. The real run gets the repo root from pyproject.toml, which
    the throwaway suite does not read. The inventory generator it also imports is
    in the installed sdgval package, so it needs no path.

    Args:
        monkeypatch: pytest's patcher, which puts the variable back when the check ends.
    """
    monkeypatch.setenv("PYTHONPATH", str(REPO_ROOT))


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
    with_repo_root(monkeypatch)
    pytester.makeconftest(CONFTEST_SOURCE)
    pytester.makepyfile(test_suite=textwrap.dedent(test_source))
    out = pytester.path / "reports_out"
    # The real run loads the selection plugin from pyproject.toml, which the
    # throwaway suite does not read, so it is named here.
    result = pytester.runpytest_subprocess(
        "-p",
        "validation.select_checks",
        "--validation-report",
        "--validation-report-dir",
        str(out),
        *extra_args,
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
    matches = [r for r in rows if r["name"] == check_name]
    assert len(matches) == 1, [r["name"] for r in rows]
    return matches[0]


#######################################################################################
### The report on a clean run ###


PASSING_SUITE = '''
    import pytest

    @pytest.mark.code("XYZ0001")
    @pytest.mark.category("repository")
    @pytest.mark.objective("correctness")
    @pytest.mark.positive
    def test_adds():
        """Two and two make four."""
        assert 2 + 2 == 4

    @pytest.mark.skipif(True, reason="not today")
    def test_left_out():
        """Never runs."""
    '''

# A suite whose first check fails, so a run given -x stops before the second one.
STOPS_EARLY_SUITE = '''
    import pytest

    @pytest.mark.code("XYZ0021")
    @pytest.mark.category("repository")
    @pytest.mark.objective("correctness")
    @pytest.mark.positive
    def test_breaks():
        """Fails on purpose."""
        assert False, "broken on purpose"

    @pytest.mark.code("XYZ0022")
    @pytest.mark.category("repository")
    @pytest.mark.objective("correctness")
    @pytest.mark.positive
    def test_never_reached():
        """Would pass if the run got as far as it."""
    '''


@pytest.fixture
def passing(pytester, monkeypatch):
    """Run a suite whose one live check passes and whose other check is skipped, and
    hand back pytest's result and the report's rows."""
    result, out = run_suite(pytester, monkeypatch, PASSING_SUITE)
    return result, the_report(out)


@code("SA00433")
@category("repository")
@objective("functionality")
@positive
def test_passing_run_is_recorded_as_pass(passing):
    """A suite whose tests all pass gets a report saying PASS, with pytest's exit
    status 0 and its meaning on every row."""
    result, rows = passing
    assert result.ret == 0
    assert {r["run_verdict"] for r in rows} == {"PASS"}
    assert {r["pytest_exit_status"] for r in rows} == {"0"}
    assert {r["exit_meaning"] for r in rows} == {"all tests passed"}


@code("SA00434")
@category("repository")
@objective("functionality")
@positive
def test_a_passing_check_gets_a_row_with_its_details(passing):
    """A check that passed gets one row carrying its id, its category, its objective,
    its staged case, its expected result and the outcome passed."""
    _, rows = passing
    adds = row_for(rows, "test_adds")
    assert adds["id"] == "XYZ0001"
    assert adds["category"] == "repository"
    assert adds["objective"] == "correctness"
    assert adds["staged_case"] == "positive"
    assert adds["expected_result"] == "Two and two make four."
    assert adds["outcome"] == "passed"


@code("SA00435")
@category("repository")
@objective("functionality")
@positive
def test_a_skipped_check_is_shown_as_skipped_with_its_reason(passing):
    """A check that was skipped gets a row saying skipped, with the skip's reason and,
    since it carries no markers, an empty category, objective and staged case."""
    _, rows = passing
    left_out = row_for(rows, "test_left_out")
    assert left_out["category"] == ""
    assert left_out["objective"] == ""
    assert left_out["staged_case"] == ""
    assert left_out["outcome"] == "skipped"
    assert left_out["outcome_reason"] == "not today"


# One suite with a parametrized check, which pytest runs once per value.
PARAMETRIZED_SUITE = '''
    import pytest

    @pytest.mark.code("XYZ0002")
    @pytest.mark.category("repository")
    @pytest.mark.objective("correctness")
    @pytest.mark.positive
    @pytest.mark.parametrize("value", ["first", "second"])
    def test_each_value(value):
        """Each value is accepted."""
        assert value

    @pytest.mark.code("XYZ0003")
    @pytest.mark.category("repository")
    @pytest.mark.objective("correctness")
    @pytest.mark.positive
    def test_plain():
        """A check with no parameter."""
    '''


@pytest.fixture
def parametrized(pytester, monkeypatch):
    """Run a suite with one parametrized check and one plain check, and hand back the
    report's rows."""
    result, out = run_suite(pytester, monkeypatch, PARAMETRIZED_SUITE)
    assert result.ret == 0
    return the_report(out)


@code("SA00436")
@category("repository")
@objective("functionality")
@positive
def test_a_parametrized_check_gets_one_row_per_value_with_the_value_in_its_own_column(
    parametrized,
):
    """A parametrized check gets one row per value, each carrying the function name
    alone in name, the same as the inventory's, and pytest's id for the value in
    parameter."""
    rows = [r for r in parametrized if r["id"] == "XYZ0002"]
    assert [r["name"] for r in rows] == ["test_each_value", "test_each_value"]
    assert [r["parameter"] for r in rows] == ["first", "second"]


@code("SA00437")
@category("repository")
@objective("functionality")
@positive
def test_a_check_without_parameters_has_an_empty_parameter(parametrized):
    """A check that is not parametrized gets an empty parameter column."""
    assert row_for(parametrized, "test_plain")["parameter"] == ""


@code("SA00438")
@category("repository")
@objective("functionality")
@positive
def test_no_flag_writes_nothing(pytester, monkeypatch):
    """Without --validation-report, a run writes no report at all, so development
    runs leave no trace."""
    with_repo_root(monkeypatch)
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


@code("SA00439")
@category("repository")
@objective("functionality")
@negative
def test_cleanup_failure_is_recorded_as_fail(pytester, monkeypatch):
    """A test whose own checks pass but whose clean-up step raises an error is a failed
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
    assert row["outcome"] == "error"
    assert row["outcome_reason"] == "clean-up failed"
    assert "passed" not in {r["outcome"] for r in rows}


@code("SA00440")
@category("repository")
@objective("functionality")
@negative
def test_a_failure_is_kept_when_the_clean_up_breaks_too(pytester, monkeypatch):
    """A test that fails its own assertion and then breaks in its clean-up keeps both
    reasons in its row, the assertion message first and the clean-up second, so the
    later step cannot hide the failure."""
    result, out = run_suite(
        pytester,
        monkeypatch,
        '''
        import pytest

        @pytest.fixture
        def cleanup_breaks():
            yield
            raise RuntimeError("clean-up broke")

        def test_fails_and_then_cleanup_fails(cleanup_breaks):
            """Fails, then its clean-up fails."""
            assert 1 == 2, "the number was not two"
        ''',
    )
    assert result.ret == 1
    row = row_for(the_report(out), "test_fails_and_then_cleanup_fails")
    assert row["outcome"] == "error"
    assert (
        row["outcome_reason"]
        == "AssertionError: the number was not two; clean-up failed"
    )


@code("SA00441")
@category("repository")
@objective("functionality")
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
    assert row["expected_result"] == "Claims two and two make five."
    assert row["outcome"] == "failed"
    assert row["outcome_reason"].startswith("assert")


@code("SA00442")
@category("repository")
@objective("functionality")
@negative
def test_setup_failure_is_recorded_as_error(pytester, monkeypatch):
    """A test whose set-up step raises an error never runs; the report says FAIL and the
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
    assert row_for(rows, "test_never_runs")["outcome"] == "error"


@code("SA00443")
@category("repository")
@objective("functionality")
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
    assert rows[0]["outcome"] == "none"
    assert rows[0]["outcome_reason"].startswith("no check ran")
    assert next(out.glob("*.csv")).name.startswith("run_")


#######################################################################################
### The run's own details on every row ###
#
# A report identifies the run it came from: a file name that never overwrites an
# earlier report, what was selected, who ran it, and the exact fixture files.


@code("SA00444")
@category("repository")
@objective("functionality")
@positive
def test_a_second_report_on_the_same_day_and_commit_gets_a_numbered_name(
    pytester, monkeypatch
):
    """A second report written on the same day at the same commit is given a numbered
    suffix, and the first report is left exactly as it was."""
    _, out = run_suite(pytester, monkeypatch, PASSING_SUITE)
    (first,) = out.glob("*.csv")
    before = first.read_bytes()
    run_suite(pytester, monkeypatch, PASSING_SUITE)
    assert first.read_bytes() == before
    assert (out / f"{first.stem}-2.csv").is_file()


@code("SA00445")
@category("repository")
@objective("functionality")
@positive
def test_run_id_is_the_report_file_name(pytester, monkeypatch):
    """Every row's run_id is the report's file name without .csv, so a second report on
    the same day and commit carries the numbered id its file has and two runs are
    never confused."""
    _, out = run_suite(pytester, monkeypatch, PASSING_SUITE)
    run_suite(pytester, monkeypatch, PASSING_SUITE)
    for path in out.glob("*.csv"):
        with path.open(encoding="utf-8", newline="") as fh:
            assert {r["run_id"] for r in csv.DictReader(fh)} == {path.stem}


@code("SA00446")
@category("repository")
@objective("functionality")
@positive
@pytest.mark.parametrize(
    ("extra_args", "expected"),
    [
        ((), "all"),
        (("test_suite.py",), "test_suite.py"),
        (("-k", "adds"), "-k adds"),
        (("test_suite.py::test_adds",), "test_suite.py::test_adds"),
        (("-m", "positive"), "-m positive"),
        (("--tb", "short"), "all"),
        (("-p", "no:cacheprovider"), "all"),
    ],
)
def test_the_selection_column_records_what_was_selected(
    pytester, monkeypatch, extra_args, expected
):
    """The selection column records the paths and the -k or -m filters the command
    line gave, or all when nothing narrowed the run. An option that changes how the
    run is reported rather than which checks it runs, such as --tb, leaves it at
    all."""
    _, out = run_suite(pytester, monkeypatch, PASSING_SUITE, *extra_args)
    assert {r["selection"] for r in the_report(out)} == {expected}


@code("SA00447")
@category("repository")
@objective("functionality")
@positive
def test_the_counts_match_when_every_check_ran(pytester, monkeypatch):
    """On a whole run, checks_collected and checks_reported are equal and both count
    every check, so a reader can see at a glance that nothing was left out."""
    _, out = run_suite(pytester, monkeypatch, PASSING_SUITE)
    rows = the_report(out)
    assert {r["checks_collected"] for r in rows} == {"2"}
    assert {r["checks_reported"] for r in rows} == {"2"}
    assert len(rows) == 2


@code("SA00448")
@category("repository")
@objective("functionality")
@positive
def test_a_dropped_check_is_counted_but_not_reported(pytester, monkeypatch):
    """A check dropped from the run before it started still counts in
    checks_collected, so a narrowed run shows a gap between the two counts rather
    than reading as a whole one."""
    _, out = run_suite(
        pytester,
        monkeypatch,
        PASSING_SUITE,
        "--deselect",
        "test_suite.py::test_left_out",
    )
    rows = the_report(out)
    assert {r["checks_collected"] for r in rows} == {"2"}
    assert {r["checks_reported"] for r in rows} == {"1"}


@code("SA00449")
@category("repository")
@objective("functionality")
@negative
def test_a_run_that_stops_early_reports_fewer_checks_than_it_collected(
    pytester, monkeypatch
):
    """A run told to stop at the first failure never reaches the checks after it, and
    checks_reported is lower than checks_collected, so a run cut short cannot read as
    one that covered the whole suite."""
    result, out = run_suite(pytester, monkeypatch, STOPS_EARLY_SUITE, "-x")
    assert result.ret == 1
    rows = the_report(out)
    assert {r["checks_collected"] for r in rows} == {"2"}
    assert {r["checks_reported"] for r in rows} == {"1"}
    assert {r["selection"] for r in rows} == {"all"}


@code("SA00450")
@category("repository")
@objective("functionality")
@positive
def test_run_by_carries_the_git_user_name(pytester, monkeypatch):
    """The run_by column carries the user name git is configured with, so a report
    says who ran it."""
    # git reads these three variables as one more configuration entry, which
    # stages a user name without touching this machine's git settings.
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "user.name")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "Staged Tester")
    _, out = run_suite(pytester, monkeypatch, PASSING_SUITE)
    assert {r["run_by"] for r in the_report(out)} == {"Staged Tester"}


@code("SA00451")
@category("repository")
@objective("functionality")
@positive
def test_target_file_names_the_mirrored_code_file_and_marks_a_missing_one(passing):
    """The target_folder_path and target_file_name columns name the code file the
    check file mirrors, by the same rule the inventory uses, and the file name is
    marked when that file is not there, so a check file that mirrors nothing shows as
    a gap rather than as a target."""
    _, rows = passing
    row = row_for(rows, "test_adds")
    assert row["target_folder_path"] == "validation"
    assert row["target_file_name"] == "suite.py (not found at run time)"


@code("SA00452")
@category("repository")
@objective("functionality")
@positive
def test_check_file_sha256_is_the_hash_of_the_check_file(passing, pytester):
    """The check_file_sha256 column is the sha256 of the check file's bytes as they
    were when the run started, so a report names the exact test code it ran."""
    _, rows = passing
    row = row_for(rows, "test_adds")
    expected = hashlib.sha256(
        (pytester.path / "test_suite.py").read_bytes()
    ).hexdigest()
    assert row["check_file_sha256"] == expected


@code("SA00453")
@category("repository")
@objective("functionality")
@positive
def test_fixture_sha256s_names_each_fixture_file_with_its_hash(pytester, monkeypatch):
    """The fixture_sha256s column names each file in the fixtures folder beside
    validation/conftest.py with its sha256, so a report says the exact bytes the checks ran on."""
    content = b"fixture bytes\n"
    fixtures = pytester.path / "fixtures"
    fixtures.mkdir()
    (fixtures / "sample.txt").write_bytes(content)
    expected = f"validation/fixtures/sample.txt={hashlib.sha256(content).hexdigest()}"
    _, out = run_suite(pytester, monkeypatch, PASSING_SUITE)
    assert all(expected in r["fixture_sha256s"] for r in the_report(out))


#######################################################################################
### The pinned-file gate ###
#
# A throwaway suite stages a small repo with one pinned file that matches its entry,
# one that has changed, one that was never downloaded, and a pattern no manifest
# records. Each of its checks names one of them with @needs_pinned, and the report
# shows what the gate did with each.


GATED_SUITE = '''
    import hashlib
    import json
    from pathlib import Path

    import pytest

    from sdg.sources import read_manifests

    # The small repo is staged beside this file, and the manifest reader is pointed at
    # it when the file is collected. That is before any check is set up, which is
    # when the pinned-file gate reads the manifests.
    ROOT = Path(__file__).parent / "staged_repo"
    for folder in ("manifests/study_documents", "inputs/set"):
        (ROOT / folder).mkdir(parents=True, exist_ok=True)
    (ROOT / "pyproject.toml").write_text('name = "sdg"', encoding="utf-8")


    def entry(name, recorded):
        return {
            "name": name,
            "url": f"https://example.invalid/{name}",
            "local": f"inputs/set/{name}",
            "bytes": len(recorded),
            "sha256": hashlib.sha256(recorded).hexdigest(),
        }


    (ROOT / "inputs/set/good.txt").write_bytes(b"good")
    (ROOT / "inputs/set/changed.txt").write_bytes(b"edited")
    recorded = [
        entry("good.txt", b"good"),
        entry("changed.txt", b"original"),
        entry("missing.txt", b"never downloaded"),
    ]
    (ROOT / "manifests/set.json").write_text(
        json.dumps({"files": recorded}), encoding="utf-8"
    )
    read_manifests.REPO_ROOT = ROOT
    read_manifests.MANIFEST_DIR = ROOT / "manifests"
    read_manifests.STUDY_MANIFEST_DIR = ROOT / "manifests" / "study_documents"


    @pytest.mark.needs_pinned("inputs/set/good.txt")
    def test_reads_good():
        """Reads a file that matches its entry."""


    @pytest.mark.needs_pinned("inputs/set/changed.txt")
    def test_reads_changed():
        """Reads a file changed since it was pinned."""


    @pytest.mark.needs_pinned("inputs/set/missing.txt")
    def test_reads_missing():
        """Reads a file never downloaded."""
    '''


@pytest.fixture
def gated(pytester, monkeypatch):
    """Run the suite with the staged pinned files and hand back pytest's result and
    the report's rows."""
    result, out = run_suite(pytester, monkeypatch, GATED_SUITE)
    return result, the_report(out)


@code("SA00454")
@category("repository")
@objective("functionality")
@positive
def test_a_check_whose_pinned_file_matches_runs(gated):
    """A check whose pinned file is on disk and matches its manifest entry runs, and
    its row says passed."""
    _, rows = gated
    assert row_for(rows, "test_reads_good")["outcome"] == "passed"


@code("SA00455")
@category("repository")
@objective("functionality")
@negative
def test_a_check_whose_pinned_file_changed_is_blocked(gated):
    """A check whose pinned file no longer matches its manifest entry is skipped as
    blocked, naming the file, and the run still passes, because only the stability
    check for that file fails for the change."""
    result, rows = gated
    row = row_for(rows, "test_reads_changed")
    assert row["outcome"] == "skipped"
    assert row["outcome_reason"].startswith(
        "blocked: inputs/set/changed.txt does not match its manifest entry"
    )
    assert result.ret == 0


@code("SA00456")
@category("repository")
@objective("functionality")
@negative
def test_a_check_whose_pinned_file_is_not_downloaded_is_skipped(gated):
    """A check whose pinned file is recorded but not on disk is skipped, and the
    reason names the file and says to run acquire_sources."""
    _, rows = gated
    row = row_for(rows, "test_reads_missing")
    assert row["outcome"] == "skipped"
    assert row["outcome_reason"] == (
        "not downloaded: inputs/set/missing.txt; run acquire_sources"
    )


UNMATCHED_SUITE = '''
    import pytest


    @pytest.mark.needs_pinned("inputs/no_such_folder/*.txt")
    def test_reads_unrecorded():
        """Reads files no manifest records."""
    '''


@code("SA00457")
@category("repository")
@objective("functionality")
@negative
def test_a_check_naming_a_file_no_manifest_records_errors(pytester, monkeypatch):
    """A check whose @needs_pinned names files no manifest records is a mistake in the
    check, so its set-up fails: the run fails, the row says error, and the terminal
    names the pattern and says to correct the marker."""
    result, out = run_suite(pytester, monkeypatch, UNMATCHED_SUITE)
    assert result.ret == 1
    row = row_for(the_report(out), "test_reads_unrecorded")
    assert row["outcome"] == "error"
    assert row["outcome_reason"] == "set-up failed"
    result.stdout.fnmatch_lines(
        [
            "*no manifest records a file matching inputs/no_such_folder/*.txt*",
            "*correct the @needs_pinned marker*",
        ]
    )


#######################################################################################
### The working folder a report is written on ###
#
# A report names the commit it validated, so the writer refuses to start when the
# working folder has uncommitted changes. These checks make the throwaway suite a
# committed git repository first, then dirty it or not.


def committed_repo(pytester, monkeypatch, test_source: str) -> str:
    """Stage the throwaway suite and commit it as a git repository.

    pytest's own cache, the files pytester writes for itself and Python's bytecode
    folders are ignored in the repository, so only the suite's own files count as
    changes. A notes file is committed too, for a check that needs a tracked file it
    can change without the run helper writing it back.

    Args:
        pytester: pytest's helper for running a separate suite.
        monkeypatch: pytest's patcher, for the import path of the separate process.
        test_source: The source of the one test file.

    Returns:
        The short hash of the commit.
    """
    with_repo_root(monkeypatch)
    pytester.makeconftest(CONFTEST_SOURCE)
    pytester.makepyfile(test_suite=textwrap.dedent(test_source))
    (pytester.path / ".gitignore").write_text(
        ".pytest_cache/\n__pycache__/\nrunpytest-*\nstdout\nstderr\n",
        encoding="utf-8",
    )
    (pytester.path / "notes.txt").write_text("kept\n", encoding="utf-8")
    identity = ["-c", "user.name=Check", "-c", "user.email=check@example.invalid"]
    for args in (["init", "-q"], ["add", "-A"], ["commit", "-q", "-m", "staged"]):
        subprocess.run(
            ["git", *identity, *args],
            cwd=pytester.path,
            check=True,
            capture_output=True,
        )
    return subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=pytester.path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


@code("SA00458")
@category("repository")
@objective("functionality")
@positive
def test_a_listing_run_writes_no_report(pytester, monkeypatch):
    """With --collect-only, the run lists the checks it would run and writes no
    report, because nothing ran."""
    result, out = run_suite(pytester, monkeypatch, PASSING_SUITE, "--collect-only")
    assert result.ret == 0
    assert "test_adds" in result.stdout.str()
    assert not out.exists()


@code("SA00459")
@category("repository")
@objective("functionality")
@negative
def test_a_report_on_uncommitted_changes_is_refused_before_any_check_runs(
    pytester, monkeypatch
):
    """With --validation-report and a working folder that has an uncommitted change,
    the run stops with pytest's usage error, exit 4, before any check runs, the
    message names the changed file and says to commit or stash, and no report is
    written."""
    committed_repo(pytester, monkeypatch, PASSING_SUITE)
    with (pytester.path / "notes.txt").open("a", encoding="utf-8") as fh:
        fh.write("an edit that is not committed\n")
    result, out = run_suite(pytester, monkeypatch, PASSING_SUITE)
    printed = result.stdout.str() + result.stderr.str()
    assert result.ret == 4
    assert "no validation report was written" in printed
    assert "M notes.txt" in printed
    assert "Commit them, or set them aside with git stash" in printed
    assert "test_adds" not in result.stdout.str()
    assert not out.exists()


@code("SA00460")
@category("repository")
@objective("functionality")
@positive
def test_a_report_on_a_clean_folder_names_its_commit(pytester, monkeypatch):
    """With --validation-report and a working folder that matches its commit, the run
    goes ahead and every row's commit column is that commit's short hash."""
    commit = committed_repo(pytester, monkeypatch, PASSING_SUITE)
    result, out = run_suite(pytester, monkeypatch, PASSING_SUITE)
    assert result.ret == 0
    assert {r["commit"] for r in the_report(out)} == {commit}


@code("SA00461")
@category("repository")
@objective("functionality")
@positive
def test_an_earlier_report_not_yet_committed_does_not_count_as_a_change(
    pytester, monkeypatch
):
    """A report already in the reports folder, not yet committed, does not make the
    working folder dirty, so a second report can be written after the first."""
    committed_repo(pytester, monkeypatch, PASSING_SUITE)
    first, out = run_suite(pytester, monkeypatch, PASSING_SUITE)
    second, _ = run_suite(pytester, monkeypatch, PASSING_SUITE)
    assert first.ret == 0
    assert second.ret == 0
    assert len(list(out.glob("*.csv"))) == 2
