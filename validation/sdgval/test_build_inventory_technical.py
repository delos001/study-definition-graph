"""
Script:      test_build_inventory_technical.py
Description: Checks for src/sdgval/build_inventory.py, the hand-run script that
             generates validation/validation_inventory.csv from the checks in the
             check files and, under --check, is the pre-commit hook that refuses
             a commit whose inventory is stale. Each check writes one or two
             small check files to a temporary validation folder, points the script
             at it, and asserts what it writes or which exit code it returns. The
             script asks pytest to collect the staged checks, in this same process.
             The checks on the hand-kept columns also write an inventory by hand
             into that folder, so a status can be staged that the check files
             alone could not produce.

Inputs:      Nothing real. Each staged check file and inventory is written to
             pytest's own temporary folder.

Outputs:     Writes nothing outside pytest's own temporary folder.

Usage:       pytest validation/sdgval/test_build_inventory_technical.py
                 run these checks
             pytest validation/sdgval/test_build_inventory_technical.py -v
                 one line per check with its result

Exit codes:  None of its own. It runs inside pytest.

Date:        2026-09-11
Owner:       Jason Delosh
"""

from __future__ import annotations

import csv
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

from sdg.exit_codes import exit_line
from sdgval import build_inventory as script
from sdgval.labels import category, code, negative, objective, positive

# One check file with two well-formed staged checks, written the way the real files
# are, one a working situation and one a broken one. The ids are made up, and they
# use the registered suite SA because the generator refuses one that is not
# registered. The numbers start at 99 to stay well clear of the real ids, so a
# reader cannot mistake one of these for a check that exists.
TWO_CHECKS = '''
import pytest

positive = pytest.mark.positive
negative = pytest.mark.negative
code = pytest.mark.code
objective = pytest.mark.objective
category = pytest.mark.category


@code("SA99001")
@category("repository")
@objective("conformance")
@positive
def test_first():
    """The first thing works,
    across two lines.

    A second paragraph the inventory must leave out.
    """


@code("SA99002")
@category("repository")
@objective("conformance")
@negative
def test_second():
    """The wrong thing is refused."""
'''

# One check file with a single check of a different objective, which
# carries no positive or negative marker.
COMPLETENESS_CHECK = '''
import pytest

code = pytest.mark.code
objective = pytest.mark.objective
category = pytest.mark.category


@code("SA99003")
@category("repository")
@objective("completeness")
def test_third():
    """Nothing is missing from the file."""
'''


#######################################################################################
### Shared staging ###
#
# One fixture builds a temporary validation folder the script reads in place of the real
# one, and helpers run the script, read an inventory back, and write one by hand.


@dataclass(frozen=True)
class Outcome:
    """What one run of the script produced."""

    exit_code: int
    printed: str


@pytest.fixture
def tests_folder(tmp_path, monkeypatch):
    """Give a check a function for staging check files the script reads.

    The script's validation folder is pointed at a temporary one, its inventory path at
    a file inside it, and its repo root at the temporary root, so reported names read
    validation/<folder>/<file> as they do for real.

    Returns:
        The staging function, which takes source text keyed by path under validation/.
    """
    root = tmp_path
    validation = root / "validation"
    validation.mkdir()
    monkeypatch.setattr(script, "REPO_ROOT", root)
    monkeypatch.setattr(script, "VALIDATION_DIR", validation)
    monkeypatch.setattr(
        script, "INVENTORY_PATH", validation / "validation_inventory.csv"
    )

    def make(files: dict[str, str]) -> Path:
        """Write the given check files under the temporary validation folder.

        Args:
            files: The files to write, source text keyed by path under validation/.

        Returns:
            The path of the inventory the script will write.
        """
        for name, source in files.items():
            target = validation / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(source, encoding="utf-8")
        return validation / "validation_inventory.csv"

    return make


def run(capsys: pytest.CaptureFixture[str], *argv: str) -> Outcome:
    """Run the script in-process with the given arguments.

    Args:
        capsys: pytest's capture of what was printed.
        *argv: The command-line arguments to hand the script.

    Returns:
        The exit code and what was printed, as an Outcome.
    """
    exit_code = script.main(list(argv))
    return Outcome(exit_code, capsys.readouterr().out)


def rows_of(inventory: Path) -> list[dict[str, str]]:
    """Read an inventory back as rows.

    Args:
        inventory: The inventory file.

    Returns:
        Its rows, each a dict keyed by column name.
    """
    with inventory.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def write_rows(inventory: Path, rows: list[dict[str, str]]) -> None:
    """Write an inventory by hand, in the script's own column order.

    Args:
        inventory: The inventory file.
        rows: The rows to write, each a dict keyed by column name.
    """
    with inventory.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=script.COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def with_hand_kept(inventory: Path, check_id: str, **values: str) -> None:
    """Change the hand-kept columns of one row of an inventory already on disk.

    Args:
        inventory: The inventory file.
        check_id: The id of the row to change.
        **values: The hand-kept columns to set, by name.
    """
    rows = rows_of(inventory)
    for row in rows:
        if row["id"] == check_id:
            row.update(values)
    write_rows(inventory, rows)


def file_a_report(root: Path) -> None:
    """Stage one filed validation report in the temporary validation folder.

    The report is named and placed as src/sdgval/report.py files one, in the folder
    of its aspect under validation/reports/. Its contents are never read, because
    the script looks only at whether a report is there.

    Args:
        root: The temporary repo root that the tests_folder fixture set up.
    """
    folder = root / "validation" / "reports" / "technical"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "technical_2026-09-29_0f3a9c2.csv").write_text(
        "run_id\ntechnical_2026-09-29_0f3a9c2\n", encoding="utf-8"
    )


def removed_row(check_id: str, **values: str) -> dict[str, str]:
    """Build an inventory row for a check that is no longer in any check file.

    The generator keeps such a row when it is marked superseded or retired. Any
    other such row is dropped while no validation report has been filed, and
    refused once one has.

    Args:
        check_id: The row's id.
        **values: The hand-kept columns to set, by name.

    Returns:
        The row, with every column filled in.
    """
    row = {column: "" for column in script.COLUMNS}
    row.update(
        folder_path="validation/sdgtools",
        file_name="test_alpha_conformance.py",
        target_folder_path="src/sdgtools",
        target_file_name="alpha.py",
        name="test_gone",
        id=check_id,
        category="repository",
        objective="conformance",
        staged_case="positive",
        expected_result="A thing that is no longer checked.",
        status="active",
        version="1",
    )
    row.update(values)
    return row


@pytest.fixture
def generated(tests_folder, capsys) -> list[dict[str, str]]:
    """Stage one check file under validation/sdgtools/ with two checks, run the script, and
    read the inventory it wrote."""
    inventory = tests_folder({"sdgtools/test_alpha_conformance.py": TWO_CHECKS})
    assert run(capsys).exit_code == 0
    return rows_of(inventory)


@pytest.fixture
def written(tests_folder, capsys) -> Path:
    """Stage one check file with two checks, run the script, and hand back the inventory
    it wrote, for a check that then changes the hand-kept columns."""
    inventory = tests_folder({"sdgtools/test_alpha_conformance.py": TWO_CHECKS})
    assert run(capsys).exit_code == 0
    return inventory


#######################################################################################
### Positive checks ###
#
# The right thing works: the rows come from the checks, the hand-kept columns come
# from the existing inventory, a deleted check drops out, and --check passes on a
# current file.


@code("SA00376")
@category("repository")
@objective("functionality")
@positive
def test_row_holds_the_check_as_written(generated):
    """A row carries the check's name, id, category, objective, case and the first
    paragraph of its docstring as one line, with the second paragraph left out.

    The staged first paragraph runs over two lines, so a generator that read only the
    first line would fail the check."""
    first = next(r for r in generated if r["name"] == "test_first")
    assert first["id"] == "SA99001"
    assert first["category"] == "repository"
    assert first["objective"] == "conformance"
    assert first["staged_case"] == "positive"
    assert first["expected_result"] == "The first thing works, across two lines."


@code("SA00377")
@category("repository")
@objective("functionality")
@positive
def test_row_names_the_check_file_and_the_target(generated):
    """A check file under validation/sdgtools/ targets the script of the same name in
    src/sdgtools/, and both paths are written as a folder and a file name."""
    first = generated[0]
    assert first["folder_path"] == "validation/sdgtools"
    assert first["file_name"] == "test_alpha_conformance.py"
    assert first["target_folder_path"] == "src/sdgtools"
    assert first["target_file_name"] == "alpha.py"


@code("SA00378")
@category("repository")
@objective("functionality")
@positive
def test_a_hook_check_targets_the_hook(tests_folder, capsys):
    """A check file under validation/claude_hooks/ targets the hook of the same name in
    .claude/hooks/."""
    inventory = tests_folder({"claude_hooks/test_alpha_conformance.py": TWO_CHECKS})
    assert run(capsys).exit_code == 0
    first = rows_of(inventory)[0]
    assert first["target_folder_path"] == ".claude/hooks"
    assert first["target_file_name"] == "alpha.py"


@code("SA00379")
@category("repository")
@objective("functionality")
@positive
def test_a_check_that_staged_nothing_has_an_empty_case(tests_folder, capsys):
    """A check carrying no positive or negative marker gets a row with its objective
    and an empty staged case, whatever that objective is."""
    inventory = tests_folder({"sdgtools/test_alpha_integrity.py": COMPLETENESS_CHECK})
    assert run(capsys).exit_code == 0
    row = rows_of(inventory)[0]
    assert row["objective"] == "completeness"
    assert row["staged_case"] == ""


@code("SA00381")
@category("repository")
@objective("functionality")
@positive
def test_new_check_starts_active_at_version_1(generated):
    """A check with no row yet starts as active at version 1, with no replacing checks
    and no reason recorded."""
    assert {
        (r["status"], r["superseded_by"], r["status_reason"], r["version"])
        for r in generated
    } == {("active", "", "", "1")}


@code("SA00382")
@category("repository")
@objective("functionality")
@positive
def test_hand_kept_columns_are_carried_over_by_id(written, capsys):
    """When the inventory already has a row for a check's id, the four columns a person
    keeps by hand are kept as they were, whatever else changed."""
    with_hand_kept(
        written,
        "SA99002",
        status="inactive",
        status_reason="Switched off while the fake server is rebuilt.",
        version="3",
    )
    assert run(capsys).exit_code == 0
    second = next(r for r in rows_of(written) if r["id"] == "SA99002")
    assert (second["status"], second["status_reason"], second["version"]) == (
        "inactive",
        "Switched off while the fake server is rebuilt.",
        "3",
    )


@code("SA00383")
@category("repository")
@objective("functionality")
@positive
def test_groups_follow_the_pipeline_order(tests_folder, capsys):
    """Rows are grouped in the pipeline's order, sources first and the checks for
    validation's own files, such as validation/conftest.py, last, whatever order the
    files are found in."""
    inventory = tests_folder(
        {
            "conftest.py": '"""The record writer."""\n',
            # One file per group, each with its own band of numbers, so that the
            # three files hold six ids between them and none repeats.
            "test_conftest_conformance.py": TWO_CHECKS.replace("SA99", "SA97"),
            "sdgtools/test_alpha_conformance.py": TWO_CHECKS,
            "sdg/sources/test_beta_conformance.py": TWO_CHECKS.replace("SA99", "SA98"),
        }
    )
    assert run(capsys).exit_code == 0
    assert [r["folder_path"] for r in rows_of(inventory)] == [
        "validation/sdg/sources",
        "validation/sdg/sources",
        "validation/sdgtools",
        "validation/sdgtools",
        "validation",
        "validation",
    ]


@code("SA00384")
@category("repository")
@objective("functionality")
@positive
def test_a_check_file_in_a_package_subfolder_targets_that_subfolder_under_src(
    tests_folder, capsys
):
    """A check file at validation/<package>/<folder>/ targets the file of the same name at
    src/<package>/<folder>/, so the pipeline's checks mirror src/sdg/ one level down."""
    inventory = tests_folder({"sdg/sources/test_alpha_conformance.py": TWO_CHECKS})
    assert run(capsys).exit_code == 0
    first = rows_of(inventory)[0]
    assert first["target_folder_path"] == "src/sdg/sources"
    assert first["target_file_name"] == "alpha.py"


@code("SA00385")
@category("repository")
@objective("functionality")
@positive
def test_a_top_level_check_file_targets_the_validation_file_of_the_same_name(
    tests_folder, capsys
):
    """A check file at the top level of validation/ targets the file of the same name in
    validation/ itself, which is how the checks for conftest.py find their target."""
    inventory = tests_folder(
        {
            "test_alpha_conformance.py": TWO_CHECKS,
            "alpha.py": '"""A file of validation\'s own."""\n',
        }
    )
    assert run(capsys).exit_code == 0
    first = rows_of(inventory)[0]
    assert first["target_folder_path"] == "validation"
    assert first["target_file_name"] == "alpha.py"


@code("SA00387")
@category("repository")
@objective("functionality")
@positive
def test_check_passes_when_inventory_is_current(tests_folder, capsys):
    """With the check option, the run exits 0 and writes nothing when the inventory
    on disk equals what would be generated."""
    inventory = tests_folder({"sdgtools/test_alpha_conformance.py": TWO_CHECKS})
    assert run(capsys).exit_code == 0
    before = inventory.stat().st_mtime_ns
    outcome = run(capsys, "--check")
    assert outcome.exit_code == 0
    assert inventory.stat().st_mtime_ns == before
    assert "is current, 2 check(s)" in outcome.printed


@code("SA00388")
@category("repository")
@objective("functionality")
@positive
def test_quiet_prints_nothing(tests_folder, capsys):
    """With the quiet option, nothing is printed. The exit code is the whole report."""
    tests_folder({"sdgtools/test_alpha_conformance.py": TWO_CHECKS})
    outcome = run(capsys, "--quiet")
    assert outcome.exit_code == 0
    assert outcome.printed == ""


#######################################################################################
### Positive checks on the hand-kept columns ###
#
# Statuses that follow their rules pass, and --check-status looks at the hand-kept
# columns of the inventory on disk without writing anything.


@code("SA00389")
@category("repository")
@objective("functionality")
@positive
def test_check_status_passes_a_superseded_check_with_an_active_successor(
    written, capsys
):
    """With the check-status option, a removed check marked superseded, naming an active
    check that replaced it, passes. The run exits 0 and writes nothing."""
    rows = rows_of(written)
    rows.append(removed_row("SA99009", status="superseded", superseded_by="SA99001"))
    write_rows(written, rows)
    before = written.read_text(encoding="utf-8")
    outcome = run(capsys, "--check-status")
    assert outcome.exit_code == 0
    assert written.read_text(encoding="utf-8") == before
    assert "the hand-kept columns are in order" in outcome.printed


@code("SA00390")
@category("repository")
@objective("functionality")
@positive
def test_check_status_passes_a_retired_check_with_a_reason(written, capsys):
    """With the check-status option, a removed check marked retired, with a reason
    saying why, passes with exit 0."""
    rows = rows_of(written)
    rows.append(
        removed_row(
            "SA99009",
            status="retired",
            status_reason="The command it tested was withdrawn.",
        )
    )
    write_rows(written, rows)
    assert run(capsys, "--check-status").exit_code == 0


#######################################################################################
### Negative checks ###
#
# The wrong thing is refused, and the message names the cause: a stale inventory, a
# check without its markers or with the wrong ones, a first sentence a spreadsheet
# would read as a formula, a duplicated id, a file that will not parse, and an empty
# validation folder.


@code("SA00392")
@category("repository")
@objective("functionality")
@negative
def test_check_fails_when_inventory_is_missing(tests_folder, capsys):
    """With the check option and no inventory on disk, the run exits 12, says the
    inventory is missing, names the command to run, and writes nothing."""
    inventory = tests_folder({"sdgtools/test_alpha_conformance.py": TWO_CHECKS})
    outcome = run(capsys, "--check")
    assert outcome.exit_code == 12
    assert exit_line(12, "INVENTORY-MISSING") in outcome.printed
    assert not inventory.exists()
    assert "is missing. Run: build_inventory" in outcome.printed


@code("SA00393")
@category("repository")
@objective("functionality")
@negative
def test_check_fails_when_inventory_is_stale(tests_folder, capsys):
    """With the check option and an inventory that no longer matches the checks, the
    run exits 16, names the command to run, and leaves the stale inventory as it was."""
    inventory = tests_folder({"sdgtools/test_alpha_conformance.py": TWO_CHECKS})
    assert run(capsys).exit_code == 0
    stale = inventory.read_text(encoding="utf-8")
    tests_folder(
        {
            "sdgtools/test_alpha_conformance.py": TWO_CHECKS.replace(
                "first thing", "other thing"
            )
        }
    )
    outcome = run(capsys, "--check")
    assert outcome.exit_code == 16
    assert exit_line(16, "INVENTORY-STALE") in outcome.printed
    assert inventory.read_text(encoding="utf-8") == stale
    assert "is stale. Run: build_inventory" in outcome.printed


@code("SA00394")
@category("repository")
@objective("functionality")
@negative
def test_check_without_id_exits_15(tests_folder, capsys):
    """A check with no id label makes the run exit 15 and name the file and the check,
    and the inventory is not written."""
    inventory = tests_folder(
        {
            "sdgtools/test_alpha_conformance.py": TWO_CHECKS.replace(
                '@code("SA99002")\n', ""
            )
        }
    )
    outcome = run(capsys)
    assert outcome.exit_code == 15
    assert exit_line(15, "CHECK-MARKERS-WRONG") in outcome.printed
    assert not inventory.exists()
    assert (
        "validation/sdgtools/test_alpha_conformance.py: test_second has no @code marker"
        in (outcome.printed)
    )


@code("SA00395")
@category("repository")
@objective("functionality")
@negative
def test_check_without_objective_exits_15(tests_folder, capsys):
    """A check with no objective label makes the run exit 15 and name the file and the
    check, and the inventory is not written."""
    inventory = tests_folder(
        {
            "sdgtools/test_alpha_conformance.py": TWO_CHECKS.replace(
                '@category("repository")\n@objective("conformance")\n',
                '@category("repository")\n',
            )
        }
    )
    outcome = run(capsys)
    assert outcome.exit_code == 15
    assert exit_line(15, "CHECK-MARKERS-WRONG") in outcome.printed
    assert not inventory.exists()
    assert "test_second has no @objective marker" in outcome.printed


@code("SA00396")
@category("repository")
@objective("functionality")
@negative
def test_check_without_category_exits_15(tests_folder, capsys):
    """A check with no category label makes the run exit 15 and name the file and the
    check, and the inventory is not written."""
    inventory = tests_folder(
        {
            "sdgtools/test_alpha_conformance.py": TWO_CHECKS.replace(
                '@code("SA99002")\n@category("repository")\n', '@code("SA99002")\n'
            )
        }
    )
    outcome = run(capsys)
    assert outcome.exit_code == 15
    assert exit_line(15, "CHECK-MARKERS-WRONG") in outcome.printed
    assert not inventory.exists()
    assert "test_second has no @category marker" in outcome.printed


@code("SA00397")
@category("repository")
@objective("functionality")
@negative
def test_a_category_not_in_the_list_exits_15(tests_folder, capsys):
    """A check whose category label names no defined category makes the run exit 15. The
    message quotes the value and lists the categories."""
    tests_folder(
        {
            "sdgtools/test_alpha_conformance.py": TWO_CHECKS.replace(
                '@code("SA99002")\n@category("repository")',
                '@code("SA99002")\n@category("machinery")',
            )
        }
    )
    outcome = run(capsys)
    assert outcome.exit_code == 15
    assert exit_line(15, "CHECK-MARKERS-WRONG") in outcome.printed
    assert "test_second has @category('machinery'), which is not one of" in (
        outcome.printed
    )
    assert ", ".join(script.CATEGORIES) in outcome.printed


@code("SA00398")
@category("repository")
@objective("functionality")
@negative
def test_an_objective_not_in_the_list_exits_15(tests_folder, capsys):
    """A check whose objective label names no defined objective makes the run exit 15.
    The message quotes the value and lists the objectives."""
    tests_folder(
        {
            "sdgtools/test_alpha_conformance.py": TWO_CHECKS.replace(
                '@code("SA99002")\n@category("repository")\n@objective("conformance")',
                '@code("SA99002")\n@category("repository")\n@objective("behaviour")',
            )
        }
    )
    outcome = run(capsys)
    assert outcome.exit_code == 15
    assert exit_line(15, "CHECK-MARKERS-WRONG") in outcome.printed
    assert "test_second has @objective('behaviour'), which is not one of" in (
        outcome.printed
    )
    assert ", ".join(script.OBJECTIVES) in outcome.printed


@code("SA00399")
@category("repository")
@objective("functionality")
@positive
def test_any_objective_may_carry_a_staged_case(tests_folder, capsys):
    """A check of any objective may be marked as staging a working or a broken
    situation, and its row records that, because the mark says how the check was set up."""
    inventory = tests_folder(
        {
            "sdgtools/test_alpha_integrity.py": COMPLETENESS_CHECK.replace(
                '@objective("completeness")\n',
                '@objective("completeness")\n@positive\n',
            ).replace(
                "objective = pytest.mark.objective",
                "objective = pytest.mark.objective\npositive = pytest.mark.positive",
            )
        }
    )
    assert run(capsys).exit_code == 0
    row = rows_of(inventory)[0]
    assert row["objective"] == "completeness"
    assert row["staged_case"] == "positive"


@code("SA00400")
@category("repository")
@objective("functionality")
@negative
@pytest.mark.parametrize("start", ["=", "+", "-", "@", "(", "*"])
def test_a_first_sentence_starting_with_a_refused_character_exits_15(
    tests_folder, capsys, start
):
    """A check whose first sentence starts with something other than a letter or a
    digit makes the run exit 15, and the message names the character and says to start
    with a letter or a digit. The run is repeated once for each character, the four a
    spreadsheet reads as the start of a formula, then a bracket and an asterisk."""
    inventory = tests_folder(
        {
            "sdgtools/test_alpha_conformance.py": TWO_CHECKS.replace(
                '"""The wrong thing', f'"""{start}The wrong thing'
            )
        }
    )
    outcome = run(capsys)
    assert outcome.exit_code == 15
    assert exit_line(15, "CHECK-MARKERS-WRONG") in outcome.printed
    assert not inventory.exists()
    assert f"test_second has a first sentence starting with {start!r}" in (
        outcome.printed
    )
    assert "start it with a letter or a digit" in outcome.printed


@code("SA00401")
@category("repository")
@objective("functionality")
@positive
def test_a_first_sentence_opening_with_whitespace_is_accepted(tests_folder, capsys):
    """A check whose docstring opens with a tab or a new line is accepted, and its row
    holds the sentence without that space, because the generator removes it before
    looking at the sentence."""
    inventory = tests_folder(
        {
            "sdgtools/test_alpha_conformance.py": TWO_CHECKS.replace(
                '"""The wrong thing', '"""\t\nThe wrong thing'
            )
        }
    )
    assert run(capsys).exit_code == 0
    row = next(r for r in rows_of(inventory) if r["id"] == "SA99002")
    assert row["expected_result"] == "The wrong thing is refused."


@code("SA00402")
@category("repository")
@objective("functionality")
@negative
def test_duplicate_id_exits_15(tests_folder, capsys):
    """Two checks carrying the same id make the run exit 15, and the message names
    both checks."""
    tests_folder(
        {"sdgtools/test_alpha_conformance.py": TWO_CHECKS.replace("SA99002", "SA99001")}
    )
    outcome = run(capsys)
    assert outcome.exit_code == 15
    assert exit_line(15, "CHECK-MARKERS-WRONG") in outcome.printed
    assert "SA99001 is carried by both test_first and test_second" in outcome.printed


@code("SA00403")
@category("repository")
@objective("functionality")
@negative
def test_an_id_of_the_wrong_shape_exits_15(tests_folder, capsys):
    """An id that is not S, a capital letter and five digits makes the run exit 15,
    and the message names the check and says what an id looks like."""
    tests_folder(
        {"sdgtools/test_alpha_conformance.py": TWO_CHECKS.replace("SA99001", "sa99001")}
    )
    outcome = run(capsys)
    assert outcome.exit_code == 15
    assert exit_line(15, "CHECK-MARKERS-WRONG") in outcome.printed
    assert (
        "validation/sdgtools/test_alpha_conformance.py: test_first has the id 'sa99001', which "
        "is not S, a capital letter and five digits" in outcome.printed
    )


@code("SA00404")
@category("repository")
@objective("functionality")
@negative
def test_an_unregistered_suite_exits_15(tests_folder, capsys):
    """An id whose two letters are not one of the registered suites makes the run
    exit 15, and the message names the suite and lists the ones that are
    registered."""
    tests_folder(
        {"sdgtools/test_alpha_conformance.py": TWO_CHECKS.replace("SA99001", "SZ99001")}
    )
    outcome = run(capsys)
    assert outcome.exit_code == 15
    assert exit_line(15, "CHECK-MARKERS-WRONG") in outcome.printed
    assert (
        "validation/sdgtools/test_alpha_conformance.py: test_first has the id SZ99001, and SZ "
        "is not one of the suites" in outcome.printed
    )
    assert ", ".join(script.SUITES) in outcome.printed


@code("SA00405")
@category("repository")
@objective("functionality")
@negative
def test_unparseable_file_exits_14(tests_folder, capsys):
    """A check file that is not valid Python makes the run exit 14, and the message
    names it."""
    tests_folder({"sdgtools/test_alpha_conformance.py": "def broken(:\n"})
    outcome = run(capsys)
    assert outcome.exit_code == 14
    assert exit_line(14, "PYTHON-UNPARSEABLE") in outcome.printed
    assert (
        "validation/sdgtools/test_alpha_conformance.py: cannot parse" in outcome.printed
    )


@code("SA00406")
@category("repository")
@objective("functionality")
@negative
@pytest.mark.parametrize(
    ("staging", "code", "sub_code", "said"),
    [
        ("empty folder", 18, "NO-CHECK-FILES", "no check files found"),
        ("no folder", 12, "VALIDATION-FOLDER-MISSING", "is missing"),
    ],
    ids=["empty folder", "no folder"],
)
def test_no_test_files_is_refused(tests_folder, capsys, staging, code, sub_code, said):
    """A validation folder with no check files makes the run exit 18, and a missing
    validation folder makes it exit 12, each naming its cause. It runs once with an
    empty validation folder and once with no validation folder at all."""
    tests_folder({})
    if staging == "no folder":
        script.VALIDATION_DIR.rmdir()
    outcome = run(capsys)
    assert outcome.exit_code == code
    assert exit_line(code, sub_code) in outcome.printed
    assert said in outcome.printed


#######################################################################################
### Negative checks on the hand-kept columns ###
#
# A hand-kept column that breaks its rule is refused with exit 15 and the row named,
# and nothing is written. A problem with a check's markers outranks it.


@code("SA00407")
@category("repository")
@objective("functionality")
@negative
def test_a_status_not_in_the_list_exits_15(written, capsys):
    """A row whose status is not one of the five makes the run exit 15, quoting the
    status, and the inventory is not rewritten."""
    with_hand_kept(written, "SA99002", status="archived")
    before = written.read_text(encoding="utf-8")
    outcome = run(capsys)
    assert outcome.exit_code == 15
    assert exit_line(15, "INVENTORY-COLUMN-INVALID") in outcome.printed
    assert written.read_text(encoding="utf-8") == before
    assert "SA99002 has status 'archived', which is not one of" in outcome.printed


@code("SA00408")
@category("repository")
@objective("functionality")
@negative
@pytest.mark.parametrize("status", ["pending", "inactive", "retired"])
def test_a_status_that_needs_a_reason_without_one_exits_15(written, capsys, status):
    """A check marked pending, inactive or retired with no reason recorded makes the
    check-status run exit 15 and say the reason is missing. The run is repeated once
    for each of the three statuses.

    A retired check is staged as removed from its check file, as a retired check is.
    A pending or inactive check is staged on a check that is still there.
    """
    if status == "retired":
        check_id = "SA99009"
        rows = rows_of(written)
        rows.append(removed_row(check_id, status=status))
        write_rows(written, rows)
    else:
        check_id = "SA99002"
        with_hand_kept(written, check_id, status=status)
    outcome = run(capsys, "--check-status")
    assert outcome.exit_code == 15
    assert exit_line(15, "INVENTORY-COLUMN-INVALID") in outcome.printed
    assert f"{check_id} is {status} but status_reason does not say why" in (
        outcome.printed
    )


@code("SA00409")
@category("repository")
@objective("functionality")
@negative
def test_superseded_without_a_successor_exits_15(written, capsys):
    """A removed check marked superseded that names no replacing check makes the
    --check-status run exit 15 and say no check is named."""
    rows = rows_of(written)
    rows.append(removed_row("SA99009", status="superseded"))
    write_rows(written, rows)
    outcome = run(capsys, "--check-status")
    assert outcome.exit_code == 15
    assert exit_line(15, "INVENTORY-COLUMN-INVALID") in outcome.printed
    assert "SA99009 is superseded but superseded_by names no check" in outcome.printed


@code("SA00410")
@category("repository")
@objective("functionality")
@negative
def test_a_successor_on_a_check_not_superseded_exits_15(written, capsys):
    """A row that names replacing checks while its status is not superseded makes the
    run exit 15."""
    with_hand_kept(written, "SA99002", superseded_by="SA99001")
    outcome = run(capsys)
    assert outcome.exit_code == 15
    assert exit_line(15, "INVENTORY-COLUMN-INVALID") in outcome.printed
    assert "SA99002 names checks in superseded_by but is active, not superseded" in (
        outcome.printed
    )


@code("SA00411")
@category("repository")
@objective("functionality")
@negative
def test_a_status_reason_on_a_check_that_is_not_off_exits_15(written, capsys):
    """A row that carries a reason while its status is not pending, inactive or retired
    makes the run exit 15, because only those three statuses record why a check does
    not run."""
    with_hand_kept(
        written, "SA99002", status_reason="Switched off while the API moved."
    )
    outcome = run(capsys)
    assert outcome.exit_code == 15
    assert exit_line(15, "INVENTORY-COLUMN-INVALID") in outcome.printed
    assert "SA99002 has a status_reason but is active" in outcome.printed


@code("SA00412")
@category("repository")
@objective("functionality")
@negative
def test_a_successor_that_is_not_in_the_inventory_exits_15(written, capsys):
    """A superseded row that names a replacing check which is not in the inventory
    makes the check-status run exit 15 and name that check."""
    rows = rows_of(written)
    rows.append(removed_row("SA99009", status="superseded", superseded_by="SA99404"))
    write_rows(written, rows)
    outcome = run(capsys, "--check-status")
    assert outcome.exit_code == 15
    assert exit_line(15, "INVENTORY-COLUMN-INVALID") in outcome.printed
    assert (
        "SA99009 is superseded by SA99404, which is not a check in the inventory"
        in (outcome.printed)
    )


@code("SA00413")
@category("repository")
@objective("functionality")
@negative
def test_a_version_that_is_not_a_whole_number_exits_15(written, capsys):
    """A row whose version is not a whole number from 1 up, such as 1.1, makes the
    run exit 15, quoting the value."""
    with_hand_kept(written, "SA99002", version="1.1")
    outcome = run(capsys)
    assert outcome.exit_code == 15
    assert exit_line(15, "INVENTORY-COLUMN-INVALID") in outcome.printed
    assert "SA99002 has version '1.1', which is not a whole number" in outcome.printed


@code("SA00414")
@category("repository")
@objective("functionality")
@negative
def test_a_retired_check_still_in_the_test_files_exits_16(written, capsys):
    """A row marked retired whose check is still in the check files makes the run exit
    16, saying to remove the check or change its status."""
    with_hand_kept(
        written, "SA99002", status="retired", status_reason="No longer needed."
    )
    outcome = run(capsys)
    assert outcome.exit_code == 16
    assert exit_line(16, "INVENTORY-ROW-MISMATCH") in outcome.printed
    assert "SA99002 is retired but is still in the check files" in outcome.printed
    assert "remove the check or change its status" in outcome.printed


@code("SA00415")
@category("repository")
@objective("functionality")
@negative
def test_check_status_without_an_inventory_exits_12(tests_folder, capsys):
    """With the check-status option and no inventory on disk, the run exits 12 and
    names the command that writes one."""
    tests_folder({"sdgtools/test_alpha_conformance.py": TWO_CHECKS})
    outcome = run(capsys, "--check-status")
    assert outcome.exit_code == 12
    assert exit_line(12, "INVENTORY-MISSING") in outcome.printed
    assert "is missing. Run: build_inventory" in outcome.printed


@code("SA00416")
@category("repository")
@objective("functionality")
@negative
def test_a_marker_problem_outranks_a_hand_kept_problem(written, tests_folder, capsys):
    """When one check has no objective label and another row has a status not in the
    list, the run exits 15 and names both problems."""
    with_hand_kept(written, "SA99001", status="archived")
    tests_folder(
        {
            "sdgtools/test_alpha_conformance.py": TWO_CHECKS.replace(
                '@category("repository")\n@objective("conformance")\n',
                '@category("repository")\n',
            )
        }
    )
    outcome = run(capsys)
    assert outcome.exit_code == 15
    assert exit_line(15, "CHECK-MARKERS-WRONG") in outcome.printed
    assert "test_second has no @objective marker" in outcome.printed
    assert "SA99001 has status 'archived'" in outcome.printed


#######################################################################################
### Aspect suffixes ###
#
# A check file holds checks of one aspect only, and its name ends with that aspect.


@code("SA00478")
@category("repository")
@objective("functionality")
@negative
def test_a_file_with_no_aspect_in_its_name_exits_15(tests_folder, capsys):
    """A check file whose name ends with no aspect of quality makes the run exit 15,
    and the message names the file and lists the endings it may take."""
    tests_folder({"sdgtools/test_alpha.py": TWO_CHECKS})
    outcome = run(capsys)
    assert outcome.exit_code == 15
    assert exit_line(15, "CHECK-FILE-NAME-WRONG") in outcome.printed
    assert (
        "validation/sdgtools/test_alpha.py has no aspect in its name; it must end "
        "with one of _conformance, _integrity, _technical" in outcome.printed
    )


@code("SA00479")
@category("repository")
@objective("functionality")
@negative
def test_a_check_of_another_aspect_exits_15(tests_folder, capsys):
    """A check whose objective belongs to another aspect than the one its file is named
    for makes the run exit 15. The message names the check, its objective, the
    objective's aspect and the file's aspect."""
    tests_folder({"sdgtools/test_alpha_integrity.py": TWO_CHECKS})
    outcome = run(capsys)
    assert outcome.exit_code == 15
    assert exit_line(15, "CHECK-FILE-NAME-WRONG") in outcome.printed
    assert (
        "validation/sdgtools/test_alpha_integrity.py: test_first has the objective "
        "conformance, which belongs to conformance, in a file named for integrity"
        in outcome.printed
    )


@code("SA00480")
@category("repository")
@objective("functionality")
@positive
def test_the_aspect_is_left_out_of_the_covered_file(tests_folder, capsys):
    """A check file named test_alpha_conformance.py covers alpha.py, because the aspect
    at the end of a check file's name is not part of the name of the file it tests."""
    inventory = tests_folder({"sdgtools/test_alpha_conformance.py": TWO_CHECKS})
    assert run(capsys).exit_code == 0
    first = rows_of(inventory)[0]
    assert first["file_name"] == "test_alpha_conformance.py"
    assert first["target_file_name"] == "alpha.py"


#######################################################################################
### Code folders ###
#
# The inventory lists its rows in an order set by code folder, so a check file in a
# folder the order does not list is refused rather than sorted last without notice.


@code("SA00505")
@category("repository")
@objective("functionality")
@negative
def test_a_file_in_an_unlisted_code_folder_exits_15(tests_folder, capsys):
    """A check file in a code folder the inventory's folder order does not list makes the
    run exit 15. The message names the file and the folder and says to add the folder to
    that order."""
    tests_folder({"sdg/classify/test_alpha_conformance.py": TWO_CHECKS})
    outcome = run(capsys)
    assert outcome.exit_code == 15
    assert exit_line(15, "CHECK-FILE-MISPLACED") in outcome.printed
    assert (
        "validation/sdg/classify/test_alpha_conformance.py is in the code folder "
        "sdg/classify, which CODE_FOLDER_ORDER" in outcome.printed
    )
    assert "add the folder there" in outcome.printed


#######################################################################################
### Confirming the hand-kept columns alone ###
#
# --check-status needs only the checks' ids, so only a file that will not parse or an
# empty folder stops it.


@code("SA00519")
@category("repository")
@objective("functionality")
@negative
def test_check_status_on_a_file_that_will_not_parse_exits_14(tests_folder, capsys):
    """With the check-status option, a check file that is not valid Python makes the run
    exit 14 and name the file."""
    tests_folder({"sdgtools/test_alpha_technical.py": "def broken(:\n"})
    outcome = run(capsys, "--check-status")
    assert outcome.exit_code == 14
    assert exit_line(14, "PYTHON-UNPARSEABLE") in outcome.printed
    assert (
        "validation/sdgtools/test_alpha_technical.py: cannot parse" in outcome.printed
    )


@code("SA00520")
@category("repository")
@objective("functionality")
@negative
def test_check_status_on_an_empty_folder_exits_18(tests_folder, capsys):
    """With the check-status option, a validation folder holding no check files makes the
    run exit 18 and say no check files were found."""
    tests_folder({})
    outcome = run(capsys, "--check-status")
    assert outcome.exit_code == 18
    assert exit_line(18, "NO-CHECK-FILES") in outcome.printed
    assert "no check files found under validation" in outcome.printed


#######################################################################################
### Rows that outlive their check ###
#
# A superseded or retired check is removed from the check files, and its row is kept.


def add_row(inventory: Path, check_id: str, **fields: str) -> None:
    """Add a row to a written inventory for a check that is not in the check files.

    Args:
        inventory: The inventory file.
        check_id: The id the row carries.
        **fields: The columns to set, beside a copy of the first row's others.
    """
    rows = rows_of(inventory)
    rows.append({**rows[0], "id": check_id, "name": f"test_{check_id}", **fields})
    with inventory.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=script.COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


@code("SA00536")
@category("repository")
@objective("functionality")
@positive
def test_a_retired_row_is_kept_when_the_inventory_is_regenerated(tests_folder, capsys):
    """A row marked retired, whose check is no longer in the check files, is kept with
    its status and reason when the inventory is regenerated."""
    inventory = tests_folder({"sdgtools/test_alpha_conformance.py": TWO_CHECKS})
    assert run(capsys).exit_code == 0
    add_row(inventory, "SA99009", status="retired", status_reason="No longer needed.")
    assert run(capsys).exit_code == 0
    kept = {row["id"]: row for row in rows_of(inventory)}["SA99009"]
    assert kept["status"] == "retired"
    assert kept["status_reason"] == "No longer needed."


@code("SA00537")
@category("repository")
@objective("functionality")
@positive
def test_a_superseded_row_is_kept_when_the_inventory_is_regenerated(
    tests_folder, capsys
):
    """A row marked superseded, whose check is no longer in the check files, is kept
    with the check that replaced it when the inventory is regenerated."""
    inventory = tests_folder({"sdgtools/test_alpha_conformance.py": TWO_CHECKS})
    assert run(capsys).exit_code == 0
    add_row(inventory, "SA99008", status="superseded", superseded_by="SA99001")
    assert run(capsys).exit_code == 0
    kept = {row["id"]: row for row in rows_of(inventory)}["SA99008"]
    assert kept["status"] == "superseded"
    assert kept["superseded_by"] == "SA99001"


#######################################################################################
### Reading the checks through pytest ###
#
# The checks are the ones pytest collects, with the labels pytest reads, so a check
# pytest runs once per value is one row, and a label given in any form pytest
# accepts is read.

# A check that runs once for each of three values, added to the two checks above.
PARAMETRIZED_CHECK = '''

@code("SA99004")
@category("repository")
@objective("conformance")
@positive
@pytest.mark.parametrize("value", [1, 2, 3])
def test_each(value):
    """Each value works."""
'''

# A check file whose labels are written in full, and two of them given to every check
# in the file through its pytestmark rather than on the function.
FILE_LABELS_CHECK = '''
import pytest

pytestmark = [pytest.mark.category("repository"), pytest.mark.objective("conformance")]


@pytest.mark.code("SA99006")
@pytest.mark.negative
def test_labelled_by_its_file():
    """The file's labels reach the check."""
'''


@code("SA00547")
@category("repository")
@objective("functionality")
@positive
def test_a_check_that_runs_once_per_value_gets_one_row(tests_folder, capsys):
    """A check that pytest runs once for each of three values gets one row in the
    inventory, beside the rows of the other checks in its file."""
    inventory = tests_folder(
        {"sdgtools/test_alpha_conformance.py": TWO_CHECKS + PARAMETRIZED_CHECK}
    )
    assert run(capsys).exit_code == 0
    assert [r["id"] for r in rows_of(inventory)] == ["SA99001", "SA99002", "SA99004"]


@code("SA00549")
@category("repository")
@objective("functionality")
@positive
def test_labels_given_to_the_whole_file_are_read_on_each_check(tests_folder, capsys):
    """A check whose category and objective are given to every check in its file
    through the file's pytestmark, and whose id and case are written in full as
    @pytest.mark labels, gets a row with all four, as a validation report reads them."""
    inventory = tests_folder({"sdgtools/test_alpha_conformance.py": FILE_LABELS_CHECK})
    assert run(capsys).exit_code == 0
    row = rows_of(inventory)[0]
    assert (row["id"], row["category"], row["objective"], row["staged_case"]) == (
        "SA99006",
        "repository",
        "conformance",
        "negative",
    )


@code("SA00644")
@category("repository")
@objective("functionality")
@positive
def test_a_module_from_outside_the_validation_folder_stays_imported(
    tests_folder, monkeypatch, capsys
):
    """A module that a check file imports while the checks are read, and that lives
    outside the validation folder, is still imported once the run ends, because
    whoever imports it gets the same module.

    colorsys, a small module of the standard library, is removed from Python's table
    of imported modules first, so the staged check file is what imports it."""
    monkeypatch.delitem(sys.modules, "colorsys", raising=False)
    tests_folder(
        {"sdgtools/test_alpha_conformance.py": "import colorsys\n" + TWO_CHECKS}
    )
    assert run(capsys).exit_code == 0
    assert "colorsys" in sys.modules


#######################################################################################
### Checks pytest reads but the inventory refuses ###
#
# A check file that fails to load stops the run. A check pytest can read but the
# inventory cannot hold as one row is refused.

# A check written inside a class, added to the two checks above.
CHECK_IN_A_CLASS = '''

class TestGroup:
    @code("SA99005")
    @category("repository")
    @objective("conformance")
    @positive
    def test_inside(self):
        """A check written inside a class."""
'''

# A check that runs once for each of two values, where the second value carries a
# label the first does not.
LABEL_ON_ONE_VALUE = '''

@code("SA99004")
@category("repository")
@objective("conformance")
@pytest.mark.parametrize("value", [1, pytest.param(2, marks=pytest.mark.negative)])
def test_each(value):
    """Each value works."""
'''


@code("SA00543")
@category("repository")
@objective("functionality")
@negative
def test_a_check_file_that_will_not_load_exits_1(tests_folder, capsys):
    """A check file that is valid Python but fails when it is loaded, because it
    imports a module that does not exist, makes the run exit 1, and the message names
    the file and the error."""
    tests_folder(
        {
            "sdgtools/test_alpha_conformance.py": "import sdg_no_such_module\n"
            + TWO_CHECKS
        }
    )
    outcome = run(capsys)
    assert outcome.exit_code == 1
    assert exit_line(1, "CHECK-FILE-LOAD-ERROR") in outcome.printed
    assert (
        "validation/sdgtools/test_alpha_conformance.py could not be loaded"
        in outcome.printed
    )
    assert "No module named 'sdg_no_such_module'" in outcome.printed


@code("SA00544")
@category("repository")
@objective("functionality")
@negative
def test_a_conftest_that_will_not_load_exits_1(tests_folder, capsys):
    """A conftest.py in the validation folder that fails when pytest loads it, before
    any check file is read, makes the run exit 1, and the message names the
    conftest.py."""
    tests_folder(
        {
            "conftest.py": "raise RuntimeError('broken on purpose')\n",
            "sdgtools/test_alpha_conformance.py": TWO_CHECKS,
        }
    )
    outcome = run(capsys)
    assert outcome.exit_code == 1
    assert exit_line(1, "CHECK-FILE-LOAD-ERROR") in outcome.printed
    assert "pytest could not collect the checks under validation" in outcome.printed
    assert "conftest.py" in outcome.printed


@code("SA00545")
@category("repository")
@objective("functionality")
@negative
def test_a_check_inside_a_class_exits_15(tests_folder, capsys):
    """A check written inside a class makes the run exit 15. The message names the
    file, the class and the check, and says to move the check out of its class."""
    tests_folder({"sdgtools/test_alpha_conformance.py": TWO_CHECKS + CHECK_IN_A_CLASS})
    outcome = run(capsys)
    assert outcome.exit_code == 15
    assert exit_line(15, "CHECK-INSIDE-CLASS") in outcome.printed
    assert (
        "validation/sdgtools/test_alpha_conformance.py: TestGroup::test_inside is not "
        "a function at the top level of its check file" in outcome.printed
    )
    assert "move it out of its class" in outcome.printed


@code("SA00643")
@category("repository")
@objective("functionality")
@negative
def test_a_check_inside_a_class_that_runs_once_per_value_is_named_once(
    tests_folder, capsys
):
    """A check written inside a class that pytest runs once for each of two values is
    named once in the refusal, not once per value, and the run exits 15."""
    in_a_class = CHECK_IN_A_CLASS.replace(
        "    @positive\n",
        '    @positive\n    @pytest.mark.parametrize("value", [1, 2])\n',
    ).replace("def test_inside(self):", "def test_inside(self, value):")
    tests_folder({"sdgtools/test_alpha_conformance.py": TWO_CHECKS + in_a_class})
    outcome = run(capsys)
    assert outcome.exit_code == 15
    assert exit_line(15, "CHECK-INSIDE-CLASS") in outcome.printed
    assert outcome.printed.count("TestGroup::test_inside is not a function") == 1


@code("SA00546")
@category("repository")
@objective("functionality")
@negative
def test_a_check_carrying_both_cases_exits_15(tests_folder, capsys):
    """A check carrying both the positive and the negative label makes the run exit
    18, and the message names the check and says to keep the one that is true."""
    tests_folder(
        {
            "sdgtools/test_alpha_conformance.py": TWO_CHECKS.replace(
                "@positive\ndef test_first", "@positive\n@negative\ndef test_first"
            )
        }
    )
    outcome = run(capsys)
    assert outcome.exit_code == 15
    assert exit_line(15, "CHECK-MARKERS-WRONG") in outcome.printed
    assert "test_first carries both @positive and @negative" in outcome.printed
    assert "keep the one that is true" in outcome.printed


@code("SA00548")
@category("repository")
@objective("functionality")
@negative
def test_runs_of_one_check_with_different_labels_exit_15(tests_folder, capsys):
    """A check that runs once per value, where one value carries a label the other
    does not, makes the run exit 15, and the message names the check."""
    tests_folder(
        {"sdgtools/test_alpha_conformance.py": TWO_CHECKS + LABEL_ON_ONE_VALUE}
    )
    outcome = run(capsys)
    assert outcome.exit_code == 15
    assert exit_line(15, "CHECK-MARKERS-WRONG") in outcome.printed
    assert "test_each carries different labels on different runs" in outcome.printed


@code("SA00550")
@category("repository")
@objective("functionality")
@negative
def test_a_check_without_a_docstring_exits_15(tests_folder, capsys):
    """A check with no docstring makes the run exit 15, and the message names the
    check and says to write the sentence that must be true for it to pass."""
    tests_folder(
        {
            "sdgtools/test_alpha_conformance.py": TWO_CHECKS.replace(
                '    """The wrong thing is refused."""\n', "    pass\n"
            )
        }
    )
    outcome = run(capsys)
    assert outcome.exit_code == 15
    assert exit_line(15, "CHECK-MARKERS-WRONG") in outcome.printed
    assert "test_second has no docstring, or its first paragraph is empty" in (
        outcome.printed
    )
    assert "Write the sentence that must be true" in outcome.printed


#######################################################################################
### Rows whose check has gone ###
#
# Once a validation report has been filed, a check is taken out of use by marking its
# row, never by deleting its function alone. While none has been filed, a row whose
# check has gone is dropped. The id of a check taken out of use is never given to
# another.

# A new check, named test_new, carrying the id SA99009.
NEW_CHECK_WITH_A_SPENT_ID = '''

@code("SA99009")
@category("repository")
@objective("conformance")
@positive
def test_new():
    """A new check given an id that is already spent."""
'''


@code("SA00551")
@category("repository")
@objective("functionality")
@negative
def test_an_active_row_whose_check_is_gone_exits_16(tests_folder, tmp_path, capsys):
    """Once a validation report has been filed, a row marked active whose check has
    been deleted from its check file makes the run exit 16. The message names the id
    and says to mark the row retired or superseded, or put the check back.

    The report is staged after the inventory is first written, as a filed report
    would be.
    """
    tests_folder({"sdgtools/test_alpha_conformance.py": TWO_CHECKS})
    assert run(capsys).exit_code == 0
    file_a_report(tmp_path)
    tests_folder(
        {"sdgtools/test_alpha_conformance.py": TWO_CHECKS.split('@code("SA99002")')[0]}
    )
    outcome = run(capsys)
    assert outcome.exit_code == 16
    assert exit_line(16, "INVENTORY-ROW-MISMATCH") in outcome.printed
    assert "SA99002 is active, but no check file holds a check with that id" in (
        outcome.printed
    )
    assert "mark it so, or put the check back" in outcome.printed


@code("SA00561")
@category("repository")
@objective("functionality")
@positive
def test_a_row_whose_check_is_gone_is_dropped_when_no_report_is_filed(
    tests_folder, tmp_path, capsys
):
    """While no validation report has been filed, a row marked active whose check has
    been deleted from its check file is dropped when the inventory is regenerated,
    and the run exits 0.

    The reports folder is staged holding its README, its dictionary, its .gitkeep
    and an empty folder for each aspect, and no report, so none of them is taken
    for a filed report.
    """
    inventory = tests_folder({"sdgtools/test_alpha_conformance.py": TWO_CHECKS})
    assert run(capsys).exit_code == 0
    reports = tmp_path / "validation" / "reports"
    for aspect in script.ASPECTS:
        (reports / aspect).mkdir(parents=True)
    for name in ("README.md", "validation_report_dictionary.md", ".gitkeep"):
        (reports / name).write_text("", encoding="utf-8")
    tests_folder(
        {"sdgtools/test_alpha_conformance.py": TWO_CHECKS.split('@code("SA99002")')[0]}
    )
    assert run(capsys).exit_code == 0
    assert [r["id"] for r in rows_of(inventory)] == ["SA99001"]


@code("SA00552")
@category("repository")
@objective("functionality")
@negative
@pytest.mark.parametrize(
    "spent",
    [
        {"status": "retired", "status_reason": "No longer needed."},
        {"status": "superseded", "superseded_by": "SA99001"},
    ],
    ids=["a retired check's id", "a superseded check's id"],
)
def test_a_new_check_given_a_spent_id_exits_16(written, tests_folder, capsys, spent):
    """A new check given the id of a check taken out of use makes the run exit 16. The
    message says the id already belongs to a check of that status and to give the new
    check the next free id, and offers no other remedy. The run is repeated for a
    retired check's id and for a superseded check's id."""
    rows = rows_of(written)
    rows.append(removed_row("SA99009", **spent))
    write_rows(written, rows)
    tests_folder(
        {"sdgtools/test_alpha_conformance.py": TWO_CHECKS + NEW_CHECK_WITH_A_SPENT_ID}
    )
    outcome = run(capsys)
    assert outcome.exit_code == 16
    assert exit_line(16, "INVENTORY-ROW-MISMATCH") in outcome.printed
    assert (
        "validation/sdgtools/test_alpha_conformance.py: test_new carries SA99009, which "
        f"already belongs to a {spent['status']} check" in outcome.printed
    )
    assert "give test_new the next free id" in outcome.printed
    assert "change its status" not in outcome.printed


@code("SA00553")
@category("repository")
@objective("functionality")
@positive
@pytest.mark.parametrize("successor_status", ["superseded", "retired"])
def test_a_successor_taken_out_of_use_since_is_accepted(
    written, capsys, successor_status
):
    """A superseded row whose replacing check has itself since been superseded or
    retired passes the check-status run with exit 0, because a row keeps the check
    that took over at the time. The run is repeated for a replacing check that was
    superseded and one that was retired."""
    successor = (
        {"status": "superseded", "superseded_by": "SA99001"}
        if successor_status == "superseded"
        else {"status": "retired", "status_reason": "No longer needed."}
    )
    rows = rows_of(written)
    rows.append(removed_row("SA99008", name="test_gone_later", **successor))
    rows.append(removed_row("SA99009", status="superseded", superseded_by="SA99008"))
    write_rows(written, rows)
    assert run(capsys, "--check-status").exit_code == 0


@code("SA00554")
@category("repository")
@objective("functionality")
@negative
def test_a_row_superseded_by_itself_exits_15(written, capsys):
    """A superseded row that names its own id in superseded_by makes the check-status
    run exit 15, and the message says to name the checks that took over from it."""
    rows = rows_of(written)
    rows.append(removed_row("SA99009", status="superseded", superseded_by="SA99009"))
    write_rows(written, rows)
    outcome = run(capsys, "--check-status")
    assert outcome.exit_code == 15
    assert exit_line(15, "INVENTORY-COLUMN-INVALID") in outcome.printed
    assert "SA99009 names itself in superseded_by" in outcome.printed


@code("SA00559")
@category("repository")
@objective("functionality")
@positive
def test_a_kept_row_keeps_its_place_by_check_file_and_id(tests_folder, capsys):
    """A retired row is written among the rows of its own check file, in id order,
    rather than after the rows of the checks still in use."""
    inventory = tests_folder(
        {
            "sdgtools/test_alpha_conformance.py": TWO_CHECKS,
            "sdgtools/test_beta_conformance.py": TWO_CHECKS.replace("SA99", "SA98"),
        }
    )
    assert run(capsys).exit_code == 0
    rows = rows_of(inventory)
    rows.append(
        removed_row("SA99000", status="retired", status_reason="No longer needed.")
    )
    write_rows(inventory, rows)
    assert run(capsys).exit_code == 0
    assert [r["id"] for r in rows_of(inventory)] == [
        "SA99000",
        "SA99001",
        "SA99002",
        "SA98001",
        "SA98002",
    ]


#######################################################################################
### A changed check moves its version ###
#
# Each row records a fingerprint of its check with the version it was taken at. The
# fingerprint covers the check's code, docstring and labels, and a change to the
# layout alone is not a change. Once a validation report has been filed, a change is
# accepted once the version has moved. While none has been filed, the new
# fingerprint is recorded against the version the row already has.

# One check file with one check whose body does something, so its layout can change.
BODY_CHECK = '''
import pytest

code = pytest.mark.code
objective = pytest.mark.objective
category = pytest.mark.category
positive = pytest.mark.positive
negative = pytest.mark.negative


@code("SA99007")
@category("repository")
@objective("conformance")
@positive
def test_adds():
    """Two and two make four."""
    total = sum([2, 2])
    assert total == 4, 'wrong sum'
'''

# The same check with a line of its code changed.
BODY_CHECK_CHANGED = BODY_CHECK.replace("sum([2, 2])", "sum([2, 2, 0])")


def fingerprint_of(inventory: Path, check_id: str) -> str:
    """Read the fingerprint recorded for one check.

    Args:
        inventory: The inventory file.
        check_id: The check's id.

    Returns:
        The value of its fingerprint column.
    """
    return next(r for r in rows_of(inventory) if r["id"] == check_id)["fingerprint"]


@code("SA00556")
@category("repository")
@objective("functionality")
@positive
def test_a_changed_check_with_a_raised_version_is_accepted(
    tests_folder, tmp_path, capsys
):
    """Once a validation report has been filed, a check whose code changed, and whose
    version was raised by hand from 1 to 2, is accepted, and its new fingerprint is
    recorded against version 2."""
    inventory = tests_folder({"sdgtools/test_alpha_conformance.py": BODY_CHECK})
    assert run(capsys).exit_code == 0
    file_a_report(tmp_path)
    before = fingerprint_of(inventory, "SA99007")
    tests_folder({"sdgtools/test_alpha_conformance.py": BODY_CHECK_CHANGED})
    with_hand_kept(inventory, "SA99007", version="2")
    assert run(capsys).exit_code == 0
    after = fingerprint_of(inventory, "SA99007")
    assert after.startswith("v2:")
    assert after.removeprefix("v2:") != before.removeprefix("v1:")


@code("SA00557")
@category("repository")
@objective("functionality")
@positive
@pytest.mark.parametrize(
    "old, new",
    [
        (
            "    total = sum([2, 2])\n    assert total == 4, 'wrong sum'\n",
            "    # Add them up.\n    total = sum(\n        [\n            2,\n"
            '            2,\n        ]\n    )\n    assert total == 4, "wrong sum"\n',
        ),
        ("Two and two make four.", "Two and two\n    make four."),
    ],
    ids=[
        "spacing, a comment, a trailing comma and other quotes",
        "a docstring rewrapped over two lines",
    ],
)
def test_a_change_to_layout_leaves_the_fingerprint(tests_folder, capsys, old, new):
    """A check whose layout changed, while its code, docstring words and labels did
    not, keeps its fingerprint, and the run exits 0 with its version still 1. The
    run is repeated for a change of layout in the code and for a docstring whose
    words were rewrapped over two lines."""
    inventory = tests_folder({"sdgtools/test_alpha_conformance.py": BODY_CHECK})
    assert run(capsys).exit_code == 0
    before = fingerprint_of(inventory, "SA99007")
    tests_folder({"sdgtools/test_alpha_conformance.py": BODY_CHECK.replace(old, new)})
    assert run(capsys).exit_code == 0
    assert fingerprint_of(inventory, "SA99007") == before


@code("SA00558")
@category("repository")
@objective("functionality")
@positive
def test_a_row_without_a_fingerprint_gets_one(tests_folder, capsys):
    """A row that has no fingerprint recorded yet, as every row had before the column
    existed, is given one against its version, and the run exits 0."""
    inventory = tests_folder({"sdgtools/test_alpha_conformance.py": BODY_CHECK})
    assert run(capsys).exit_code == 0
    with_hand_kept(inventory, "SA99007", fingerprint="")
    tests_folder({"sdgtools/test_alpha_conformance.py": BODY_CHECK_CHANGED})
    assert run(capsys).exit_code == 0
    assert fingerprint_of(inventory, "SA99007").startswith("v1:")


@code("SA00562")
@category("repository")
@objective("functionality")
@positive
@pytest.mark.parametrize(
    "source, old, new",
    [
        (BODY_CHECK, "Two and two make four.", "The sum of two and two is four."),
        (BODY_CHECK, '@category("repository")', '@category("sources")'),
        (
            FILE_LABELS_CHECK,
            'pytest.mark.category("repository")',
            'pytest.mark.category("sources")',
        ),
    ],
    ids=[
        "a reworded docstring",
        "a label on the function",
        "a label given to the whole file",
    ],
)
def test_a_change_to_the_docstring_or_labels_moves_the_fingerprint(
    tests_folder, capsys, source, old, new
):
    """A check whose docstring or labels changed, while its code did not, gets a new
    fingerprint. The run is repeated for a reworded docstring, a changed label on the
    function and a changed label given to the whole check file."""
    inventory = tests_folder({"sdgtools/test_alpha_conformance.py": source})
    assert run(capsys).exit_code == 0
    before = rows_of(inventory)[0]["fingerprint"]
    tests_folder({"sdgtools/test_alpha_conformance.py": source.replace(old, new)})
    assert run(capsys).exit_code == 0
    assert rows_of(inventory)[0]["fingerprint"] != before


@code("SA00563")
@category("repository")
@objective("functionality")
@positive
def test_a_changed_check_is_refingerprinted_when_no_report_is_filed(
    tests_folder, capsys
):
    """While no validation report has been filed, a check whose code changed while its
    version stayed at 1 is accepted, the run exits 0, and its new fingerprint is
    recorded against version 1."""
    inventory = tests_folder({"sdgtools/test_alpha_conformance.py": BODY_CHECK})
    assert run(capsys).exit_code == 0
    before = fingerprint_of(inventory, "SA99007")
    tests_folder({"sdgtools/test_alpha_conformance.py": BODY_CHECK_CHANGED})
    assert run(capsys).exit_code == 0
    after = fingerprint_of(inventory, "SA99007")
    assert after.startswith("v1:")
    assert after != before


#######################################################################################
### A changed check whose version stayed put ###


@code("SA00555")
@category("repository")
@objective("functionality")
@negative
def test_a_changed_check_whose_version_did_not_move_exits_16(
    tests_folder, tmp_path, capsys
):
    """Once a validation report has been filed, a check whose code changed while its
    version stayed at 1 makes the run exit 16. The message names the check and its
    id and says to raise its version to 2."""
    tests_folder({"sdgtools/test_alpha_conformance.py": BODY_CHECK})
    assert run(capsys).exit_code == 0
    file_a_report(tmp_path)
    tests_folder({"sdgtools/test_alpha_conformance.py": BODY_CHECK_CHANGED})
    outcome = run(capsys)
    assert outcome.exit_code == 16
    assert exit_line(16, "CHECK-CHANGED-VERSION-SAME") in outcome.printed
    assert "test_adds (SA99007) has changed since version 1 was recorded" in (
        outcome.printed
    )
    assert "Raise its version to 2" in outcome.printed


#######################################################################################
### The Python version that made the fingerprints ###
#
# Each fingerprint cell records the Python version, major and minor, that took it,
# because a new Python can write the same code out differently. Once a validation
# report has been filed, a run on another Python stops with one message, and
# --python-changed records new fingerprints for the rows the other Python made.

# The Python version this run fingerprints with, as the cells record it.
RUNNING = f"py{sys.version_info.major}.{sys.version_info.minor}"


def made_by_another_python(inventory: Path, check_id: str) -> None:
    """Rewrite one row's fingerprint cell as though Python 2.7 had made it.

    Args:
        inventory: The inventory file.
        check_id: The id of the row to change.
    """
    cell = fingerprint_of(inventory, check_id)
    with_hand_kept(inventory, check_id, fingerprint=cell.replace(RUNNING, "py2.7"))


@code("SA00581")
@category("repository")
@objective("functionality")
@positive
def test_a_fingerprint_records_the_python_version_that_made_it(tests_folder, capsys):
    """A check's fingerprint cell records the version it was taken at and then the
    running Python's major and minor version, such as v1:py3.12: before the sixteen
    hexadecimal characters."""
    inventory = tests_folder({"sdgtools/test_alpha_conformance.py": BODY_CHECK})
    assert run(capsys).exit_code == 0
    assert re.fullmatch(
        rf"v1:{re.escape(RUNNING)}:[0-9a-f]{{16}}", fingerprint_of(inventory, "SA99007")
    )


@code("SA00582")
@category("repository")
@objective("functionality")
@negative
def test_fingerprints_made_by_another_python_exit_8(tests_folder, tmp_path, capsys):
    """Once a validation report has been filed, an inventory whose fingerprints another
    Python version made stops the run with exit 8 and one message. The message names
    both Python versions and says to run build_inventory --python-changed in a commit
    that changes nothing else."""
    inventory = tests_folder({"sdgtools/test_alpha_conformance.py": BODY_CHECK})
    assert run(capsys).exit_code == 0
    file_a_report(tmp_path)
    made_by_another_python(inventory, "SA99007")
    outcome = run(capsys)
    assert outcome.exit_code == 8
    assert exit_line(8, "PYTHON-VERSION-CHANGED") in outcome.printed
    assert "were made by Python 2.7, and this is Python" in outcome.printed
    assert "Run build_inventory --python-changed" in outcome.printed
    assert "in a commit that changes nothing else" in outcome.printed


@code("SA00583")
@category("repository")
@objective("functionality")
@positive
def test_python_changed_records_new_fingerprints(tests_folder, tmp_path, capsys):
    """Once a validation report has been filed, build_inventory --python-changed
    records a new fingerprint, made by the running Python, for a row another Python
    made, without comparing it, and the run exits 0."""
    inventory = tests_folder({"sdgtools/test_alpha_conformance.py": BODY_CHECK})
    assert run(capsys).exit_code == 0
    file_a_report(tmp_path)
    made_by_another_python(inventory, "SA99007")
    tests_folder({"sdgtools/test_alpha_conformance.py": BODY_CHECK_CHANGED})
    assert run(capsys, "--python-changed").exit_code == 0
    assert fingerprint_of(inventory, "SA99007").startswith(f"v1:{RUNNING}:")


@code("SA00584")
@category("repository")
@objective("functionality")
@negative
def test_an_empty_fingerprint_exits_15(tests_folder, tmp_path, capsys):
    """Once a validation report has been filed, a row whose fingerprint cell was
    emptied makes the run exit 15. The message names the check and its id and says
    to put its fingerprint back as git last recorded it."""
    inventory = tests_folder({"sdgtools/test_alpha_conformance.py": BODY_CHECK})
    assert run(capsys).exit_code == 0
    file_a_report(tmp_path)
    with_hand_kept(inventory, "SA99007", fingerprint="")
    outcome = run(capsys)
    assert outcome.exit_code == 15
    assert exit_line(15, "FINGERPRINT-MISSING") in outcome.printed
    assert "test_adds (SA99007) has no fingerprint recorded" in outcome.printed
    assert "Put its fingerprint back as git last recorded it" in outcome.printed


#######################################################################################
### Which sub-code decides the exit line ###
#
# The header ranks the sub-codes, so a run that finds problems of several kinds ends
# on the one ranked highest. Each pair of sub-codes next to each other in the
# header's order is staged as two problems, the lower-ranked one found first.

# Each sub-code and the sub-code the header ranks next below it, read from the order
# the script itself keeps.
RANKED_PAIRS = list(
    zip(script.EXIT_PRECEDENCE, script.EXIT_PRECEDENCE[1:], strict=False)
)


@code("SA00622")
@category("repository")
@objective("functionality")
@negative
@pytest.mark.parametrize(
    ("higher", "lower"),
    RANKED_PAIRS,
    ids=[f"{higher} over {lower}" for higher, lower in RANKED_PAIRS],
)
def test_the_higher_ranked_sub_code_decides(higher, lower):
    """When a run finds two problems, the one whose sub-code the header ranks higher
    decides the exit line, even when the other problem was found first. It runs once
    for each pair of sub-codes next to each other in the header's order."""
    problems = [
        script.Problem("found first", 0, lower),
        script.Problem("found second", 0, higher),
    ]
    assert script.deciding_problem(problems).sub_code == higher
