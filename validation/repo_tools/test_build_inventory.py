"""
Script:      test_build_inventory.py
Description: Checks for repo_tools/build_inventory.py, the hand-run script that
             generates validation/validation_inventory.csv from the checks in the
             test files and, under --check, is the pre-commit hook that refuses
             a commit whose inventory is stale. Each check writes one or two
             small test files to a temporary validation folder, points the script at
             it, and asserts what it writes or which exit code it returns. The
             checks on the hand-kept columns also write an inventory by hand
             into that folder, so a status can be staged that the test files
             alone could not produce. One check runs --check on the real
             validation/ folder, the same run the hook makes.

Inputs:      validation/**/test_*.py and validation/validation_inventory.csv
             (read-only; the one real-folder check)

Outputs:     Writes nothing outside pytest's own temporary folder.

Usage:       pytest validation/repo_tools/test_build_inventory.py
                 run these checks
             pytest validation/repo_tools/test_build_inventory.py -v
                 one line per check with its result

Exit codes:  pytest's own: 0 all passed, 1 some failed

Date:        2026-09-11
Owner:       Jason Delosh
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

import pytest

import build_inventory as script

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

# One test file with two well-formed staged checks, written the way the real files
# are, one a working situation and one a broken one. The ids are made up, and they
# use a registered prefix because the
# generator refuses one that is not registered. The numbers start at 9 to stay well
# clear of the band the real repo_tools ids sit in, so a reader cannot mistake one
# of these for a check that exists.
TWO_CHECKS = '''
import pytest

positive = pytest.mark.positive
negative = pytest.mark.negative
code = pytest.mark.code
objective = pytest.mark.objective
category = pytest.mark.category


@code("HRS9001")
@category("repository")
@objective("conformance")
@positive
def test_first():
    """The first thing works.

    A second paragraph the inventory must leave out.
    """


@code("HRS9002")
@category("repository")
@objective("conformance")
@negative
def test_second():
    """The wrong thing is refused."""
'''

# One test file with a single check of a different objective, which
# carries no positive or negative marker.
COMPLETENESS_CHECK = '''
import pytest

code = pytest.mark.code
objective = pytest.mark.objective
category = pytest.mark.category


@code("HRS9003")
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
    """Give a check a function for staging test files the script reads.

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
        """Write the given test files under the temporary validation folder.

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


def run(capsys, *argv: str) -> Outcome:
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


def removed_row(check_id: str, **values: str) -> dict[str, str]:
    """Build an inventory row for a check that is no longer in any test file.

    Only --check-status reads such a row, since the generator drops it.

    Args:
        check_id: The row's id.
        **values: The hand-kept columns to set, by name.

    Returns:
        The row, with every column filled in.
    """
    row = {column: "" for column in script.COLUMNS}
    row.update(
        folder_path="validation/repo_tools",
        file_name="test_alpha.py",
        target_folder_path="repo_tools",
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
    """Stage one test file under validation/repo_tools/ with two checks, run the script, and
    read the inventory it wrote."""
    inventory = tests_folder({"repo_tools/test_alpha.py": TWO_CHECKS})
    assert run(capsys).exit_code == 0
    return rows_of(inventory)


@pytest.fixture
def written(tests_folder, capsys) -> Path:
    """Stage one test file with two checks, run the script, and hand back the inventory
    it wrote, for a check that then changes the hand-kept columns."""
    inventory = tests_folder({"repo_tools/test_alpha.py": TWO_CHECKS})
    assert run(capsys).exit_code == 0
    return inventory


#######################################################################################
### Positive checks ###
#
# The right thing works: the rows come from the checks, the hand-kept columns come
# from the existing inventory, a deleted check drops out, and --check passes on a
# current file.


@code("HRS0053")
@category("repository")
@objective("conformance")
@positive
def test_row_holds_the_check_as_written(generated):
    """A row carries the check's name, id, category, objective, case and the first
    paragraph of its docstring as one line, with the second paragraph left out."""
    first = next(r for r in generated if r["name"] == "test_first")
    assert first["id"] == "HRS9001"
    assert first["category"] == "repository"
    assert first["objective"] == "conformance"
    assert first["staged_case"] == "positive"
    assert first["expected_result"] == "The first thing works."


@code("HRS0054")
@category("repository")
@objective("conformance")
@positive
def test_row_names_the_check_file_and_the_target(generated):
    """A test file under validation/repo_tools/ targets the script of the same name in
    repo_tools/, and both paths are written as a folder and a file name."""
    first = generated[0]
    assert first["folder_path"] == "validation/repo_tools"
    assert first["file_name"] == "test_alpha.py"
    assert first["target_folder_path"] == "repo_tools"
    assert first["target_file_name"] == "alpha.py"


@code("HRS0122")
@category("repository")
@objective("conformance")
@positive
def test_a_hook_check_targets_the_hook(tests_folder, capsys):
    """A test file under validation/claude_hooks/ targets the hook of the same name in
    .claude/hooks/."""
    inventory = tests_folder({"claude_hooks/test_alpha.py": TWO_CHECKS})
    assert run(capsys).exit_code == 0
    first = rows_of(inventory)[0]
    assert first["target_folder_path"] == ".claude/hooks"
    assert first["target_file_name"] == "alpha.py"


@code("HRS0154")
@category("repository")
@objective("conformance")
@positive
def test_a_check_that_staged_nothing_has_an_empty_case(tests_folder, capsys):
    """A check carrying no positive or negative marker gets a row with its objective
    and an empty staged case, whatever that objective is."""
    inventory = tests_folder({"repo_tools/test_alpha.py": COMPLETENESS_CHECK})
    assert run(capsys).exit_code == 0
    row = rows_of(inventory)[0]
    assert row["objective"] == "completeness"
    assert row["staged_case"] == ""


@code("HRS0171")
@category("repository")
@objective("conformance")
@positive
def test_a_check_with_neither_marker_has_no_case(tests_folder, capsys):
    """A check with neither @positive nor @negative gets a row with an empty staged
    case, because it looked at something real rather than staging a situation."""
    inventory = tests_folder(
        {"repo_tools/test_alpha.py": TWO_CHECKS.replace("@negative\n", "")}
    )
    assert run(capsys).exit_code == 0
    row = next(r for r in rows_of(inventory) if r["id"] == "HRS9002")
    assert row["objective"] == "conformance"
    assert row["staged_case"] == ""


@code("HRS0055")
@category("repository")
@objective("conformance")
@positive
def test_new_check_starts_active_at_version_1(generated):
    """A check with no existing row starts active at version 1, with superseded_by and
    status_reason empty."""
    assert {
        (r["status"], r["superseded_by"], r["status_reason"], r["version"])
        for r in generated
    } == {("active", "", "", "1")}


@code("HRS0056")
@category("repository")
@objective("conformance")
@positive
def test_hand_kept_columns_are_carried_over_by_id(written, capsys):
    """When the inventory already has a row for a check's id, its status,
    superseded_by, status_reason and version are kept, whatever else changed."""
    with_hand_kept(
        written,
        "HRS9002",
        status="inactive",
        status_reason="Switched off while the fake server is rebuilt.",
        version="3",
    )
    assert run(capsys).exit_code == 0
    second = next(r for r in rows_of(written) if r["id"] == "HRS9002")
    assert (second["status"], second["status_reason"], second["version"]) == (
        "inactive",
        "Switched off while the fake server is rebuilt.",
        "3",
    )


@code("HRS0057")
@category("repository")
@objective("conformance")
@positive
def test_groups_follow_the_pipeline_order(tests_folder, capsys):
    """Rows are grouped in the pipeline's order, sources first and the checks for
    validation's own files, such as validation/conftest.py, last, whatever order the
    files are found in."""
    inventory = tests_folder(
        {
            "conftest.py": '"""The record writer."""\n',
            # One file per group, each carrying the prefix its folder really uses,
            # so that the three files hold six ids between them and none repeats.
            "test_conftest.py": TWO_CHECKS.replace("HRS9", "TST9"),
            "repo_tools/test_alpha.py": TWO_CHECKS,
            "sources/test_beta.py": TWO_CHECKS.replace("HRS9", "SRC9"),
        }
    )
    assert run(capsys).exit_code == 0
    assert [r["folder_path"] for r in rows_of(inventory)] == [
        "validation/sources",
        "validation/sources",
        "validation/repo_tools",
        "validation/repo_tools",
        "validation",
        "validation",
    ]


@code("HRS0141")
@category("repository")
@objective("conformance")
@positive
def test_a_top_level_check_file_targets_the_package_file_of_the_same_name(
    tests_folder, capsys
):
    """A test file at the top level of validation/ targets the file of the same name at
    the top of src/sdg/ when validation/ itself holds no file of that name."""
    inventory = tests_folder({"test_alpha.py": TWO_CHECKS})
    assert run(capsys).exit_code == 0
    first = rows_of(inventory)[0]
    assert first["target_folder_path"] == "src/sdg"
    assert first["target_file_name"] == "alpha.py"


@code("HRS0174")
@category("repository")
@objective("conformance")
@positive
def test_a_top_level_check_file_targets_the_validation_file_of_the_same_name(
    tests_folder, capsys
):
    """A test file at the top level of validation/ targets the file of the same name in
    validation/ itself when one is there, which is how the checks for conftest.py and
    select_checks.py find their targets."""
    inventory = tests_folder(
        {
            "test_alpha.py": TWO_CHECKS,
            "alpha.py": '"""A file of validation\'s own."""\n',
        }
    )
    assert run(capsys).exit_code == 0
    first = rows_of(inventory)[0]
    assert first["target_folder_path"] == "validation"
    assert first["target_file_name"] == "alpha.py"


@code("HRS0062")
@category("repository")
@objective("conformance")
@positive
def test_deleted_check_drops_out(tests_folder, capsys):
    """A row whose check no longer exists in any test file is not written again."""
    inventory = tests_folder({"repo_tools/test_alpha.py": TWO_CHECKS})
    assert run(capsys).exit_code == 0
    tests_folder({"repo_tools/test_alpha.py": TWO_CHECKS.split('@code("HRS9002")')[0]})
    assert run(capsys).exit_code == 0
    assert [r["id"] for r in rows_of(inventory)] == ["HRS9001"]


@code("HRS0058")
@category("repository")
@objective("conformance")
@positive
def test_check_passes_when_inventory_is_current(tests_folder, capsys):
    """With the check option, the run exits 0 and writes nothing when the inventory
    on disk equals what would be generated."""
    inventory = tests_folder({"repo_tools/test_alpha.py": TWO_CHECKS})
    assert run(capsys).exit_code == 0
    before = inventory.stat().st_mtime_ns
    outcome = run(capsys, "--check")
    assert outcome.exit_code == 0
    assert inventory.stat().st_mtime_ns == before
    assert "is current, 2 check(s)" in outcome.printed


@code("HRS0059")
@category("repository")
@objective("conformance")
@positive
def test_quiet_prints_nothing(tests_folder, capsys):
    """With the quiet option, nothing is printed; the exit code is the whole
    report."""
    tests_folder({"repo_tools/test_alpha.py": TWO_CHECKS})
    outcome = run(capsys, "--quiet")
    assert outcome.exit_code == 0
    assert outcome.printed == ""


#######################################################################################
### Positive checks on the hand-kept columns ###
#
# Statuses that follow their rules pass, and --check-status looks at the hand-kept
# columns of the inventory on disk without writing anything.


@code("HRS0155")
@category("repository")
@objective("conformance")
@positive
def test_check_status_passes_a_superseded_check_with_an_active_successor(
    written, capsys
):
    """With the check-status option, a removed check marked superseded, whose
    superseded_by names an active check, passes: the run exits 0 and writes
    nothing."""
    rows = rows_of(written)
    rows.append(removed_row("HRS9009", status="superseded", superseded_by="HRS9001"))
    write_rows(written, rows)
    before = written.read_text(encoding="utf-8")
    outcome = run(capsys, "--check-status")
    assert outcome.exit_code == 0
    assert written.read_text(encoding="utf-8") == before
    assert "the hand-kept columns are in order" in outcome.printed


@code("HRS0156")
@category("repository")
@objective("conformance")
@positive
def test_check_status_passes_a_retired_check_with_a_reason(written, capsys):
    """With the check-status option, a removed check marked retired, whose
    status_reason says why, passes with exit 0."""
    rows = rows_of(written)
    rows.append(
        removed_row(
            "HRS9009",
            status="retired",
            status_reason="The command it tested was withdrawn.",
        )
    )
    write_rows(written, rows)
    assert run(capsys, "--check-status").exit_code == 0


#######################################################################################
### Checks on the real repo ###
#
# The real inventory agrees with the real test files, which is the run the pre-commit
# hook makes.


@code("HRS0060")
@category("repository")
@objective("correctness")
def test_real_inventory_is_current():
    """validation/validation_inventory.csv matches the checks in the real test files,
    which is the run the pre-commit hook makes."""
    assert script.main(["--check", "--quiet"]) == 0


#######################################################################################
### Negative checks ###
#
# The wrong thing is refused, and the message names the cause: a stale inventory, a
# check without its markers or with the wrong ones, a first sentence a spreadsheet
# would read as a formula, a duplicated id, a file that will not parse, and an empty
# validation folder.


@code("HRS0061")
@category("repository")
@objective("conformance")
@negative
def test_check_fails_when_inventory_is_missing(tests_folder, capsys):
    """With the check option and no inventory on disk, the run exits 16, names the
    command to run, and writes nothing."""
    inventory = tests_folder({"repo_tools/test_alpha.py": TWO_CHECKS})
    outcome = run(capsys, "--check")
    assert outcome.exit_code == 16
    assert not inventory.exists()
    assert "is stale. Run: python repo_tools/build_inventory.py" in outcome.printed


@code("HRS0133")
@category("repository")
@objective("conformance")
@negative
def test_check_fails_when_inventory_is_stale(tests_folder, capsys):
    """With the check option and an inventory that no longer matches the checks, the
    run exits 16, names the command to run, and leaves the stale inventory as it was."""
    inventory = tests_folder({"repo_tools/test_alpha.py": TWO_CHECKS})
    assert run(capsys).exit_code == 0
    stale = inventory.read_text(encoding="utf-8")
    tests_folder(
        {"repo_tools/test_alpha.py": TWO_CHECKS.replace("first thing", "other thing")}
    )
    outcome = run(capsys, "--check")
    assert outcome.exit_code == 16
    assert inventory.read_text(encoding="utf-8") == stale
    assert "is stale. Run: python repo_tools/build_inventory.py" in outcome.printed


@code("HRS0063")
@category("repository")
@objective("conformance")
@negative
def test_check_without_id_exits_18(tests_folder, capsys):
    """A check with no @code marker makes the run exit 18, naming the file and the
    check, and the inventory is not written."""
    inventory = tests_folder(
        {"repo_tools/test_alpha.py": TWO_CHECKS.replace('@code("HRS9002")\n', "")}
    )
    outcome = run(capsys)
    assert outcome.exit_code == 18
    assert not inventory.exists()
    assert "validation/repo_tools/test_alpha.py: test_second has no @code marker" in (
        outcome.printed
    )


@code("HRS0157")
@category("repository")
@objective("conformance")
@negative
def test_check_without_objective_exits_18(tests_folder, capsys):
    """A check with no @objective marker makes the run exit 18, naming the file and
    the check, and the inventory is not written."""
    inventory = tests_folder(
        {
            "repo_tools/test_alpha.py": TWO_CHECKS.replace(
                '@category("repository")\n@objective("conformance")\n',
                '@category("repository")\n',
            )
        }
    )
    outcome = run(capsys)
    assert outcome.exit_code == 18
    assert not inventory.exists()
    assert "test_second has no @objective marker" in outcome.printed


@code("HRS0172")
@category("repository")
@objective("conformance")
@negative
def test_check_without_category_exits_18(tests_folder, capsys):
    """A check with no @category marker makes the run exit 18, naming the file and
    the check, and the inventory is not written."""
    inventory = tests_folder(
        {
            "repo_tools/test_alpha.py": TWO_CHECKS.replace(
                '@code("HRS9002")\n@category("repository")\n', '@code("HRS9002")\n'
            )
        }
    )
    outcome = run(capsys)
    assert outcome.exit_code == 18
    assert not inventory.exists()
    assert "test_second has no @category marker" in outcome.printed


@code("HRS0173")
@category("repository")
@objective("conformance")
@negative
def test_a_category_not_in_the_list_exits_18(tests_folder, capsys):
    """A check whose @category names no defined category makes the run exit 18, and the
    message quotes the value and lists the categories."""
    tests_folder(
        {
            "repo_tools/test_alpha.py": TWO_CHECKS.replace(
                '@code("HRS9002")\n@category("repository")',
                '@code("HRS9002")\n@category("machinery")',
            )
        }
    )
    outcome = run(capsys)
    assert outcome.exit_code == 18
    assert "test_second has @category('machinery'), which is not one of" in (
        outcome.printed
    )


@code("HRS0158")
@category("repository")
@objective("conformance")
@negative
def test_an_objective_not_in_the_list_exits_18(tests_folder, capsys):
    """A check whose @objective names no defined objective makes the run exit 18, and
    the message quotes the value and lists the objectives."""
    tests_folder(
        {
            "repo_tools/test_alpha.py": TWO_CHECKS.replace(
                '@code("HRS9002")\n@category("repository")\n@objective("conformance")',
                '@code("HRS9002")\n@category("repository")\n@objective("behaviour")',
            )
        }
    )
    outcome = run(capsys)
    assert outcome.exit_code == 18
    assert "test_second has @objective('behaviour'), which is not one of" in (
        outcome.printed
    )


@code("HRS0178")
@category("repository")
@objective("conformance")
@positive
def test_any_objective_may_carry_a_staged_case(tests_folder, capsys):
    """A check whose objective is not correctness may carry @positive or @negative,
    and its row records that case, because the case says how the check was set up
    rather than what question the check asks."""
    inventory = tests_folder(
        {
            "repo_tools/test_alpha.py": COMPLETENESS_CHECK.replace(
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


@code("HRS0160")
@category("repository")
@objective("conformance")
@negative
@pytest.mark.parametrize("start", ["=", "+", "-", "@"])
def test_a_first_sentence_a_spreadsheet_reads_as_a_formula_exits_18(
    tests_folder, capsys, start
):
    """A check whose first sentence starts with a character a spreadsheet reads as a
    formula makes the run exit 18, and the message names the character and says to
    start with a word."""
    inventory = tests_folder(
        {
            "repo_tools/test_alpha.py": TWO_CHECKS.replace(
                '"""The wrong thing', f'"""{start}The wrong thing'
            )
        }
    )
    outcome = run(capsys)
    assert outcome.exit_code == 18
    assert not inventory.exists()
    assert f"test_second has a first sentence starting with {start!r}" in (
        outcome.printed
    )
    assert "start it with a word" in outcome.printed


@code("HRS0065")
@category("repository")
@objective("conformance")
@negative
def test_duplicate_id_exits_18(tests_folder, capsys):
    """Two checks carrying the same id make the run exit 18, and the message names
    both checks."""
    tests_folder({"repo_tools/test_alpha.py": TWO_CHECKS.replace("HRS9002", "HRS9001")})
    outcome = run(capsys)
    assert outcome.exit_code == 18
    assert "HRS9001 is carried by both test_first and test_second" in outcome.printed


@code("HRS0175")
@category("repository")
@objective("conformance")
@negative
def test_an_id_of_the_wrong_shape_exits_18(tests_folder, capsys):
    """An id that is not three capital letters and four digits makes the run exit 18,
    and the message names the check and says what an id looks like."""
    tests_folder({"repo_tools/test_alpha.py": TWO_CHECKS.replace("HRS9001", "hrs9001")})
    outcome = run(capsys)
    assert outcome.exit_code == 18
    assert (
        "validation/repo_tools/test_alpha.py: test_first has the id 'hrs9001', which "
        "is not three capital letters and four digits" in outcome.printed
    )


@code("HRS0176")
@category("repository")
@objective("conformance")
@negative
def test_an_unregistered_id_prefix_exits_18(tests_folder, capsys):
    """An id whose three letters are not one of the registered prefixes makes the run
    exit 18, and the message names the prefix and lists the ones that are
    registered."""
    tests_folder({"repo_tools/test_alpha.py": TWO_CHECKS.replace("HRS9001", "ZZZ9001")})
    outcome = run(capsys)
    assert outcome.exit_code == 18
    assert (
        "validation/repo_tools/test_alpha.py: test_first has the id ZZZ9001, and ZZZ "
        "is not one of the prefixes" in outcome.printed
    )


@code("HRS0066")
@category("repository")
@objective("conformance")
@negative
def test_unparseable_file_exits_19(tests_folder, capsys):
    """A test file that is not valid Python makes the run exit 19, and the message
    names it."""
    tests_folder({"repo_tools/test_alpha.py": "def broken(:\n"})
    outcome = run(capsys)
    assert outcome.exit_code == 19
    assert "validation/repo_tools/test_alpha.py: cannot parse" in outcome.printed


@code("HRS0067")
@category("repository")
@objective("conformance")
@negative
def test_no_test_files_exits_20(tests_folder, capsys):
    """A validation folder with no test files makes the run exit 20."""
    tests_folder({})
    outcome = run(capsys)
    assert outcome.exit_code == 20
    assert "no test files found" in outcome.printed


#######################################################################################
### Negative checks on the hand-kept columns ###
#
# A hand-kept column that breaks its rule is refused with exit 45 and the row named,
# and nothing is written. A problem with a check's markers outranks it.


@code("HRS0161")
@category("repository")
@objective("conformance")
@negative
def test_a_status_not_in_the_list_exits_45(written, capsys):
    """A row whose status is not one of the five makes the run exit 45, quoting the
    status, and the inventory is not rewritten."""
    with_hand_kept(written, "HRS9002", status="archived")
    before = written.read_text(encoding="utf-8")
    outcome = run(capsys)
    assert outcome.exit_code == 45
    assert written.read_text(encoding="utf-8") == before
    assert "HRS9002 has status 'archived', which is not one of" in outcome.printed


@code("HRS0162")
@category("repository")
@objective("conformance")
@negative
@pytest.mark.parametrize("status", ["inactive", "retired"])
def test_a_status_that_needs_a_reason_without_one_exits_45(written, capsys, status):
    """A removed check marked inactive or retired with status_reason empty makes the
    check-status run exit 45, saying the reason is missing."""
    rows = rows_of(written)
    rows.append(removed_row("HRS9009", status=status))
    write_rows(written, rows)
    outcome = run(capsys, "--check-status")
    assert outcome.exit_code == 45
    assert f"HRS9009 is {status} but status_reason does not say why" in (
        outcome.printed
    )


@code("HRS0163")
@category("repository")
@objective("conformance")
@negative
def test_superseded_without_a_successor_exits_45(written, capsys):
    """A removed check marked superseded with superseded_by empty makes the
    check-status run exit 45, saying no check is named."""
    rows = rows_of(written)
    rows.append(removed_row("HRS9009", status="superseded"))
    write_rows(written, rows)
    outcome = run(capsys, "--check-status")
    assert outcome.exit_code == 45
    assert "HRS9009 is superseded but superseded_by names no check" in outcome.printed


@code("HRS0164")
@category("repository")
@objective("conformance")
@negative
def test_a_successor_on_a_check_not_superseded_exits_45(written, capsys):
    """A row that names checks in superseded_by while its status is not superseded
    makes the run exit 45."""
    with_hand_kept(written, "HRS9002", superseded_by="HRS9001")
    outcome = run(capsys)
    assert outcome.exit_code == 45
    assert "HRS9002 names checks in superseded_by but is active, not superseded" in (
        outcome.printed
    )


@code("HRS0177")
@category("repository")
@objective("conformance")
@negative
def test_a_status_reason_on_a_check_that_is_not_off_exits_45(written, capsys):
    """A row carrying a status_reason while its status is neither inactive nor retired
    makes the run exit 45, because a sentence saying why a check is switched off does
    not belong on one that is running."""
    with_hand_kept(
        written, "HRS9002", status_reason="Switched off while the API moved."
    )
    outcome = run(capsys)
    assert outcome.exit_code == 45
    assert "HRS9002 has a status_reason but is active" in outcome.printed


@code("HRS0165")
@category("repository")
@objective("conformance")
@negative
def test_a_successor_that_is_not_active_exits_45(written, capsys):
    """A superseded row whose superseded_by names a check that is not active in the
    inventory makes the check-status run exit 45, naming that check."""
    rows = rows_of(written)
    rows.append(removed_row("HRS9009", status="superseded", superseded_by="HRS9404"))
    write_rows(written, rows)
    outcome = run(capsys, "--check-status")
    assert outcome.exit_code == 45
    assert "HRS9009 is superseded by HRS9404, which is not an active check" in (
        outcome.printed
    )


@code("HRS0166")
@category("repository")
@objective("conformance")
@negative
def test_a_version_that_is_not_a_whole_number_exits_45(written, capsys):
    """A row whose version is not a whole number from 1 up, such as 1.1, makes the
    run exit 45, quoting the value."""
    with_hand_kept(written, "HRS9002", version="1.1")
    outcome = run(capsys)
    assert outcome.exit_code == 45
    assert "HRS9002 has version '1.1', which is not a whole number" in outcome.printed


@code("HRS0167")
@category("repository")
@objective("conformance")
@negative
def test_a_retired_check_still_in_the_test_files_exits_45(written, capsys):
    """A row marked retired whose check is still in the test files makes the run exit
    45, saying to remove the check or change its status."""
    with_hand_kept(
        written, "HRS9002", status="retired", status_reason="No longer needed."
    )
    outcome = run(capsys)
    assert outcome.exit_code == 45
    assert "HRS9002 is retired but is still in the test files" in outcome.printed


@code("HRS0168")
@category("repository")
@objective("conformance")
@negative
def test_check_status_without_an_inventory_exits_16(tests_folder, capsys):
    """With the check-status option and no inventory on disk, the run exits 16 and
    names the command that writes one."""
    tests_folder({"repo_tools/test_alpha.py": TWO_CHECKS})
    outcome = run(capsys, "--check-status")
    assert outcome.exit_code == 16
    assert "is missing. Run: python repo_tools/build_inventory.py" in outcome.printed


@code("HRS0169")
@category("repository")
@objective("conformance")
@negative
def test_a_marker_problem_outranks_a_hand_kept_problem(written, tests_folder, capsys):
    """When one check has no @objective marker and another row has a status not in
    the list, the run exits 18, and both problems are named."""
    with_hand_kept(written, "HRS9001", status="archived")
    tests_folder(
        {
            "repo_tools/test_alpha.py": TWO_CHECKS.replace(
                '@category("repository")\n@objective("conformance")\n',
                '@category("repository")\n',
            )
        }
    )
    outcome = run(capsys)
    assert outcome.exit_code == 18
    assert "test_second has no @objective marker" in outcome.printed
    assert "HRS9001 has status 'archived'" in outcome.printed
