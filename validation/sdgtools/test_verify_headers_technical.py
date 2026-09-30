"""
Script:      test_verify_headers_technical.py
Description: Checks for src/sdgtools/verify_headers.py, the hand-run script the
             pre-commit hook runs to refuse a commit whose Python files lack
             the full header block. Each check writes one or two small files to
             a temporary folder, points the script's checked folders at it,
             runs main() in-process, and asserts the exit code or the problem
             line the header promises. The runs over the real code folders, the
             same run the pre-commit hook makes, are in
             test_verify_headers_conformance.py, beside this file.

Inputs:      Nothing real. Each staged file and exit-code table is written to
             pytest's own temporary folder.

Outputs:     Writes nothing outside pytest's own temporary folder.

Usage:       pytest validation/sdgtools/test_verify_headers_technical.py
                 run these checks
             pytest validation/sdgtools/test_verify_headers_technical.py -v
                 one line per check with its result

Exit codes:  None of its own. It runs inside pytest.

Date:        2026-09-11
Owner:       Jason Delosh
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass

import pytest

from sdg.exit_codes import GROUPS, exit_line
from sdgtools import verify_headers as script
from sdgval.labels import category, code, negative, objective, positive

# A complete header in this repo's convention, with the eight fields in order.
GOOD_HEADER = '''"""
Script:      alpha.py
Description: Does the first thing.
Inputs:      nothing
Outputs:     nothing
Usage:       alpha
Exit codes:  0   SUCCEEDED  the command succeeded
Date:        2026-09-04
Owner:       Jason Delosh
"""
'''

# The one entry most checks stage beside success, as a header writes it.
NOT_DOWNLOADED = "12  PINNED-FILE-NOT-DOWNLOADED  a pinned file has not been downloaded"


def table_text(*extra: list[str], groups: dict[int, str] | None = None) -> str:
    """Write a staged exit-code table.

    It holds a row for every group, success, a pinned file not downloaded, and any
    further rows given, so it is well formed unless a check breaks it on purpose.

    Args:
        *extra: Further rows, each as its code, group, sub-code, what happened and
            what to do.
        groups: The groups to write, or None for the real ones.

    Returns:
        The table as CSV text.
    """
    groups = GROUPS if groups is None else groups
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["code", "group", "sub_code", "what_happened", "what_to_do"])
    writer.writerow([0, groups[0], "SUCCEEDED", "the command succeeded", "Nothing."])
    writer.writerow(
        [
            12,
            groups[12],
            "PINNED-FILE-NOT-DOWNLOADED",
            "a pinned file has not been downloaded",
            "Run acquire_sources.",
        ]
    )
    for number, group in groups.items():
        if number not in (0, 12):
            writer.writerow([number, group, "", "no command fails this way yet", ""])
    for row in extra:
        writer.writerow(row)
    return buffer.getvalue()


#######################################################################################
### Shared staging ###
#
# One fixture builds a folder the script checks in place of the real package, and one
# helper runs the script and keeps what it printed. The situation most checks share,
# a folder where every header is complete, is staged once.


@dataclass(frozen=True)
class Outcome:
    """What one run of the script produced."""

    exit_code: int
    printed: str


@pytest.fixture
def folder(tmp_path, monkeypatch):
    """Give a check a function for staging the files the script checks.

    The script's checked folders are pointed at one folder under a temporary root,
    and its repo root at that root, so a reported name reads src/sdg/<file> as it
    does for the real package.

    Returns:
        The staging function, which takes source text keyed by file name.
    """
    checked = tmp_path / "src" / "sdg"
    checked.mkdir(parents=True)
    monkeypatch.setattr(script, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(script, "CHECKED_FOLDERS", (checked,))

    # The exit-code table is staged too, so no check reads the real one and a
    # check about a wrong entry can say what the right one is.
    table = tmp_path / "exit_codes.csv"
    table.write_text(table_text(), encoding="utf-8")
    monkeypatch.setattr(script, "EXIT_CODES_FILE", table)

    def make(files: dict[str, str]) -> None:
        """Write the given files into the checked folder.

        Args:
            files: The files to write, source text keyed by file name.
        """
        for name, source in files.items():
            (checked / name).write_text(source, encoding="utf-8")

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


@pytest.fixture
def complete(folder, capsys) -> Outcome:
    """Stage one file with a complete header, and run the script."""
    folder({"alpha.py": GOOD_HEADER})
    return run(capsys)


#######################################################################################
### Positive checks ###
#
# The right thing works: complete headers pass silently, a package marker file is
# not held to the header rule, and the real folders pass the same run the pre-commit
# hook makes from .pre-commit-config.yaml.


@code("SA00345")
@category("repository")
@objective("functionality")
@positive
def test_complete_header_exits_0(complete):
    """A file whose header holds the eight fields in order makes the run exit 0."""
    assert complete.exit_code == 0


@code("SA00346")
@category("repository")
@objective("functionality")
@positive
def test_complete_header_prints_nothing(complete):
    """When every header is complete, nothing is printed."""
    assert complete.printed == ""


@code("SA00347")
@category("repository")
@objective("functionality")
@positive
def test_init_file_is_skipped(folder, capsys):
    """A package marker file with a one-paragraph docstring and no header block is not a
    problem, since it names its folder rather than describing a script."""
    folder({"alpha.py": GOOD_HEADER, "__init__.py": '"""The package."""\n'})
    assert run(capsys).exit_code == 0


#######################################################################################
### Negative checks ###
#
# The wrong thing is refused, and the problem line names the file and the cause: a
# missing field, fields out of order, a Date that is not a plain calendar date, a
# file with no docstring at all, and a file that is not valid Python or is not saved
# as UTF-8 text.
# With the quiet option, a refusal prints nothing and its exit code still names the
# cause.


@code("SA00348")
@category("repository")
@objective("functionality")
@negative
def test_quiet_prints_nothing(folder, capsys):
    """With the quiet option, nothing is printed even when a header is incomplete. The
    exit code is the whole report."""
    folder({"alpha.py": GOOD_HEADER.replace("Owner:       Jason Delosh\n", "")})
    outcome = run(capsys, "--quiet")
    assert outcome.exit_code == 15
    assert outcome.printed == ""


@code("SA00349")
@category("repository")
@objective("functionality")
@negative
def test_missing_fields_exit_15(folder, capsys):
    """A header lacking fields makes the run exit 15, and the problem line names the
    file and every missing field."""
    folder(
        {
            "alpha.py": GOOD_HEADER.replace("Outputs:     nothing\n", "").replace(
                "Owner:       Jason Delosh\n", ""
            )
        }
    )
    outcome = run(capsys)
    assert outcome.exit_code == 15
    assert exit_line(15, "HEADER-INCOMPLETE") in outcome.printed
    assert "src/sdg/alpha.py: missing Outputs, Owner" in outcome.printed


@code("SA00350")
@category("repository")
@objective("functionality")
@negative
def test_fields_out_of_order_exit_15(folder, capsys):
    """A header with its fields in the wrong order makes the run exit 15, and the
    problem line says so and shows the order found."""
    swapped = GOOD_HEADER.replace(
        "Date:        2026-09-04\nOwner:       Jason Delosh\n",
        "Owner:       Jason Delosh\nDate:        2026-09-04\n",
    )
    folder({"alpha.py": swapped})
    outcome = run(capsys)
    assert outcome.exit_code == 15
    assert exit_line(15, "HEADER-INCOMPLETE") in outcome.printed
    assert "src/sdg/alpha.py: fields out of order" in outcome.printed
    assert "Owner, Date" in outcome.printed


@code("SA00351")
@category("repository")
@objective("functionality")
@negative
def test_bad_date_exits_15(folder, capsys):
    """A Date that is not a plain calendar date makes the run exit 15, and the
    problem line quotes the value found."""
    folder({"alpha.py": GOOD_HEADER.replace("2026-09-04", "September 2026")})
    outcome = run(capsys)
    assert outcome.exit_code == 15
    assert exit_line(15, "HEADER-INCOMPLETE") in outcome.printed
    assert "src/sdg/alpha.py: Date is 'September 2026', not YYYY-MM-DD" in (
        outcome.printed
    )


@code("SA00352")
@category("repository")
@objective("functionality")
@negative
def test_no_docstring_exits_15(folder, capsys):
    """A file with no docstring at the top has no header block at all, and the run exits
    15 with a problem line saying so."""
    folder({"alpha.py": "print('hello')\n"})
    outcome = run(capsys)
    assert outcome.exit_code == 15
    assert exit_line(15, "HEADER-MISSING") in outcome.printed
    assert "src/sdg/alpha.py: no module docstring" in outcome.printed


@code("SA00353")
@category("repository")
@objective("functionality")
@negative
def test_unparseable_file_exits_14(folder, capsys):
    """A file that is not valid Python makes the run exit 14, and the problem line
    says it cannot be parsed."""
    folder({"alpha.py": "def broken(:\n"})
    outcome = run(capsys)
    assert outcome.exit_code == 14
    assert exit_line(14, "PYTHON-UNPARSEABLE") in outcome.printed
    assert "src/sdg/alpha.py: cannot parse" in outcome.printed


@code("SA00354")
@category("repository")
@objective("functionality")
@negative
def test_unparseable_outranks_incomplete(folder, capsys):
    """When one file cannot be parsed and another has no header, the file that cannot
    be parsed decides the exit line, and both problems are still named."""
    folder({"alpha.py": "def broken(:\n", "beta.py": "print('no header')\n"})
    outcome = run(capsys)
    assert outcome.exit_code == 14
    assert exit_line(14, "PYTHON-UNPARSEABLE") in outcome.printed
    assert "alpha.py: cannot parse" in outcome.printed
    assert "beta.py: no module docstring" in outcome.printed


@code("SA00590")
@category("repository")
@objective("functionality")
@negative
def test_a_file_not_saved_as_utf8_exits_14(folder, capsys):
    """A file that is not saved as UTF-8 text makes the run exit 14, and the problem
    line names the file and says it is not saved as UTF-8 text."""
    folder({})
    (script.CHECKED_FOLDERS[0] / "alpha.py").write_bytes(GOOD_HEADER.encode("utf-16"))
    outcome = run(capsys)
    assert outcome.exit_code == 14
    assert exit_line(14, "PYTHON-NOT-UTF8") in outcome.printed
    assert "src/sdg/alpha.py: cannot parse, because it is not saved as UTF-8 text" in (
        outcome.printed
    )


#######################################################################################
### Checks on the exit codes a header names ###
#
# Each entry is the exit number, the sub-code and what happened, all three as the
# table has them. A file-specific aside may follow the wording in brackets. These
# checks stage a header whose Exit codes field is right, then wrong in one way at a
# time.


def with_codes(lines: str) -> str:
    """Build a complete header whose Exit codes field holds the given lines.

    Args:
        lines: The Exit codes field, written as it appears in a header.

    Returns:
        The whole header block.
    """
    return GOOD_HEADER.replace(
        "Exit codes:  0   SUCCEEDED  the command succeeded", f"Exit codes:  {lines}"
    )


@code("SA00355")
@category("repository")
@objective("functionality")
@positive
def test_wording_from_the_table_passes(folder, capsys):
    """An entry written with the number, sub-code and wording docs/exit_codes.csv gives
    it passes."""
    folder({"alpha.py": with_codes(NOT_DOWNLOADED)})
    assert run(capsys).exit_code == 0


@code("SA00356")
@category("repository")
@objective("functionality")
@positive
def test_a_bracketed_aside_is_allowed(folder, capsys):
    """An entry may add a bracketed aside after the wording in docs/exit_codes.csv, saying what the
    failure means in that file."""
    folder({"alpha.py": with_codes(NOT_DOWNLOADED + " (a dry run only)")})
    assert run(capsys).exit_code == 0


@code("SA00357")
@category("repository")
@objective("functionality")
@positive
def test_a_wrapped_entry_is_read_as_one(folder, capsys):
    """An entry too long for one line is joined before it is compared, so wrapping it
    does not make it disagree. The entry wraps inside the table's wording, and another
    entry follows it."""
    folder(
        {
            "alpha.py": with_codes(
                "12  PINNED-FILE-NOT-DOWNLOADED  a pinned file has not\n"
                "                 been downloaded\n"
                "             0   SUCCEEDED  the command succeeded"
            )
        }
    )
    assert run(capsys).exit_code == 0


@code("SA00358")
@category("repository")
@objective("functionality")
@positive
def test_a_lone_wrapped_entry_keeps_its_second_line(folder, capsys):
    """An entry that runs onto a second line and ends the field keeps its second line.
    So a header holding one long entry is not refused as disagreeing with
    docs/exit_codes.csv."""
    folder(
        {
            "alpha.py": with_codes(
                "12  PINNED-FILE-NOT-DOWNLOADED  a pinned file has not been\n"
                "                 downloaded"
            )
        }
    )
    assert run(capsys).exit_code == 0


@code("SA00359")
@category("repository")
@objective("functionality")
@positive
def test_the_closing_prose_is_not_read_as_an_entry(folder, capsys):
    """The sentence a field ends with is not mistaken for an entry, so it is never
    compared with docs/exit_codes.csv."""
    folder(
        {
            "alpha.py": with_codes(
                "0   SUCCEEDED  the command succeeded\n"
                "             The wording is the repo-wide table."
            )
        }
    )
    assert run(capsys).exit_code == 0


@code("SA00360")
@category("repository")
@objective("functionality")
@negative
def test_a_sub_code_the_table_lacks_exits_16(folder, capsys):
    """An entry for a sub-code docs/exit_codes.csv does not hold makes the run exit 16,
    and the problem line names the file and the sub-code."""
    folder({"alpha.py": with_codes("9   NOBODY-AGREED  something nobody agreed on")})
    outcome = run(capsys)
    assert outcome.exit_code == 16
    assert exit_line(16, "HEADER-EXIT-CODES-DISAGREE") in outcome.printed
    assert "src/sdg/alpha.py: the sub-code NOBODY-AGREED is not in" in outcome.printed


@code("SA00361")
@category("repository")
@objective("functionality")
@negative
def test_different_wording_exits_16(folder, capsys):
    """An entry giving a sub-code a second meaning makes the run exit 16, and the
    problem line prints what the header says beside what docs/exit_codes.csv says."""
    folder(
        {
            "alpha.py": with_codes(
                "12  PINNED-FILE-NOT-DOWNLOADED  the file is missing somehow"
            )
        }
    )
    outcome = run(capsys)
    assert outcome.exit_code == 16
    assert exit_line(16, "HEADER-EXIT-CODES-DISAGREE") in outcome.printed
    assert "the file is missing somehow" in outcome.printed
    assert "a pinned file has not been downloaded" in outcome.printed


@code("SA00362")
@category("repository")
@objective("functionality")
@negative
def test_an_incomplete_header_outranks_a_wrong_code(folder, capsys):
    """When one file has no header and another has a wrong entry, the missing header
    decides the exit line, because a header that cannot be read is the worse problem.
    Both problems are named."""
    folder(
        {
            "alpha.py": "print('no header')\n",
            "beta.py": with_codes("9   NOBODY-AGREED  something nobody agreed on"),
        }
    )
    outcome = run(capsys)
    assert outcome.exit_code == 15
    assert exit_line(15, "HEADER-MISSING") in outcome.printed
    assert "no module docstring" in outcome.printed
    assert "the sub-code NOBODY-AGREED is not in" in outcome.printed


@code("SA00363")
@category("repository")
@objective("functionality")
@negative
def test_a_missing_table_exits_12(folder, monkeypatch, capsys):
    """With docs/exit_codes.csv missing, the run exits 12, says the file is missing and
    to restore it from git, rather than reporting every file as disagreeing with
    nothing."""
    folder({"alpha.py": GOOD_HEADER})
    monkeypatch.setattr(script, "EXIT_CODES_FILE", script.REPO_ROOT / "gone.csv")
    outcome = run(capsys)
    assert outcome.exit_code == 12
    assert exit_line(12, "EXIT-TABLE-MISSING") in outcome.printed
    assert "is missing" in outcome.printed
    assert "restore docs/exit_codes.csv from git" in outcome.printed


@code("SA00364")
@category("repository")
@objective("functionality")
@negative
@pytest.mark.parametrize(
    ("row", "said"),
    [
        (
            ["thirteen", GROUPS[13], "A-B", "x", ""],
            "is not a whole number from 0 to 125",
        ),
        (["126", GROUPS[13], "A-B", "x", ""], "is not a whole number from 0 to 125"),
        (
            [str(max(GROUPS) + 1), "a group nobody made", "A-B", "x", ""],
            "is not a group in GROUPS",
        ),
        (["13", GROUPS[13], "not a sub code", "x", ""], "is not words in capitals"),
        (["13", GROUPS[13], "SUCCEEDED", "x", ""], "SUCCEEDED is listed twice"),
        (["13"], "has fewer columns than the table's header"),
        (["13", GROUPS[13], "A-B", "x"], "has fewer columns than the table's header"),
    ],
    ids=[
        "a code that is not a number",
        "a code above 125",
        "a code with no group",
        "a sub-code of the wrong form",
        "a sub-code listed twice",
        "a row with too few columns",
        "a row missing only what to do",
    ],
)
def test_a_table_row_that_breaks_the_rules_exits_15(folder, capsys, row, said):
    """A row of docs/exit_codes.csv that breaks the table's rules makes the run exit 15
    before any file is read, and the message names what is wrong with the row and says
    to correct it, rather than ending in a Python error. It runs once for each rule a
    row can break.

    A file with no header block is staged too, and nothing about it is printed, which
    shows no file was read."""
    folder({"alpha.py": GOOD_HEADER, "beta.py": "x = 1\n"})
    script.EXIT_CODES_FILE.write_text(table_text(row), encoding="utf-8")
    outcome = run(capsys)
    assert outcome.exit_code == 15
    assert exit_line(15, "EXIT-TABLE-INVALID") in outcome.printed
    assert said in outcome.printed
    assert "correct that row" in outcome.printed
    assert "beta.py" not in outcome.printed


@code("SA00654")
@category("repository")
@objective("functionality")
@negative
@pytest.mark.parametrize(
    ("groups", "said"),
    [
        ({**GROUPS, 9: "the network is down"}, "the group of code 9 is"),
        ({k: v for k, v in GROUPS.items() if k != 22}, "22 are groups"),
    ],
    ids=["a group worded differently", "a group with no row"],
)
def test_a_table_that_disagrees_with_the_groups_exits_16(folder, capsys, groups, said):
    """A table whose groups disagree with GROUPS in src/sdg/exit_codes.py, because one
    is worded differently or one has no row, makes the run exit 16 before any file is
    read, and the message names the group. It runs once for each way to disagree.

    A file with no header block is staged too, and nothing about it is printed, which
    shows no file was read."""
    folder({"alpha.py": GOOD_HEADER, "beta.py": "x = 1\n"})
    script.EXIT_CODES_FILE.write_text(table_text(groups=groups), encoding="utf-8")
    outcome = run(capsys)
    assert outcome.exit_code == 16
    assert exit_line(16, "EXIT-GROUPS-DISAGREE") in outcome.printed
    assert said in outcome.printed
    assert "beta.py" not in outcome.printed


@code("SA00587")
@category("repository")
@objective("functionality")
@negative
def test_an_entry_under_another_number_exits_16(folder, capsys):
    """An entry that lists a sub-code under a number other than the table's, such as
    one above 125, makes the run exit 16, and the problem line names both numbers."""
    folder(
        {
            "alpha.py": with_codes(
                "126  PINNED-FILE-NOT-DOWNLOADED  a pinned file has not been downloaded"
            )
        }
    )
    outcome = run(capsys)
    assert outcome.exit_code == 16
    assert exit_line(16, "HEADER-EXIT-CODES-DISAGREE") in outcome.printed
    assert (
        "PINNED-FILE-NOT-DOWNLOADED is listed under 126, and the table gives it 12"
        in outcome.printed
    )


@code("SA00589")
@category("repository")
@objective("functionality")
@negative
def test_wording_that_reads_like_another_problem_still_exits_16(folder, capsys):
    """An entry that gives a sub-code a second meaning exits 16 with the wording named,
    even when the wording holds the words another kind of problem prints, because each
    problem carries its own sub-code and the wording of a message never chooses it."""
    folder(
        {
            "alpha.py": with_codes(
                "12  PINNED-FILE-NOT-DOWNLOADED  the header does not list it"
            )
        }
    )
    outcome = run(capsys)
    assert outcome.exit_code == 16
    assert exit_line(16, "HEADER-EXIT-CODES-DISAGREE") in outcome.printed
    assert "PINNED-FILE-NOT-DOWNLOADED says 'the header does not list it'" in (
        outcome.printed
    )


#######################################################################################
### Checks on the exit numbers and sub-codes the code names ###
#
# The code names each failure it reports by its number and sub-code together, as in
# fail(say, 12, "PINNED-FILE-NOT-DOWNLOADED", message), or in an error class's
# exit_code and sub_code. Each pair has to be a row of the table, whatever file it is
# in, and a command's header has to list each one its own code names.


@code("SA00655")
@category("repository")
@objective("functionality")
@negative
@pytest.mark.parametrize(
    ("source", "said"),
    [
        (
            'failure = (12, "NOBODY-AGREED")\n',
            "names the sub-code NOBODY-AGREED, which is not in",
        ),
        (
            'failure = (9, "PINNED-FILE-NOT-DOWNLOADED")\n',
            "names PINNED-FILE-NOT-DOWNLOADED with exit 9, and the table gives it 12",
        ),
        (
            "class Refused(Exception):\n"
            "    exit_code = 9\n"
            '    sub_code = "PINNED-FILE-NOT-DOWNLOADED"\n',
            "names PINNED-FILE-NOT-DOWNLOADED with exit 9, and the table gives it 12",
        ),
    ],
    ids=["a sub-code the table lacks", "a wrong number", "an error class"],
)
def test_a_pair_the_table_does_not_hold_exits_16(folder, capsys, source, said):
    """An exit number and sub-code the code names together that the table does not
    hold, in any file, make the run exit 16, and the problem line names the pair. It
    runs once for a sub-code the table lacks, a number the table gives otherwise, and
    the same wrong number set in an error class."""
    folder({"alpha.py": GOOD_HEADER + "\n" + source})
    outcome = run(capsys)
    assert outcome.exit_code == 16
    assert exit_line(16, "HEADER-EXIT-CODES-DISAGREE") in outcome.printed
    assert said in outcome.printed


def with_main(returns: str, codes: str = "0   SUCCEEDED  the command succeeded") -> str:
    """Build a file whose header lists the given codes and whose main() returns.

    Args:
        returns: The body of main(), written as the lines inside the function.
        codes: The Exit codes field, written as it appears in a header.

    Returns:
        The whole file, header and code.
    """
    return with_codes(codes) + "\n\ndef main(argv=None):\n" + returns + "\n"


@code("SA00656")
@category("repository")
@objective("functionality")
@negative
def test_a_sub_code_a_command_names_but_does_not_list_exits_16(folder, capsys):
    """A command whose code ends on a sub-code its header does not list makes the run
    exit 16, and the problem line names the sub-code."""
    folder(
        {
            "alpha.py": with_main(
                '    return fail(print, 12, "PINNED-FILE-NOT-DOWNLOADED", "gone")'
            )
        }
    )
    outcome = run(capsys)
    assert outcome.exit_code == 16
    assert exit_line(16, "HEADER-EXIT-CODE-UNLISTED") in outcome.printed
    assert (
        "the code ends on PINNED-FILE-NOT-DOWNLOADED but the header does not list it"
        in outcome.printed
    )


@code("SA00657")
@category("repository")
@objective("functionality")
@positive
def test_a_listed_sub_code_a_command_names_passes(folder, capsys):
    """A command whose code ends on a sub-code its header lists, with the table's
    number and wording, passes."""
    folder(
        {
            "alpha.py": with_main(
                '    return fail(print, 12, "PINNED-FILE-NOT-DOWNLOADED", "gone")',
                "0   SUCCEEDED  the command succeeded\n             " + NOT_DOWNLOADED,
            )
        }
    )
    assert run(capsys).exit_code == 0


#######################################################################################
### Checks on the codes main() returns ###
#
# A header can list every entry correctly and still forget a number the code
# returns. These checks stage a file with a main() and compare what it returns with
# what it lists. A file with a main() also has to list at least one entry, while a
# file with no main() may describe its codes in a sentence.


@code("SA00365")
@category("repository")
@objective("functionality")
@positive
def test_a_listed_return_passes(folder, capsys):
    """An exit code that the tool can return and that its header lists passes."""
    folder({"alpha.py": with_main("    return 0")})
    assert run(capsys).exit_code == 0


@code("SA00366")
@category("repository")
@objective("functionality")
@positive
def test_a_return_of_a_call_is_passed_over(folder, capsys):
    """A return of something other than a plain number is passed over rather than
    guessed at, so a computed exit code is never reported as unlisted."""
    folder({"alpha.py": with_main("    return len(argv or [])")})
    assert run(capsys).exit_code == 0


@code("SA00367")
@category("repository")
@objective("functionality")
@positive
def test_a_listed_code_that_is_never_returned_is_not_a_problem(folder, capsys):
    """A header may list a code the tool never returns as a plain number, because only
    codes a header forgot are looked for."""
    folder(
        {
            "alpha.py": with_main(
                "    return 0",
                "0   SUCCEEDED  the command succeeded\n             " + NOT_DOWNLOADED,
            )
        }
    )
    assert run(capsys).exit_code == 0


@code("SA00368")
@category("repository")
@objective("functionality")
@positive
def test_a_nested_helpers_return_is_not_read_as_mains(folder, capsys):
    """A number returned by a helper inside the tool's main function belongs to the
    helper, so a header that does not list it is not refused."""
    folder(
        {
            "alpha.py": with_main(
                "    def helper():\n        return 99\n    helper()\n    return 0"
            )
        }
    )
    assert run(capsys).exit_code == 0


@code("SA00369")
@category("repository")
@objective("functionality")
@negative
def test_an_unlisted_return_exits_16(folder, capsys):
    """A code the tool returns that the header does not list makes the run exit 16, and
    the problem line names the file and the number."""
    folder({"alpha.py": with_main("    return 8")})
    outcome = run(capsys)
    assert outcome.exit_code == 16
    assert exit_line(16, "HEADER-EXIT-CODE-UNLISTED") in outcome.printed
    assert "exit code 8 is returned by main()" in outcome.printed


@code("SA00370")
@category("repository")
@objective("functionality")
@pytest.mark.parametrize(
    "choice",
    ["    return 8 if argv else 0", "    return 0 if argv else 8"],
    ids=["unlisted code first", "unlisted code second"],
)
@negative
def test_both_sides_of_a_one_line_choice_are_read(folder, capsys, choice):
    """A return written as a one-line choice is read on both sides, so the branch that
    is not listed is still caught whichever side it sits on."""
    folder({"alpha.py": with_main(choice)})
    outcome = run(capsys)
    assert outcome.exit_code == 16
    assert exit_line(16, "HEADER-EXIT-CODE-UNLISTED") in outcome.printed
    assert "exit code 8 is returned by main()" in outcome.printed


@code("SA00371")
@category("repository")
@objective("functionality")
@negative
def test_an_incomplete_header_outranks_a_forgotten_code(folder, capsys):
    """When one file has no header and another forgets a code it returns, the missing
    header decides the exit line, because a header that cannot be read is the worse
    problem. Both problems are named."""
    folder(
        {
            "alpha.py": "print('no header')\n",
            "beta.py": with_main("    return 8").replace("alpha.py", "beta.py"),
        }
    )
    outcome = run(capsys)
    assert outcome.exit_code == 15
    assert exit_line(15, "HEADER-MISSING") in outcome.printed
    assert "no module docstring" in outcome.printed
    assert "exit code 8 is returned by main()" in outcome.printed


@code("SA00372")
@category("repository")
@objective("functionality")
@negative
def test_a_forgotten_code_outranks_a_reworded_one(folder, capsys):
    """When one file forgets a code and another rewords one, the forgotten code decides
    the exit line, because a missing entry is the worse problem."""
    folder(
        {
            "alpha.py": with_main("    return 8"),
            "beta.py": with_codes(
                "12  PINNED-FILE-NOT-DOWNLOADED  the file is missing somehow"
            ).replace("alpha.py", "beta.py"),
        }
    )
    outcome = run(capsys)
    assert outcome.exit_code == 16
    assert exit_line(16, "HEADER-EXIT-CODE-UNLISTED") in outcome.printed
    assert "exit code 8 is returned by main()" in outcome.printed
    assert "PINNED-FILE-NOT-DOWNLOADED says" in outcome.printed


@code("SA00585")
@category("repository")
@objective("functionality")
@negative
def test_a_main_with_no_listed_code_exits_15(folder, capsys):
    """A file with a main() whose Exit codes field is written only as a sentence makes
    the run exit 15, and the problem line names the file and says to list each code
    the file can end on."""
    folder({"alpha.py": with_main("    return 0", "The codes are the usual ones.")})
    outcome = run(capsys)
    assert outcome.exit_code == 15
    assert exit_line(15, "HEADER-INCOMPLETE") in outcome.printed
    assert (
        "src/sdg/alpha.py: the Exit codes field lists no exit code, but the file "
        "has a main()"
    ) in outcome.printed
    assert "list each one it can end on" in outcome.printed


@code("SA00586")
@category("repository")
@objective("functionality")
@positive
def test_a_file_with_no_main_may_describe_its_codes_in_a_sentence(folder, capsys):
    """A file with no main(), such as a check file, may write its Exit codes field as
    a sentence, and the run exits 0."""
    folder({"alpha.py": with_codes("None of its own. It runs inside pytest.")})
    assert run(capsys).exit_code == 0


#######################################################################################
### A refusal of the table with the quiet option ###
#
# With the quiet option, each way docs/exit_codes.csv can be refused prints nothing
# and still exits with its own code. One check runs once per refusal.


@code("SA00524")
@category("repository")
@objective("functionality")
@negative
@pytest.mark.parametrize("refusal", ["missing table", "code above 125"])
def test_every_table_refusal_is_silent_under_quiet(
    folder, monkeypatch, capsys, refusal
):
    """With the quiet option, a refusal of docs/exit_codes.csv prints nothing and still
    exits with its own code. It runs once for a missing table, which exits 12, and
    once for a table holding a code above 125, which exits 15."""
    folder({"alpha.py": GOOD_HEADER})
    if refusal == "missing table":
        monkeypatch.setattr(script, "EXIT_CODES_FILE", script.REPO_ROOT / "gone.csv")
        expected = 12
    else:
        script.EXIT_CODES_FILE.write_text(
            table_text(["126", GROUPS[13], "A-B", "x", ""]), encoding="utf-8"
        )
        expected = 15
    outcome = run(capsys, "--quiet")
    assert outcome.printed == ""
    assert outcome.exit_code == expected


#######################################################################################
### A header with no Exit codes field ###


@code("SA00531")
@category("repository")
@objective("functionality")
@negative
def test_a_header_with_no_exit_codes_field_is_refused(folder, capsys):
    """A header with no Exit codes field makes the run exit 15, and the problem line
    names the field as missing."""
    lines = GOOD_HEADER.splitlines(keepends=True)
    header = "".join(line for line in lines if not line.startswith("Exit codes:"))
    folder({"alpha.py": header})
    outcome = run(capsys)
    assert outcome.exit_code == 15
    assert exit_line(15, "HEADER-INCOMPLETE") in outcome.printed
    assert "missing Exit codes" in outcome.printed
