"""
Script:      test_read_xlsx.py
Description: Checks for src/sdg/view/read_xlsx.py, the command that prints a sheet
             out of a pinned workbook. They cover how a workbook is found from
             what a person types, how a sheet is rendered in each format, and
             every refusal the header promises.

             The workbooks are built by openpyxl in pytest's own temporary folder,
             so nothing under inputs/ is opened and no real workbook is needed for
             the checks to run.

Inputs:      Nothing real. Every workbook is written to pytest's own temporary
             folder, which the command's inputs folder is pointed at.

Outputs:     Writes nothing to disk outside pytest's own folder.

Usage:       pytest validation/view/test_read_xlsx.py
                 run these checks
             pytest validation/view/test_read_xlsx.py -v
                 one line per check with its result

Exit codes:  pytest's own: 0 all passed, 1 some failed

Date:        2026-09-15
Owner:       Jason Delosh
"""

from __future__ import annotations

from dataclasses import dataclass

import openpyxl
import pytest

from sdg.view import read_xlsx

positive = pytest.mark.positive
negative = pytest.mark.negative
# Every check carries a @code line: its short, permanent id in
# validation/validation_inventory.csv, assigned once and never reused.
code = pytest.mark.code

# The rows every staged workbook holds. The empty cell and the cell holding a
# newline are here because both appear in the real worked-example spreadsheets.
ROWS = [
    ["Visit", "Activity", "Note"],
    ["Screening", "Vital signs", None],
    ["Day 1", "Blood sample", "predose\nand 1h"],
]


#######################################################################################
### Shared staging ###
#
# One fixture builds a temporary inputs folder holding two workbooks and points the
# command at it. The run helper calls the command in-process and hands back the exit
# code with everything it printed.


@dataclass(frozen=True)
class Outcome:
    """What one run of the command produced."""

    exit_code: int
    printed: str


def write_workbook(path, sheets):
    """Write one workbook with the given sheets.

    Args:
        path: Where the workbook is written. Parent folders are created.
        sheets: The sheet name to rows mapping to write.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook = openpyxl.Workbook()
    workbook.remove(workbook.active)
    for name, rows in sheets.items():
        sheet = workbook.create_sheet(name)
        for row in rows:
            sheet.append(row)
    workbook.save(path)


@pytest.fixture
def inputs(tmp_path, monkeypatch):
    """Give a check a temporary inputs folder holding two workbooks.

    The command works out both its inputs folder and the repo root when it is first
    loaded, so both are pointed at the temporary folder for the length of the check.

    Returns:
        The folder standing in for inputs/.
    """
    root = tmp_path / "repo"
    folder = root / "inputs"
    write_workbook(
        folder / "standards" / "Example_Terms.xlsx",
        {"terms": ROWS, "notes": [["A"], ["B"]]},
    )
    write_workbook(folder / "examples" / "Example_Study.xlsx", {"study": ROWS})
    monkeypatch.setattr(read_xlsx, "INPUTS_DIR", folder)
    monkeypatch.setattr(read_xlsx, "REPO_ROOT", root)
    return folder


def run(capsys, *argv):
    """Run the command in-process with the given arguments.

    Args:
        capsys: pytest's capture of what was printed.
        *argv: The command-line arguments to hand the command.

    Returns:
        The exit code and what was printed, as an Outcome.
    """
    exit_code = read_xlsx.main(list(argv))
    captured = capsys.readouterr()
    return Outcome(exit_code, captured.out + captured.err)


#######################################################################################
### Positive checks ###
#
# The right thing works: a workbook is found from a fragment of its name, its sheets
# are listed, one sheet prints in either format, a search reports its hits, and the
# cell values that would otherwise break a row are handled.


@code("VIW0018")
@positive
def test_a_name_fragment_finds_the_workbook(inputs, capsys):
    """A fragment of a filename finds the one workbook it matches, so a nested path
    never has to be typed."""
    assert run(capsys, "Terms").exit_code == 0


@code("VIW0019")
@positive
def test_listing_names_every_sheet(inputs, capsys):
    """Naming a workbook without a sheet lists every sheet it holds."""
    printed = run(capsys, "Example_Terms").printed
    assert "terms" in printed
    assert "notes" in printed


@code("VIW0020")
@positive
def test_a_sheet_prints_as_a_table(inputs, capsys):
    """A named sheet prints as a table holding the cells it was written with."""
    outcome = run(capsys, "Example_Terms", "--sheet", "terms")
    assert outcome.exit_code == 0
    assert "Screening" in outcome.printed


@code("VIW0021")
@positive
def test_a_sheet_name_matches_whatever_the_case(inputs, capsys):
    """A sheet name is matched whatever its case, so mainTimeline answers to
    maintimeline."""
    assert run(capsys, "Example_Terms", "--sheet", "TERMS").exit_code == 0


@code("VIW0022")
@positive
def test_records_format_prints_one_field_per_line(inputs, capsys):
    """In records format each field is on its own line, which is what makes a sheet
    too wide for a table readable."""
    printed = run(
        capsys, "Example_Terms", "--sheet", "terms", "--format", "records"
    ).printed
    assert "Visit: Screening" in printed


@code("VIW0023")
@positive
def test_an_empty_cell_prints_as_nothing(inputs, capsys):
    """An empty cell prints as blank rather than as the word None, which would fill a
    sparse schedule grid with noise."""
    printed = run(capsys, "Example_Terms", "--sheet", "terms").printed
    assert "None" not in printed


@code("VIW0024")
@positive
def test_a_newline_inside_a_cell_does_not_break_the_row(inputs, capsys):
    """A cell holding a newline is printed on one line, so the row stays aligned."""
    printed = run(capsys, "Example_Terms", "--sheet", "terms").printed
    assert "predose and 1h" in printed


@code("VIW0025")
@positive
def test_find_reports_the_hits_in_one_workbook(inputs, capsys):
    """Searching one workbook reports the cells that contain the term."""
    outcome = run(capsys, "Example_Terms", "--find", "Screening")
    assert outcome.exit_code == 0
    assert "Screening" in outcome.printed


@code("VIW0026")
@positive
def test_find_with_no_hits_says_so_and_exits_0(inputs, capsys):
    """A search that matches nothing says so and exits 0, because finding nothing is
    an answer rather than a failure."""
    outcome = run(capsys, "Example_Terms", "--find", "nothing matches this")
    assert outcome.exit_code == 0
    assert "No cells contain" in outcome.printed


@code("VIW0027")
@positive
def test_all_searches_every_workbook(inputs, capsys):
    """With --all the search covers every workbook under the inputs folder, not just
    one."""
    printed = run(capsys, "--all", "--find", "Blood sample").printed
    assert "Example_Terms.xlsx" in printed
    assert "Example_Study.xlsx" in printed


@code("VIW0028")
@positive
def test_an_excel_lock_file_is_not_a_workbook(inputs, capsys):
    """A ~$ lock file that Excel leaves beside an open workbook is left out of
    discovery, because opening one raises rather than reading."""
    (inputs / "standards" / "~$Example_Terms.xlsx").write_bytes(b"lock")
    assert read_xlsx.find_workbooks() == sorted(
        p for p in inputs.rglob("*.xlsx") if not p.name.startswith("~$")
    )


#######################################################################################
### Negative checks ###
#
# The wrong thing is refused. Each check breaks one thing, and asserts the exit code
# and that the message names that cause and what to do instead.


@code("VIW0029")
@negative
def test_a_sheet_that_does_not_exist_exits_25(inputs, capsys):
    """Naming a sheet the workbook does not hold exits 25 and says to run without
    --sheet to list them."""
    outcome = run(capsys, "Example_Terms", "--sheet", "nowhere")
    assert outcome.exit_code == 25
    assert "Run without --sheet" in outcome.printed


@code("VIW0030")
@negative
def test_a_workbook_that_matches_nothing_exits_26(inputs, capsys):
    """A name matching no workbook exits 26 and repeats the name that was looked
    for."""
    outcome = run(capsys, "Nothing_Like_This")
    assert outcome.exit_code == 26
    assert "Nothing_Like_This" in outcome.printed


@code("VIW0031")
@negative
def test_an_ambiguous_name_exits_26_listing_the_matches(inputs, capsys):
    """A fragment matching more than one workbook exits 26 and lists what it matched,
    so the next attempt can be exact."""
    outcome = run(capsys, "Example")
    assert outcome.exit_code == 26
    assert "Example_Terms.xlsx" in outcome.printed
    assert "Example_Study.xlsx" in outcome.printed


@code("VIW0032")
@negative
def test_all_without_find_is_a_usage_mistake(inputs, capsys):
    """Asking for --all without --find exits 2, the argument parser's own code, because
    it is a mistake in the command line rather than a failure to read anything."""
    with pytest.raises(SystemExit) as raised:
        run(capsys, "--all")
    assert raised.value.code == 2


@code("VIW0033")
@negative
def test_no_workbook_named_is_a_usage_mistake(inputs, capsys):
    """Running with no workbook named exits 2 and lists the workbooks a person can
    name."""
    with pytest.raises(SystemExit) as raised:
        run(capsys)
    assert raised.value.code == 2
    assert "Example_Terms.xlsx" in capsys.readouterr().err
