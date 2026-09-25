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

Exit codes:  pytest's own: 0 all passed, 1 some failed

Date:        2026-09-04
Owner:       Jason Delosh
"""

from __future__ import annotations

import csv
import hashlib
import json

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
    its staged case, its expected result and the outcome passed."""
    _, rows = passing
    adds = staged_suite.row(rows, "test_adds")
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
    """Without --validation-report, a run writes no report at all, so development
    runs leave no trace."""
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
    """A test whose own checks pass but whose clean-up step raises an error is a failed
    run to pytest (exit 1). The report says FAIL, and that test's row says error
    with 'clean-up failed', never passed."""
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
    """A test whose set-up step raises an error never runs; the report says FAIL and the
    row says error."""
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
    """When a test file cannot even be loaded (a syntax error), no test runs and
    pytest exits 2. A report is still written, says FAIL, and holds one row saying
    that no check ran, so a broken run cannot pass unnoticed by leaving no report
    behind."""
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
    """Every row's run_id is the report's file name without .csv, so a second report on
    the same day and commit carries the numbered id its file has and two runs are
    never confused."""
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
    """Beside each report is the run's own file, named as the report with _run added,
    and its one row carries the same run_id as every row of the report, so the two
    join."""
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
    """The selection column records, as JSON, the paths and the -k or -m filters the
    command line gave, each under its own key, and holds an empty JSON object when
    nothing narrowed the run. An option that changes how the run is reported rather
    than which checks it runs, such as --tb, adds nothing to it."""
    _, out = staged_suite.run(PASSING_SUITE, *extra_args)
    selections = {r["selection"] for r in staged_suite.report(out)}
    assert [json.loads(s) for s in selections] == [expected]


@code("SA00447")
@category("repository")
@objective("functionality")
@positive
def test_the_counts_match_when_every_check_ran(staged_suite):
    """On a whole run, checks_collected and checks_reported in the run's own file are
    equal and both count every check, so a reader can see at a glance that nothing
    was left out."""
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
    """A check dropped from the run before it started still counts in
    checks_collected, so a narrowed run shows a gap between the two counts rather
    than reading as a whole one."""
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
    checks_reported is lower than checks_collected, so a run cut short cannot read as
    one that covered the whole suite."""
    result, out = staged_suite.run(STOPS_EARLY_SUITE, "-x")
    assert result.ret == 1
    run = staged_suite.run_details(out)
    assert run["checks_collected"] == "2"
    assert run["checks_reported"] == "1"
    assert {r["selection"] for r in staged_suite.report(out)} == {"{}"}


@code("SA00450")
@category("repository")
@objective("functionality")
@positive
def test_run_by_carries_the_git_user_name(staged_suite, monkeypatch):
    """The run_by column of the run's own file carries the user name git is
    configured with, so a report says who ran it."""
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
    """The target_folder_path and target_file_name columns name the code file the
    check file mirrors, by the same rule the inventory uses, and the file name is
    marked when that file is not there, so a check file that mirrors nothing shows as
    a gap rather than as a target."""
    _, rows = passing
    row = staged_suite.row(rows, "test_adds")
    assert row["target_folder_path"] == "validation"
    assert row["target_file_name"] == "suite.py (not found at run time)"


@code("SA00452")
@category("repository")
@objective("functionality")
@positive
def test_check_file_sha256_is_the_hash_of_the_check_file(passing, staged_suite):
    """The check_file_sha256 column is the sha256 of the check file's bytes as they
    were when the run started, so a report names the exact test code it ran."""
    _, rows = passing
    row = staged_suite.row(rows, "test_adds")
    expected = hashlib.sha256(staged_suite.test_file.read_bytes()).hexdigest()
    assert row["check_file_sha256"] == expected


@code("SA00453")
@category("repository")
@objective("functionality")
@positive
def test_fixture_sha256s_names_each_fixture_file_with_its_hash(staged_suite):
    """The fixture_sha256s column names each file in validation/fixtures/ with its
    sha256, so a report says the exact bytes the checks ran on."""
    content = b"fixture bytes\n"
    fixtures = staged_suite.validation / "fixtures"
    fixtures.mkdir(parents=True)
    (fixtures / "sample.txt").write_bytes(content)
    expected = f"validation/fixtures/sample.txt={hashlib.sha256(content).hexdigest()}"
    _, out = staged_suite.run(PASSING_SUITE)
    assert all(expected in r["fixture_sha256s"] for r in staged_suite.report(out))


#######################################################################################
### Where a report may come from ###


@code("SA00485")
@category("repository")
@objective("functionality")
@negative
def test_a_report_asked_of_plain_pytest_is_refused_before_any_check_runs(
    staged_suite, pytester
):
    """With --validation-report and no aspect's command starting the run, the run
    stops with pytest's usage error, exit 4, before any check runs, the message says
    a report comes only from an aspect's command and names validate_technical, and
    no report is written.

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
    """With --collect-only, the run lists the checks it would run and writes no
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
    """With --validation-report and a working folder that has an uncommitted change,
    the run stops with pytest's usage error, exit 4, before any check runs, the
    message names the changed file and says to commit or stash, and no report is
    written."""
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


@code("SA00460")
@category("repository")
@objective("functionality")
@positive
def test_a_report_on_a_clean_folder_names_its_commit(staged_suite):
    """With --validation-report and a working folder that matches its commit, the run
    goes ahead and the commit column of the run's own file is that commit's short
    hash."""
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
