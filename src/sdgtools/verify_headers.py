"""
Script:      verify_headers.py
Description: Confirms that every Python file in the three code folders, src/,
             validation/ and .claude/hooks/, opens with the full
             header block .claude/rules/writing_python_files.md requires, with the eight fields in the set
             order and a Date in YYYY-MM-DD form. It reports each file that falls
             short and names what is wrong.

             The pre-commit hook runs it, so a commit that adds a file with
             a missing or disordered header is refused before it lands, whoever
             made the edit. It reads the header the same way build_index.py
             does, by borrowing that file's parser, so the two can never
             disagree about what a header is.

             It also holds every file to the repo-wide table in
             docs/exit_codes.csv, which lists each failure's sub-code with its
             exit number and what happened. It confirms four things.
             - The table is well formed, and each group in it is worded the
               way GROUPS in src/sdg/exit_codes.py words it, since that file
               prints the group on every exit line.
             - Each entry in a header's Exit codes field is written as the exit
               number, the sub-code, then what happened, and all three match
               the table. An entry may add a bracketed aside after the table's
               wording, saying what the failure means in that file.
             - Each exit number and sub-code the file's code names together,
               such as fail(say, 9, "NEO4J-UNREACHABLE", message) or an error
               class's exit_code and sub_code, is a row of the table. That
               holds in a check file too, so a check cannot expect a pair the
               table does not hold.
             - A file with a main() lists in its header every sub-code its own
               code names, and every number main() returns as a plain number,
               and lists at least one entry. A failure reported through an
               error from another file, such as the manifest reader's, is
               passed over rather than guessed at, so this finds an entry a
               header forgot and never claims a listed entry is unreachable.
             An exit number stops at 125, because a shell gives the numbers from
             126 up meanings of its own.

             __init__.py files are skipped: they carry a one-paragraph
             docstring naming the folder, not a header block.

Inputs:      src/**/*.py, validation/**/*.py and .claude/hooks/*.py
                                        (read-only, parsed rather than imported)
             docs/exit_codes.csv  (read-only, the repo-wide table)

Outputs:     Nothing on disk. Prints one line per problem, starting with its
             sub-code, and an exit line, or nothing when every header is
             complete.

Usage:       verify_headers
                 confirm every file's header, report each problem
             verify_headers --quiet
                 print nothing; use the exit code

Exit codes:  0   SUCCEEDED  the command succeeded (every header is complete and
                 in order)
             1   UNHANDLED-ERROR  Python stopped on an error that nothing
                 handled
             2   COMMAND-LINE-REFUSED  the argument parser refused the command
                 line
             12  EXIT-TABLE-MISSING  docs/exit_codes.csv is missing
             13  EXIT-TABLE-UNREADABLE  docs/exit_codes.csv cannot be opened
             13  PYTHON-FILE-UNREADABLE  a Python file cannot be opened
             14  PYTHON-UNPARSEABLE  a Python file is not valid Python
             14  PYTHON-NOT-UTF8  a Python file is not saved as UTF-8 text
             15  EXIT-TABLE-INVALID  a row of docs/exit_codes.csv breaks the
                 table's rules (a number that is not a whole number from 0 to
                 125, a sub-code of the wrong form or listed twice, a number
                 GROUPS does not hold, or a row with fewer columns than the
                 header)
             15  HEADER-MISSING  a Python file has no header block
             15  HEADER-INCOMPLETE  a header block is incomplete, out of order,
                 has a bad Date, or lists no exit code though the file has a
                 main()
             16  EXIT-GROUPS-DISAGREE  a group in docs/exit_codes.csv is worded
                 differently from src/sdg/exit_codes.py (or a group there has
                 no row in the table)
             16  HEADER-EXIT-CODE-UNLISTED  a header does not list an exit code
                 or sub-code its file uses
             16  HEADER-EXIT-CODES-DISAGREE  a header's Exit codes field
                 disagrees with docs/exit_codes.csv (this includes an exit
                 number and sub-code named together in the code that the table
                 does not hold)
             A problem with the table stops the run before any file is read,
             because nothing can be compared with a table that is missing or
             wrong. After that, a file that cannot be read decides the exit line
             first, then a header that is missing or incomplete, then an entry a
             header forgot, then an entry that disagrees with the table. Every
             problem is still named. The wording is the table in
             docs/exit_codes.csv.

Date:        2026-09-09
Owner:       Jason Delosh
"""

from __future__ import annotations

import argparse
import ast
import csv
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from sdg.exit_codes import GROUPS, fail, finish, problem_line

# The parser, the field list and the shape of a problem live in build_index.py, in
# the sdgtools package, so the two tools read a header the same way.
from sdgtools.build_index import FIELD_RE, REQUIRED_FIELDS, HeaderProblem, parse_header

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

# The repo-wide table of exit codes, one row per sub-code. A header names only the
# failures its file can end on, each with the table's number and wording, so that
# one number means one group of failure across the whole repo.
EXIT_CODES_FILE = REPO_ROOT / "docs" / "exit_codes.csv"

# The highest number an exit code of the project's own can take. A shell gives the
# numbers from 126 up meanings of its own. 126 means a command could not be run,
# 127 means a command was not found, and 128 plus a number means a command was
# stopped by that signal. A tool's own number above 125 would be read as one of
# those.
HIGHEST_EXIT_CODE = 125

# A sub-code is words in capitals and digits joined by hyphens, such as
# NEO4J-UNREACHABLE. SUCCEEDED, the sub-code of exit 0, is the one written as a
# single word. Written without shorthand character classes so the pattern reads as
# what it matches.
SUB_CODE_RE = re.compile(r"^(SUCCEEDED|[A-Z][A-Z0-9]*(-[A-Z0-9]+)+)$")

# An entry in an Exit codes field opens with the number, then a run of spaces, then
# the sub-code, then a run of spaces, then what happened.
ENTRY_RE = re.compile(r"^( *)([0-9]+)  +([A-Z][A-Z0-9-]*)  +([^ ].*)$")

# A header may add a file-specific aside after the table's wording, in brackets.
# Everything before the bracket is what has to match, so an aside can say what
# the failure means here without redefining it.
ASIDE = " ("

# The order in which the kinds of problem decide the exit line, worst first. A file
# that cannot be read is worse than a header missing a field, which is worse than a
# header that forgot an entry, which is worse than one whose wording has drifted.
PRECEDENCE = (
    "PYTHON-FILE-UNREADABLE",
    "PYTHON-UNPARSEABLE",
    "PYTHON-NOT-UTF8",
    "HEADER-MISSING",
    "HEADER-INCOMPLETE",
    "HEADER-EXIT-CODE-UNLISTED",
    "HEADER-EXIT-CODES-DISAGREE",
)


#######################################################################################
### The exit-code table ###


@dataclass(frozen=True)
class Row:
    """One failure the table lists: its exit number and what happened."""

    code: int
    what_happened: str


class TableError(Exception):
    """Raised when docs/exit_codes.csv breaks the table's rules.

    It carries the exit number and sub-code the command reports it with.
    """

    exit_code = 15
    sub_code = "EXIT-TABLE-INVALID"


class GroupsDisagreeError(TableError):
    """Raised when a group in docs/exit_codes.csv is worded differently from GROUPS in
    src/sdg/exit_codes.py, or a group there has no row in the table."""

    exit_code = 16
    sub_code = "EXIT-GROUPS-DISAGREE"


def exit_code_table(path: Path | None = None) -> dict[str, Row]:
    """Read the repo-wide exit-code table.

    Args:
        path: The table to read, or None for docs/exit_codes.csv.

    Returns:
        Each failure the table lists, keyed by its sub-code.

    Raises:
        OSError: The table cannot be opened.
        TableError: A row's number is not a whole number from 0 to 125, its
            number is not one GROUPS holds, it has fewer columns than the header,
            or its sub-code is of the wrong form or listed twice.
        GroupsDisagreeError: A row's group is worded differently from GROUPS, or
            a group in GROUPS has no row.
    """
    table: dict[str, Row] = {}
    numbers: set[int] = set()
    with open(path or EXIT_CODES_FILE, encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            try:
                number = int(row["code"])
            except (TypeError, ValueError):
                number = -1
            if not 0 <= number <= HIGHEST_EXIT_CODE:
                raise TableError(
                    f"the code {row['code']!r} is not a whole number from 0 to "
                    f"{HIGHEST_EXIT_CODE}, the numbers an exit code can take"
                )
            if number not in GROUPS:
                raise TableError(
                    f"the code {number} is not a group in GROUPS in src/sdg/exit_codes.py"
                )
            # A row with fewer columns than the table's header has no value at all in
            # the columns it lacks, so it is refused here rather than failing on them
            # below.
            if None in (row["group"], row["sub_code"], row["what_happened"]):
                raise TableError(
                    f"the row for code {number} has fewer columns than the table's "
                    "header"
                )
            if row["group"].strip() != GROUPS[number]:
                raise GroupsDisagreeError(
                    f"the group of code {number} is {row['group']!r}, and "
                    f"src/sdg/exit_codes.py words it {GROUPS[number]!r}"
                )
            numbers.add(number)
            sub_code = row["sub_code"].strip()
            # A group no failure uses yet has a row with no sub-code, so the table
            # still lists every group.
            if not sub_code:
                continue
            if not SUB_CODE_RE.match(sub_code):
                raise TableError(
                    f"the sub-code {sub_code!r} is not words in capitals joined by "
                    "hyphens, such as NEO4J-UNREACHABLE"
                )
            if sub_code in table:
                raise TableError(f"the sub-code {sub_code} is listed twice")
            table[sub_code] = Row(number, row["what_happened"].strip())
    missing = sorted(set(GROUPS) - numbers)
    if missing:
        raise GroupsDisagreeError(
            f"the codes {', '.join(map(str, missing))} are groups in "
            "src/sdg/exit_codes.py with no row in the table"
        )
    return table


#######################################################################################
### Reading a header's Exit codes field ###


def value_column(path: Path) -> int:
    """Find the column where the Exit codes field's value starts in a file's header.

    The header parser hands the field's first line over without the label in front of
    it, so its indent is lost. The column is read here from the raw header instead of
    being guessed from the lines that follow, because a guess goes wrong when the only
    line that follows is the first entry's own continuation.

    It is called only for a file the header parser has already read, so the file
    is known to parse.

    Args:
        path: The file whose header is read.

    Returns:
        The column, or 0 when the file has no Exit codes line.
    """
    docstring = ast.get_docstring(
        ast.parse(path.read_text(encoding="utf-8")), clean=False
    )
    for line in (docstring or "").splitlines():
        match = FIELD_RE.match(line)
        if match and match.group(1) == "Exit codes":
            return len(line) - len(match.group(2))
    return 0


def code_entries(lines: list[str], first_indent: int) -> list[tuple[int, str, str]]:
    """Read the entries out of one Exit codes field.

    A field ends with a sentence or two of prose about the codes, and a long entry
    wraps onto the next line. The two are told apart by indentation: a wrapped line
    is indented further than the entry it belongs to, and the closing prose is not.

    Args:
        lines: The field's lines, as the header parser hands them over.
        first_indent: The column the first line really sits at, since the parser
            hands that line over with no indent.

    Returns:
        Each entry as its number, its sub-code and what happened, in the order the
            header lists them.
    """
    entries: list[tuple[int, str, str]] = []
    indents: list[int] = []
    for position, raw in enumerate(lines):
        if not raw.strip():
            continue
        match = ENTRY_RE.match(raw)
        if match:
            entries.append(
                (int(match.group(2)), match.group(3), match.group(4).strip())
            )
            indents.append(first_indent if position == 0 else len(match.group(1)))
            continue
        if entries and len(raw) - len(raw.lstrip()) > indents[-1]:
            number, sub_code, wording = entries[-1]
            entries[-1] = (number, sub_code, wording + " " + raw.strip())
            continue
        # Anything else closes the entries: it is the prose the field ends with.
        break
    return entries


def code_problems(
    entries: list[tuple[int, str, str]], table: dict[str, Row]
) -> list[HeaderProblem]:
    """Compare one file's entries with the repo-wide table.

    Args:
        entries: The entries the header lists.
        table: Each failure the table lists, keyed by its sub-code.

    Returns:
        One problem per entry that disagrees, empty when every entry matches.
    """
    problems: list[HeaderProblem] = []
    for number, sub_code, wording in entries:
        row = table.get(sub_code)
        if row is None:
            message = f"the sub-code {sub_code} is not in {EXIT_CODES_FILE.name}"
        elif number != row.code:
            message = (
                f"{sub_code} is listed under {number}, and the table gives it "
                f"{row.code}"
            )
        elif wording.split(ASIDE, 1)[0].rstrip(".") != row.what_happened:
            stated = wording.split(ASIDE, 1)[0].rstrip(".")
            message = (
                f"{sub_code} says {stated!r}, and the table says {row.what_happened!r}"
            )
        else:
            continue
        problems.append(HeaderProblem(message, 16, "HEADER-EXIT-CODES-DISAGREE"))
    return problems


#######################################################################################
### Reading what the code names ###


def defines_main(tree: ast.Module) -> bool:
    """Say whether a file defines a main() function.

    A main() is found wherever returned_codes looks for one, so the two never
    disagree about whether a file has one.

    Args:
        tree: The parsed file.

    Returns:
        True when the file defines a function named main.
    """
    return any(
        isinstance(node, ast.FunctionDef) and node.name == "main"
        for node in ast.walk(tree)
    )


def returned_codes(tree: ast.Module) -> set[int]:
    """Collect the exit codes a file's main() hands back as a plain number.

    Only main() is read, and only returns written as a number are collected, including
    the two sides of a one-line choice such as "return 10 if stray else 0". A return
    of anything else, a call or a computed value, is passed over rather than guessed
    at. A failure reported through fail() or finish() is found by named_pairs()
    instead.

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


def _number_then_sub_code(nodes: list[ast.expr]) -> list[tuple[int, str]]:
    """Find each number written straight before a sub-code in a run of values.

    Args:
        nodes: The values, such as a call's arguments or a tuple's items.

    Returns:
        Each number and the sub-code written after it.
    """
    found = []
    for first, second in zip(nodes, nodes[1:], strict=False):
        if (
            isinstance(first, ast.Constant)
            and type(first.value) is int
            and isinstance(second, ast.Constant)
            and isinstance(second.value, str)
            and SUB_CODE_RE.match(second.value)
        ):
            found.append((first.value, second.value))
    return found


def named_pairs(tree: ast.Module) -> list[tuple[int, str]]:
    """Collect every exit number and sub-code the file's code names together.

    Two forms are read. A number written straight before a sub-code, among a call's
    arguments or a tuple's or list's items, as in fail(say, 9, "NEO4J-UNREACHABLE",
    message) or (12, "GROUPS-FILE-MISSING"). And an error class that sets exit_code
    and sub_code in its body. A number or sub-code held in a variable is passed over
    rather than guessed at.

    Args:
        tree: The parsed file.

    Returns:
        Each number and sub-code, in the order the file names them.
    """
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            found.extend(_number_then_sub_code(list(node.args)))
        elif isinstance(node, ast.Tuple | ast.List):
            found.extend(_number_then_sub_code(list(node.elts)))
        elif isinstance(node, ast.ClassDef):
            values: dict[str, object] = {}
            for statement in node.body:
                if (
                    isinstance(statement, ast.Assign)
                    and len(statement.targets) == 1
                    and isinstance(statement.targets[0], ast.Name)
                    and isinstance(statement.value, ast.Constant)
                ):
                    values[statement.targets[0].id] = statement.value.value
            number, sub_code = values.get("exit_code"), values.get("sub_code")
            if isinstance(number, int) and isinstance(sub_code, str):
                found.append((number, sub_code))
    return found


def pair_problems(
    pairs: list[tuple[int, str]], table: dict[str, Row]
) -> list[HeaderProblem]:
    """Name every number and sub-code the code names together that the table does not
    hold.

    Args:
        pairs: The numbers and sub-codes the code names.
        table: Each failure the table lists, keyed by its sub-code.

    Returns:
        One problem per pair the table does not hold, each named once.
    """
    problems: list[HeaderProblem] = []
    for number, sub_code in sorted(set(pairs)):
        row = table.get(sub_code)
        if row is None:
            message = (
                f"the code names the sub-code {sub_code}, which is not in "
                f"{EXIT_CODES_FILE.name}"
            )
        elif row.code != number:
            message = (
                f"the code names {sub_code} with exit {number}, and the table gives "
                f"it {row.code}"
            )
        else:
            continue
        problems.append(HeaderProblem(message, 16, "HEADER-EXIT-CODES-DISAGREE"))
    return problems


def unlisted_codes(
    returned: set[int],
    pairs: list[tuple[int, str]],
    entries: list[tuple[int, str, str]],
) -> list[HeaderProblem]:
    """Name every number main() returns and every sub-code the code names that the
    header does not list.

    Args:
        returned: The numbers main() can return.
        pairs: The numbers and sub-codes the file's code names.
        entries: The entries the header lists.

    Returns:
        One problem per number or sub-code that is used but not listed.
    """
    listed_numbers = {number for number, _, _ in entries}
    listed_sub_codes = {sub_code for _, sub_code, _ in entries}
    problems = [
        HeaderProblem(
            f"exit code {number} is returned by main() but the header does not list it",
            16,
            "HEADER-EXIT-CODE-UNLISTED",
        )
        for number in sorted(returned - listed_numbers)
    ]
    problems += [
        HeaderProblem(
            f"the code ends on {sub_code} but the header does not list it",
            16,
            "HEADER-EXIT-CODE-UNLISTED",
        )
        for sub_code in sorted({sub_code for _, sub_code in pairs} - listed_sub_codes)
    ]
    return problems


#######################################################################################
### Find the files and confirm each header ###


def files_to_check() -> list[Path]:
    """List every Python file under the folders this script validates, with __init__.py files left out.

    Returns:
        The files, sorted.
    """
    found: list[Path] = []
    for folder in CHECKED_FOLDERS:
        found.extend(p for p in folder.rglob("*.py") if p.name != "__init__.py")
    return sorted(found)


def problems_in(
    path: Path, table: dict[str, Row]
) -> tuple[list[HeaderProblem], list[HeaderProblem]]:
    """Confirm one file's header block, and the exit codes it and its code name.

    Args:
        path: The file to confirm.
        table: Each failure the repo-wide table lists, keyed by its sub-code.

    Returns:
        Two lists: the problems with the block itself, and the problems with the exit
            codes. Each problem carries the exit number and sub-code its kind calls
            for.
    """
    fields, error = parse_header(path)
    if error:
        return [error], []

    # parse_header hands back either the fields or an error, never neither,
    # so once the error is handled the fields are present. mypy cannot see the
    # two halves of the pair move together, hence the assertion.
    assert fields is not None

    problems: list[HeaderProblem] = []

    missing = [field for field in REQUIRED_FIELDS if field not in fields]
    if missing:
        problems.append(
            HeaderProblem(f"missing {', '.join(missing)}", 15, "HEADER-INCOMPLETE")
        )

    # Order is confirmed only over the fields present, so a missing field is
    # reported once, above, and not again as a misordering.
    present = [field for field in fields if field in REQUIRED_FIELDS]
    expected = [field for field in REQUIRED_FIELDS if field in fields]
    if present != expected:
        problems.append(
            HeaderProblem(
                f"fields out of order: {', '.join(present)}", 15, "HEADER-INCOMPLETE"
            )
        )

    date = (fields.get("Date") or [""])[0].strip()
    if "Date" in fields and not DATE_RE.match(date):
        problems.append(
            HeaderProblem(f"Date is {date!r}, not YYYY-MM-DD", 15, "HEADER-INCOMPLETE")
        )

    entries = code_entries(fields.get("Exit codes", []), value_column(path))
    codes = code_problems(entries, table)

    # The file is parsed a second time here rather than threaded through the header
    # parser, which hands back the header alone. Parsing is cheap and keeps the two
    # readers independent. A file that will not parse never reaches this point,
    # because the header parser's error returns above.
    tree = ast.parse(path.read_text(encoding="utf-8"))
    pairs = named_pairs(tree)
    codes += pair_problems(pairs, table)

    # A tool run as a command has a main(), and its exit codes are what a person
    # reads to learn why it stopped. An Exit codes field with no entry would be
    # compared with nothing, so it is refused, and every failure the command's own
    # code names has to be listed. A file with no main(), such as a check file or a
    # library module, may describe its codes in a sentence. A field that is missing
    # altogether is already reported above.
    if defines_main(tree):
        if "Exit codes" in fields and not entries:
            problems.append(
                HeaderProblem(
                    "the Exit codes field lists no exit code, but the file has a "
                    "main(); list each one it can end on, one per line, with the "
                    f"number, sub-code and wording from {EXIT_CODES_FILE.name}",
                    15,
                    "HEADER-INCOMPLETE",
                )
            )
        codes += unlisted_codes(returned_codes(tree), pairs, entries)

    return problems, codes


#######################################################################################
### Command line ###


def main(argv: list[str] | None = None) -> int:
    """Confirm every file and print each problem, unless --quiet.

    Args:
        argv: The command-line arguments, or None to read the real ones.

    Returns:
        The exit code, as the header block lists them.
    """
    parser = argparse.ArgumentParser(
        description="Confirm every header block in the three code folders."
    )
    parser.add_argument(
        "--quiet", action="store_true", help="print nothing; use the exit code"
    )
    args = parser.parse_args(argv)

    def say(message: str) -> None:
        """Print a line, unless --quiet was given."""
        if not args.quiet:
            print(message)

    # The table is read once, so a table that cannot be read stops the run rather
    # than being reported against every file in turn. A table that is missing, one
    # that cannot be opened, and one that breaks its rules have different fixes, so
    # each has its own sub-code.
    try:
        table = exit_code_table()
    except FileNotFoundError as exc:
        return fail(
            say,
            12,
            "EXIT-TABLE-MISSING",
            f"{EXIT_CODES_FILE.name} is missing: {exc}\n"
            "  fix -> restore docs/exit_codes.csv from git",
        )
    except OSError as exc:
        return fail(
            say,
            13,
            "EXIT-TABLE-UNREADABLE",
            f"{EXIT_CODES_FILE.name} cannot be opened: {exc}\n"
            "  fix -> close any program holding the file, then run this again",
        )
    except TableError as exc:
        return fail(
            say,
            exc.exit_code,
            exc.sub_code,
            f"{EXIT_CODES_FILE.name}: {exc}\n"
            "  fix -> correct that row of docs/exit_codes.csv",
        )

    # Each problem carries its own number and sub-code, so the run's exit line is
    # chosen from the kinds found and never from how a message is worded.
    found: dict[str, HeaderProblem] = {}
    for path in files_to_check():
        problems, codes = problems_in(path, table)
        for problem in problems + codes:
            found.setdefault(problem.sub_code, problem)
            name = path.relative_to(REPO_ROOT).as_posix()
            say(problem_line(problem.sub_code, f"{name}: {problem.message}"))

    for sub_code in PRECEDENCE:
        if sub_code in found:
            return finish(say, found[sub_code].code, sub_code)
    return 0


if __name__ == "__main__":
    sys.exit(main())
