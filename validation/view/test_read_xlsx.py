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

import io
import re
import zipfile
from dataclasses import dataclass

import openpyxl
import pytest

from sdg.view import read_xlsx

positive = pytest.mark.positive
negative = pytest.mark.negative
# Every check carries a @code line: its short, permanent id in
# validation/validation_inventory.csv, assigned once and never reused.
code = pytest.mark.code
# Every check carries an @objective line: why the check exists, one of the
# objectives validation/README.md defines.
objective = pytest.mark.objective

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
@objective("behavior")
@positive
def test_a_name_fragment_finds_the_workbook(inputs, capsys):
    """A fragment of a filename finds the one workbook it matches, so a nested path
    never has to be typed."""
    assert run(capsys, "Terms").exit_code == 0


@code("VIW0019")
@objective("behavior")
@positive
def test_listing_names_every_sheet(inputs, capsys):
    """Naming a workbook without a sheet lists every sheet it holds."""
    printed = run(capsys, "Example_Terms").printed
    assert "terms" in printed
    assert "notes" in printed


@code("VIW0050")
@objective("behavior")
@positive
def test_listing_survives_a_sheet_without_a_dimension_record(inputs, capsys):
    """A workbook whose sheet file carries no dimension record, which some writers
    leave out, is still listed with its sheet named and the counts left blank, rather
    than ending in a traceback."""
    path = inputs / "examples" / "Example_Study.xlsx"
    original = zipfile.ZipFile(path)
    rewritten = io.BytesIO()
    records_removed = 0
    with zipfile.ZipFile(rewritten, "w") as target:
        for item in original.infolist():
            data = original.read(item.filename)
            if item.filename.startswith("xl/worksheets/sheet"):
                data, removed = re.subn(rb"<dimension[^>]*/>", b"", data)
                records_removed += removed
            target.writestr(item, data)
    original.close()
    path.write_bytes(rewritten.getvalue())
    # The staging has to have changed the file, or the check would pass on an
    # ordinary workbook and prove nothing.
    assert records_removed > 0
    outcome = run(capsys, "Example_Study")
    assert outcome.exit_code == 0
    # The sheet is named, and the count columns hold no digits.
    assert re.search(r"study +rows x +cols", outcome.printed)


@code("VIW0020")
@objective("behavior")
@positive
def test_a_sheet_prints_as_a_table(inputs, capsys):
    """A named sheet prints as a table holding the cells it was written with."""
    outcome = run(capsys, "Example_Terms", "--sheet", "terms")
    assert outcome.exit_code == 0
    assert "Screening" in outcome.printed


@code("VIW0021")
@objective("behavior")
@positive
def test_a_sheet_name_matches_whatever_the_case(inputs, capsys):
    """A sheet name is matched whatever its case, so mainTimeline answers to
    maintimeline."""
    assert run(capsys, "Example_Terms", "--sheet", "TERMS").exit_code == 0


@code("VIW0022")
@objective("behavior")
@positive
def test_records_format_prints_one_field_per_line(inputs, capsys):
    """In records format each field is on its own line, which is what makes a sheet
    too wide for a table readable."""
    printed = run(
        capsys, "Example_Terms", "--sheet", "terms", "--format", "records"
    ).printed
    assert "Visit: Screening" in printed


@code("VIW0023")
@objective("behavior")
@positive
def test_an_empty_cell_prints_as_nothing(inputs, capsys):
    """An empty cell prints as blank rather than as the word None, which would fill a
    sparse schedule grid with noise."""
    printed = run(capsys, "Example_Terms", "--sheet", "terms").printed
    assert "None" not in printed


@code("VIW0024")
@objective("behavior")
@positive
def test_a_newline_inside_a_cell_does_not_break_the_row(inputs, capsys):
    """A cell holding a newline is printed on one line, so the row stays aligned."""
    printed = run(capsys, "Example_Terms", "--sheet", "terms").printed
    assert "predose and 1h" in printed


@code("VIW0025")
@objective("behavior")
@positive
def test_find_reports_the_hits_in_one_workbook(inputs, capsys):
    """Searching one workbook reports each cell that contains the term by its sheet
    and row, rather than answering that no cell contains it."""
    outcome = run(capsys, "Example_Terms", "--find", "Screening")
    assert outcome.exit_code == 0
    assert "terms row 2" in outcome.printed
    assert "No cells contain" not in outcome.printed


@code("VIW0026")
@objective("behavior")
@positive
def test_find_with_no_hits_says_so_and_exits_0(inputs, capsys):
    """A search that matches nothing says so and exits 0, because finding nothing is
    an answer rather than a failure."""
    outcome = run(capsys, "Example_Terms", "--find", "nothing matches this")
    assert outcome.exit_code == 0
    assert "No cells contain" in outcome.printed


@code("VIW0027")
@objective("behavior")
@positive
def test_all_searches_every_workbook(inputs, capsys):
    """With --all the search covers every workbook under the inputs folder, not just
    one."""
    printed = run(capsys, "--all", "--find", "Blood sample").printed
    assert "Example_Terms.xlsx" in printed
    assert "Example_Study.xlsx" in printed


@code("VIW0028")
@objective("behavior")
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
@objective("behavior")
@negative
def test_a_sheet_that_does_not_exist_exits_25(inputs, capsys):
    """Naming a sheet the workbook does not hold exits 25 and says to run without
    --sheet to list them."""
    outcome = run(capsys, "Example_Terms", "--sheet", "nowhere")
    assert outcome.exit_code == 25
    assert "Run without --sheet" in outcome.printed


@code("VIW0030")
@objective("behavior")
@negative
def test_a_workbook_that_matches_nothing_exits_26(inputs, capsys):
    """A name matching no workbook exits 26 and repeats the name that was looked
    for."""
    outcome = run(capsys, "Nothing_Like_This")
    assert outcome.exit_code == 26
    assert "Nothing_Like_This" in outcome.printed


@code("VIW0031")
@objective("behavior")
@negative
def test_an_ambiguous_name_exits_26_listing_the_matches(inputs, capsys):
    """A fragment matching more than one workbook exits 26 and lists what it matched,
    so the next attempt can be exact."""
    outcome = run(capsys, "Example")
    assert outcome.exit_code == 26
    assert "Example_Terms.xlsx" in outcome.printed
    assert "Example_Study.xlsx" in outcome.printed


@code("VIW0032")
@objective("behavior")
@negative
def test_all_without_find_is_a_usage_mistake(inputs, capsys):
    """Asking for --all without --find exits 2, the argument parser's own code, because
    it is a mistake in the command line rather than a failure to read anything."""
    with pytest.raises(SystemExit) as raised:
        run(capsys, "--all")
    assert raised.value.code == 2
    assert "--all requires --find" in capsys.readouterr().err


@code("VIW0033")
@objective("behavior")
@negative
def test_no_workbook_named_is_a_usage_mistake(inputs, capsys):
    """Running with no workbook named exits 2 and lists the workbooks a person can
    name."""
    with pytest.raises(SystemExit) as raised:
        run(capsys)
    assert raised.value.code == 2
    assert "Example_Terms.xlsx" in capsys.readouterr().err


#######################################################################################
### Checks on how a workbook is named ###
#
# The command accepts a full path, a path from the repo root, or a filename in any
# case, so a person can type whichever they have to hand.


@code("VIW0061")
@objective("behavior")
@positive
def test_a_full_path_finds_the_workbook(inputs, capsys):
    """A workbook named by its full path is opened."""
    assert run(capsys, str(inputs / "standards" / "Example_Terms.xlsx")).exit_code == 0


@code("VIW0062")
@objective("behavior")
@positive
def test_a_repo_relative_path_finds_the_workbook(inputs, capsys, monkeypatch, tmp_path):
    """A workbook named by its path from the repo root is opened, whichever folder the
    command was started from."""
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    assert run(capsys, "inputs/standards/Example_Terms.xlsx").exit_code == 0


@code("VIW0063")
@objective("behavior")
@positive
def test_a_filename_is_matched_whatever_its_case(inputs, capsys):
    """A filename typed in the wrong case finds the workbook."""
    assert run(capsys, "example_terms.XLSX").exit_code == 0


#######################################################################################
### Checks on long and empty cells ###


@code("VIW0059")
@objective("behavior")
@positive
def test_a_long_cell_is_cut_short_with_an_ellipsis_in_a_table(inputs, capsys):
    """In table format a cell longer than the width limit is cut short and ends with
    an ellipsis, so one long note cannot push the other columns off the screen."""
    long_cell = "x" * (read_xlsx.MAX_CELL_WIDTH + 20)
    write_workbook(
        inputs / "examples" / "Wide_Notes.xlsx", {"notes": [["Note"], [long_cell]]}
    )
    printed = run(capsys, "Wide_Notes", "--sheet", "notes").printed
    assert "x" * (read_xlsx.MAX_CELL_WIDTH - 3) + "..." in printed
    assert long_cell not in printed


@code("VIW0060")
@objective("behavior")
@positive
def test_an_empty_field_is_skipped_in_records_format(inputs, capsys):
    """In records format a row's empty field is left out rather than printed as a
    header with nothing after it, which keeps a sparse grid readable."""
    printed = run(
        capsys, "Example_Terms", "--sheet", "terms", "--format", "records"
    ).printed
    screening = printed.split("--- row 2 ---")[1].split("--- row 3 ---")[0]
    assert "Visit: Screening" in screening
    assert "Note" not in screening


#######################################################################################
### Checks on what a search reports ###


@code("VIW0064")
@objective("behavior")
@positive
def test_a_search_reports_one_hit_per_row(inputs):
    """A row in which the term appears in two cells is reported once, since one line
    is enough to find the row."""
    path = inputs / "examples" / "Repeated.xlsx"
    write_workbook(path, {"pairs": [["Left", "Right"], ["hit here", "hit there"]]})
    assert len(read_xlsx.search_workbook(path, "hit")) == 1


@code("VIW0065")
@objective("behavior")
@positive
def test_a_search_hit_cuts_a_long_cell_short(inputs):
    """A hit in a cell longer than 120 characters shows the first 120 characters and
    an ellipsis, so one wide cell does not dominate the search output."""
    path = inputs / "examples" / "Long_Cell.xlsx"
    long_cell = "hit " + "y" * 150
    write_workbook(path, {"notes": [["Note"], [long_cell]]})
    (hit,) = read_xlsx.search_workbook(path, "hit")
    assert hit.endswith(long_cell[:120] + "...")
