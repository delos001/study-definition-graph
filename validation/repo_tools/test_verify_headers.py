"""
Script:      test_verify_headers.py
Description: Checks for repo_tools/verify_headers.py, the hand-run script the
             pre-commit hook runs to refuse a commit whose Python files lack
             the full header block. Each check writes one or two small files to
             a temporary folder, points the script's checked folders at it,
             runs main() in-process, and asserts the exit code or the problem
             line the header promises. One check runs the script over the four
             real code folders, the same run the hook makes.

Inputs:      src/sdg/**/*.py, repo_tools/*.py, validation/**/*.py and
             .claude/hooks/*.py  (read-only; the one real-folder check)

Outputs:     Writes nothing outside pytest's own temporary folder.

Usage:       pytest validation/repo_tools/test_verify_headers.py
                 run these checks
             pytest validation/repo_tools/test_verify_headers.py -v
                 one line per check with its result

Exit codes:  pytest's own: 0 all passed, 1 some failed

Date:        2026-09-11
Owner:       Jason Delosh
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

import verify_headers as script

positive = pytest.mark.positive
negative = pytest.mark.negative
# Every check carries a @code line: its short, permanent id in
# validation/validation_inventory.csv, assigned once and never reused.
code = pytest.mark.code

# A complete header in this repo's convention, with the eight fields in order.
GOOD_HEADER = '''"""
Script:      alpha.py
Description: Does the first thing.
Inputs:      nothing
Outputs:     nothing
Usage:       python repo_tools/alpha.py
Exit codes:  0   success
Date:        2026-09-04
Owner:       Jason Delosh
"""
'''


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
    # check about a wrong code can say what the right one is.
    table = tmp_path / "exit_codes.csv"
    table.write_text(
        "code,cause\n0,success\n8,a pinned file has not been downloaded\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(script, "EXIT_CODES_FILE", table)

    def make(files: dict[str, str]) -> None:
        """Write the given files into the checked folder.

        Args:
            files: The files to write, source text keyed by file name.
        """
        for name, source in files.items():
            (checked / name).write_text(source, encoding="utf-8")

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


@pytest.fixture
def complete(folder, capsys) -> Outcome:
    """Stage one file with a complete header, and run the script."""
    folder({"alpha.py": GOOD_HEADER})
    return run(capsys)


#######################################################################################
### Positive checks ###
#
# The right thing works: complete headers pass silently, a package marker file is
# not held to the header rule, --quiet leaves the exit code to speak, and the real
# folders pass the same run the hook makes.


@code("HRS0042")
@positive
def test_complete_header_exits_0(complete):
    """A file whose header holds the eight fields in order makes the run exit 0."""
    assert complete.exit_code == 0


@code("HRS0043")
@positive
def test_complete_header_prints_nothing(complete):
    """When every header is complete, nothing is printed."""
    assert complete.printed == ""


@code("HRS0044")
@positive
def test_init_file_is_skipped(folder, capsys):
    """An __init__.py with a one-paragraph docstring and no header block is not a
    problem, since a package marker names the folder rather than describing a
    script."""
    folder({"alpha.py": GOOD_HEADER, "__init__.py": '"""The package."""\n'})
    assert run(capsys).exit_code == 0


@code("HRS0045")
@positive
def test_quiet_prints_nothing(folder, capsys):
    """With the quiet option, nothing is printed even when a header is incomplete;
    the exit code is the whole report."""
    folder({"alpha.py": GOOD_HEADER.replace("Owner:       Jason Delosh\n", "")})
    outcome = run(capsys, "--quiet")
    assert outcome.exit_code == 17
    assert outcome.printed == ""


@code("HRS0046")
@positive
def test_real_folders_pass():
    """Every Python file in the four real code folders has a complete header, which
    is the run the pre-commit hook makes."""
    assert script.main(["--quiet"]) == 0


#######################################################################################
### Negative checks ###
#
# The wrong thing is refused, and the problem line names the file and the cause: a
# missing field, fields out of order, a Date that is not a plain calendar date, a
# file with no docstring at all, and a file that is not valid Python.


@code("HRS0047")
@negative
def test_missing_fields_exit_17(folder, capsys):
    """A header lacking fields makes the run exit 17, and the problem line names the
    file and every missing field."""
    folder(
        {
            "alpha.py": GOOD_HEADER.replace("Outputs:     nothing\n", "").replace(
                "Owner:       Jason Delosh\n", ""
            )
        }
    )
    outcome = run(capsys)
    assert outcome.exit_code == 17
    assert "src/sdg/alpha.py: missing Outputs, Owner" in outcome.printed


@code("HRS0048")
@negative
def test_fields_out_of_order_exit_17(folder, capsys):
    """A header with its fields in the wrong order makes the run exit 17, and the
    problem line says so and shows the order found."""
    swapped = GOOD_HEADER.replace(
        "Date:        2026-09-04\nOwner:       Jason Delosh\n",
        "Owner:       Jason Delosh\nDate:        2026-09-04\n",
    )
    folder({"alpha.py": swapped})
    outcome = run(capsys)
    assert outcome.exit_code == 17
    assert "src/sdg/alpha.py: fields out of order" in outcome.printed
    assert "Owner, Date" in outcome.printed


@code("HRS0049")
@negative
def test_bad_date_exits_17(folder, capsys):
    """A Date that is not a plain calendar date makes the run exit 17, and the
    problem line quotes the value found."""
    folder({"alpha.py": GOOD_HEADER.replace("2026-09-04", "September 2026")})
    outcome = run(capsys)
    assert outcome.exit_code == 17
    assert "src/sdg/alpha.py: Date is 'September 2026', not YYYY-MM-DD" in (
        outcome.printed
    )


@code("HRS0050")
@negative
def test_no_docstring_exits_17(folder, capsys):
    """A file with no module docstring has no header block at all: the run exits 17
    and the problem line says so."""
    folder({"alpha.py": "print('hello')\n"})
    outcome = run(capsys)
    assert outcome.exit_code == 17
    assert "src/sdg/alpha.py: no module docstring" in outcome.printed


@code("HRS0051")
@negative
def test_unparseable_file_exits_19(folder, capsys):
    """A file that is not valid Python makes the run exit 19, and the problem line
    says it cannot be parsed."""
    folder({"alpha.py": "def broken(:\n"})
    outcome = run(capsys)
    assert outcome.exit_code == 19
    assert "src/sdg/alpha.py: cannot parse" in outcome.printed


@code("HRS0052")
@negative
def test_unparseable_outranks_incomplete(folder, capsys):
    """When one file cannot be parsed and another has an incomplete header, the run
    exits 19, and both problems are still named."""
    folder({"alpha.py": "def broken(:\n", "beta.py": "print('no header')\n"})
    outcome = run(capsys)
    assert outcome.exit_code == 19
    assert "alpha.py: cannot parse" in outcome.printed
    assert "beta.py: no module docstring" in outcome.printed


@code("HRS0079")
@positive
def test_all_four_code_folders_are_checked():
    """The checker covers the four folders the writing rule names, so a file added
    under any of them is held to the header block like any other."""
    covered = {
        folder.relative_to(script.REPO_ROOT).as_posix()
        for folder in script.CHECKED_FOLDERS
    }
    assert covered == {"src/sdg", "repo_tools", "validation", ".claude/hooks"}


#######################################################################################
### Checks on the exit codes a header names ###
#
# One number means one cause across the repo, so each entry has to open with the
# table's wording. A file-specific aside may follow it in brackets. These checks stage
# a header whose Exit codes field is right, then wrong in one way at a time.


def with_codes(lines: str) -> str:
    """Build a complete header whose Exit codes field holds the given lines.

    Args:
        lines: The Exit codes field, written as it appears in a header.

    Returns:
        The whole header block.
    """
    return GOOD_HEADER.replace("Exit codes:  0   success", f"Exit codes:  {lines}")


@code("HRS0080")
@positive
def test_wording_from_the_table_passes(folder, capsys):
    """An entry written with the table's wording for its number passes."""
    folder({"alpha.py": with_codes("8   a pinned file has not been downloaded")})
    assert run(capsys).exit_code == 0


@code("HRS0081")
@positive
def test_a_bracketed_aside_is_allowed(folder, capsys):
    """An entry may add a bracketed aside after the table's wording, saying what the
    cause means in that file."""
    folder(
        {
            "alpha.py": with_codes(
                "8   a pinned file has not been downloaded (a dry run only)"
            )
        }
    )
    assert run(capsys).exit_code == 0


@code("HRS0082")
@positive
def test_a_wrapped_entry_is_read_as_one(folder, capsys):
    """An entry too long for one line is joined before it is compared, so wrapping it
    does not make it disagree."""
    folder(
        {
            "alpha.py": with_codes(
                "8   a pinned file has not been downloaded (a dry run\n"
                "                 only; a real run fetches it)"
            )
        }
    )
    assert run(capsys).exit_code == 0


@code("HRS0083")
@positive
def test_the_closing_prose_is_not_read_as_an_entry(folder, capsys):
    """The sentence a field ends with is not mistaken for an entry, so it is never
    compared with the table."""
    folder(
        {
            "alpha.py": with_codes(
                "0   success\n             The numbers are the repo-wide table."
            )
        }
    )
    assert run(capsys).exit_code == 0


@code("HRS0084")
@negative
def test_a_code_the_table_lacks_exits_33(folder, capsys):
    """An entry for a number the table does not hold makes the run exit 33, and the
    problem line names the file and the number."""
    folder({"alpha.py": with_codes("99  something nobody agreed on")})
    outcome = run(capsys)
    assert outcome.exit_code == 33
    assert "src/sdg/alpha.py: exit code 99 is not in" in outcome.printed


@code("HRS0085")
@negative
def test_different_wording_exits_33(folder, capsys):
    """An entry giving a number a second meaning makes the run exit 33, and the problem
    line prints what the header says beside what the table says."""
    folder({"alpha.py": with_codes("8   the file is missing somehow")})
    outcome = run(capsys)
    assert outcome.exit_code == 33
    assert "the file is missing somehow" in outcome.printed
    assert "a pinned file has not been downloaded" in outcome.printed


@code("HRS0086")
@negative
def test_an_incomplete_header_outranks_a_wrong_code(folder, capsys):
    """When one file has an incomplete header and another has a wrong code, the run
    exits 17, because a header that cannot be read is the worse problem."""
    folder(
        {
            "alpha.py": "print('no header')\n",
            "beta.py": with_codes("99  something nobody agreed on"),
        }
    )
    assert run(capsys).exit_code == 17


@code("HRS0087")
@negative
def test_an_unreadable_table_exits_13(folder, monkeypatch, capsys):
    """With the exit-code table missing, the run exits 13 and says the table cannot be
    read, rather than reporting every file as disagreeing with nothing."""
    folder({"alpha.py": GOOD_HEADER})
    monkeypatch.setattr(script, "EXIT_CODES_FILE", script.REPO_ROOT / "gone.csv")
    outcome = run(capsys)
    assert outcome.exit_code == 13
    assert "cannot be read" in outcome.printed


#######################################################################################
### Checks on the codes main() returns ###
#
# A header can list every code correctly and still forget one the code returns. These
# checks stage a file with a main() and compare what it returns with what it lists.


def with_main(returns: str, codes: str = "0   success") -> str:
    """Build a file whose header lists the given codes and whose main() returns.

    Args:
        returns: The body of main(), written as the lines inside the function.
        codes: The Exit codes field, written as it appears in a header.

    Returns:
        The whole file, header and code.
    """
    header = GOOD_HEADER.replace("Exit codes:  0   success", f"Exit codes:  {codes}")
    return header + "\n\ndef main(argv=None):\n" + returns + "\n"


@code("HRS0088")
@positive
def test_a_listed_return_passes(folder, capsys):
    """A code main() returns and the header lists is no problem."""
    folder({"alpha.py": with_main("    return 0")})
    assert run(capsys).exit_code == 0


@code("HRS0089")
@positive
def test_a_return_of_a_call_is_passed_over(folder, capsys):
    """A return of something other than a plain number is passed over rather than
    guessed at, so a computed exit code is never reported as unlisted."""
    folder({"alpha.py": with_main("    return len(argv or [])")})
    assert run(capsys).exit_code == 0


@code("HRS0090")
@positive
def test_a_listed_code_that_is_never_returned_is_not_a_problem(folder, capsys):
    """A header may list a code main() does not return as a plain number, because the
    check only looks for codes a header forgot."""
    folder(
        {
            "alpha.py": with_main(
                "    return 0",
                "0   success\n             8   a pinned file has not been downloaded",
            )
        }
    )
    assert run(capsys).exit_code == 0


@code("HRS0091")
@negative
def test_an_unlisted_return_exits_34(folder, capsys):
    """A code main() returns that the header does not list makes the run exit 34, and
    the problem line names the file and the number."""
    folder({"alpha.py": with_main("    return 8")})
    outcome = run(capsys)
    assert outcome.exit_code == 34
    assert "exit code 8 is returned by main()" in outcome.printed


@code("HRS0092")
@negative
def test_both_sides_of_a_one_line_choice_are_read(folder, capsys):
    """A return written as a one-line choice is read on both sides, so the branch that
    is not listed is still caught."""
    folder({"alpha.py": with_main("    return 8 if argv else 0")})
    assert run(capsys).exit_code == 34


@code("HRS0093")
@negative
def test_a_forgotten_code_outranks_a_reworded_one(folder, capsys):
    """When one file forgets a code and another rewords one, the run exits 34, because
    a missing code is the worse problem."""
    folder(
        {
            "alpha.py": with_main("    return 8"),
            "beta.py": GOOD_HEADER.replace(
                "0   success", "8   the file is missing somehow"
            ).replace("alpha.py", "beta.py"),
        }
    )
    assert run(capsys).exit_code == 34
