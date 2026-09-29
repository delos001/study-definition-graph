"""
Script:      test_validate_technical_technical.py
Description: Checks for src/sdgval/validate_technical.py, the command that runs the
             technical checks and writes the technical report.

             Each check stages a tiny throwaway suite holding technical checks and
             an integrity check, with the staged_suite fixture in
             validation/conftest.py, runs the command on it as a separate process,
             and reads the report that comes out, or the number the command exits
             with. The command runs pytest, which cannot be run a second time
             inside the pytest process running these checks, so a separate process
             is the only way to run it whole.

Inputs:      Nothing real. Each staged suite is written to pytest's own temporary
             folder.

Outputs:     Writes nothing to disk outside pytest's temporary folder.

Usage:       pytest validation/sdgval/test_validate_technical_technical.py
                 run these checks
             pytest validation/sdgval/test_validate_technical_technical.py -v
                 one line per check with its result

Exit codes:  None of its own. It runs inside pytest.

Date:        2026-09-25
Owner:       Jason Delosh
"""

from __future__ import annotations

import json
import sys

import pytest

from sdgval.labels import category, code, negative, objective, positive

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


def run_command(staged_suite, pytester, *args, report=True, suite=MIXED_SUITE):
    """Commit a suite as a git repository and run the command on it in a separate
    process. A report is written only in a git repository.

    Args:
        staged_suite: The throwaway suite to write.
        pytester: pytest's helper for running a separate process.
        *args: The arguments a person would type after the command.
        report: Whether --validation-report is given.
        suite: The source of the suite's one check file, the mixed suite unless a
            check needs another.

    Returns:
        The result of the run and the technical folder inside the report folder,
        where the report is written.
    """
    staged_suite.commit(suite, aspect_conftest=False)
    return run_uncommitted(staged_suite, pytester, *args, report=report)


def run_uncommitted(staged_suite, pytester, *args, report=True):
    """Run the command in a separate process on whatever the suite's folder holds.

    Args:
        staged_suite: The throwaway suite, already written.
        pytester: pytest's helper for running a separate process.
        *args: The arguments a person would type after the command.
        report: Whether --validation-report is given.

    Returns:
        The result of the run and the technical folder inside the report folder,
        where the report is written.
    """
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
    """An option typed after the command, such as the id option, narrows the run the way
    it narrows pytest, so the report holds only the checks it selects."""
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
    """Without the report option, the command runs the technical checks, exits 0 and
    writes no report, so a development run leaves no record."""
    result, out = run_command(staged_suite, pytester, "-v", report=False)
    assert result.ret == 0
    assert "test_runs PASSED" in result.stdout.str()
    assert not out.exists()


@code("SA00484")
@category("repository")
@objective("functionality")
@positive
def test_the_report_is_named_for_its_aspect(staged_suite, pytester):
    """The report's file name starts with technical, and every row's run id is that
    name, so a report copied out of its folder still says which aspect it covers."""
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
    """In the run's own file, each way the run was narrowed has its own selection
    column, and a way that was not used leaves its column empty."""
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
    """A run given the aspect option stops with exit 55 before any check runs and
    writes no report. The message says the command already runs only technical
    checks."""
    result, out = run_command(staged_suite, pytester, "--aspect", "integrity")
    printed = result.stdout.str() + result.stderr.str()
    assert result.ret == 55
    assert (
        "validate_technical already runs only technical checks, so it does not "
        "accept --aspect. Run it without --aspect." in printed
    )
    assert "test_holds" not in result.stdout.str()
    assert not out.exists()


#######################################################################################
### Saying why a selection matches no technical check ###


@code("SA00503")
@category("repository")
@objective("functionality")
@negative
def test_options_matching_only_other_aspects_are_refused_plainly(
    staged_suite, pytester
):
    """Options that match checks, none of them technical, stop the run with exit 56.
    The message gives how many checks the options match together and says none are
    technical."""
    result, out = run_command(staged_suite, pytester, "--id", "XYZ0102")
    printed = result.stdout.str() + result.stderr.str()
    assert result.ret == 56
    assert (
        "No technical checks match the options given. The options match 1 check "
        "together, but none of them are technical. Widen or drop an option." in printed
    )
    assert "--aspect matched" not in printed
    assert not out.exists()


@code("SA00504")
@category("repository")
@objective("functionality")
@negative
def test_an_objective_of_another_aspect_is_named_as_such(staged_suite, pytester):
    """An objective that belongs to another aspect stops the run with exit 56. The
    message names the aspect it belongs to and lists the technical objectives."""
    result, out = run_command(staged_suite, pytester, "--objective", "correctness")
    printed = result.stdout.str() + result.stderr.str()
    assert result.ret == 56
    assert (
        "correctness is an integrity objective, so validate_technical has none of "
        "its checks. The technical objectives are functionality," in printed
    )
    assert not out.exists()


@code("SA00515")
@category("repository")
@objective("functionality")
@negative
def test_options_matching_nothing_at_all_give_each_count(staged_suite, pytester):
    """Options that match no check of any aspect stop the run with exit 56. The
    message gives each option's own count and never names the aspect the command
    added."""
    result, out = run_command(staged_suite, pytester, "--category", "products")
    printed = result.stdout.str() + result.stderr.str()
    assert result.ret == 56
    assert (
        "no check matches every option given: --category matched 0, in combination 0."
        in printed
    )
    assert "--aspect matched" not in printed
    assert not out.exists()


@code("SA00516")
@category("repository")
@objective("functionality")
@negative
def test_several_objectives_of_other_aspects_are_named_together(staged_suite, pytester):
    """Several objectives that all belong to other aspects stop the run with exit 56.
    The message names them together as not technical and lists the technical
    objectives."""
    result, out = run_command(
        staged_suite, pytester, "--objective", "correctness,conformance"
    )
    printed = result.stdout.str() + result.stderr.str()
    assert result.ret == 56
    assert (
        "correctness, conformance are not technical objectives, so validate_technical "
        "has none of their checks. The technical objectives are functionality,"
        in printed
    )
    assert not out.exists()


#######################################################################################
### The number the command exits with for each cause ###
#
# The command ends with the repo's own number from docs/exit_codes.csv rather than
# pytest's. Each check stages one cause and confirms the number. The message for a
# refusal is confirmed where the refusal is made, in the checks of
# src/sdgval/select_checks.py and src/sdgval/report.py.

# A technical check that fails.
FAILING_SUITE = """
    import pytest

    @pytest.mark.code("XYZ0111")
    @pytest.mark.objective("functionality")
    def test_fails():
        \"\"\"A technical check that fails.\"\"\"
        assert False, "on purpose"
    """

# A technical check that stops the run part way, as a person pressing Ctrl+C does.
INTERRUPTING_SUITE = """
    import pytest

    @pytest.mark.code("XYZ0112")
    @pytest.mark.objective("functionality")
    def test_stops_the_run():
        \"\"\"A technical check that stops the run.\"\"\"
        raise KeyboardInterrupt
    """

# A conftest.py whose hook breaks while pytest collects, which pytest reports as its
# own internal error.
BREAKING_CONFTEST = (
    "def pytest_collection_modifyitems(items):\n"
    "    raise RuntimeError('a hook that breaks')\n"
)


def stage_groups(staged_suite, text: str) -> None:
    """Write validation/validation_groups.yml under the suite's root, before it is
    committed.

    Args:
        staged_suite: The throwaway suite, from validation/conftest.py.
        text: The groups file's contents.
    """
    staged_suite.validation.mkdir(exist_ok=True)
    (staged_suite.validation / "validation_groups.yml").write_text(
        text, encoding="utf-8"
    )


@code("SA00564")
@category("repository")
@objective("functionality")
@negative
def test_a_failed_check_exits_52(staged_suite, pytester):
    """A run in which a technical check fails exits 52, the repo's number for one or
    more checks failing, rather than pytest's own 1."""
    result, _ = run_command(staged_suite, pytester, report=False, suite=FAILING_SUITE)
    assert result.ret == 52


@code("SA00565")
@category("repository")
@objective("functionality")
@negative
def test_an_interrupted_run_exits_53(staged_suite, pytester):
    """A run stopped part way, as pressing Ctrl+C stops it, exits 53, the repo's number
    for a run that stopped before every check ran, rather than pytest's own 2."""
    result, _ = run_command(
        staged_suite, pytester, report=False, suite=INTERRUPTING_SUITE
    )
    assert result.ret == 53


@code("SA00566")
@category("repository")
@objective("functionality")
@negative
@pytest.mark.parametrize("report", [False, True], ids=["no report", "a report"])
def test_a_run_that_collects_no_check_exits_54(staged_suite, pytester, report):
    """A run given a check file that holds no check exits 54, the repo's number for no
    check collected, rather than pytest's own 5 or its usage error. The run is
    repeated without a report and with one asked for, because the report writer
    refuses such a run itself."""
    result, _ = run_command(
        staged_suite, pytester, "validation/test_suite.py", report=report, suite=""
    )
    assert result.ret == 54


@code("SA00567")
@category("repository")
@objective("functionality")
@negative
def test_a_report_on_uncommitted_changes_exits_57(staged_suite, pytester):
    """A report run on a working folder with an uncommitted change exits 57, the repo's
    number for that refusal, rather than pytest's own 4."""
    staged_suite.commit(MIXED_SUITE, aspect_conftest=False)
    with (staged_suite.root / "notes.txt").open("a", encoding="utf-8") as fh:
        fh.write("an edit that is not committed\n")
    result, _ = run_uncommitted(staged_suite, pytester)
    assert result.ret == 57


@code("SA00568")
@category("repository")
@objective("functionality")
@negative
def test_a_report_git_cannot_answer_for_exits_58(staged_suite, pytester, monkeypatch):
    """A report run in a folder where git does not answer exits 58, the repo's number
    for that refusal, rather than pytest's own 4.

    The suite is written without being committed, so its folder is not a git
    repository, and git is told not to look in the folders above it."""
    staged_suite.write(MIXED_SUITE)
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(staged_suite.root.parent))
    result, _ = run_uncommitted(staged_suite, pytester)
    assert result.ret == 58


@code("SA00569")
@category("repository")
@objective("functionality")
@negative
def test_a_group_of_mixed_aspects_exits_59(staged_suite, pytester):
    """A group whose checks belong to more than one aspect of quality stops the run
    with exit 59, the repo's number for that refusal."""
    stage_groups(staged_suite, "mixed:\n  ids: [XYZ0101, XYZ0102]\n")
    result, _ = run_command(staged_suite, pytester, "--group", "mixed", report=False)
    assert result.ret == 59


@code("SA00570")
@category("repository")
@objective("functionality")
@negative
def test_a_group_with_no_ids_exits_60(staged_suite, pytester):
    """A group that lists no ids stops the run with exit 60, the repo's number for that
    refusal."""
    stage_groups(staged_suite, "empty:\n  ids: []\n")
    result, _ = run_command(staged_suite, pytester, "--group", "empty", report=False)
    assert result.ret == 60


@code("SA00571")
@category("repository")
@objective("functionality")
@negative
def test_a_group_listing_an_id_no_check_has_exits_61(staged_suite, pytester):
    """A group that lists an id no check has stops the run with exit 61, the repo's
    number for that refusal."""
    stage_groups(staged_suite, "stale:\n  ids: [XYZ0199]\n")
    result, _ = run_command(staged_suite, pytester, "--group", "stale", report=False)
    assert result.ret == 61


@code("SA00572")
@category("repository")
@objective("functionality")
@negative
def test_a_group_without_the_groups_file_exits_13(staged_suite, pytester):
    """The group option with validation/validation_groups.yml missing stops the run
    with exit 13, the repo's number for a file that cannot be read."""
    result, _ = run_command(staged_suite, pytester, "--group", "any", report=False)
    assert result.ret == 13


@code("SA00573")
@category("repository")
@objective("functionality")
@negative
def test_an_option_pytest_does_not_know_exits_2(staged_suite, pytester):
    """A command line pytest refuses, such as one holding an option it does not know,
    exits 2, the repo's number for an invalid command line, rather than pytest's own
    4."""
    result, _ = run_command(staged_suite, pytester, "--no-such-option", report=False)
    assert result.ret == 2


@code("SA00574")
@category("repository")
@objective("functionality")
@negative
def test_an_internal_error_in_pytest_exits_1(staged_suite, pytester):
    """A run in which pytest hits an internal error, because a hook breaks while the
    checks are collected, exits 1, the repo's number for an unhandled error, rather
    than pytest's own 3."""
    staged_suite.commit(MIXED_SUITE, aspect_conftest=False)
    (staged_suite.root / "conftest.py").write_text(BREAKING_CONFTEST, encoding="utf-8")
    result, _ = run_uncommitted(staged_suite, pytester, report=False)
    assert result.ret == 1
