"""
Script:      build_inventory.py
Description: Generates validation/validation_inventory.csv, the list of every check
             in the test files under validation/, from the checks themselves, so the inventory
             cannot drift from the code it describes. Each check's name, its
             permanent id (the @code marker), its category (the @category marker),
             its objective (the @objective marker), whether a correctness check
             is a positive or a negative case, and its expected result (its
             docstring's first paragraph) are read from the file. Four columns are kept by hand and carried over from the
             existing inventory by id: status, superseded_by, status_reason and
             version. A new check starts as active at version 1. A check that no
             longer exists drops out, which holds until the first validation run.

             A check is refused, and nothing is written, when any of these is
             true:
               - it has no @code marker, or an id another check already carries,
                 because the id is what joins a validation report to the inventory;
               - its id is not three capital letters and four digits, or those
                 letters are not one of the registered prefixes. Whether a prefix
                 still names the folder of the file its check covers is not
                 checked, because a check that moves keeps the id it was filed
                 under;
               - it has no @category marker, or one that names no category;
               - it has no @objective marker, or one that names no objective;
               - its first sentence starts with a character a spreadsheet reads
                 as the start of a formula.

             The hand-kept columns are checked too. A status must be one of the
             five, superseded_by must name the active checks that took over
             exactly when the status is superseded, status_reason must say why
             when the status is inactive or retired, a version must be a whole
             number, and a check that is still in the test files can be neither
             superseded nor retired. --check-status runs this check alone on the
             inventory on disk.

             With --check, nothing is written: the script says whether the
             inventory on disk is what would be generated, and the pre-commit
             hook runs it that way, so a commit that changes a check without
             regenerating the inventory is refused.

Inputs:      validation/**/test_*.py             (read-only, parsed rather than imported)
             validation/validation_inventory.csv (read for the hand-kept columns)

Outputs:     validation/validation_inventory.csv, rewritten in full. With --check
             or --check-status, nothing on disk.

Usage:       python repo_tools/build_inventory.py
                 regenerate the inventory
             python repo_tools/build_inventory.py --check
                 report whether the inventory on disk is current; write nothing.
                 For hooks.
             python repo_tools/build_inventory.py --check-status
                 check only the hand-kept columns of the inventory on disk;
                 write nothing
             python repo_tools/build_inventory.py --quiet
                 print nothing; use the exit code

Exit codes:  0   success (the inventory was written, or a check found it in order)
             1   unhandled error, Python's own
             2   invalid command line, the argument parser's own
             16  the validation inventory is stale or missing (--check and
                 --check-status only)
             18  a check's markers, id or first sentence are missing or wrong, or
                 its id is a duplicate
             19  a Python file could not be parsed
             20  no files found to work on
             45  a hand-kept column of the validation inventory breaks its rules
             19 outranks 20, 20 outranks 18, and 18 outranks 45. Every problem is
             still named. The numbers are the repo-wide table in
             validation/exit_codes.csv.

Date:        2026-09-11
Owner:       Jason Delosh
"""

from __future__ import annotations

import argparse
import ast
import csv
import io
import re
import sys
from dataclasses import dataclass
from pathlib import Path

#######################################################################################
### Settings ###

REPO_ROOT = Path(__file__).resolve().parents[1]
VALIDATION_DIR = REPO_ROOT / "validation"
INVENTORY_PATH = VALIDATION_DIR / "validation_inventory.csv"

# The columns, in order. The check's own columns are bare; only the two about the
# covered file carry a prefix. The check columns are shared with the validation
# report, which joins on id. What each column holds is defined in
# validation/validation_inventory_dictionary.md.
COLUMNS = (
    "category",
    "quality_aspect",
    "objective",
    "staged_case",
    "folder_path",
    "file_name",
    "name",
    "id",
    "target_folder_path",
    "target_file_name",
    "expected_result",
    "version",
    "status",
    "superseded_by",
    "status_reason",
)

# The columns a person keeps by hand. The generator carries them over by id and
# never works them out.
HAND_KEPT = ("status", "superseded_by", "status_reason", "version")

# What kind of thing a check confirms. validation/validation_inventory_dictionary.md
# defines each one.
CATEGORIES = ("repository", "sources", "processing", "products")

# The objectives each aspect of quality holds. A check carries only its objective,
# and the generator looks the aspect up here, so an objective can never be filed
# under an aspect it does not belong to. Adding an objective means adding it here,
# which is what keeps the two in step. The dictionary defines every one of them.
OBJECTIVES_BY_ASPECT = {
    "conformance": ("conformance",),
    "integrity": ("correctness", "completeness", "stability", "consistency"),
    "operation": (
        "performance",
        "reliability",
        "security",
        "compatibility",
        "maintainability",
        "portability",
    ),
}

# Every objective, and the aspect each one belongs to. Both are worked out from the
# table above rather than typed a second time, so neither can drift from it.
ASPECT_OF = {
    objective: aspect
    for aspect, objectives in OBJECTIVES_BY_ASPECT.items()
    for objective in objectives
}
OBJECTIVES = tuple(ASPECT_OF)

# A check that staged its own situation carries one of these, saying whether the
# situation was a working one or a broken one. A check that looked at something real
# carries neither. The case says how the check was set up, which is a separate thing
# from the question it asks, so any objective may carry one.
CASES = ("positive", "negative")

# The three letters a check's id may start with, and the folder each one names. A
# check takes its folder's prefix when it is first filed, and the id never changes
# afterwards, so a check that later moves keeps a prefix its folder no longer
# matches. That is why only the letters themselves are checked, not whether they
# still fit. A new folder needs a new prefix added here.
# validation/validation_inventory_dictionary.md describes them for a reader.
ID_PREFIXES = {
    "SRC": "src/sdg/sources",
    "USD": "src/sdg/usdm",
    "VIW": "src/sdg/view",
    "SDG": "src/sdg",
    "HRS": "repo_tools",
    "CCH": ".claude/hooks",
    "TST": "validation",
}

# An id is three capital letters and four digits, such as SRC0042.
ID_SHAPE = re.compile(r"[A-Z]{3}[0-9]{4}")

# Where a check stands. validation/README.md says what each one means.
STATUSES = ("pending", "active", "inactive", "superseded", "retired")

# The statuses that need a reason written down, because each leaves something
# unguarded.
NEEDS_REASON = ("inactive", "retired")

# A spreadsheet reads a cell that starts with one of these as a formula, and shows
# or mangles it rather than the sentence.
FORMULA_STARTS = ("=", "+", "-", "@", "\t", "\r")

# Rows are grouped by the folder the test file sits in, in the order the pipeline
# runs, then the top-level files of the sdg package, then the tools and hooks, with
# the checks for validation's own files last. Within a folder, files are in name order and
# checks in file order.
TYPE_ORDER = (
    "sources",
    "usdm",
    "view",
    "sdg",
    "repo_tools",
    "claude_hooks",
    "validation",
)

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
    check_id: str
    category: str
    objective: str
    case: str
    expected_result: str


def first_paragraph(doc: str | None) -> str:
    """Give a docstring's first paragraph as one line.

    That paragraph is the check's expected result, and it is what the inventory and
    the validation report both show.

    Args:
        doc: The docstring, or None when there is none.

    Returns:
        The first paragraph joined to one line, or an empty string.
    """
    if not doc:
        return ""
    return " ".join(doc.strip().split("\n\n")[0].split())


def type_and_target(
    check_file: Path, validation_dir: Path | None = None
) -> tuple[str, str]:
    """Work out a test file's group and the code file it proves.

    This is the one place the rule is written. validation/conftest.py uses it too, to
    fill the same columns of a validation report, so the inventory and the report can
    never disagree about what a check file proves.

    validation/ mirrors the code. A test file in validation/repo_tools/ tests the script of the
    same name in repo_tools/. A test file in validation/claude_hooks/ tests the hook of the
    same name in .claude/hooks/, which cannot be mirrored by name because pytest does
    not look inside a folder whose name starts with a dot. A test file in any other
    subfolder tests the file of the same name in that folder under src/sdg/. A test
    file at the top level tests the file of the same name in validation/ itself when
    one is there, as the checks for conftest.py and select_checks.py do, and
    otherwise the file of the same name at the top of src/sdg/.

    Args:
        check_file: The test file's path.
        validation_dir: The validation folder the path is read against, or None for
            the repo's own.

    Returns:
        The group name and the target's repo-relative path.
    """
    relative = check_file.relative_to(validation_dir or VALIDATION_DIR)
    folder = relative.parent.as_posix()
    component = f"{check_file.stem.removeprefix('test_')}.py"
    if folder == "." and (check_file.parent / component).is_file():
        return "validation", f"validation/{component}"
    if folder == ".":
        return "sdg", f"src/sdg/{component}"
    if folder == "repo_tools":
        return "repo_tools", f"repo_tools/{component}"
    if folder == "claude_hooks":
        return "claude_hooks", f".claude/hooks/{component}"
    return folder, f"src/sdg/{folder}/{component}"


def split_path(path: str) -> tuple[str, str]:
    """Split a repo-relative path into its folder and its file name.

    Args:
        path: The path, written with forward slashes.

    Returns:
        The folder, or an empty string for a file at the repo root, and the file name.
    """
    folder, _, name = path.rpartition("/")
    return folder, name


def _marker_argument(decorator: ast.expr, name: str) -> str | None:
    """Read the text a marker such as @code("XYZ0001") was given.

    Args:
        decorator: One decorator of a check.
        name: The marker's short name, such as code, target or objective.

    Returns:
        The text in the brackets, or None when the decorator is not that marker.
    """
    if (
        isinstance(decorator, ast.Call)
        and getattr(decorator.func, "id", "") == name
        and decorator.args
        and isinstance(decorator.args[0], ast.Constant)
    ):
        return str(decorator.args[0].value)
    return None


def checks_in(path: Path) -> tuple[list[Check], list[str]]:
    """Read every check in one test file.

    Args:
        path: The test file.

    Returns:
        The checks found, and the problems found with their markers and first
        sentences. A file that cannot be parsed is one problem and no checks.
    """
    # A file that will not parse is reported as one problem with no checks, so
    # one broken file does not hide the state of the rest.
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, ValueError, OSError) as exc:
        return [], [f"{_name(path)}: cannot parse ({exc})"]

    checks: list[Check] = []
    problems: list[str] = []
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef) or not node.name.startswith("test_"):
            continue
        # A check is written as @code("XYZ0001"), @category("repository"),
        # @objective("correctness") and, for a correctness check that staged its
        # situation, @positive or @negative: the short names the test files give
        # pytest's markers.
        code = category = objective = case = ""
        has_category = has_objective = False
        for decorator in node.decorator_list:
            if (found := _marker_argument(decorator, "code")) is not None:
                code = found
            elif (found := _marker_argument(decorator, "category")) is not None:
                category, has_category = found, True
            elif (found := _marker_argument(decorator, "objective")) is not None:
                objective, has_objective = found, True
            elif isinstance(decorator, ast.Name) and decorator.id in CASES:
                case = decorator.id
        expected = first_paragraph(ast.get_docstring(node))
        where = f"{_name(path)}: {node.name}"

        if not code:
            problems.append(f"{where} has no @code marker")
        if not has_category:
            problems.append(f"{where} has no @category marker")
        elif category not in CATEGORIES:
            problems.append(
                f"{where} has @category({category!r}), which is not one of "
                f"{', '.join(CATEGORIES)}"
            )
        if not has_objective:
            problems.append(f"{where} has no @objective marker")
        elif objective not in OBJECTIVES:
            problems.append(
                f"{where} has @objective({objective!r}), which is not one of "
                f"{', '.join(OBJECTIVES)}"
            )
        if expected.startswith(FORMULA_STARTS):
            problems.append(
                f"{where} has a first sentence starting with {expected[0]!r}, which a "
                "spreadsheet reads as a formula; start it with a word"
            )

        checks.append(
            Check(
                check_file=_name(path),
                check_name=node.name,
                check_id=code,
                category=category,
                objective=objective,
                case=case,
                expected_result=expected,
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


def read_checks() -> tuple[list[tuple[str, str, Check]], list[str]]:
    """Read every check in every test file under the validation folder.

    Returns:
        Each check with its group and target, and the problems found. An empty
        validation folder is one problem.
    """
    files = sorted(VALIDATION_DIR.rglob("test_*.py"))
    if not files:
        return [], [f"no test files found under {_name(VALIDATION_DIR)}"]
    found: list[tuple[str, str, Check]] = []
    problems: list[str] = []
    for path in files:
        group, target = type_and_target(path)
        checks, file_problems = checks_in(path)
        problems.extend(file_problems)
        found.extend((group, target, check) for check in checks)
    return found, problems


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
        return {row["id"]: row for row in csv.DictReader(fh)}


def build_rows() -> tuple[list[dict[str, str]], list[str]]:
    """Build every inventory row from the test files.

    Returns:
        The rows in inventory order, and the problems found with the checks. When
        there is any problem the rows are not to be written.
    """
    found, problems = read_checks()

    # An id must name one check, since a validation report joins on it.
    seen: dict[str, str] = {}
    for _, _, check in found:
        if check.check_id in seen:
            problems.append(
                f"{check.check_id} is carried by both {seen[check.check_id]} "
                f"and {check.check_name}"
            )
        elif check.check_id:
            seen[check.check_id] = check.check_name

    previous = existing_rows()
    grouped: list[tuple[str, dict[str, str]]] = []
    for group, target, check in found:
        old = previous.get(check.check_id, {})
        validation_folder, validation_file = split_path(check.check_file)
        target_folder, target_file = split_path(target)
        row = {
            "folder_path": validation_folder,
            "file_name": validation_file,
            "target_folder_path": target_folder,
            "target_file_name": target_file,
            "name": check.check_name,
            "id": check.check_id,
            "category": check.category,
            # Worked out from the objective rather than marked on the check, so the
            # two can never disagree and nobody has to keep them in step by hand.
            "quality_aspect": ASPECT_OF.get(check.objective, ""),
            "objective": check.objective,
            "staged_case": check.case,
            "expected_result": check.expected_result,
        }
        # The hand-kept columns come from the existing row. A new check gets the
        # starting status and version and leaves the other two empty.
        row["status"] = old.get("status", NEW_STATUS)
        row["superseded_by"] = old.get("superseded_by", "")
        row["status_reason"] = old.get("status_reason", "")
        row["version"] = old.get("version", NEW_VERSION)
        grouped.append((group, row))
    # Groups in pipeline order; a group not in the list, a new folder, goes last.
    grouped.sort(
        key=lambda pair: (
            TYPE_ORDER.index(pair[0]) if pair[0] in TYPE_ORDER else len(TYPE_ORDER)
        )
    )
    rows = [row for _, row in grouped]
    problems.extend(id_problems(rows))
    return rows, problems


def id_problems(rows: list[dict[str, str]]) -> list[str]:
    """Check every id for its shape and for carrying a registered prefix.

    Whether a prefix still names the folder of the file its check covers is not
    checked. A prefix is chosen when a check is first filed and the id never
    changes, so a check that later moves keeps one its folder no longer matches,
    and the generator cannot tell that apart from a wrong choice without a record
    of when each check was filed.

    Args:
        rows: The rows about to be written.

    Returns:
        One problem per rule an id breaks, or nothing when every id is in order.
    """
    problems: list[str] = []
    for row in rows:
        check_id = row["id"]
        where = f"{row['folder_path']}/{row['file_name']}: {row['name']}"
        # A missing marker is already reported where the check was read, so it is
        # not reported a second time here.
        if not check_id:
            continue
        if not ID_SHAPE.fullmatch(check_id):
            problems.append(
                f"{where} has the id {check_id!r}, which is not three capital "
                "letters and four digits, such as SRC0042"
            )
        elif check_id[:3] not in ID_PREFIXES:
            problems.append(
                f"{where} has the id {check_id}, and {check_id[:3]} is not one of "
                f"the prefixes {', '.join(ID_PREFIXES)}"
            )
    return problems


def status_problems(rows: list[dict[str, str]], live_ids: set[str]) -> list[str]:
    """Check the hand-kept columns of every row against their rules.

    It can run on the rows the generator is about to write or on the inventory on
    disk, which is what --check-status does.

    Args:
        rows: The inventory's rows.
        live_ids: The ids of the checks that are in the test files now.

    Returns:
        One line per problem, naming the check and what is wrong.
    """
    status_of = {row["id"]: row["status"] for row in rows}
    problems: list[str] = []
    for row in rows:
        check_id, status = row["id"], row["status"]
        successors = [s.strip() for s in row["superseded_by"].split(";") if s.strip()]

        if status not in STATUSES:
            problems.append(
                f"{check_id} has status {status!r}, which is not one of "
                f"{', '.join(STATUSES)}"
            )
        if status == "superseded" and not successors:
            problems.append(
                f"{check_id} is superseded but superseded_by names no check"
            )
        if status != "superseded" and successors:
            problems.append(
                f"{check_id} names checks in superseded_by but is {status}, "
                "not superseded"
            )
        for successor in successors:
            if status_of.get(successor) != "active":
                problems.append(
                    f"{check_id} is superseded by {successor}, which is not an "
                    "active check in the inventory"
                )
        if status in NEEDS_REASON and not row["status_reason"].strip():
            problems.append(
                f"{check_id} is {status} but status_reason does not say why"
            )
        if status not in NEEDS_REASON and row["status_reason"].strip():
            problems.append(
                f"{check_id} has a status_reason but is {status}, and only "
                f"{' and '.join(NEEDS_REASON)} say why they are off"
            )
        if not row["version"].isdigit() or int(row["version"]) < 1:
            problems.append(
                f"{check_id} has version {row['version']!r}, which is not a whole "
                "number from 1 up"
            )
        # A superseded or retired check has been taken out of use, so it cannot
        # still be in the test files, where every run would run it.
        if status in ("superseded", "retired") and check_id in live_ids:
            problems.append(
                f"{check_id} is {status} but is still in the test files; remove the "
                "check or change its status"
            )
    return problems


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
        description="Generate validation/validation_inventory.csv from the checks."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--check",
        action="store_true",
        help="report whether the inventory is current; write nothing",
    )
    mode.add_argument(
        "--check-status",
        action="store_true",
        help="check only the hand-kept columns of the inventory on disk; write nothing",
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

    inventory = _name(INVENTORY_PATH)

    if args.check_status:
        found, problems = read_checks()
        # Only a file that will not parse or an empty folder stops this mode, since
        # it needs the checks' ids and nothing else about them.
        blocking = [
            p for p in problems if ": cannot parse" in p or "no test files" in p
        ]
        for problem in blocking:
            say(problem)
        if blocking:
            return 19 if any(": cannot parse" in p for p in blocking) else 20
        if not INVENTORY_PATH.is_file():
            say(f"{inventory} is missing. Run: python repo_tools/build_inventory.py")
            return 16
        on_disk = list(existing_rows().values())
        live = {check.check_id for _, _, check in found}
        status = status_problems(on_disk, live)
        for problem in status:
            say(problem)
        if status:
            return 45
        say(f"{inventory}: the hand-kept columns are in order")
        return 0

    rows, problems = build_rows()
    live = {row["id"] for row in rows}
    status = status_problems(rows, live)
    for problem in problems + status:
        say(problem)
    if problems or status:
        # A parse failure, an empty validation folder, a check with bad markers and
        # a bad hand-kept column need different fixes, so each carries its own code.
        say("Inventory not written.")
        if any(": cannot parse" in p for p in problems):
            return 19
        if any(p.startswith("no test files") for p in problems):
            return 20
        if problems:
            return 18
        return 45

    text = render(rows)

    if args.check:
        current = (
            INVENTORY_PATH.open(encoding="utf-8", newline="").read()
            if INVENTORY_PATH.is_file()
            else None
        )
        if current == text:
            say(f"{inventory} is current, {len(rows)} check(s)")
            return 0
        say(f"{inventory} is stale. Run: python repo_tools/build_inventory.py")
        return 16

    INVENTORY_PATH.write_text(text, encoding="utf-8", newline="")
    say(f"{inventory} written, {len(rows)} check(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
