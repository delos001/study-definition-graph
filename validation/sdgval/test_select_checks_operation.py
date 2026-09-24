"""
Script:      test_select_checks_operation.py
Description: Checks for src/sdgval/select_checks.py, the plugin that selects checks
             by category, objective, id or named group. Each check runs one
             throwaway suite of four checks, which differ in category, objective
             and id, in a separate pytest process with the real plugins, staged by
             the staged_suite fixture in validation/conftest.py, and reads the
             report to see which checks ran. A
             deselected check neither runs nor gets a report row, so the report's
             ids say what was kept. The refusals are confirmed by exit code, by
             message and by the absence of a report.

Inputs:      Nothing real. The throwaway suite is written to pytest's own
             temporary folder, and the installed plugins are loaded by its process.

Outputs:     Writes nothing outside pytest's own temporary folder.

Usage:       pytest validation/sdgval/test_select_checks_operation.py
                 run these checks
             pytest validation/sdgval/test_select_checks_operation.py -v
                 one line per check with its result

Exit codes:  pytest's own: 0 all passed, 1 some failed

Date:        2026-09-21
Owner:       Jason Delosh
"""

from __future__ import annotations

import textwrap

import pytest

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
    @pytest.mark.category("processing")
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
    staged_suite, *args: str
) -> tuple[int, set[str], list[dict[str, str]], str]:
    """Run the selection suite with the given options and say which checks ran.

    Args:
        staged_suite: The throwaway suite, from validation/conftest.py.
        *args: The selection options.

    Returns:
        pytest's exit code, the ids of the checks that got a report row, the rows,
        and everything pytest printed.
    """
    result, out = staged_suite.run(SELECTION_SUITE, *args)
    rows = staged_suite.report(out) if out.exists() else []
    printed = result.stdout.str() + result.stderr.str()
    return result.ret, {r["id"] for r in rows}, rows, printed


def stage_groups(staged_suite) -> None:
    """Write the groups file under the throwaway suite's root, where the plugin reads it.

    Args:
        staged_suite: The throwaway suite, from validation/conftest.py.
    """
    folder = staged_suite.validation
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


@code("SA00462")
@category("repository")
@objective("functionality")
@positive
def test_category_keeps_only_that_category(staged_suite):
    """With --category, only the checks carrying that category run, and the others get
    no report row."""
    ret, ids, _, _ = selected(staged_suite, "--category", "repository")
    assert ret == 0
    assert ids == {"XYZ0011", "XYZ0014"}


@code("SA00463")
@category("repository")
@objective("functionality")
@positive
def test_objective_keeps_only_that_objective(staged_suite):
    """With --objective, only the checks carrying that objective run."""
    ret, ids, _, _ = selected(staged_suite, "--objective", "correctness")
    assert ret == 0
    assert ids == {"XYZ0011", "XYZ0013"}


@code("SA00464")
@category("repository")
@objective("functionality")
@positive
def test_category_and_objective_narrow_each_other(staged_suite):
    """With both --category and --objective, only the checks matching both run."""
    ret, ids, _, _ = selected(
        staged_suite, "--category", "repository", "--objective", "correctness"
    )
    assert ret == 0
    assert ids == {"XYZ0011"}


@code("SA00465")
@category("repository")
@objective("functionality")
@positive
def test_a_comma_separated_list_means_any_of_the_values(staged_suite):
    """A comma-separated list on one option keeps the checks matching any value in it."""
    ret, ids, _, _ = selected(staged_suite, "--category", "sources,processing")
    assert ret == 0
    assert ids == {"XYZ0012", "XYZ0013"}


@code("SA00466")
@category("repository")
@objective("functionality")
@positive
def test_id_keeps_only_those_checks(staged_suite):
    """With --id, only the checks carrying those ids run."""
    ret, ids, _, _ = selected(staged_suite, "--id", "XYZ0012,XYZ0014")
    assert ret == 0
    assert ids == {"XYZ0012", "XYZ0014"}


@code("SA00467")
@category("repository")
@objective("functionality")
@positive
def test_group_runs_the_ids_the_groups_file_lists(staged_suite):
    """With --group, the checks whose ids the named group lists in
    validation/validation_groups.yml run, and no others."""
    stage_groups(staged_suite)
    ret, ids, _, _ = selected(staged_suite, "--group", "odd")
    assert ret == 0
    assert ids == {"XYZ0011", "XYZ0013"}


@code("SA00468")
@category("repository")
@objective("functionality")
@positive
def test_the_selection_column_records_the_options(staged_suite):
    """The report's selection column records the selection options as given, so a
    narrowed run cannot pass for a full one."""
    _, _, rows, _ = selected(
        staged_suite, "--category", "repository", "--objective", "correctness"
    )
    assert {r["selection"] for r in rows} == {
        "--category repository --objective correctness"
    }


#######################################################################################
### Negative checks ###
#
# A value that names nothing stops the run with pytest's usage error, exit 4, says
# why, and leaves no report.


@code("SA00469")
@category("repository")
@objective("functionality")
@negative
def test_a_category_not_in_the_list_stops_the_run(staged_suite):
    """A --category value that is not a defined category stops the run with pytest's
    usage error, exit 4, the message names the value and the categories, and no
    report is written."""
    ret, ids, _, printed = selected(staged_suite, "--category", "machinery")
    assert ret == 4
    assert "--category machinery: not one of repository, sources, processing" in printed
    assert ids == set()


@code("SA00470")
@category("repository")
@objective("functionality")
@negative
def test_an_id_no_collected_check_carries_stops_the_run(staged_suite):
    """An --id that no collected check carries stops the run with exit 4 rather than
    running nothing, so a typo cannot pass for a clean run."""
    ret, ids, _, printed = selected(staged_suite, "--id", "XYZ0099")
    assert ret == 4
    assert "no collected check carries the id XYZ0099" in printed
    assert ids == set()


@code("SA00471")
@category("repository")
@objective("functionality")
@negative
def test_a_group_not_in_the_file_stops_the_run(staged_suite):
    """A --group name that validation/validation_groups.yml does not define stops the
    run with exit 4, naming the groups that do exist."""
    stage_groups(staged_suite)
    ret, ids, _, printed = selected(staged_suite, "--group", "even")
    assert ret == 4
    assert "--group even: no such group in validation/validation_groups.yml" in printed
    assert "the groups are odd" in printed
    assert ids == set()


@code("SA00472")
@category("repository")
@objective("functionality")
@negative
def test_group_without_the_groups_file_stops_the_run(staged_suite):
    """A --group when validation/validation_groups.yml is missing stops the run with
    exit 4 and a message naming the file."""
    ret, ids, _, printed = selected(staged_suite, "--group", "odd")
    assert ret == 4
    assert "--group needs validation/validation_groups.yml" in printed
    assert ids == set()


@code("SA00473")
@category("repository")
@objective("functionality")
@negative
def test_a_defined_value_matching_no_check_stops_the_run(staged_suite):
    """A --category that is a defined category but that no collected check carries
    stops the run with exit 4 rather than running nothing, and the message says the
    option matched no check and what to do about it."""
    ret, ids, _, printed = selected(staged_suite, "--category", "products")
    assert ret == 4
    assert "no check matches every option given: --category matched 0" in printed
    assert "Drop or widen the option that matched fewest." in printed
    assert ids == set()


@code("SA00474")
@category("repository")
@objective("functionality")
@negative
def test_options_that_together_match_nothing_stop_the_run(staged_suite):
    """Two options that each match a check, but no one check, stop the run with exit
    4 rather than running nothing, and the message gives each option's own count and
    what to do, so the reader can see which one is the odd one out."""
    ret, ids, _, printed = selected(
        staged_suite, "--category", "sources", "--id", "XYZ0011"
    )
    assert ret == 4
    assert (
        "no check matches every option given: --category matched 1, --id matched 1, in combination 0. Drop or widen the option that matched fewest."
        in printed
    )
    assert ids == set()


@code("SA00475")
@category("repository")
@objective("functionality")
@positive
def test_aspect_keeps_only_the_checks_of_that_aspect(staged_suite):
    """With --aspect, only the checks whose objective belongs to that aspect of
    quality run, although no check carries the aspect itself."""
    ret, ids, _, _ = selected(staged_suite, "--aspect", "conformance")
    assert ret == 0
    assert ids == {"XYZ0014"}


@code("SA00476")
@category("repository")
@objective("functionality")
@positive
def test_aspect_and_category_narrow_each_other(staged_suite):
    """With both --aspect and --category, only the checks matching both run, so a run
    can be aimed at one aspect of one kind of thing."""
    ret, ids, _, _ = selected(
        staged_suite, "--aspect", "integrity", "--category", "repository"
    )
    assert ret == 0
    assert ids == {"XYZ0011"}


@code("SA00477")
@category("repository")
@objective("functionality")
@negative
def test_an_aspect_not_in_the_list_stops_the_run(staged_suite):
    """An --aspect value that is not a defined aspect of quality stops the run with
    pytest's usage error, exit 4, and the message names the value and the aspects."""
    ret, ids, _, printed = selected(staged_suite, "--aspect", "quality")
    assert ret == 4
    assert "--aspect quality: not one of conformance, integrity, operation" in printed
    assert ids == set()
