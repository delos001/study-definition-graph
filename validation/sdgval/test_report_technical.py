"""
Script:      test_report_technical.py
Description: Checks for src/sdgval/report.py, the plugin that writes a validation
             report. A report is the proof that the code was validated, so the
             writer itself has to be proven: above all, that it can never say
             PASS when pytest said the run failed.

             Each check stages a tiny throwaway suite in a temporary folder with
             the staged_suite fixture in validation/conftest.py, runs pytest on it
             as a separate process, with --validation-report pointed at a
             temporary folder, and reads the CSV report that comes out. Nothing
             is written under validation/reports/.

Inputs:      Nothing real. Each staged suite is written to pytest's own temporary
             folder.

Outputs:     Writes nothing to disk outside pytest's temporary folder.

Usage:       pytest validation/sdgval/test_report_technical.py
                 run these checks
             pytest validation/sdgval/test_report_technical.py -v
                 one line per check with its result

Exit codes:  None of its own. It runs inside pytest.

Date:        2026-09-04
Owner:       Jason Delosh
"""

from __future__ import annotations

import csv
import json
import re
import subprocess
import sys

import pytest

from sdgval.labels import category, code, negative, objective, positive
from sdgval.select_checks import SELECTION_OPTIONS

#######################################################################################
### The report on a clean run ###


PASSING_SUITE = '''
    import pytest

    @pytest.mark.code("XYZ0001")
    @pytest.mark.category("repository")
    @pytest.mark.objective("correctness")
    @pytest.mark.positive
    def test_adds():
        """Two and two
        make four.

        A second paragraph the report leaves out.
        """
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
def passing(staged_suite):
    """Run a suite whose one live check passes and whose other check is skipped, and
    hand back pytest's result and the report's rows."""
    result, out = staged_suite.run(PASSING_SUITE)
    return result, staged_suite.report(out)


@code("SA00433")
@category("repository")
@objective("functionality")
@positive
def test_passing_run_is_recorded_as_pass(passing, staged_suite):
    """A suite whose tests all pass gets a run's own file saying PASS, with pytest's
    exit code 0 and its cause."""
    result, _ = passing
    assert result.ret == 0
    run = staged_suite.run_details(staged_suite.technical_dir)
    assert run["run_verdict"] == "PASS"
    assert run["pytest_exit_code"] == "0"
    assert run["pytest_exit_cause"] == "all tests passed"


@code("SA00434")
@category("repository")
@objective("functionality")
@positive
def test_a_passing_check_gets_a_row_with_its_details(passing, staged_suite):
    """A check that passed gets one row carrying its id, its category, its objective,
    its staged case, its expected result and the outcome passed. The expected result
    is the first paragraph of the check's docstring alone, written as one line.

    The staged check's first paragraph runs over two lines and a second paragraph
    follows it, so a report that wrote the first line alone, or the whole docstring,
    would fail the check."""
    _, rows = passing
    adds = staged_suite.row(rows, "test_adds")
    assert adds["id"] == "XYZ0001"
    assert adds["category"] == "repository"
    assert adds["objective"] == "correctness"
    assert adds["staged_case"] == "positive"
    assert adds["expected_result"] == "Two and two make four."
    assert adds["outcome"] == "passed"


@code("SA00560")
@category("repository")
@objective("functionality")
@positive
def test_a_row_carries_the_version_the_inventory_records(staged_suite):
    """A check's row carries the version that validation/validation_inventory.csv
    records for the check's id."""
    staged_suite.validation.mkdir(exist_ok=True)
    (staged_suite.validation / "validation_inventory.csv").write_text(
        "id,version,status,status_reason\nXYZ0001,3,active,\n", encoding="utf-8"
    )
    _, out = staged_suite.run(PASSING_SUITE)
    assert staged_suite.row(staged_suite.report(out), "test_adds")["version"] == "3"


@code("SA00435")
@category("repository")
@objective("functionality")
@positive
def test_a_skipped_check_is_shown_as_skipped_with_its_reason(passing, staged_suite):
    """A check that was skipped gets a row saying skipped, with the skip's reason and,
    since it carries no markers, an empty category, objective and staged case."""
    _, rows = passing
    left_out = staged_suite.row(rows, "test_left_out")
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
def parametrized(staged_suite):
    """Run a suite with one parametrized check and one plain check, and hand back the
    report's rows."""
    result, out = staged_suite.run(PARAMETRIZED_SUITE)
    assert result.ret == 0
    return staged_suite.report(out)


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
def test_a_check_without_parameters_has_an_empty_parameter(parametrized, staged_suite):
    """A check that is not parametrized gets an empty parameter column."""
    assert staged_suite.row(parametrized, "test_plain")["parameter"] == ""


@code("SA00438")
@category("repository")
@objective("functionality")
@positive
def test_no_flag_writes_nothing(staged_suite, pytester):
    """Without the report option, a run writes no report at all, so development runs
    leave no trace."""
    staged_suite.write("def test_ok():\n    assert True\n")
    result = pytester.runpytest_subprocess()
    assert result.ret == 0
    # The default report folder is validation/reports under the suite's root.
    assert not (staged_suite.validation / "reports").exists()


#######################################################################################
### The report on a failing run ###
#
# Each of these stages one way a run can fail that a naive tally of test results
# would miss, and asserts the report says FAIL because pytest's exit status did.


@code("SA00439")
@category("repository")
@objective("functionality")
@negative
def test_cleanup_failure_is_recorded_as_fail(staged_suite):
    """A test whose own checks pass but whose clean-up breaks makes pytest exit 1. The
    report says FAIL, and that test's row says error with the reason clean-up failed."""
    result, out = staged_suite.run(
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
    rows = staged_suite.report(out)
    run = staged_suite.run_details(out)
    assert run["run_verdict"] == "FAIL"
    assert run["pytest_exit_code"] == "1"
    row = staged_suite.row(rows, "test_checks_pass_but_cleanup_fails")
    assert row["outcome"] == "error"
    assert row["outcome_reason"] == "clean-up failed"
    assert "passed" not in {r["outcome"] for r in rows}


@code("SA00440")
@category("repository")
@objective("functionality")
@negative
def test_a_failure_is_kept_when_the_clean_up_breaks_too(staged_suite):
    """A test that fails its own assertion and then breaks in its clean-up keeps both
    reasons in its row, the assertion message first and the clean-up second, so the
    later step cannot hide the failure."""
    result, out = staged_suite.run(
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
    row = staged_suite.row(
        staged_suite.report(out), "test_fails_and_then_cleanup_fails"
    )
    assert row["outcome"] == "error"
    assert (
        row["outcome_reason"]
        == "AssertionError: the number was not two; clean-up failed"
    )


@code("SA00441")
@category("repository")
@objective("functionality")
@negative
def test_failing_assertion_is_recorded_as_fail(staged_suite):
    """A test whose checks fail gives a FAIL report with that row marked failed and
    the assertion message as its reason."""
    result, out = staged_suite.run(
        '''
        def test_wrong():
            """Claims two and two make five."""
            assert 2 + 2 == 5
        ''',
    )
    assert result.ret == 1
    rows = staged_suite.report(out)
    assert staged_suite.run_details(out)["run_verdict"] == "FAIL"
    row = staged_suite.row(rows, "test_wrong")
    assert row["expected_result"] == "Claims two and two make five."
    assert row["outcome"] == "failed"
    assert row["outcome_reason"].startswith("assert")


@code("SA00442")
@category("repository")
@objective("functionality")
@negative
def test_setup_failure_is_recorded_as_error(staged_suite):
    """A test whose set-up breaks never runs. The report says FAIL and the row says
    error."""
    result, out = staged_suite.run(
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
    rows = staged_suite.report(out)
    assert staged_suite.run_details(out)["run_verdict"] == "FAIL"
    assert staged_suite.row(rows, "test_never_runs")["outcome"] == "error"


@code("SA00443")
@category("repository")
@objective("functionality")
@negative
def test_file_that_will_not_load_still_gets_a_fail_report(staged_suite):
    """When a check file cannot even be loaded, no test runs and pytest exits 2. A report
    is still written, says FAIL and holds one row saying no check ran, so a broken run
    cannot go unnoticed."""
    result, out = staged_suite.run("def test_broken(:\n    pass\n")
    assert result.ret == 2
    rows = staged_suite.report(out)
    run = staged_suite.run_details(out)
    assert len(rows) == 1
    assert run["run_verdict"] == "FAIL"
    assert run["pytest_exit_cause"] == "the run was interrupted"
    assert rows[0]["outcome"] == "none"
    assert rows[0]["outcome_reason"].startswith("no check ran")


#######################################################################################
### The run's own details on every row ###
#
# A report identifies the run it came from: a file name that never overwrites an
# earlier report, what was selected, who ran it, and the exact fixture files.


@code("SA00444")
@category("repository")
@objective("functionality")
@positive
def test_a_second_report_on_the_same_day_and_commit_gets_a_numbered_name(staged_suite):
    """A second report written on the same day at the same commit is given a numbered
    suffix, and the first report is left exactly as it was."""
    _, out = staged_suite.run(PASSING_SUITE)
    (first,) = (p for p in out.glob("*.csv") if not p.stem.endswith("_run"))
    before = first.read_bytes()
    staged_suite.run(PASSING_SUITE)
    assert first.read_bytes() == before
    assert (out / f"{first.stem}-2.csv").is_file()


@code("SA00445")
@category("repository")
@objective("functionality")
@positive
def test_run_id_is_the_report_file_name(staged_suite):
    """Every row's run id is the report's file name, so a second report on the same day
    and commit carries its own numbered id and two runs are never confused."""
    _, out = staged_suite.run(PASSING_SUITE)
    staged_suite.run(PASSING_SUITE)
    for path in (p for p in out.glob("*.csv") if not p.stem.endswith("_run")):
        with path.open(encoding="utf-8", newline="") as fh:
            assert {r["run_id"] for r in csv.DictReader(fh)} == {path.stem}


@code("SA00488")
@category("repository")
@objective("functionality")
@positive
def test_the_runs_own_file_sits_beside_the_report_and_shares_its_run_id(staged_suite):
    """Beside each report is the run's own file, named like the report with run added,
    and its one row carries the same run id as the report's rows, so the two join."""
    _, out = staged_suite.run(PASSING_SUITE)
    (report,) = (p for p in out.glob("*.csv") if not p.stem.endswith("_run"))
    assert (out / f"{report.stem}_run.csv").is_file()
    run_ids = {r["run_id"] for r in staged_suite.report(out)}
    assert run_ids == {staged_suite.run_details(out)["run_id"]}


@code("SA00489")
@category("repository")
@objective("functionality")
@positive
def test_the_runs_own_file_holds_the_run_columns_in_order(staged_suite):
    """The run's own file holds the run's details in this order, with one selection
    column per way of narrowing a run at the end, so a new way adds a column at the
    right."""
    _, out = staged_suite.run(PASSING_SUITE)
    assert list(staged_suite.run_details(out)) == [
        "run_id",
        "run_started",
        "run_by",
        "run_verdict",
        "pytest_exit_code",
        "pytest_exit_cause",
        "checks_collected",
        "checks_reported",
        "commit",
        "python_version",
        "pytest_version",
        "platform",
        "installed_packages",
        "selection_aspect",
        "selection_category",
        "selection_objective",
        "selection_id",
        "selection_group",
        "selection_keyword",
        "selection_marker",
        "selection_paths",
    ]


@code("SA00446")
@category("repository")
@objective("functionality")
@positive
@pytest.mark.parametrize(
    ("extra_args", "expected"),
    [
        ((), {}),
        (("validation/test_suite.py",), {"paths": ["validation/test_suite.py"]}),
        (("-k", "adds"), {"keyword": "adds"}),
        (
            ("validation/test_suite.py::test_adds",),
            {"paths": ["validation/test_suite.py::test_adds"]},
        ),
        (("-m", "positive"), {"marker": "positive"}),
        (("--tb", "short"), {}),
        (("-p", "no:cacheprovider"), {}),
    ],
    ids=[
        "nothing narrows the run",
        "a file path",
        "a -k filter",
        "one check's node id",
        "a -m filter",
        "the --tb option",
        "the -p option",
    ],
)
def test_the_selection_column_records_what_was_selected(
    staged_suite, extra_args, expected
):
    """The selection column records the paths and the keyword and marker filters the
    command line gave, each under its own entry. It is empty when nothing narrowed the
    run, and an option that changes only how results are shown adds nothing."""
    _, out = staged_suite.run(PASSING_SUITE, *extra_args)
    selections = {r["selection"] for r in staged_suite.report(out)}
    assert [json.loads(s) for s in selections] == [expected]


@code("SA00447")
@category("repository")
@objective("functionality")
@positive
def test_the_counts_match_when_every_check_ran(staged_suite):
    """On a whole run, the collected and reported counts in the run's own file are equal
    and both count every check, so a reader can see at a glance that nothing was left
    out."""
    _, out = staged_suite.run(PASSING_SUITE)
    run = staged_suite.run_details(out)
    assert run["checks_collected"] == "2"
    assert run["checks_reported"] == "2"
    assert len(staged_suite.report(out)) == 2


@code("SA00448")
@category("repository")
@objective("functionality")
@positive
def test_a_dropped_check_is_counted_but_not_reported(staged_suite):
    """A check dropped before the run started still counts as collected, so a narrowed
    run shows a gap between the two counts rather than reading as a whole one."""
    _, out = staged_suite.run(
        PASSING_SUITE,
        "--deselect",
        "validation/test_suite.py::test_left_out",
    )
    run = staged_suite.run_details(out)
    assert run["checks_collected"] == "2"
    assert run["checks_reported"] == "1"


@code("SA00449")
@category("repository")
@objective("functionality")
@negative
def test_a_run_that_stops_early_reports_fewer_checks_than_it_collected(staged_suite):
    """A run told to stop at the first failure never reaches the checks after it, and
    its reported count is lower than its collected count, so a run cut short cannot read
    as a whole one."""
    result, out = staged_suite.run(STOPS_EARLY_SUITE, "-x")
    assert result.ret == 1
    run = staged_suite.run_details(out)
    assert run["checks_collected"] == "2"
    assert run["checks_reported"] == "1"
    assert {r["selection"] for r in staged_suite.report(out)} == {"{}"}


@code("SA00579")
@category("repository")
@objective("functionality")
@positive
def test_a_check_that_runs_once_per_value_counts_once(staged_suite):
    """A check that runs once per value counts once in both the collected and the
    reported counts, as it has one row in the inventory, while each of its runs keeps
    its own row in the report."""
    _, out = staged_suite.run(PARAMETRIZED_SUITE)
    run = staged_suite.run_details(out)
    assert (run["checks_collected"], run["checks_reported"]) == ("2", "2")
    assert len(staged_suite.report(out)) == 3


# A value for each selection option that keeps the passing suite's check XYZ0001,
# which is a repository check with the correctness objective of the integrity aspect.
# The group adds names a groups file the check stages.
OPTION_VALUES = {
    "aspect": "integrity",
    "category": "repository",
    "objective": "correctness",
    "id": "XYZ0001",
    "group": "adds",
}


@code("SA00580")
@category("repository")
@objective("functionality")
@positive
def test_every_selection_option_reaches_its_own_column(staged_suite):
    """Every selection option src/sdgval/select_checks.py defines, given on the command
    line, is recorded in its own selection column of the run's own file, holding the
    value given. An option this check has no value for fails it, so a new option
    cannot be left out."""
    staged_suite.validation.mkdir(exist_ok=True)
    (staged_suite.validation / "validation_groups.yml").write_text(
        "adds:\n  ids: [XYZ0001]\n", encoding="utf-8"
    )
    args = [
        argument
        for option in SELECTION_OPTIONS
        for argument in (f"--{option.name}", OPTION_VALUES[option.name])
    ]
    _, out = staged_suite.run(PASSING_SUITE, *args)
    run = staged_suite.run_details(out)
    recorded = {
        option.name: json.loads(run.get(f"selection_{option.name}") or "null")
        for option in SELECTION_OPTIONS
    }
    assert recorded == {
        option.name: [OPTION_VALUES[option.name]] for option in SELECTION_OPTIONS
    }


# Two technical checks and one integrity check, for a run held to the technical
# aspect by its command.
TECHNICAL_AND_INTEGRITY_SUITE = '''
    import pytest

    @pytest.mark.code("XYZ0401")
    @pytest.mark.objective("functionality")
    def test_runs():
        """A technical check."""

    @pytest.mark.code("XYZ0402")
    @pytest.mark.objective("correctness")
    def test_holds():
        """An integrity check."""

    @pytest.mark.code("XYZ0403")
    @pytest.mark.objective("functionality")
    def test_also_runs():
        """A second technical check."""
    '''


@code("SA00497")
@category("repository")
@objective("functionality")
@positive
def test_other_aspects_are_not_counted_as_collected(staged_suite, pytester):
    """On a whole run of an aspect's command, the collected and reported counts are
    equal, because the checks of other aspects the command drops were never part of what
    it set out to cover."""
    staged_suite.commit(TECHNICAL_AND_INTEGRITY_SUITE, aspect_conftest=False)
    result = pytester.run(
        sys.executable,
        "-m",
        "sdgval.validate_technical",
        "--validation-report",
        "--validation-report-dir",
        str(staged_suite.report_dir),
    )
    assert result.ret == 0
    run = staged_suite.run_details(staged_suite.technical_dir)
    assert run["checks_collected"] == "2"
    assert run["checks_reported"] == "2"


@code("SA00450")
@category("repository")
@objective("functionality")
@positive
def test_run_by_carries_the_git_user_name(staged_suite, monkeypatch):
    """The run's own file names the git user who ran it, so a report says who ran it."""
    # git reads these three variables as one more configuration entry, which
    # stages a user name without touching this machine's git settings.
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "user.name")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "Staged Tester")
    _, out = staged_suite.run(PASSING_SUITE)
    assert staged_suite.run_details(out)["run_by"] == "Staged Tester"


@code("SA00451")
@category("repository")
@objective("functionality")
@positive
def test_target_file_names_the_mirrored_code_file_and_marks_a_missing_one(
    passing, staged_suite
):
    """The target columns name the code file the check file mirrors, by the same rule
    the inventory uses. When that file is not there its name is marked, so the gap
    shows."""
    _, rows = passing
    row = staged_suite.row(rows, "test_adds")
    assert row["target_folder_path"] == "validation"
    assert row["target_file_name"] == "suite.py (not found at run time)"


#######################################################################################
### Which version of each file a check ran ###
#
# A staged suite is committed as a git repository with the script it covers and one
# fixture, so every file has a last change for the report to record. Two checks name
# the fixture and one does not.

FIXTURE_SUITE = '''
    import pytest

    @pytest.mark.objective("functionality")
    @pytest.mark.needs_fixture("sample.txt")
    def test_reads_sample():
        """Reads the sample fixture."""

    @pytest.mark.objective("functionality")
    @pytest.mark.needs_fixture("sample.txt")
    def test_reads_sample_again():
        """Reads the sample fixture too."""

    @pytest.mark.objective("functionality")
    def test_reads_nothing():
        """Reads no fixture."""
    '''

# A date as git writes it with --format=%cs.
DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")


@pytest.fixture
def committed(staged_suite):
    """Commit a suite with its covered script and one fixture, run it with a report,
    and hand back the commit's short id and the report's rows."""
    (staged_suite.validation / "fixtures").mkdir(parents=True)
    (staged_suite.validation / "fixtures" / "sample.txt").write_text(
        "fixture\n", encoding="utf-8"
    )
    (staged_suite.validation / "suite.py").write_text("", encoding="utf-8")
    commit = staged_suite.commit(FIXTURE_SUITE)
    result, out = staged_suite.run(FIXTURE_SUITE)
    assert result.ret == 0
    return commit, staged_suite.report(out)


@code("SA00491")
@category("repository")
@objective("functionality")
@positive
def test_the_script_under_test_is_recorded_by_its_last_change(committed, staged_suite):
    """Each row holds the date and id of the last change in git to the script the check
    covers, so a report says which version of the script ran."""
    commit, rows = committed
    row = staged_suite.row(rows, "test_reads_sample")
    assert row["target_change_id"] == commit
    assert DATE.fullmatch(row["target_last_changed"])


@code("SA00492")
@category("repository")
@objective("functionality")
@positive
def test_the_test_file_is_recorded_by_its_last_change(committed, staged_suite):
    """Each row holds the date and id of the last change in git to the check file the
    check sits in, so a report says which version of the check ran."""
    commit, rows = committed
    row = staged_suite.row(rows, "test_reads_sample")
    assert row["check_file_change_id"] == commit
    assert DATE.fullmatch(row["check_file_last_changed"])


@code("SA00493")
@category("repository")
@objective("functionality")
@positive
def test_a_named_fixture_is_recorded_on_its_checks_row_only(committed, staged_suite):
    """A check that names a fixture has that fixture in its fixtures column, with the
    date and id of its last change. A check that names none leaves the column empty."""
    commit, rows = committed
    (fixture,) = json.loads(staged_suite.row(rows, "test_reads_sample")["fixtures"])
    assert fixture["name"] == "sample.txt"
    assert fixture["change_id"] == commit
    assert DATE.fullmatch(fixture["last_changed"])
    assert staged_suite.row(rows, "test_reads_nothing")["fixtures"] == ""


@code("SA00630")
@category("repository")
@objective("functionality")
@positive
def test_two_checks_naming_one_fixture_both_record_it(committed, staged_suite):
    """Two checks that name the same fixture both record it with the date and id of
    its last change, so a file the report has already looked up is recorded again
    for the next check that names it."""
    commit, rows = committed
    for name in ("test_reads_sample", "test_reads_sample_again"):
        (fixture,) = json.loads(staged_suite.row(rows, name)["fixtures"])
        assert fixture["change_id"] == commit
        assert DATE.fullmatch(fixture["last_changed"])


@code("SA00494")
@category("repository")
@objective("functionality")
@positive
def test_the_runs_own_file_lists_the_installed_packages(staged_suite):
    """The run's own file lists every installed package with its version, so a report
    says which versions the run used."""
    _, out = staged_suite.run(PASSING_SUITE)
    packages = json.loads(staged_suite.run_details(out)["installed_packages"])
    assert packages["pytest"] == pytest.__version__


#######################################################################################
### Two runs in one process ###
#
# A command that runs several aspects in order may start more than one pytest run in
# the same process. Each run's report must hold that run alone.

TWO_TECHNICAL_CHECKS = '''
    import pytest

    @pytest.mark.code("XYZ0301")
    @pytest.mark.objective("functionality")
    def test_first():
        """A technical check."""

    @pytest.mark.code("XYZ0302")
    @pytest.mark.objective("functionality")
    def test_second():
        """A second technical check."""
    '''

# Two runs of the shared code in one process: the first covering both checks and
# writing nothing, the second narrowed to one check and writing its report. The
# second run reports fewer checks than the first ran, so a check the first run ran,
# if carried over, would show in the second run's counts.
TWO_RUNS_IN_ONE_PROCESS = (
    "import sys\n"
    "from sdgval.aspect_run import run_aspect\n"
    "first = run_aspect('technical', [])\n"
    "second = run_aspect('technical', ['--id', 'XYZ0301', '--validation-report', "
    "'--validation-report-dir', sys.argv[1]])\n"
    "sys.exit(first or second)\n"
)


@code("SA00496")
@category("repository")
@objective("functionality")
@positive
def test_a_second_run_in_the_same_process_reports_on_itself_alone(
    staged_suite, pytester
):
    """When two runs happen in one process, the second run's own file counts only
    its own checks, so no check the first run ran is carried into it."""
    staged_suite.commit(TWO_TECHNICAL_CHECKS, aspect_conftest=False)
    result = pytester.run(
        sys.executable, "-c", TWO_RUNS_IN_ONE_PROCESS, str(staged_suite.report_dir)
    )
    assert result.ret == 0
    second = staged_suite.run_details(staged_suite.technical_dir)
    assert second["checks_collected"] == "2"
    assert second["checks_reported"] == "1"


#######################################################################################
### Where a report may come from ###


@code("SA00485")
@category("repository")
@objective("functionality")
@negative
def test_a_report_asked_of_plain_pytest_is_refused_before_any_check_runs(
    staged_suite, pytester
):
    """A report asked of plain pytest, with no aspect's command starting the run, stops
    with exit 4 before any check runs and writes no report. The message says a report
    comes only from an aspect's command.

    The suite is written without the conftest that stands in for the command."""
    staged_suite.write(PASSING_SUITE)
    result = pytester.runpytest_subprocess(
        "--validation-report", "--validation-report-dir", str(staged_suite.report_dir)
    )
    printed = result.stdout.str() + result.stderr.str()
    assert result.ret == 4
    assert "a report comes only from the command for one aspect" in printed
    assert "Run validate_technical --validation-report instead" in printed
    assert "test_adds" not in result.stdout.str()
    assert not staged_suite.report_dir.exists()


@code("SA00499")
@category("repository")
@objective("functionality")
@negative
def test_a_report_run_emptied_by_a_keyword_filter_is_refused(staged_suite):
    """A report run whose keyword filter removes every check stops with exit 4 and
    writes no report. The message says the filter removed every check and to widen or
    drop it."""
    result, out = staged_suite.run(PASSING_SUITE, "-k", "no_check_has_this_name")
    printed = result.stdout.str() + result.stderr.str()
    assert result.ret == 4
    assert "pytest's -k or -m option removed every check" in printed
    assert "Widen or drop -k or -m." in printed
    assert not out.exists()


@code("SA00517")
@category("repository")
@objective("functionality")
@negative
def test_a_report_run_that_collects_no_check_is_refused(staged_suite):
    """A report run given only a check file that holds no check stops with pytest's
    usage error, exit 4, the message says no checks were collected, and no report is
    written."""
    staged_suite.validation.mkdir(exist_ok=True)
    (staged_suite.validation / "test_empty.py").write_text(
        '"""No checks here."""\n', encoding="utf-8"
    )
    result, out = staged_suite.run(PASSING_SUITE, "validation/test_empty.py")
    printed = result.stdout.str() + result.stderr.str()
    assert result.ret == 4
    assert "because no checks were collected" in printed
    assert not out.exists()


@code("SA00673")
@category("repository")
@objective("functionality")
@negative
def test_a_report_run_given_a_missing_file_says_the_file_is_not_found(staged_suite):
    """A report run given a check file that does not exist stops with pytest's usage
    error, exit 4, and pytest's own message names the file as not found, rather than
    saying no checks were collected. No report is written."""
    result, out = staged_suite.run(PASSING_SUITE, "validation/test_typo.py")
    printed = result.stdout.str() + result.stderr.str()
    assert result.ret == 4
    assert "file or directory not found: validation/test_typo.py" in printed
    assert "because no checks were collected" not in printed
    assert not out.exists()


@code("SA00518")
@category("repository")
@objective("functionality")
@positive
def test_a_report_folder_outside_the_repo_is_written(staged_suite):
    """A report asked for in a folder outside the repository is written there, and
    the run goes ahead, because a folder outside the repository cannot hold changes
    to the code being validated."""
    staged_suite.commit(PASSING_SUITE)
    outside = staged_suite.root.parent / f"{staged_suite.root.name}_reports"
    result = staged_suite.pytester.runpytest_subprocess(
        "--validation-report", "--validation-report-dir", str(outside)
    )
    assert result.ret == 0
    assert len(staged_suite.report(outside / "technical")) == 2


@code("SA00631")
@category("repository")
@objective("functionality")
@positive
def test_a_report_is_written_with_pytests_printing_switched_off(staged_suite):
    """With pytest's own printing switched off, the report and the run's own file are
    still written, and the run exits 0 without an error."""
    result, out = staged_suite.run(PASSING_SUITE, "-p", "no:terminal")
    assert result.ret == 0
    assert len(staged_suite.report(out)) == 2
    assert staged_suite.run_details(out)["run_verdict"] == "PASS"


#######################################################################################
### The working folder a report is written on ###
#
# A report names the commit it validated, so the writer refuses to start when the
# working folder has uncommitted changes. These checks make the throwaway suite a
# committed git repository first, then dirty it or not.


@code("SA00458")
@category("repository")
@objective("functionality")
@positive
def test_a_listing_run_writes_no_report(staged_suite):
    """With the collect-only option, the run lists the checks it would run and writes no
    report, because nothing ran."""
    result, out = staged_suite.run(PASSING_SUITE, "--collect-only")
    assert result.ret == 0
    assert "test_adds" in result.stdout.str()
    assert not out.exists()


@code("SA00459")
@category("repository")
@objective("functionality")
@negative
def test_a_report_on_uncommitted_changes_is_refused_before_any_check_runs(staged_suite):
    """A report run on a working folder with an uncommitted change stops with exit 4
    before any check runs and writes no report. The message names the changed file and
    says to commit or stash it."""
    staged_suite.commit(PASSING_SUITE)
    with (staged_suite.root / "notes.txt").open("a", encoding="utf-8") as fh:
        fh.write("an edit that is not committed\n")
    result, out = staged_suite.run(PASSING_SUITE)
    printed = result.stdout.str() + result.stderr.str()
    assert result.ret == 4
    assert "no validation report was written" in printed
    assert "M notes.txt" in printed
    assert "Commit them, or set them aside with git stash" in printed
    assert "test_adds" not in result.stdout.str()
    assert not out.exists()


@code("SA00653")
@category("repository")
@objective("functionality")
@negative
def test_a_report_without_git_is_refused_before_any_check_runs(staged_suite):
    """A report run where git cannot be found stops with exit 4 before any check runs
    and writes no report. The message opens with its sub-code, says git cannot be found
    and says to install it.

    The suite's conftest hides git from the run, the way a machine without git would,
    by making the lookup for it find nothing."""
    staged_suite.commit(PASSING_SUITE)
    (staged_suite.root / "conftest.py").write_text(
        staged_suite.ASPECT_CONFTEST
        + "\n\nimport shutil\n\n_which = shutil.which\n"
        + "shutil.which = lambda name, *args, **kwargs: (\n"
        + '    None if name == "git" else _which(name, *args, **kwargs)\n'
        + ")\n",
        encoding="utf-8",
    )
    result = staged_suite.pytester.runpytest_subprocess(
        "--validation-report", "--validation-report-dir", str(staged_suite.report_dir)
    )
    printed = result.stdout.str() + result.stderr.str()
    assert result.ret == 4
    assert "GIT-NOT-FOUND  No checks were run" in printed
    assert "git cannot be found on the path" in printed
    assert "Install git" in printed
    assert "test_adds" not in result.stdout.str()
    assert not staged_suite.technical_dir.exists()


@code("SA00623")
@category("repository")
@objective("functionality")
@negative
def test_a_report_on_a_new_file_is_refused(staged_suite):
    """A report run on a working folder holding a new file git does not track yet
    stops with exit 4 and writes no report. The message names the new file by its
    full path, even inside a new folder, and says to commit or stash it."""
    staged_suite.commit(PASSING_SUITE)
    drafts = staged_suite.root / "drafts"
    drafts.mkdir()
    (drafts / "new_check.txt").write_text("not yet committed\n", encoding="utf-8")
    result, out = staged_suite.run(PASSING_SUITE)
    printed = result.stdout.str() + result.stderr.str()
    assert result.ret == 4
    assert "?? drafts/new_check.txt" in printed
    assert "Commit them, or set them aside with git stash" in printed
    assert not out.exists()


@code("SA00624")
@category("repository")
@objective("functionality")
@negative
def test_a_report_on_a_staged_change_is_refused(staged_suite):
    """A report run on a working folder whose only change is staged for the next commit
    stops with exit 4 and writes no report. The message names the staged file and says
    to commit or stash it."""
    staged_suite.commit(PASSING_SUITE)
    with (staged_suite.root / "notes.txt").open("a", encoding="utf-8") as fh:
        fh.write("an edit that is staged but not committed\n")
    subprocess.run(
        ["git", "add", "notes.txt"],
        cwd=staged_suite.root,
        check=True,
        capture_output=True,
    )
    result, out = staged_suite.run(PASSING_SUITE)
    printed = result.stdout.str() + result.stderr.str()
    assert result.ret == 4
    assert "M  notes.txt" in printed
    assert "Commit them, or set them aside with git stash" in printed
    assert not out.exists()


@code("SA00498")
@category("repository")
@objective("functionality")
@negative
def test_a_report_git_cannot_answer_for_is_refused_before_any_check_runs(
    staged_suite, pytester, monkeypatch
):
    """A report run in a folder where git does not answer stops with exit 4 before any
    check runs and writes no report. The message says git did not answer and a report
    needs it.

    The suite is written without being committed, so its folder is not a git
    repository, and git is told not to look in the folders above it."""
    staged_suite.write(PASSING_SUITE)
    (staged_suite.root / "conftest.py").write_text(
        staged_suite.ASPECT_CONFTEST, encoding="utf-8"
    )
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(staged_suite.root.parent))
    result = pytester.runpytest_subprocess(
        "--validation-report", "--validation-report-dir", str(staged_suite.report_dir)
    )
    printed = result.stdout.str() + result.stderr.str()
    assert result.ret == 4
    assert "git did not answer" in printed
    assert "so it needs git" in printed
    assert "test_adds" not in result.stdout.str()
    assert not staged_suite.report_dir.exists()


@code("SA00460")
@category("repository")
@objective("functionality")
@positive
def test_a_report_on_a_clean_folder_names_its_commit(staged_suite):
    """A report run on a working folder that matches its commit goes ahead, and the
    run's own file records that commit's short id."""
    commit = staged_suite.commit(PASSING_SUITE)
    result, out = staged_suite.run(PASSING_SUITE)
    assert result.ret == 0
    assert staged_suite.run_details(out)["commit"] == commit


@code("SA00461")
@category("repository")
@objective("functionality")
@positive
def test_an_earlier_report_not_yet_committed_does_not_count_as_a_change(staged_suite):
    """A report already in the reports folder, not yet committed, does not make the
    working folder dirty, so a second report can be written after the first."""
    staged_suite.commit(PASSING_SUITE)
    first, out = staged_suite.run(PASSING_SUITE)
    second, _ = staged_suite.run(PASSING_SUITE)
    assert first.ret == 0
    assert second.ret == 0
    assert len([p for p in out.glob("*.csv") if not p.stem.endswith("_run")]) == 2
