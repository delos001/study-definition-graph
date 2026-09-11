"""
Script:      test_verify_headers.py
Description: Checks for scripts/verify_headers.py, the hand-run script the
             pre-commit hook runs to refuse a commit whose Python files lack
             the full header block. Each check writes one or two small files to
             a temporary folder, points the script's checked folders at it,
             runs main() in-process, and asserts the exit code or the problem
             line the header promises. One check runs the script over the real
             package and scripts/ folders, the same run the hook makes.

Inputs:      src/sdg/**/*.py and scripts/*.py  (read-only; the one real-folder check)

Outputs:     Writes nothing outside pytest's own temporary folder.

Usage:       pytest tests/scripts/test_verify_headers.py
                 run these checks
             pytest tests/scripts/test_verify_headers.py -v
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
# tests/validation_inventory.csv, assigned once and never reused.
code = pytest.mark.code

# A complete header in this repo's convention, with the eight fields in order.
GOOD_HEADER = '''"""
Script:      alpha.py
Description: Does the first thing.
Inputs:      nothing
Outputs:     nothing
Usage:       python scripts/alpha.py
Exit codes:  0 fine
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


@code("SCR0042")
@positive
def test_complete_header_exits_0(complete):
    """A file whose header holds the eight fields in order makes the run exit 0."""
    assert complete.exit_code == 0


@code("SCR0043")
@positive
def test_complete_header_prints_nothing(complete):
    """When every header is complete, nothing is printed."""
    assert complete.printed == ""


@code("SCR0044")
@positive
def test_init_file_is_skipped(folder, capsys):
    """An __init__.py with a one-paragraph docstring and no header block is not a
    problem, since a package marker names the folder rather than describing a
    script."""
    folder({"alpha.py": GOOD_HEADER, "__init__.py": '"""The package."""\n'})
    assert run(capsys).exit_code == 0


@code("SCR0045")
@positive
def test_quiet_prints_nothing(folder, capsys):
    """With the quiet option, nothing is printed even when a header is incomplete;
    the exit code is the whole report."""
    folder({"alpha.py": GOOD_HEADER.replace("Owner:       Jason Delosh\n", "")})
    outcome = run(capsys, "--quiet")
    assert outcome.exit_code == 1
    assert outcome.printed == ""


@code("SCR0046")
@positive
def test_real_folders_pass():
    """Every Python file in the real package and scripts/ folders has a complete
    header, which is the run the pre-commit hook makes."""
    assert script.main(["--quiet"]) == 0


#######################################################################################
### Negative checks ###
#
# The wrong thing is refused, and the problem line names the file and the cause: a
# missing field, fields out of order, a Date that is not a plain calendar date, a
# file with no docstring at all, and a file that is not valid Python.


@code("SCR0047")
@negative
def test_missing_fields_exit_1(folder, capsys):
    """A header lacking fields makes the run exit 1, and the problem line names the
    file and every missing field."""
    folder(
        {
            "alpha.py": GOOD_HEADER.replace("Outputs:     nothing\n", "").replace(
                "Owner:       Jason Delosh\n", ""
            )
        }
    )
    outcome = run(capsys)
    assert outcome.exit_code == 1
    assert "src/sdg/alpha.py: missing Outputs, Owner" in outcome.printed


@code("SCR0048")
@negative
def test_fields_out_of_order_exit_1(folder, capsys):
    """A header with its fields in the wrong order makes the run exit 1, and the
    problem line says so and shows the order found."""
    swapped = GOOD_HEADER.replace(
        "Date:        2026-09-04\nOwner:       Jason Delosh\n",
        "Owner:       Jason Delosh\nDate:        2026-09-04\n",
    )
    folder({"alpha.py": swapped})
    outcome = run(capsys)
    assert outcome.exit_code == 1
    assert "src/sdg/alpha.py: fields out of order" in outcome.printed
    assert "Owner, Date" in outcome.printed


@code("SCR0049")
@negative
def test_bad_date_exits_1(folder, capsys):
    """A Date that is not a plain calendar date makes the run exit 1, and the
    problem line quotes the value found."""
    folder({"alpha.py": GOOD_HEADER.replace("2026-09-04", "September 2026")})
    outcome = run(capsys)
    assert outcome.exit_code == 1
    assert "src/sdg/alpha.py: Date is 'September 2026', not YYYY-MM-DD" in (
        outcome.printed
    )


@code("SCR0050")
@negative
def test_no_docstring_exits_1(folder, capsys):
    """A file with no module docstring has no header block at all: the run exits 1
    and the problem line says so."""
    folder({"alpha.py": "print('hello')\n"})
    outcome = run(capsys)
    assert outcome.exit_code == 1
    assert "src/sdg/alpha.py: no module docstring" in outcome.printed


@code("SCR0051")
@negative
def test_unparseable_file_exits_3(folder, capsys):
    """A file that is not valid Python makes the run exit 3, and the problem line
    says it cannot be parsed."""
    folder({"alpha.py": "def broken(:\n"})
    outcome = run(capsys)
    assert outcome.exit_code == 3
    assert "src/sdg/alpha.py: cannot parse" in outcome.printed


@code("SCR0052")
@negative
def test_unparseable_outranks_incomplete(folder, capsys):
    """When one file cannot be parsed and another has an incomplete header, the run
    exits 3, and both problems are still named."""
    folder({"alpha.py": "def broken(:\n", "beta.py": "print('no header')\n"})
    outcome = run(capsys)
    assert outcome.exit_code == 3
    assert "alpha.py: cannot parse" in outcome.printed
    assert "beta.py: no module docstring" in outcome.printed
