"""
Script:      test_build_inventory.py
Description: Checks for scripts/build_inventory.py, the hand-run script that
             generates tests/validation_inventory.csv from the checks in the
             test files and, under --check, is the pre-commit hook that refuses
             a commit whose inventory is stale. Each check writes one or two
             small test files to a temporary tests folder, points the script at
             it, and asserts what it writes or which exit code it returns. One
             check runs --check on the real tests/ folder, the same run the
             hook makes.

Inputs:      tests/**/test_*.py and tests/validation_inventory.csv
             (read-only; the one real-folder check)

Outputs:     Writes nothing outside pytest's own temporary folder.

Usage:       pytest tests/scripts/test_build_inventory.py
                 run these checks
             pytest tests/scripts/test_build_inventory.py -v
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
# tests/validation_inventory.csv, assigned once and never reused.
code = pytest.mark.code

# One test file with two well-formed checks, written the way the real files are.
TWO_CHECKS = '''
import pytest

positive = pytest.mark.positive
negative = pytest.mark.negative
code = pytest.mark.code


@code("ABC0001")
@positive
def test_first():
    """The first thing works.

    A second paragraph the inventory must leave out.
    """


@code("ABC0002")
@negative
def test_second():
    """The wrong thing is refused."""
'''


#######################################################################################
### Shared staging ###
#
# One fixture builds a temporary tests folder the script reads in place of the real
# one, and one helper runs the script and keeps what it printed.


@dataclass(frozen=True)
class Outcome:
    """What one run of the script produced."""

    exit_code: int
    printed: str


@pytest.fixture
def tests_folder(tmp_path, monkeypatch):
    """Give a check a function for staging test files the script reads.

    The script's tests folder is pointed at a temporary one, its inventory path at
    a file inside it, and its repo root at the temporary root, so reported names read
    tests/<folder>/<file> as they do for real.

    Returns:
        The staging function, which takes source text keyed by path under tests/.
    """
    root = tmp_path
    tests = root / "tests"
    tests.mkdir()
    monkeypatch.setattr(script, "REPO_ROOT", root)
    monkeypatch.setattr(script, "TESTS_DIR", tests)
    monkeypatch.setattr(script, "INVENTORY_PATH", tests / "validation_inventory.csv")

    def make(files: dict[str, str]) -> Path:
        """Write the given test files under the temporary tests folder.

        Args:
            files: The files to write, source text keyed by path under tests/.

        Returns:
            The path of the inventory the script will write.
        """
        for name, source in files.items():
            target = tests / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(source, encoding="utf-8")
        return tests / "validation_inventory.csv"

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


@pytest.fixture
def generated(tests_folder, capsys) -> list[dict[str, str]]:
    """Stage one test file under tests/scripts/ with two checks, run the script, and
    read the inventory it wrote."""
    inventory = tests_folder({"scripts/test_alpha.py": TWO_CHECKS})
    assert run(capsys).exit_code == 0
    return rows_of(inventory)


#######################################################################################
### Positive checks ###
#
# The right thing works: the rows come from the checks, the hand-kept columns come
# from the existing inventory, --check passes on a current file, and the real
# inventory is current.


@code("HRS0053")
@positive
def test_row_holds_the_check_as_written(generated):
    """A row carries the check's name, id, kind and the first paragraph of its
    docstring as one line, with the second paragraph left out."""
    first = next(r for r in generated if r["check_name"] == "test_first")
    assert first["check_name_code"] == "ABC0001"
    assert first["kind"] == "positive"
    assert first["proves"] == "The first thing works."


@code("HRS0054")
@positive
def test_row_names_the_group_and_the_target(generated):
    """A test file under tests/scripts/ is grouped as scripts, and its target is the
    script of the same name."""
    first = generated[0]
    assert first["type"] == "scripts"
    assert first["target_file"] == "scripts/alpha.py"
    assert first["check_file"] == "tests/scripts/test_alpha.py"


@code("HRS0055")
@positive
def test_new_check_starts_active_at_version_1(generated):
    """A check with no existing row starts with status active and version 1."""
    assert {(r["status"], r["version"]) for r in generated} == {("active", "1")}


@code("HRS0056")
@positive
def test_hand_kept_columns_are_carried_over_by_id(tests_folder, capsys):
    """When the inventory already has a row for a check's id, its status and
    version are kept, whatever else changed."""
    inventory = tests_folder({"scripts/test_alpha.py": TWO_CHECKS})
    assert run(capsys).exit_code == 0
    text = inventory.read_text(encoding="utf-8").replace(
        "ABC0002,negative,The wrong thing is refused.,active,1",
        "ABC0002,negative,The wrong thing is refused.,pending,3",
    )
    inventory.write_text(text, encoding="utf-8")
    assert run(capsys).exit_code == 0
    second = next(r for r in rows_of(inventory) if r["check_name_code"] == "ABC0002")
    assert (second["status"], second["version"]) == ("pending", "3")


@code("HRS0057")
@positive
def test_groups_follow_the_pipeline_order(tests_folder, capsys):
    """Rows are grouped sources, then usdm, then scripts, then tests, whatever
    order the files are found in."""
    inventory = tests_folder(
        {
            "test_report.py": TWO_CHECKS.replace("ABC", "TTT"),
            "scripts/test_alpha.py": TWO_CHECKS.replace("ABC", "SSS"),
            "sources/test_beta.py": TWO_CHECKS,
        }
    )
    assert run(capsys).exit_code == 0
    assert [r["type"] for r in rows_of(inventory)] == [
        "sources",
        "sources",
        "scripts",
        "scripts",
        "tests",
        "tests",
    ]


@code("HRS0058")
@positive
def test_check_passes_when_inventory_is_current(tests_folder, capsys):
    """With the check option, the run exits 0 and writes nothing when the inventory
    on disk equals what would be generated."""
    inventory = tests_folder({"scripts/test_alpha.py": TWO_CHECKS})
    assert run(capsys).exit_code == 0
    before = inventory.stat().st_mtime_ns
    outcome = run(capsys, "--check")
    assert outcome.exit_code == 0
    assert inventory.stat().st_mtime_ns == before
    assert "is current, 2 check(s)" in outcome.printed


@code("HRS0059")
@positive
def test_quiet_prints_nothing(tests_folder, capsys):
    """With the quiet option, nothing is printed; the exit code is the whole
    report."""
    tests_folder({"scripts/test_alpha.py": TWO_CHECKS})
    outcome = run(capsys, "--quiet")
    assert outcome.exit_code == 0
    assert outcome.printed == ""


@code("HRS0060")
@positive
def test_real_inventory_is_current():
    """tests/validation_inventory.csv matches the checks in the real test files,
    which is the run the pre-commit hook makes."""
    assert script.main(["--check", "--quiet"]) == 0


#######################################################################################
### Negative checks ###
#
# The wrong thing is refused, and the message names the cause: a stale inventory, a
# deleted check, a check without its markers, a duplicated id, a file that will not
# parse, and an empty tests folder.


@code("HRS0061")
@negative
def test_check_fails_when_inventory_is_stale_or_missing(tests_folder, capsys):
    """With the check option, the run exits 1 and names the command to run when
    the inventory is missing or no longer matches the checks; nothing is written
    either way."""
    inventory = tests_folder({"scripts/test_alpha.py": TWO_CHECKS})
    outcome = run(capsys, "--check")
    assert outcome.exit_code == 1
    assert not inventory.exists()
    assert "is stale. Run: python scripts/build_inventory.py" in outcome.printed

    assert run(capsys).exit_code == 0
    tests_folder(
        {"scripts/test_alpha.py": TWO_CHECKS.replace("first thing", "other thing")}
    )
    assert run(capsys, "--check").exit_code == 1


@code("HRS0062")
@negative
def test_deleted_check_drops_out(tests_folder, capsys):
    """A row whose check no longer exists in any test file is not written again."""
    inventory = tests_folder({"scripts/test_alpha.py": TWO_CHECKS})
    assert run(capsys).exit_code == 0
    tests_folder({"scripts/test_alpha.py": TWO_CHECKS.split('@code("ABC0002")')[0]})
    assert run(capsys).exit_code == 0
    assert [r["check_name_code"] for r in rows_of(inventory)] == ["ABC0001"]


@code("HRS0063")
@negative
def test_check_without_id_exits_2(tests_folder, capsys):
    """A check with no @code marker makes the run exit 2, naming the file and the
    check, and the inventory is not written."""
    inventory = tests_folder(
        {"scripts/test_alpha.py": TWO_CHECKS.replace('@code("ABC0002")\n', "")}
    )
    outcome = run(capsys)
    assert outcome.exit_code == 2
    assert not inventory.exists()
    assert "tests/scripts/test_alpha.py: test_second has no @code marker" in (
        outcome.printed
    )


@code("HRS0064")
@negative
def test_check_without_kind_exits_2(tests_folder, capsys):
    """A check with neither @positive nor @negative makes the run exit 2, naming
    the file and the check."""
    tests_folder({"scripts/test_alpha.py": TWO_CHECKS.replace("@negative\n", "")})
    outcome = run(capsys)
    assert outcome.exit_code == 2
    assert "test_second has no @positive or @negative marker" in outcome.printed


@code("HRS0065")
@negative
def test_duplicate_id_exits_2(tests_folder, capsys):
    """Two checks carrying the same id make the run exit 2, and the message names
    both checks."""
    tests_folder({"scripts/test_alpha.py": TWO_CHECKS.replace("ABC0002", "ABC0001")})
    outcome = run(capsys)
    assert outcome.exit_code == 2
    assert "ABC0001 is carried by both test_first and test_second" in outcome.printed


@code("HRS0066")
@negative
def test_unparseable_file_exits_3(tests_folder, capsys):
    """A test file that is not valid Python makes the run exit 3, and the message
    names it."""
    tests_folder({"scripts/test_alpha.py": "def broken(:\n"})
    outcome = run(capsys)
    assert outcome.exit_code == 3
    assert "tests/scripts/test_alpha.py: cannot parse" in outcome.printed


@code("HRS0067")
@negative
def test_no_test_files_exits_3(tests_folder, capsys):
    """A tests folder with no test files makes the run exit 3."""
    tests_folder({})
    outcome = run(capsys)
    assert outcome.exit_code == 3
    assert "no test files found" in outcome.printed
