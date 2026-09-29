"""
Script:      test_select_checks_technical.py
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

Usage:       pytest validation/sdgval/test_select_checks_technical.py
                 run these checks
             pytest validation/sdgval/test_select_checks_technical.py -v
                 one line per check with its result

Exit codes:  None of its own. It runs inside pytest.

Date:        2026-09-21
Owner:       Jason Delosh
"""

from __future__ import annotations

import json
import textwrap

import pytest

from sdgval.labels import category, code, negative, objective, positive

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
    """With the category option, only the checks carrying that category run, and the
    others get no report row."""
    ret, ids, _, _ = selected(staged_suite, "--category", "repository")
    assert ret == 0
    assert ids == {"XYZ0011", "XYZ0014"}


@code("SA00463")
@category("repository")
@objective("functionality")
@positive
def test_objective_keeps_only_that_objective(staged_suite):
    """With the objective option, only the checks carrying that objective run."""
    ret, ids, _, _ = selected(staged_suite, "--objective", "correctness")
    assert ret == 0
    assert ids == {"XYZ0011", "XYZ0013"}


@code("SA00464")
@category("repository")
@objective("functionality")
@positive
def test_category_and_objective_narrow_each_other(staged_suite):
    """With both the category and objective options, only the checks matching both run."""
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
    """With the id option, only the checks carrying those ids run."""
    ret, ids, _, _ = selected(staged_suite, "--id", "XYZ0012,XYZ0014")
    assert ret == 0
    assert ids == {"XYZ0012", "XYZ0014"}


@code("SA00619")
@category("repository")
@objective("functionality")
@positive
def test_an_option_given_twice_means_any_of_the_values(staged_suite):
    """The same option given twice keeps the checks matching either value, the same as
    a comma-separated list on one option."""
    ret, ids, _, _ = selected(staged_suite, "--id", "XYZ0012", "--id", "XYZ0014")
    assert ret == 0
    assert ids == {"XYZ0012", "XYZ0014"}


@code("SA00467")
@category("repository")
@objective("functionality")
@positive
def test_group_runs_the_ids_the_groups_file_lists(staged_suite):
    """With the group option, the checks the named group lists in
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
    """The report's selection column records the selection options as given, one entry
    per option, so a narrowed run cannot pass for a full one."""
    _, _, rows, _ = selected(
        staged_suite, "--category", "repository", "--objective", "correctness"
    )
    assert [json.loads(s) for s in {r["selection"] for r in rows}] == [
        {"category": ["repository"], "objective": ["correctness"]}
    ]


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
    """A category that is not a defined category stops the run with exit 4 and writes no
    report, and the message names the value and the categories."""
    ret, ids, _, printed = selected(staged_suite, "--category", "machinery")
    assert ret == 4
    assert "--category machinery: not one of repository, sources, processing" in printed
    assert ids == set()


@code("SA00470")
@category("repository")
@objective("functionality")
@negative
def test_an_id_no_collected_check_carries_stops_the_run(staged_suite):
    """An id that no check has stops the run with exit 4 rather than running nothing.
    The message says no check has it and where every id is listed."""
    ret, ids, _, printed = selected(staged_suite, "--id", "XYZ0099")
    assert ret == 4
    assert (
        "No check has the id XYZ0099. Every check's id is listed in "
        "validation/validation_inventory.csv." in printed
    )
    assert ids == set()


@code("SA00501")
@category("repository")
@objective("functionality")
@negative
def test_an_id_outside_the_files_given_stops_the_run(staged_suite):
    """An id the inventory lists that is not among the files the run was given stops the
    run with exit 4. The message says the id is not in the files or folders given."""
    staged_suite.validation.mkdir(exist_ok=True)
    (staged_suite.validation / "validation_inventory.csv").write_text(
        "id\nXYZ0099\n", encoding="utf-8"
    )
    ret, ids, _, printed = selected(staged_suite, "--id", "XYZ0099")
    assert ret == 4
    assert "XYZ0099 is not in the files or folders given to this run." in printed
    assert ids == set()


@code("SA00502")
@category("repository")
@objective("functionality")
@negative
def test_a_group_listing_an_id_no_check_has_stops_the_run(staged_suite):
    """A group that lists an id no check has stops the run with exit 4. The message
    names the group and the id and says to correct the groups file."""
    staged_suite.validation.mkdir(exist_ok=True)
    (staged_suite.validation / "validation_groups.yml").write_text(
        "stale:\n  purpose: A stale group.\n  ids: [XYZ0098]\n", encoding="utf-8"
    )
    ret, ids, _, printed = selected(staged_suite, "--group", "stale")
    assert ret == 4
    assert (
        "The group stale lists XYZ0098, but no check has that id. Correct the group "
        "in validation/validation_groups.yml." in printed
    )
    assert ids == set()


@code("SA00471")
@category("repository")
@objective("functionality")
@negative
def test_a_group_not_in_the_file_stops_the_run(staged_suite):
    """A group name that validation/validation_groups.yml does not define stops the run
    with exit 4, and the message names the groups that do exist."""
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
    """The group option with validation/validation_groups.yml missing stops the run with
    exit 4, and the message names the file."""
    ret, ids, _, printed = selected(staged_suite, "--group", "odd")
    assert ret == 4
    assert "--group needs validation/validation_groups.yml" in printed
    assert ids == set()


@code("SA00473")
@category("repository")
@objective("functionality")
@negative
def test_a_defined_value_matching_no_check_stops_the_run(staged_suite):
    """A defined category that no collected check carries stops the run with exit 4
    rather than running nothing. The message says the option matched no check and what
    to do."""
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
    """Two options that each match a check, but never the same check, stop the run with
    exit 4. The message gives each option's own count, so the reader can see which one
    to change."""
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
    """With the aspect option, only the checks whose objective belongs to that aspect
    run, although no check carries the aspect itself."""
    ret, ids, _, _ = selected(staged_suite, "--aspect", "conformance")
    assert ret == 0
    assert ids == {"XYZ0014"}


@code("SA00476")
@category("repository")
@objective("functionality")
@positive
def test_aspect_and_category_narrow_each_other(staged_suite):
    """With both the aspect and category options, only the checks matching both run, so
    a run can be aimed at one aspect of one kind of thing."""
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
    """An aspect that is not a defined aspect of quality stops the run with exit 4, and
    the message names the value and the aspects."""
    ret, ids, _, printed = selected(staged_suite, "--aspect", "quality")
    assert ret == 4
    assert "--aspect quality: not one of conformance, integrity, technical" in printed
    assert ids == set()


@code("SA00514")
@category("repository")
@objective("functionality")
@negative
def test_an_objective_not_in_the_list_stops_the_run(staged_suite):
    """An objective that is not a defined objective stops the run with exit 4, and the
    message names the value and the objectives."""
    ret, ids, _, printed = selected(staged_suite, "--objective", "speed")
    assert ret == 4
    assert "--objective speed: not one of conformance, correctness" in printed
    assert ids == set()


#######################################################################################
### Refusing a group that cannot run as written ###
#
# A group is refused when its checks belong to more than one aspect of quality, and
# when it lists no ids. Each refusal stops the run with exit 4, names the group and
# says what to change.


@code("SA00575")
@category("repository")
@objective("functionality")
@negative
def test_a_group_of_mixed_aspects_stops_the_run(staged_suite):
    """A group whose checks belong to more than one aspect of quality stops the run with
    exit 4. The message names the group and its aspects and says to split it into one
    group per aspect."""
    staged_suite.validation.mkdir(exist_ok=True)
    (staged_suite.validation / "validation_groups.yml").write_text(
        "mixed:\n  ids: [XYZ0011, XYZ0014]\n", encoding="utf-8"
    )
    ret, ids, _, printed = selected(staged_suite, "--group", "mixed")
    assert ret == 4
    assert (
        "The group mixed in validation/validation_groups.yml lists checks of more "
        "than one aspect of quality, conformance, integrity. A group holds the checks "
        "of one aspect, so split it into one group per aspect." in printed
    )
    assert ids == set()


@code("SA00576")
@category("repository")
@objective("functionality")
@negative
@pytest.mark.parametrize(
    "group",
    ["empty:\n  ids: []\n", "empty:\n  purpose: No ids.\n", "empty:\n  ids: XYZ0011\n"],
    ids=["an empty list of ids", "no ids at all", "ids that are not a list"],
)
def test_a_group_with_no_list_of_ids_stops_the_run(staged_suite, group):
    """A group that has no list of ids stops the run with exit 4. The message names the
    group and says to give it an ids list naming at least one check. The run is
    repeated for an empty list, for a group with no ids at all, and for ids written
    as one value rather than a list."""
    staged_suite.validation.mkdir(exist_ok=True)
    (staged_suite.validation / "validation_groups.yml").write_text(
        group, encoding="utf-8"
    )
    ret, ids, _, printed = selected(staged_suite, "--group", "empty")
    assert ret == 4
    assert (
        "The group empty in validation/validation_groups.yml has no list of ids, so it "
        "names no check to run. Give it an ids list naming at least one check."
        in printed
    )
    assert ids == set()
