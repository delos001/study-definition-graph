"""
Script:      test_select_checks.py
Description: Checks for validation/select_checks.py, the plugin that selects checks
             by category, objective, id or named group. Each check runs one
             throwaway suite of four checks, which differ in category, objective
             and id, in a separate pytest process with the real conftest.py and
             the real plugin, and reads the report to see which checks ran. A
             deselected check neither runs nor gets a report row, so the report's
             ids say what was kept. The refusals are checked by exit code, by
             message and by the absence of a report.

Inputs:      validation/conftest.py and validation/select_checks.py (read-only;
             copied into, and loaded by, the throwaway suite's process)

Outputs:     Writes nothing outside pytest's own temporary folder.

Usage:       pytest validation/test_select_checks.py
                 run these checks
             pytest validation/test_select_checks.py -v
                 one line per check with its result

Exit codes:  pytest's own: 0 all passed, 1 some failed

Date:        2026-09-21
Owner:       Jason Delosh
"""

from __future__ import annotations

import textwrap

import pytest
from validation.test_conftest import run_suite, the_report

positive = pytest.mark.positive
negative = pytest.mark.negative
# Every check carries a @code line: its short, permanent id in
# validation/validation_inventory.csv, assigned once and never reused.
code = pytest.mark.code
# Every check carries an @objective line: what the check confirms about its target,
# one of the objectives validation/validation_inventory_dictionary.md defines.
objective = pytest.mark.objective
# Every check carries a @category line: what kind of thing the check confirms, one
# of the categories validation/validation_inventory_dictionary.md defines.
category = pytest.mark.category

# One suite with four checks that differ in category, objective and id.
SELECTION_SUITE = '''
    import pytest

    @pytest.mark.code("XYZ0011")
    @pytest.mark.category("repository")
    @pytest.mark.objective("correctness")
    @pytest.mark.positive
    def test_one():
        """One."""

    @pytest.mark.code("XYZ0012")
    @pytest.mark.category("sources")
    @pytest.mark.objective("stability")
    def test_two():
        """Two."""

    @pytest.mark.code("XYZ0013")
    @pytest.mark.category("conversion")
    @pytest.mark.objective("correctness")
    @pytest.mark.positive
    def test_three():
        """Three."""

    @pytest.mark.code("XYZ0014")
    @pytest.mark.category("repository")
    @pytest.mark.objective("conformance")
    def test_four():
        """Four."""
    '''

# A groups file with one group, written where the plugin looks for it.
GROUPS_FILE = """
    odd:
      purpose: The odd ones.
      ids: [XYZ0011, XYZ0013]
    """


#######################################################################################
### Shared staging ###


def selected(
    pytester, monkeypatch, *args: str
) -> tuple[int, set[str], list[dict[str, str]], str]:
    """Run the selection suite with the given options and say which checks ran.

    Args:
        pytester: pytest's helper for running a separate suite.
        monkeypatch: pytest's patcher, for the import path of the separate process.
        *args: The selection options.

    Returns:
        pytest's exit code, the ids of the checks that got a report row, the rows,
        and everything pytest printed.
    """
    result, out = run_suite(pytester, monkeypatch, SELECTION_SUITE, *args)
    rows = the_report(out) if out.exists() else []
    printed = result.stdout.str() + result.stderr.str()
    return result.ret, {r["id"] for r in rows}, rows, printed


def stage_groups(pytester) -> None:
    """Write the groups file under the throwaway suite's root, where the plugin reads it.

    Args:
        pytester: pytest's helper for running a separate suite.
    """
    folder = pytester.path / "validation"
    folder.mkdir(exist_ok=True)
    (folder / "validation_groups.yml").write_text(
        textwrap.dedent(GROUPS_FILE), encoding="utf-8"
    )


#######################################################################################
### Positive checks ###
#
# The right checks run: each option keeps what it names, two options narrow each
# other, a list means any of its values, a group runs what its file lists, and the
# report records what was asked for.


@code("TST0021")
@category("repository")
@objective("correctness")
@positive
def test_category_keeps_only_that_category(pytester, monkeypatch):
    """With --category, only the checks carrying that category run, and the others get
    no report row."""
    ret, ids, _, _ = selected(pytester, monkeypatch, "--category", "repository")
    assert ret == 0
    assert ids == {"XYZ0011", "XYZ0014"}


@code("TST0022")
@category("repository")
@objective("correctness")
@positive
def test_objective_keeps_only_that_objective(pytester, monkeypatch):
    """With --objective, only the checks carrying that objective run."""
    ret, ids, _, _ = selected(pytester, monkeypatch, "--objective", "correctness")
    assert ret == 0
    assert ids == {"XYZ0011", "XYZ0013"}


@code("TST0023")
@category("repository")
@objective("correctness")
@positive
def test_category_and_objective_narrow_each_other(pytester, monkeypatch):
    """With both --category and --objective, only the checks matching both run."""
    ret, ids, _, _ = selected(
        pytester, monkeypatch, "--category", "repository", "--objective", "correctness"
    )
    assert ret == 0
    assert ids == {"XYZ0011"}


@code("TST0024")
@category("repository")
@objective("correctness")
@positive
def test_a_comma_separated_list_means_any_of_the_values(pytester, monkeypatch):
    """A comma-separated list on one option keeps the checks matching any value in it."""
    ret, ids, _, _ = selected(pytester, monkeypatch, "--category", "sources,conversion")
    assert ret == 0
    assert ids == {"XYZ0012", "XYZ0013"}


@code("TST0025")
@category("repository")
@objective("correctness")
@positive
def test_id_keeps_only_those_checks(pytester, monkeypatch):
    """With --id, only the checks carrying those ids run."""
    ret, ids, _, _ = selected(pytester, monkeypatch, "--id", "XYZ0012,XYZ0014")
    assert ret == 0
    assert ids == {"XYZ0012", "XYZ0014"}


@code("TST0026")
@category("repository")
@objective("correctness")
@positive
def test_group_runs_the_ids_the_groups_file_lists(pytester, monkeypatch):
    """With --group, the checks whose ids the named group lists in
    validation/validation_groups.yml run, and no others."""
    stage_groups(pytester)
    ret, ids, _, _ = selected(pytester, monkeypatch, "--group", "odd")
    assert ret == 0
    assert ids == {"XYZ0011", "XYZ0013"}


@code("TST0027")
@category("repository")
@objective("correctness")
@positive
def test_the_selection_column_records_the_options(pytester, monkeypatch):
    """The report's selection column records the selection options as given, so a
    narrowed run cannot pass for a full one."""
    _, _, rows, _ = selected(
        pytester, monkeypatch, "--category", "repository", "--objective", "correctness"
    )
    assert {r["selection"] for r in rows} == {
        "--category repository --objective correctness"
    }


#######################################################################################
### Negative checks ###
#
# A value that names nothing stops the run with pytest's usage error, exit 4, says
# why, and leaves no report.


@code("TST0028")
@category("repository")
@objective("correctness")
@negative
def test_a_category_not_in_the_list_stops_the_run(pytester, monkeypatch):
    """A --category value that is not a defined category stops the run with pytest's
    usage error, exit 4, the message names the value and the categories, and no
    report is written."""
    ret, ids, _, printed = selected(pytester, monkeypatch, "--category", "machinery")
    assert ret == 4
    assert "--category machinery: not one of repository, sources, conversion" in printed
    assert ids == set()


@code("TST0029")
@category("repository")
@objective("correctness")
@negative
def test_an_id_no_collected_check_carries_stops_the_run(pytester, monkeypatch):
    """An --id that no collected check carries stops the run with exit 4 rather than
    running nothing, so a typo cannot pass for a clean run."""
    ret, ids, _, printed = selected(pytester, monkeypatch, "--id", "XYZ0099")
    assert ret == 4
    assert "no collected check carries the id XYZ0099" in printed
    assert ids == set()


@code("TST0030")
@category("repository")
@objective("correctness")
@negative
def test_a_group_not_in_the_file_stops_the_run(pytester, monkeypatch):
    """A --group name that validation/validation_groups.yml does not define stops the
    run with exit 4, naming the groups that do exist."""
    stage_groups(pytester)
    ret, ids, _, printed = selected(pytester, monkeypatch, "--group", "even")
    assert ret == 4
    assert "--group even: no such group in validation/validation_groups.yml" in printed
    assert "the groups are odd" in printed
    assert ids == set()


@code("TST0031")
@category("repository")
@objective("correctness")
@negative
def test_group_without_the_groups_file_stops_the_run(pytester, monkeypatch):
    """A --group when validation/validation_groups.yml is missing stops the run with
    exit 4 and a message naming the file."""
    ret, ids, _, printed = selected(pytester, monkeypatch, "--group", "odd")
    assert ret == 4
    assert "--group needs validation/validation_groups.yml" in printed
    assert ids == set()
