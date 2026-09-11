"""
Script:      build_inventory.py
Description: Generates tests/validation_inventory.csv, the list of every check
             in the test files, from the checks themselves, so the inventory
             cannot drift from the code it describes. Each check's name, its
             permanent id (the @code marker), whether it is positive or
             negative, and the sentence it proves (its docstring's first
             paragraph) are read from the file. Two columns are kept by hand
             and carried over from the existing inventory by id: status and
             version. A new check starts as active at version 1. A check that
             no longer exists drops out.

             A check with no @code marker, no positive or negative marker, or an
             id another check already carries is refused, and nothing is
             written, because the id is what joins a validation record to the
             inventory.

             With --check, nothing is written: the script says whether the
             inventory on disk is what would be generated, and the pre-commit
             hook runs it that way, so a commit that changes a check without
             regenerating the inventory is refused.

Inputs:      tests/**/test_*.py             (read-only, parsed rather than imported)
             tests/validation_inventory.csv (read for the hand-kept columns)

Outputs:     tests/validation_inventory.csv, rewritten in full. With --check,
             nothing on disk.

Usage:       python scripts/build_inventory.py
                 regenerate the inventory
             python scripts/build_inventory.py --check
                 report whether the inventory on disk is current; write nothing.
                 For hooks.
             python scripts/build_inventory.py --quiet
                 print nothing; use the exit code

Exit codes:  0  the inventory was written, or --check found it current
             1  --check found the inventory stale or missing
             2  a check has no id, no kind, or an id another check carries
             3  no checks were found, or a test file could not be parsed

Date:        2026-09-11
Owner:       Jason Delosh
"""

from __future__ import annotations

import argparse
import ast
import csv
import io
import sys
from dataclasses import dataclass
from pathlib import Path

#######################################################################################
### Settings ###

REPO_ROOT = Path(__file__).resolve().parents[1]
TESTS_DIR = REPO_ROOT / "tests"
INVENTORY_PATH = TESTS_DIR / "validation_inventory.csv"

# The columns, in the order the inventory has always had them. The check columns
# are shared with the validation record, which joins on check_name_code.
COLUMNS = (
    "type",
    "target_file",
    "check_file",
    "check_name",
    "check_name_code",
    "kind",
    "proves",
    "status",
    "version",
)

# Rows are grouped by the folder the test file sits in, in the order the pipeline
# runs, with the record writer's own checks last. Within a folder, files are in
# name order and checks in file order.
TYPE_ORDER = ("sources", "usdm", "scripts", "tests")

# What a check starts with when it first appears in the inventory.
NEW_STATUS = "active"
NEW_VERSION = "1"


#######################################################################################
### Reading the checks ###
#
# The test files are parsed with ast rather than imported, so generating the
# inventory never runs a check and needs none of the packages the checks import.


@dataclass(frozen=True)
class Check:
    """One check as read from its test file."""

    check_file: str
    check_name: str
    check_name_code: str
    kind: str
    proves: str


def first_paragraph(doc: str | None) -> str:
    """Give a docstring's first paragraph as one line.

    That paragraph is the sentence the check proves, and it is what the inventory
    and the validation record both show.

    Args:
        doc: The docstring, or None when there is none.

    Returns:
        The first paragraph joined to one line, or an empty string.
    """
    if not doc:
        return ""
    return " ".join(doc.strip().split("\n\n")[0].split())


def type_and_target(check_file: Path) -> tuple[str, str]:
    """Work out a test file's group and the code file it proves.

    tests/ mirrors the code. A test file in tests/scripts/ tests the script of the
    same name in scripts/. A test file in any other subfolder tests the file of the
    same name in that folder under src/sdg/. A test file at the top level tests the
    record writer in tests/conftest.py.

    Args:
        check_file: The test file's path.

    Returns:
        The group name and the target's repo-relative path.
    """
    relative = check_file.relative_to(TESTS_DIR)
    folder = relative.parent.as_posix()
    component = f"{check_file.stem.removeprefix('test_')}.py"
    if folder == ".":
        return "tests", "tests/conftest.py"
    if folder == "scripts":
        return "scripts", f"scripts/{component}"
    return folder, f"src/sdg/{folder}/{component}"


def checks_in(path: Path) -> tuple[list[Check], list[str]]:
    """Read every check in one test file.

    Args:
        path: The test file.

    Returns:
        The checks found, and the problems found: a check with no id, or with no
        positive or negative marker. A file that cannot be parsed is one problem
        and no checks.
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, ValueError, OSError) as exc:
        return [], [f"{_name(path)}: cannot parse ({exc})"]

    checks: list[Check] = []
    problems: list[str] = []
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef) or not node.name.startswith("test_"):
            continue
        code = kind = ""
        for decorator in node.decorator_list:
            # A check is written as @code("XYZ0001") and @positive or @negative,
            # the short names the test files give pytest's markers.
            if (
                isinstance(decorator, ast.Call)
                and getattr(decorator.func, "id", "") == "code"
                and decorator.args
                and isinstance(decorator.args[0], ast.Constant)
            ):
                code = str(decorator.args[0].value)
            elif isinstance(decorator, ast.Name) and decorator.id in (
                "positive",
                "negative",
            ):
                kind = decorator.id
        if not code:
            problems.append(f"{_name(path)}: {node.name} has no @code marker")
        if not kind:
            problems.append(
                f"{_name(path)}: {node.name} has no @positive or @negative marker"
            )
        checks.append(
            Check(
                check_file=_name(path),
                check_name=node.name,
                check_name_code=code,
                kind=kind,
                proves=first_paragraph(ast.get_docstring(node)),
            )
        )
    return checks, problems


def _name(path: Path) -> str:
    """Give a file's repo-relative path with forward slashes, as the inventory writes it.

    Args:
        path: The file.

    Returns:
        The repo-relative path.
    """
    return path.relative_to(REPO_ROOT).as_posix()


#######################################################################################
### Building the rows ###


def existing_rows() -> dict[str, dict[str, str]]:
    """Read the inventory on disk, for the hand-kept columns.

    Returns:
        The existing rows keyed by check id, or nothing when there is no inventory
        yet.
    """
    if not INVENTORY_PATH.is_file():
        return {}
    with INVENTORY_PATH.open(encoding="utf-8", newline="") as fh:
        return {row["check_name_code"]: row for row in csv.DictReader(fh)}


def build_rows() -> tuple[list[dict[str, str]], list[str]]:
    """Build every inventory row from the test files.

    Returns:
        The rows in inventory order, and the problems found. When there is any
        problem the rows are not to be written.
    """
    files = sorted(TESTS_DIR.rglob("test_*.py"))
    if not files:
        return [], [f"no test files found under {_name(TESTS_DIR)}"]

    found: list[tuple[str, str, Check]] = []
    problems: list[str] = []
    for path in files:
        group, target = type_and_target(path)
        checks, file_problems = checks_in(path)
        problems.extend(file_problems)
        found.extend((group, target, check) for check in checks)

    # An id must name one check, since a validation record joins on it.
    seen: dict[str, str] = {}
    for _, _, check in found:
        if check.check_name_code in seen:
            problems.append(
                f"{check.check_name_code} is carried by both {seen[check.check_name_code]} "
                f"and {check.check_name}"
            )
        elif check.check_name_code:
            seen[check.check_name_code] = check.check_name

    previous = existing_rows()
    rows: list[dict[str, str]] = []
    for group, target, check in found:
        old = previous.get(check.check_name_code, {})
        rows.append(
            {
                "type": group,
                "target_file": target,
                "check_file": check.check_file,
                "check_name": check.check_name,
                "check_name_code": check.check_name_code,
                "kind": check.kind,
                "proves": check.proves,
                "status": old.get("status", NEW_STATUS),
                "version": old.get("version", NEW_VERSION),
            }
        )
    # Groups in pipeline order; a group not in the list, a new folder, goes last.
    rows.sort(
        key=lambda r: (
            TYPE_ORDER.index(r["type"]) if r["type"] in TYPE_ORDER else len(TYPE_ORDER)
        )
    )
    return rows, problems


def render(rows: list[dict[str, str]]) -> str:
    """Turn the rows into the inventory's text.

    The text is handed back rather than written, so that --check can compare it
    against the file on disk without a temporary file.

    Args:
        rows: The rows in inventory order.

    Returns:
        The complete CSV text.
    """
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


#######################################################################################
### Command line ###


def main(argv: list[str] | None = None) -> int:
    """Read every check, then write or check the inventory.

    Problems are collected across every file before returning, so one run names
    every check that needs fixing rather than stopping at the first.

    Args:
        argv: The command-line arguments, or None to read the real ones.

    Returns:
        The exit code, as the header block lists them.
    """
    parser = argparse.ArgumentParser(
        description="Generate tests/validation_inventory.csv from the checks."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="report whether the inventory is current; write nothing",
    )
    parser.add_argument(
        "--quiet", action="store_true", help="print nothing; use the exit code"
    )
    args = parser.parse_args(argv)

    def say(message: str = "") -> None:
        """Print the message, unless the run is quiet.

        Args:
            message: The line to print. Empty prints a blank line.
        """
        if not args.quiet:
            print(message)

    rows, problems = build_rows()
    for problem in problems:
        say(problem)
    if problems:
        # A parse failure or an empty tests folder is a broken repo; a check
        # without its markers is a broken check. They need different fixes and
        # so carry different codes.
        broken_repo = any(
            p.startswith("no test files") or ": cannot parse" in p for p in problems
        )
        say("Inventory not written.")
        return 3 if broken_repo else 2

    text = render(rows)
    inventory = _name(INVENTORY_PATH)

    if args.check:
        current = (
            INVENTORY_PATH.open(encoding="utf-8", newline="").read()
            if INVENTORY_PATH.is_file()
            else None
        )
        if current == text:
            say(f"{inventory} is current, {len(rows)} check(s)")
            return 0
        say(f"{inventory} is stale. Run: python scripts/build_inventory.py")
        return 1

    INVENTORY_PATH.write_text(text, encoding="utf-8", newline="")
    say(f"{inventory} written, {len(rows)} check(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
