"""
Script:      verify_headers.py
Description: Checks that every Python file in the package and in scripts/ opens
             with the full header block the writing_python_files rule requires, with the eight fields
             in the set order and a Date in YYYY-MM-DD form. It reports each file
             that falls short and names what is wrong.

             The git pre-commit hook runs it, so a commit that adds a file with
             a missing or disordered header is refused before it lands, whoever
             made the edit. It reads the header the same way build_index.py
             does, by borrowing that script's parser, so the two can never
             disagree about what a header is.

             __init__.py files are skipped: they carry a one-paragraph
             docstring naming the folder, not a header block.

Inputs:      src/sdg/**/*.py and scripts/*.py   (read-only, parsed rather than imported)

Outputs:     Nothing on disk. Prints one line per problem, or nothing when
             every header is complete.

Usage:       python scripts/verify_headers.py
                 check every file, report each problem
             python scripts/verify_headers.py --quiet
                 print nothing; use the exit code. For hooks.

Exit codes:  0  every header is complete and in order
             1  a header is missing, incomplete, out of order, or has a bad Date
             3  a file could not be parsed as Python

Date:        2026-09-09
Owner:       Jason Delosh
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# The parser and the field list live in build_index.py, which sits in this same
# folder. Python puts a running script's own folder first on its search path,
# so the plain import resolves without the package being installed.
from build_index import REQUIRED_FIELDS, parse_header

REPO_ROOT = Path(__file__).resolve().parents[1]
CHECKED_FOLDERS = (REPO_ROOT / "src" / "sdg", REPO_ROOT / "scripts")

# The Date field is the day the file was first committed, written as a plain
# calendar date. Anything else, a time, a range, a word, is a mistake.
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def files_to_check() -> list[Path]:
    """List every Python file under the checked folders, with __init__.py files left out.

    Returns:
        The files, sorted.
    """
    found: list[Path] = []
    for folder in CHECKED_FOLDERS:
        found.extend(p for p in folder.rglob("*.py") if p.name != "__init__.py")
    return sorted(found)


def problems_in(path: Path) -> tuple[list[str], bool]:
    """Check one file's header block.

    Args:
        path: The file to check.

    Returns:
        A pair: the list of problems found, empty when the header is complete, and
            whether the file could be parsed at all.
    """
    fields, error = parse_header(path)
    if error:
        return [error], "cannot parse" not in error

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

    return problems, True


def main(argv: list[str] | None = None) -> int:
    """Check every file and print each problem, unless --quiet.

    Args:
        argv: The command-line arguments, or None to read the real ones.

    Returns:
        The exit code, as the header block lists them.
    """
    parser = argparse.ArgumentParser(
        description="Check every header block in the package and scripts/."
    )
    parser.add_argument(
        "--quiet", action="store_true", help="print nothing; use the exit code"
    )
    args = parser.parse_args(argv)

    unparseable = 0
    incomplete = 0

    for path in files_to_check():
        problems, parsed = problems_in(path)
        if not problems:
            continue
        if parsed:
            incomplete += 1
        else:
            unparseable += 1
        if not args.quiet:
            name = path.relative_to(REPO_ROOT).as_posix()
            for problem in problems:
                print(f"{name}: {problem}")

    if unparseable:
        return 3
    if incomplete:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
