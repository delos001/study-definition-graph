"""
Script:      verify_headers.py
Description: Checks that every Python file in the three code folders, src/,
             validation/ and .claude/hooks/, opens with the full
             header block .claude/rules/writing_python_files.md requires, with the eight fields in the set
             order and a Date in YYYY-MM-DD form. It reports each file that falls
             short and names what is wrong.

             The git pre-commit hook runs it, so a commit that adds a file with
             a missing or disordered header is refused before it lands, whoever
             made the edit. It reads the header the same way build_index.py
             does, by borrowing that script's parser, so the two can never
             disagree about what a header is.

             It also compares each header's Exit codes field with the
             repo-wide table in validation/exit_codes.csv. An entry must open
             with the table's wording for that number, and may then add a
             bracketed aside saying what the cause means in that file. That is
             what keeps one number meaning one cause everywhere, once a tool has
             been renumbered by hand.

             Separately, it reads each file's main() and reports any code the
             function returns as a plain number that the header does not list.
             That direction only: a return of a call or a computed value is
             passed over rather than guessed at, so the check finds a code a
             header forgot and never claims a listed code is unreachable.

             __init__.py files are skipped: they carry a one-paragraph
             docstring naming the folder, not a header block.

Inputs:      src/**/*.py, validation/**/*.py and .claude/hooks/*.py
                                        (read-only, parsed rather than imported)
             validation/exit_codes.csv  (read-only, the repo-wide table)

Outputs:     Nothing on disk. Prints one line per problem, or nothing when
             every header is complete.

Usage:       verify_headers
                 check every file, report each problem
             verify_headers --quiet
                 print nothing; use the exit code

Exit codes:  0   success (every header is complete and in order)
             1   unhandled error, Python's own
             2   invalid command line, the argument parser's own
             13  a file on disk cannot be read (the exit-code table is missing,
                 or holds a code that is not a number)
             17  a header block is missing, incomplete, out of order, or has a
                 bad Date
             19  a Python file could not be parsed
             33  a header's exit codes disagree with the repo-wide table
             34  a header does not list a code its main() returns
             19 outranks 17, 17 outranks 34, and 34 outranks 33, because a header
             that cannot be read at all is worse than one missing a code, which is
             worse than one whose wording has drifted. Every problem is still named.
             The numbers are the repo-wide table in
             validation/exit_codes.csv.

Date:        2026-09-09
Owner:       Jason Delosh
"""

from __future__ import annotations

import argparse
import ast
import csv
import re
import sys
from pathlib import Path

# The parser and the field list live in build_index.py, in the sdgtools package,
# so the two tools read a header the same way.
from sdgtools.build_index import FIELD_RE, REQUIRED_FIELDS, parse_header

#######################################################################################
### Settings ###

REPO_ROOT = Path(__file__).resolve().parents[2]
# src/ as a whole, so a package added beside sdg, sdgtools and sdgval is covered
# without an edit here.
CHECKED_FOLDERS = (
    REPO_ROOT / "src",
    REPO_ROOT / "validation",
    REPO_ROOT / ".claude" / "hooks",
)

# The Date field is the day the file was first committed, written as a plain
# calendar date. Anything else, a time, a range, a word, is a mistake.
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# The repo-wide table of exit codes, one row per number. A header names only the
# codes its file can return, each opening with the table's wording, so that one
# number means one cause across the whole repo.
EXIT_CODES_FILE = REPO_ROOT / "validation" / "exit_codes.csv"

# An entry in an Exit codes field opens with the number, then a run of spaces,
# then the cause. Written without shorthand character classes so the pattern
# reads as what it matches.
ENTRY_RE = re.compile(r"^( *)([0-9]+)  +([^ ].*)$")

# A header may add a file-specific aside after the table's wording, in brackets.
# Everything before the bracket is what has to match, so an aside can say what
# the cause means here without redefining it.
ASIDE = " ("


#######################################################################################
### The exit-code table ###


def exit_code_table(path: Path | None = None) -> dict[int, str]:
    """Read the repo-wide exit-code table.

    Args:
        path: The table to read, or None for the one under validation/.

    Returns:
        The cause each number means, keyed by the number.

    Raises:
        OSError: The table cannot be opened.
        ValueError: A row's code is not a whole number, so the table cannot be read.
    """
    table: dict[int, str] = {}
    with open(path or EXIT_CODES_FILE, encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            table[int(row["code"])] = row["cause"].strip()
    return table


def value_column(path: Path) -> int:
    """Find the column where the Exit codes field's value starts in a file's header.

    The header parser hands the field's first line over without the label in front of
    it, so its indent is lost. The column is read here from the raw header instead of
    being guessed from the lines that follow, because a guess goes wrong when the only
    line that follows is the first entry's own continuation.

    Args:
        path: The file whose header is read.

    Returns:
        The column, or 0 when the file has no Exit codes line.
    """
    # A file that will not parse is already reported by the header parser, so the
    # column falls back to 0 here rather than raising the same problem twice.
    try:
        docstring = ast.get_docstring(
            ast.parse(path.read_text(encoding="utf-8")), clean=False
        )
    except (SyntaxError, OSError):
        return 0
    for line in (docstring or "").splitlines():
        match = FIELD_RE.match(line)
        if match and match.group(1) == "Exit codes":
            return len(line) - len(match.group(2))
    return 0


def code_entries(lines: list[str], first_indent: int) -> list[tuple[int, str]]:
    """Read the code entries out of one Exit codes field.

    A field ends with a sentence or two of prose about the codes, and a long entry
    wraps onto the next line. The two are told apart by indentation: a wrapped line
    is indented further than the entry it belongs to, and the closing prose is not.

    Args:
        lines: The field's lines, as the header parser hands them over.
        first_indent: The column the first line really sits at, since the parser
            hands that line over with no indent.

    Returns:
        Each entry as its number and the cause written beside it, in the order the
            header lists them.
    """
    entries: list[tuple[int, str]] = []
    indents: list[int] = []
    for position, raw in enumerate(lines):
        if not raw.strip():
            continue
        match = ENTRY_RE.match(raw)
        if match:
            entries.append((int(match.group(2)), match.group(3).strip()))
            indents.append(first_indent if position == 0 else len(match.group(1)))
            continue
        if entries and len(raw) - len(raw.lstrip()) > indents[-1]:
            number, wording = entries[-1]
            entries[-1] = (number, wording + " " + raw.strip())
            continue
        # Anything else closes the entries: it is the prose the field ends with.
        break
    return entries


def returned_codes(tree: ast.Module) -> set[int]:
    """Collect the exit codes a file's main() hands back as a plain number.

    Only main() is read, and only returns written as a number are collected, including
    the two sides of a one-line choice such as "return 10 if stray else 0". A return
    of anything else, a call or a computed value, is passed over rather than guessed
    at. That makes this deliberately one-sided: it finds a code the header forgot,
    and never claims a listed code is unreachable.

    Args:
        tree: The parsed file.

    Returns:
        The numbers main() can return.
    """
    found: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or node.name != "main":
            continue
        for inner in _returns_of(node):
            values = [inner.value]
            if isinstance(inner.value, ast.IfExp):
                values = [inner.value.body, inner.value.orelse]
            for value in values:
                if isinstance(value, ast.Constant) and isinstance(value.value, int):
                    found.add(value.value)
    return found


def _returns_of(function: ast.AST) -> list[ast.Return]:
    """Collect the return statements that belong to one function.

    A function defined inside main(), such as a small printing helper, has returns of
    its own that say nothing about main()'s exit code, so the walk stops at any nested
    function, class or lambda rather than reading their returns as main()'s.

    Args:
        function: The function's node, or a node inside it.

    Returns:
        The return statements in the function's own body, in source order.
    """
    found: list[ast.Return] = []
    for child in ast.iter_child_nodes(function):
        if isinstance(
            child, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef | ast.Lambda
        ):
            continue
        if isinstance(child, ast.Return):
            found.append(child)
        found.extend(_returns_of(child))
    return found


def unlisted_codes(returned: set[int], entries: list[tuple[int, str]]) -> list[str]:
    """Name every code main() returns that the header does not list.

    Args:
        returned: The numbers main() can return.
        entries: The entries the header lists.

    Returns:
        One problem per code that is returned but not listed.
    """
    listed = {number for number, _ in entries}
    return [
        f"exit code {number} is returned by main() but the header does not list it"
        for number in sorted(returned - listed)
    ]


def code_problems(entries: list[tuple[int, str]], table: dict[int, str]) -> list[str]:
    """Compare one file's code entries with the repo-wide table.

    Args:
        entries: The entries the header lists.
        table: The cause each number means, from the table.

    Returns:
        One problem per entry that disagrees, empty when every entry matches.
    """
    problems: list[str] = []
    for number, wording in entries:
        if number not in table:
            problems.append(f"exit code {number} is not in {EXIT_CODES_FILE.name}")
            continue
        stated = wording.split(ASIDE, 1)[0].rstrip(".")
        if stated != table[number]:
            problems.append(
                f"exit code {number} says {stated!r}, the table says {table[number]!r}"
            )
    return problems


#######################################################################################
### Find and check the files ###


def files_to_check() -> list[Path]:
    """List every Python file under the checked folders, with __init__.py files left out.

    Returns:
        The files, sorted.
    """
    found: list[Path] = []
    for folder in CHECKED_FOLDERS:
        found.extend(p for p in folder.rglob("*.py") if p.name != "__init__.py")
    return sorted(found)


def problems_in(path: Path, table: dict[int, str]) -> tuple[list[str], list[str], bool]:
    """Check one file's header block, and the exit codes it names.

    Args:
        path: The file to check.
        table: The cause each exit code means, from the repo-wide table.

    Returns:
        Three things: the problems with the block itself, the problems with the exit
            codes it names, and whether the file could be parsed at all.
    """
    fields, error = parse_header(path)
    if error:
        return [error], [], "cannot parse" not in error

    # parse_header hands back either the fields or an error, never neither,
    # so once the error is handled the fields are present. mypy cannot see the
    # two halves of the pair move together, hence the assertion.
    assert fields is not None

    problems: list[str] = []

    missing = [field for field in REQUIRED_FIELDS if field not in fields]
    if missing:
        problems.append(f"missing {', '.join(missing)}")

    # Order is checked only over the fields present, so a missing field is
    # reported once, above, and not again as a misordering.
    present = [field for field in fields if field in REQUIRED_FIELDS]
    expected = [field for field in REQUIRED_FIELDS if field in fields]
    if present != expected:
        problems.append(f"fields out of order: {', '.join(present)}")

    date = (fields.get("Date") or [""])[0].strip()
    if "Date" in fields and not DATE_RE.match(date):
        problems.append(f"Date is {date!r}, not YYYY-MM-DD")

    entries = code_entries(fields.get("Exit codes", []), value_column(path))
    codes = code_problems(entries, table)

    # The file is parsed a second time here rather than threaded through the header
    # parser, which hands back the header alone. Parsing is cheap and keeps the two
    # readers independent.
    try:
        codes += unlisted_codes(
            returned_codes(ast.parse(path.read_text(encoding="utf-8"))), entries
        )
    except (SyntaxError, OSError):
        # A file that will not parse is already reported by the header parser above.
        pass

    return problems, codes, True


#######################################################################################
### Command line ###


def main(argv: list[str] | None = None) -> int:
    """Check every file and print each problem, unless --quiet.

    Args:
        argv: The command-line arguments, or None to read the real ones.

    Returns:
        The exit code, as the header block lists them.
    """
    parser = argparse.ArgumentParser(
        description="Check every header block in the three code folders."
    )
    parser.add_argument(
        "--quiet", action="store_true", help="print nothing; use the exit code"
    )
    args = parser.parse_args(argv)

    unparseable = 0
    incomplete = 0
    disagreeing = 0
    unlisted = 0

    # The table is read once, so a table that cannot be read stops the run rather
    # than being reported against every file in turn. A table that cannot be opened
    # and one holding a code that is not a number are the same problem, because
    # neither can be compared with anything.
    try:
        table = exit_code_table()
    except (OSError, ValueError) as exc:
        if not args.quiet:
            print(f"{EXIT_CODES_FILE.name} cannot be read: {exc}")
        return 13

    for path in files_to_check():
        problems, codes, parsed = problems_in(path, table)
        if not problems and not codes:
            continue
        if not parsed:
            unparseable += 1
        elif problems:
            incomplete += 1
        if codes:
            # The two causes are counted apart, because a forgotten code and a
            # reworded one have different fixes and so different exit codes.
            if any("does not list it" in problem for problem in codes):
                unlisted += 1
            else:
                disagreeing += 1
        if not args.quiet:
            name = path.relative_to(REPO_ROOT).as_posix()
            for problem in problems + codes:
                print(f"{name}: {problem}")

    if unparseable:
        return 19
    if incomplete:
        return 17
    if unlisted:
        return 34
    if disagreeing:
        return 33
    return 0


if __name__ == "__main__":
    sys.exit(main())
