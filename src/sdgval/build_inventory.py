"""
Script:      build_inventory.py
Description: Generates validation/validation_inventory.csv, the list of every check
             in the check files under validation/, from the checks themselves, so
             the inventory cannot drift from the code it describes.

             The checks are found by pytest. The script asks pytest to collect the
             checks under validation/ without running any, the way pytest
             --collect-only does, and reads each check's labels with the same
             readers a validation report uses, in src/sdgval/labels.py. So the
             inventory lists exactly the checks a run would run, and it cannot read
             a label differently from a report. A check that pytest runs once per
             value is one check and gets one row.

             Each row holds these columns, read from the check:
               - its name and its check file;
               - its permanent id, from the @code marker;
               - its category, from the @category marker;
               - its objective, from the @objective marker;
               - whether a check that staged its own situation staged a working
                 case or a broken one;
               - its expected result, which is its docstring's first paragraph;
               - a fingerprint of the check, which is how the script knows the
                 check changed. It covers the check's code, its docstring and its
                 labels, and ignores how they are laid out. The cell also records
                 the version the fingerprint was taken at and the Python version,
                 major and minor, that took it.
             Four columns are kept by hand and carried over from the existing
             inventory by id: status, superseded_by, status_reason and version. A
             new check starts as active at version 1.

             Once a validation report has been filed, any change to a check that
             moves its fingerprint needs its version raised, because a report
             names the check by its id and version. While no validation report
             has been filed, a changed check's new fingerprint is recorded against
             the version it already has.

             A new Python version can write a check's code out differently, so
             every fingerprint may move although no check changed. Once a report
             has been filed, a run on a Python other than the one that made the
             recorded fingerprints stops with one message saying so, rather than
             refusing every check. --python-changed then records new fingerprints
             for the rows another Python made, without comparing them, and it
             belongs in a commit that changes nothing else. Rows the running
             Python made are still compared as usual. Once a report has been
             filed, a row whose fingerprint cell is empty or unreadable is
             refused too, because the change to its check could no longer be
             told.

             A row whose check is no longer in any check file is handled by its
             status and by whether a validation report has been filed:
               - a row marked superseded or retired is kept, so a filed report that
                 names it still finds it;
               - any other row is dropped while no validation report has been
                 filed under validation/reports/, because no report can name it;
               - any other row is refused once a validation report has been filed,
                 because that report may name it, and the row must be marked
                 superseded or retired instead.
             A filed report is a file src/sdgval/report.py writes, which is
             validation/reports/<aspect>/<aspect>_<YYYY-MM-DD>_<commit>.csv or the
             run file beside it. The folder's README, its dictionary, its .gitkeep
             and an empty aspect folder are not reports.

             The inventory stops, and nothing is written, when a check file cannot
             be loaded, because none of its checks can be read. A check file that
             is not valid Python is named with its own cause.

             A check is refused, and nothing is written, when any of these is
             true:
               - it has no @code marker, or an id another check already carries,
                 because the id is what joins a validation report to the inventory;
               - its id is not S, a suite letter and five digits, such as
                 SA00042, or its suite is not one of those SUITES lists;
               - it has no @category marker, or one that names no category;
               - it has no @objective marker, or one that names no objective;
               - it carries both @positive and @negative;
               - the runs of a check that runs once per value carry different
                 labels;
               - its docstring's first paragraph is missing or empty;
               - its first sentence starts with anything other than a letter or a
                 digit. Leading whitespace is not refused, because it is stripped
                 before the sentence is looked at;
               - it is written inside a class rather than as a function at the top
                 level of its check file, because the inventory and a report name a
                 check by its function's name alone;
               - its check file is in a code folder CODE_FOLDER_ORDER does not
                 list, because the folder's place in the inventory is a choice to
                 make, not a default;
               - a validation report has been filed, the check's code, docstring
                 or labels changed since its version was recorded, and its version
                 did not move;
               - a validation report has been filed, and the check's row has no
                 fingerprint recorded in the shape the fingerprint column holds.

             The hand-kept columns are confirmed too, by status_problems() below,
             whose docstring lists each rule. --check-status confirms these
             columns alone, on the inventory on disk.

             With --check, nothing is written: the script says whether the
             inventory on disk is what would be generated, and the pre-commit
             hook runs it that way, so a commit that changes a check without
             regenerating the inventory is refused.

Inputs:      validation/**/test_*.py             (read-only; imported by pytest's
                                                  collection, which runs no check)
             validation/conftest.py              (read-only; loaded by pytest's
                                                  collection)
             validation/validation_inventory.csv (read for the hand-kept columns
                                                  and the fingerprints)
             validation/reports/                 (read-only; looked at only to see
                                                  whether a validation report has
                                                  been filed)

Outputs:     validation/validation_inventory.csv, rewritten in full. With --check
             or --check-status, nothing on disk.

Usage:       build_inventory
                 regenerate the inventory
             build_inventory --check
                 report whether the inventory on disk is current; write nothing.
                 For hooks.
             build_inventory --check-status
                 confirm only the hand-kept columns of the inventory on disk;
                 write nothing
             build_inventory --python-changed
                 record new fingerprints for the rows another Python version
                 made; run it alone in a commit that changes nothing else
             build_inventory --quiet
                 print nothing; use the exit code

Exit codes:  0   the command succeeded (the inventory was written, or a check
                 found it in order)
             1   Python stopped on an error that nothing handled
             2   the argument parser refused the command line
             16  the validation inventory is stale or missing (--check and
                 --check-status only)
             18  a check's markers, id or first sentence are missing or wrong, or
                 its id is a duplicate
             19  a Python file could not be parsed
             20  no files were found to work on
             45  a hand-kept column of the validation inventory breaks its rules
             47  a check file's name has no aspect of quality or holds a check of
                 another aspect
             48  a check file is in a code folder the inventory has no place for
             49  a check file could not be loaded
             50  a check's code changed but its version in the validation
                 inventory did not (only once a validation report has been
                 filed, and a change to its docstring or labels counts)
             51  a check is not written as a function at the top level of its
                 check file
             62  the fingerprints in the validation inventory were made by another
                 Python version (only once a validation report has been filed,
                 and not with --python-changed)
             63  a check's fingerprint in the validation inventory is missing or
                 unreadable (only once a validation report has been filed)
             19 outranks 49, 49 outranks 20, 20 outranks 62, 62 outranks 18, 18
             outranks 51, 51 outranks 48, 48 outranks 47, 47 outranks 45, 45
             outranks 63, and 63 outranks 50. A run that finds 19, 49, 20 or 62
             stops there and names only those. Every other problem is still
             named. The numbers are the repo-wide table in docs/exit_codes.csv.

Date:        2026-09-11
Owner:       Jason Delosh
"""

from __future__ import annotations

import argparse
import ast
import contextlib
import csv
import hashlib
import inspect
import io
import re
import sys
import textwrap
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

#######################################################################################
### Settings ###

REPO_ROOT = Path(__file__).resolve().parents[2]
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
    "fingerprint",
    "status",
    "superseded_by",
    "status_reason",
)

# The columns a person keeps by hand, each with what a new check starts with. The
# generator carries them over by id and never works them out.
HAND_KEPT = {
    "status": "active",
    "superseded_by": "",
    "status_reason": "",
    "version": "1",
}

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
    "technical": (
        "functionality",
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

# The aspects, in the order the vocabulary lists them. A check file's name ends with
# one of them, so the names come from the vocabulary rather than a list of their own.
ASPECTS = tuple(OBJECTIVES_BY_ASPECT)

# A check that staged its own situation carries one of these, saying whether the
# situation was a working one or a broken one. A check that looked at something real
# carries neither. The case says how the check was set up, which is a separate thing
# from the question it asks, so any objective may carry one.
CASES = ("positive", "negative")

# The suites a check's id may belong to, and what each one holds. An id is a plain
# unique key: where a check lives and what it covers are columns of their own, so
# the id says nothing about either and never has to change when they do. Every check
# in validation/ is in suite A. A separate suite of checks, if one is ever needed,
# is added here as SB. validation/README.md describes them
# for a reader.
SUITES = {
    "SA": "suite A, every check under validation/",
}

# An id is S, the suite's letter and five digits, such as SA00042.
ID_SHAPE = re.compile(r"S[A-Z][0-9]{5}")

# Where a check stands. validation/validation_inventory_dictionary.md says what each one means.
STATUSES = ("pending", "active", "inactive", "superseded", "retired")

# The statuses that need a reason written down. Each one means the check does not
# run, and a reader needs to know why.
NEEDS_REASON = ("pending", "inactive", "retired")

# The statuses of a check that has been taken out of use. Its row is kept after its
# function is removed from its check file, so a filed report that names it still
# finds it.
OUT_OF_USE = ("superseded", "retired")

# The folder validation reports are filed in, inside the validation folder. Each
# aspect's reports are in a folder of its own inside it, as src/sdgval/report.py
# writes them.
REPORTS_FOLDER = "reports"

# Rows are ordered by the code folder the check file mirrors: the pipeline's folders
# in the order the pipeline runs, then the top of the sdg package, then the repo
# tools, the validation package and the hooks, with the checks for validation's own
# files last. Within a folder, rows are in check file name order, then in id order,
# whatever their status. A check file in a folder not listed here is refused, so a
# new folder is placed on purpose.
CODE_FOLDER_ORDER = (
    "sdg/sources",
    "sdg/usdm",
    "sdg/view",
    "sdg",
    "sdgtools",
    "sdgval",
    "claude_hooks",
    "validation",
)

# A recorded fingerprint is v and the version it was taken at, then py and the
# Python version that took it, then sixteen hexadecimal characters, each part
# followed by a colon but the last, such as v1:py3.12:0f3a9c2b7d4e5a61. The version
# is kept with it, so the script can tell whether the version moved since the code
# was fingerprinted. The Python version is kept with it because a new Python can
# write the same code out differently, which moves the fingerprint of a check that
# did not change. It is kept in each cell rather than once for the whole file, so a
# row read on its own still says what made it.
FINGERPRINT_SHAPE = re.compile(r"v([0-9]+):py([0-9]+\.[0-9]+):([0-9a-f]{16})")

# The Python version this run fingerprints with, as major and minor, such as 3.12.
# A patch release does not change how Python writes code out, so it is left out.
RUNNING_PYTHON = f"{sys.version_info.major}.{sys.version_info.minor}"

# When several kinds of problem are found in one run, the exit code is the first of
# these that any problem carries. Every problem is still printed.
EXIT_PRECEDENCE = (19, 49, 20, 62, 18, 51, 48, 47, 45, 63, 50)

# The problems that stop a run before anything else is looked at. Without every
# check file loaded, the checks read are not the whole set, so every row whose
# check was not read would look removed.
STOPPING = (19, 49, 20)


#######################################################################################
### Asking pytest for the checks ###
#
# pytest is asked to collect the checks and run none of them. Its answer is the same
# list of checks, with the same labels, that a real run and a validation report see.


@dataclass(frozen=True)
class Problem:
    """One thing wrong, with the exit code its kind of problem carries.

    The code travels with the problem from where it is found, so the exit code
    never depends on how a message is worded.
    """

    message: str
    code: int


@dataclass(frozen=True)
class Check:
    """One check as pytest collected it from its check file."""

    check_file: str
    check_name: str
    check_id: str
    category: str
    objective: str
    case: str
    expected_result: str
    fingerprint: str


@dataclass
class CollectionRecord:
    """A pytest plugin, handed to one collection run, that keeps what pytest found.

    pytest calls the three methods below as it works. The checks are kept before any
    other plugin could drop one, and a file that fails to load is kept with the
    error that stopped it.
    """

    # Every check file pytest opened, including one that failed to load.
    files: list[Path] = field(default_factory=list)
    # Every check pytest found, one per run of a check that runs once per value.
    items: list[pytest.Item] = field(default_factory=list)
    # Each file or folder that failed to load, with the error that stopped it.
    failures: list[tuple[Path, BaseException]] = field(default_factory=list)

    def pytest_collectstart(self, collector: pytest.Collector) -> None:
        """Keep the path of each check file pytest opens.

        Args:
            collector: The file or folder pytest is about to read.
        """
        if isinstance(collector, pytest.Module):
            self.files.append(collector.path)

    def pytest_itemcollected(self, item: pytest.Item) -> None:
        """Keep each check pytest finds.

        Args:
            item: The check.
        """
        self.items.append(item)

    def pytest_exception_interact(
        self,
        node: pytest.Item | pytest.Collector,
        call: pytest.CallInfo[Any],
        report: pytest.CollectReport | pytest.TestReport,
    ) -> None:
        """Keep a file that failed to load, with the error that stopped it.

        pytest calls this for every error while it collects. It wraps the error it
        met in one of its own, so the error underneath is kept, because that is
        the one that says what is wrong with the file. A conftest.py that fails
        names itself on the error, and a check file is the node pytest was
        reading.

        Args:
            node: The file or folder that failed.
            call: How reading it ended, with the error.
            report: pytest's report of the failure.
        """
        if call.excinfo is None:
            return
        error = call.excinfo.value
        underneath = error.__cause__ or error
        self.failures.append((Path(getattr(error, "path", node.path)), underneath))


def collect() -> tuple[CollectionRecord, int, str]:
    """Ask pytest to collect every check under the validation folder, running none.

    pytest runs in this process, which is faster than starting another. Collecting
    imports every check file, and pytest adds folders to Python's search path to do
    it, so both are put back afterwards. That matters when the script runs inside
    another pytest run, as its own checks run it, where a check file left imported
    would be handed back in place of a changed one with the same name. Python is
    told not to write compiled copies of the files it imports, for the same reason:
    a copy is matched to its file by size and by time to the second, so a file
    rewritten within the same second could be read from a stale copy.

    Only pytest's own collecting is used. The validation package's plugins that
    select, skip and report are left out, because each would act on the checks
    rather than list them. The labels plugin stays, because it declares the labels.

    Returns:
        What pytest found, pytest's exit number, and what pytest printed, which
        names the file when a conftest.py fails before collecting starts.
    """
    record = CollectionRecord()
    arguments = [
        str(VALIDATION_DIR),
        "--collect-only",
        f"--rootdir={REPO_ROOT}",
        "--capture=no",
        "--assert=plain",
        "-p",
        "no:terminal",
        "-p",
        "no:cacheprovider",
        "-p",
        "no:faulthandler",
        "-p",
        "no:sdgval_select_checks",
        "-p",
        "no:sdgval_skip_rules",
        "-p",
        "no:sdgval_report",
    ]
    modules_before = dict(sys.modules)
    path_before = list(sys.path)
    bytecode_before = sys.dont_write_bytecode
    printed = io.StringIO()
    sys.dont_write_bytecode = True
    try:
        with contextlib.redirect_stdout(printed), contextlib.redirect_stderr(printed):
            status = int(pytest.main(arguments, plugins=[record]))
    finally:
        sys.dont_write_bytecode = bytecode_before
        sys.path[:] = path_before
        _forget_imported_check_files(modules_before)
    return record, status, printed.getvalue()


def _forget_imported_check_files(modules_before: dict[str, Any]) -> None:
    """Put Python's table of imported modules back as it was before collecting.

    A module collecting imported from under the validation folder is removed, and
    one it replaced is put back. pytest itself replaces a conftest.py it loads, so
    the conftest of a pytest run that called this script is restored. Modules
    imported from anywhere else stay, since they are the same whoever imports them.

    Args:
        modules_before: The table as it was before collecting.
    """
    validation = VALIDATION_DIR.resolve()
    for name, module in list(sys.modules.items()):
        if name in modules_before:
            continue
        location = getattr(module, "__file__", None)
        if location and Path(location).resolve().is_relative_to(validation):
            del sys.modules[name]
    for name, module in modules_before.items():
        if sys.modules.get(name) is not module:
            sys.modules[name] = module


def first_paragraph(doc: str | None) -> str:
    """Give a docstring's first paragraph as one line.

    That paragraph is the check's expected result, and it is what the inventory and
    the validation report both show. A line holding only spaces counts as the blank
    line that ends the paragraph.

    Args:
        doc: The docstring, or None when there is none.

    Returns:
        The first paragraph joined to one line, or an empty string.
    """
    if not doc:
        return ""
    return " ".join(re.split(r"\n[ \t]*\n", doc.strip())[0].split())


def fingerprint(function: Callable[..., Any], labels: tuple[str, ...]) -> str:
    """Give a fingerprint of everything about a check except how it is laid out.

    The fingerprint covers the check's whole function: its code, its docstring and
    every decorator on it, the labels and the values a check runs once for
    included. It also covers the labels pytest read for the check, so a label given
    to the whole check file counts as well as one written on the function.

    The check's source is read as Python and written back out in Python's one
    standard layout, with ast.unparse, before it is fingerprinted, and the
    docstring's words are rejoined with single spaces inside each paragraph. So
    these changes leave the fingerprint alone:
      - spacing, indentation and line breaks, in the docstring too;
      - comments;
      - the kind of quotes around a string;
      - brackets that only wrap a long line, and a comma after the last item.

    Args:
        function: The check's function.
        labels: The labels pytest read for the check, which are its id, its
            category, its objective and its case.

    Returns:
        The first sixteen hexadecimal characters of the SHA-256 hash of the
        rewritten source and the labels.
    """
    source = textwrap.dedent(inspect.getsource(function))
    node = ast.parse(source).body[0]
    assert isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    doc = ast.get_docstring(node, clean=False)
    if doc is not None:
        # Rewrapping the docstring's lines changes none of its words, so the words
        # of each paragraph are joined with single spaces, and the paragraphs with
        # one blank line, before the source is written back out.
        paragraphs = re.split(r"\n[ \t]*\n", doc.strip())
        words = "\n\n".join(" ".join(paragraph.split()) for paragraph in paragraphs)
        node.body[0] = ast.Expr(ast.Constant(words))
    text = ast.unparse(node) + "\n" + "\n".join(labels)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def code_folder_and_target(
    check_file: Path, validation_dir: Path | None = None
) -> tuple[str, str]:
    """Work out the code folder a check file mirrors and the code file it proves.

    This is the one place the rule is written. src/sdgval/report.py uses it too, to
    fill the same columns of a validation report, so the inventory and the report can
    never disagree about what a check file proves.

    validation/ mirrors src/, one folder per installed package. A check file at
    validation/<package>/<path> tests the file of the same name at
    src/<package>/<path>, so validation/sdg/sources/test_fetch_file_technical.py
    tests src/sdg/sources/fetch_file.py. Two places are exceptions. A check file in
    validation/claude_hooks/ tests the hook of the same name in .claude/hooks/, which
    cannot be mirrored by name because pytest does not look inside a folder whose name
    starts with a dot. A check file at the top level of validation/ tests the file of
    the same name in validation/ itself, as the checks for conftest.py do.

    A check file's name ends with the aspect of quality its checks belong to, as in
    test_build_index_technical.py, and the aspect is left out of the name of the
    file it tests. A name with no aspect is kept whole, and read_checks() reports it.

    Args:
        check_file: The check file's path.
        validation_dir: The validation folder the path is read against, or None for
            the repo's own.

    Returns:
        The code folder's name and the target's repo-relative path.
    """
    relative = check_file.relative_to(validation_dir or VALIDATION_DIR)
    folder = relative.parent.as_posix()
    name = check_file.stem.removeprefix("test_")
    aspect = aspect_of_file(check_file)
    if aspect:
        name = name.removesuffix(f"_{aspect}")
    component = f"{name}.py"
    if folder == ".":
        return "validation", f"validation/{component}"
    if folder == "claude_hooks":
        return "claude_hooks", f".claude/hooks/{component}"
    return folder, f"src/{folder}/{component}"


def split_path(path: str) -> tuple[str, str]:
    """Split a repo-relative path into its folder and its file name.

    Args:
        path: The path, written with forward slashes.

    Returns:
        The folder, or an empty string for a file at the repo root, and the file name.
    """
    folder, _, name = path.rpartition("/")
    return folder, name


def _name(path: Path) -> str:
    """Give a file's repo-relative path with forward slashes, as the inventory writes it.

    Args:
        path: The file.

    Returns:
        The repo-relative path.
    """
    return path.relative_to(REPO_ROOT).as_posix()


def load_problems(record: CollectionRecord, status: int, printed: str) -> list[Problem]:
    """Name each file that failed to load, or the folder when nothing was found.

    A file that is not valid Python carries 19, as every file that cannot be parsed
    does. Any other failure carries 49. A conftest.py that fails before collecting
    starts leaves no record, only pytest's exit number and what it printed, which
    names the file.

    Args:
        record: What pytest found.
        status: pytest's exit number for the collection run.
        printed: What pytest printed.

    Returns:
        One problem per file that failed to load, or one for an empty folder, or
        nothing when every check file loaded.
    """
    problems = []
    for path, error in record.failures:
        if isinstance(error, SyntaxError):
            problems.append(Problem(f"{_name(path)}: cannot parse ({error})", 19))
        else:
            problems.append(
                Problem(
                    f"{_name(path)} could not be loaded, so the checks in it cannot "
                    f"be read ({type(error).__name__}: {error}). Fix the error, then "
                    "run build_inventory again",
                    49,
                )
            )
    if problems:
        return problems
    if status not in (pytest.ExitCode.OK, pytest.ExitCode.NO_TESTS_COLLECTED):
        said = next((line for line in printed.splitlines() if line.strip()), "")
        return [
            Problem(
                f"pytest could not collect the checks under {_name(VALIDATION_DIR)} "
                f"(exit {status}): {said}",
                49,
            )
        ]
    if not record.files:
        return [Problem(f"no check files found under {_name(VALIDATION_DIR)}", 20)]
    return []


def read_checks() -> tuple[list[tuple[str, str, Check]], list[Problem]]:
    """Read every check in every check file under the validation folder.

    Returns:
        Each check with its code folder and target, and the problems found. When a
        file failed to load, or there is no check file, the problems say so and no
        check is handed back.
    """
    # pytest refuses a folder that is not there as a bad command line, so a missing
    # folder is caught first and reported like an empty one.
    if not VALIDATION_DIR.is_dir():
        return [], [Problem(f"no check files found under {_name(VALIDATION_DIR)}", 20)]
    record, status, printed = collect()
    stopping = load_problems(record, status, printed)
    if stopping:
        return [], stopping

    # The label readers are imported here rather than at the top, because
    # src/sdgval/labels.py imports ASPECT_OF from this file, and a module that
    # imports it at the top would find this one half loaded.
    from sdgval.labels import case_of, category_of, code_of, objective_of

    problems: list[Problem] = []
    # The runs of one check function are gathered under the function, in the
    # order pytest found them.
    runs: dict[tuple[Path, str], list[pytest.Function]] = {}
    refused: set[str] = set()
    for item in record.items:
        if isinstance(item, pytest.Function) and item.cls is None:
            runs.setdefault((item.path, item.originalname), []).append(item)
            continue
        where = f"{_name(item.path)}: {item.nodeid.split('::', 1)[-1].split('[')[0]}"
        if where not in refused:
            refused.add(where)
            problems.append(
                Problem(
                    f"{where} is not a function at the top level of its check file. "
                    "The inventory and a validation report name a check by its "
                    "function's name alone, so move it out of its class",
                    51,
                )
            )

    checks: list[Check] = []
    for (path, name), items in runs.items():
        where = f"{_name(path)}: {name}"
        labels = {
            (code_of(item), category_of(item), objective_of(item), case_of(item))
            for item in items
        }
        if len(labels) > 1:
            problems.append(
                Problem(
                    f"{where} carries different labels on different runs. A check is "
                    "one row of the inventory, so put its labels on the function "
                    "rather than on its values",
                    18,
                )
            )
        first = items[0]
        code, category, objective, case = (
            code_of(first),
            category_of(first),
            objective_of(first),
            case_of(first),
        )
        expected = first_paragraph(first.function.__doc__)
        problems.extend(label_problems(where, first, code, category, objective))
        if not expected:
            problems.append(
                Problem(
                    f"{where} has no docstring, or its first paragraph is empty. "
                    "Write the sentence that must be true for the check to pass",
                    18,
                )
            )
        elif not expected[0].isalnum():
            problems.append(
                Problem(
                    f"{where} has a first sentence starting with {expected[0]!r}; "
                    "start it with a letter or a digit",
                    18,
                )
            )
        checks.append(
            Check(
                check_file=_name(path),
                check_name=name,
                check_id=code,
                category=category,
                objective=objective,
                case=case,
                expected_result=expected,
                fingerprint=fingerprint(
                    first.function, (code, category, objective, case)
                ),
            )
        )

    found: list[tuple[str, str, Check]] = []
    for path in sorted(record.files):
        code_folder, target = code_folder_and_target(path)
        if code_folder not in CODE_FOLDER_ORDER:
            problems.append(
                Problem(
                    f"{_name(path)} is in the code folder {code_folder}, which "
                    "CODE_FOLDER_ORDER in src/sdgval/build_inventory.py does not "
                    "list; add the folder there, where it belongs in the order",
                    48,
                )
            )
        in_file = [check for check in checks if check.check_file == _name(path)]
        problems.extend(aspect_problems(path, in_file))
        found.extend((code_folder, target, check) for check in in_file)
    return found, problems


def label_problems(
    where: str, item: pytest.Item, code: str, category: str, objective: str
) -> list[Problem]:
    """Confirm a check carries its three labels, each with a known value, and one case.

    Args:
        where: The check file and the check, as a message names them.
        item: One run of the check, for the case labels.
        code: The id its @code label gives, or an empty string.
        category: The value of its @category label, or an empty string.
        objective: The value of its @objective label, or an empty string.

    Returns:
        One problem per rule broken, each carrying exit code 18.
    """
    problems = []
    if not code:
        problems.append(Problem(f"{where} has no @code marker", 18))
    if not category:
        problems.append(Problem(f"{where} has no @category marker", 18))
    elif category not in CATEGORIES:
        problems.append(
            Problem(
                f"{where} has @category({category!r}), which is not one of "
                f"{', '.join(CATEGORIES)}",
                18,
            )
        )
    if not objective:
        problems.append(Problem(f"{where} has no @objective marker", 18))
    elif objective not in OBJECTIVES:
        problems.append(
            Problem(
                f"{where} has @objective({objective!r}), which is not one of "
                f"{', '.join(OBJECTIVES)}",
                18,
            )
        )
    # A check stages a working situation or a broken one, never both. The reader in
    # src/sdgval/labels.py gives positive when both are there, so both are looked
    # for here, where the mistake can be refused.
    if all(item.get_closest_marker(case) for case in CASES):
        problems.append(
            Problem(
                f"{where} carries both @positive and @negative. A check stages either "
                "a working situation or a broken one, so keep the one that is true",
                18,
            )
        )
    return problems


def aspect_of_file(check_file: Path) -> str | None:
    """Read the aspect of quality a check file's name ends with.

    Args:
        check_file: The check file's path.

    Returns:
        The aspect, or None when the name ends with none of them.
    """
    stem = check_file.stem
    for aspect in ASPECTS:
        if stem.endswith(f"_{aspect}"):
            return aspect
    return None


def aspect_problems(check_file: Path, checks: list[Check]) -> list[Problem]:
    """Hold a check file to one aspect of quality, the one its name ends with.

    A check file holds checks of one aspect only, so a run and a report of one aspect
    never have to split a file. The file's name says which, and a check's objective
    says which aspect it belongs to, so the two must agree.

    Args:
        check_file: The check file's path.
        checks: The checks read from it.

    Returns:
        One problem when the name ends with no aspect, or one per check whose
        objective belongs to another aspect, or nothing when the file is in order.
    """
    name = _name(check_file)
    aspect = aspect_of_file(check_file)
    if aspect is None:
        return [
            Problem(
                f"{name} has no aspect in its name; it must end with one of "
                + ", ".join(f"_{a}" for a in ASPECTS),
                47,
            )
        ]
    problems = []
    for check in checks:
        belongs = ASPECT_OF.get(check.objective)
        # An objective the vocabulary does not know is already reported where the
        # check was read, so it is not reported a second time here.
        if belongs and belongs != aspect:
            problems.append(
                Problem(
                    f"{name}: {check.check_name} has the objective "
                    f"{check.objective}, which belongs to {belongs}, in a file "
                    f"named for {aspect}",
                    47,
                )
            )
    return problems


#######################################################################################
### Building the rows ###


def report_filed() -> bool:
    """Say whether any validation report has been filed under validation/reports/.

    src/sdgval/report.py writes each report into the folder of its aspect, named
    <aspect>_<YYYY-MM-DD>_<commit>.csv, with a numbered suffix when that name is
    taken, and the run's own file beside it with _run before .csv. A file of either
    shape counts. Anything else in the folder, such as its README, its dictionary,
    its .gitkeep or an empty aspect folder, does not, so a folder that holds no
    report reads as none filed.

    Returns:
        True when at least one report or run file is there, and False otherwise.
    """
    reports = VALIDATION_DIR / REPORTS_FOLDER
    for aspect in ASPECTS:
        shape = re.compile(rf"{aspect}_[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}_.+\.csv")
        folder = reports / aspect
        if folder.is_dir() and any(
            path.is_file() and shape.fullmatch(path.name) for path in folder.iterdir()
        ):
            return True
    return False


def existing_rows() -> dict[str, dict[str, str]]:
    """Read the inventory on disk, for the hand-kept columns and the fingerprints.

    Returns:
        The existing rows keyed by check id, or nothing when there is no inventory
        yet.
    """
    if not INVENTORY_PATH.is_file():
        return {}
    with INVENTORY_PATH.open(encoding="utf-8", newline="") as fh:
        return {row["id"]: row for row in csv.DictReader(fh)}


def other_pythons(previous: dict[str, dict[str, str]]) -> list[str]:
    """List the Python versions, other than the running one, that made fingerprints.

    Args:
        previous: The inventory on disk, keyed by id.

    Returns:
        Each other version that made a recorded fingerprint, in order, or an empty
        list when every recorded fingerprint was made by the running Python.
    """
    made_by = {
        recorded[2]
        for row in previous.values()
        if (recorded := FINGERPRINT_SHAPE.fullmatch(row.get("fingerprint", "")))
    }
    return sorted(made_by - {RUNNING_PYTHON})


def build_rows(
    found: list[tuple[str, str, Check]],
    previous: dict[str, dict[str, str]],
    filed: bool,
    python_changed: bool = False,
) -> tuple[list[dict[str, str]], list[Problem]]:
    """Build every inventory row from the checks and the inventory on disk.

    A row of the inventory on disk whose check is no longer read is kept when it is
    superseded or retired. Any other such row is kept when a validation report has
    been filed, so that status_problems() refuses it, and dropped when none has,
    because no report can name it.

    Args:
        found: Each check read, with its code folder and target.
        previous: The inventory on disk, keyed by id.
        filed: Whether a validation report has been filed, as report_filed() says.
        python_changed: Whether --python-changed was given, so a fingerprint
            another Python made is recorded afresh rather than compared.

    Returns:
        The rows in inventory order and the problems found. When there is any
        problem the rows are not to be written.
    """
    problems: list[Problem] = []

    # An id must name one check, since a validation report joins on it.
    seen: dict[str, str] = {}
    for _, _, check in found:
        if check.check_id in seen:
            problems.append(
                Problem(
                    f"{check.check_id} is carried by both {seen[check.check_id]} "
                    f"and {check.check_name}",
                    18,
                )
            )
        elif check.check_id:
            seen[check.check_id] = check.check_name

    rows: list[dict[str, str]] = []
    for _, target, check in found:
        old = previous.get(check.check_id, {})
        validation_folder, validation_file = split_path(check.check_file)
        # A new check given the id of a row taken out of use leaves that row as it
        # is, so status_problems() can say the id is already spent.
        if old.get("status") in OUT_OF_USE and (
            f"{old['folder_path']}/{old['file_name']}",
            old["name"],
        ) != (check.check_file, check.check_name):
            continue
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
        # starting value of each.
        for column, start in HAND_KEPT.items():
            row[column] = old.get(column, start)
        cell, problem = fingerprint_cell(
            check, row["version"], old, filed, python_changed
        )
        row["fingerprint"] = cell
        if problem:
            problems.append(problem)
        rows.append(row)

    # The other rows on disk are the rows whose check has gone. A superseded or
    # retired check has been taken out of the check files, and its row stays so a
    # filed report that names it still finds it and a reader can see what happened
    # to it. Any other such row is dropped while no report has been filed, since no
    # report can name it. Once one has been filed, the row is kept so that
    # status_problems() refuses it.
    written = {row["id"] for row in rows}
    for check_id, old in previous.items():
        if check_id in written:
            continue
        if old.get("status") in OUT_OF_USE or filed:
            rows.append({column: old.get(column, "") for column in COLUMNS})

    rows.sort(key=_place)
    problems.extend(id_problems(rows))
    return rows, problems


def fingerprint_cell(
    check: Check,
    version: str,
    old: dict[str, str],
    filed: bool,
    python_changed: bool = False,
) -> tuple[str, Problem | None]:
    """Record a check's fingerprint, refusing a changed check whose version stayed put.

    The fingerprint on disk carries the version it was taken at. Once a validation
    report has been filed, a check whose fingerprint differs from it while the
    version on the row is no higher changed without its version moving, and is
    refused, because the report names the check by its id and version. While no
    report has been filed, the new fingerprint is recorded against the version on
    the row, and no rise is needed. A new check is simply recorded.

    Once a report has been filed, a row on disk with no fingerprint in the recorded
    shape is refused, because emptying the cell would otherwise let a changed check
    through. A fingerprint another Python made is recorded afresh, without being
    compared, when --python-changed was given. Without it, main() has already
    stopped the run.

    Args:
        check: The check as read now.
        version: The version on the check's row.
        old: The check's row on disk, or an empty dict for a new check.
        filed: Whether a validation report has been filed, as report_filed() says.
        python_changed: Whether --python-changed was given.

    Returns:
        The value for the fingerprint column, and the problem, or None when there
        is none.
    """
    cell = f"v{version}:py{RUNNING_PYTHON}:{check.fingerprint}"
    # A version that is not a whole number is refused by status_problems(), so it
    # is not compared here.
    if not filed or not old or not version.isdigit():
        return cell, None
    recorded = FINGERPRINT_SHAPE.fullmatch(old.get("fingerprint", ""))
    if recorded is None:
        return cell, Problem(
            f"{check.check_file}: {check.check_name} ({check.check_id}) has no "
            f"fingerprint recorded in {_name(INVENTORY_PATH)}, or one that cannot be "
            "read, so whether the check changed cannot be told. Put its fingerprint "
            "back as git last recorded it, then run build_inventory again",
            63,
        )
    was, python, digest = int(recorded[1]), recorded[2], recorded[3]
    if python != RUNNING_PYTHON and python_changed:
        return cell, None
    if digest != check.fingerprint and int(version) <= was:
        return cell, Problem(
            f"{check.check_file}: {check.check_name} ({check.check_id}) has changed "
            f"since version {was} was recorded, and its version in "
            f"{_name(INVENTORY_PATH)} is still {version}. Raise its version to "
            f"{was + 1} there, then run build_inventory again",
            50,
        )
    return cell, None


def _place(row: dict[str, str]) -> tuple[int, str, str]:
    """Give a row's place in the inventory: code folder, then check file, then id.

    Args:
        row: One inventory row.

    Returns:
        The code folder's place in CODE_FOLDER_ORDER, the check file's name and the
        id. A folder not in the list is refused elsewhere, and sorts last only so the
        refusal can still name every problem.
    """
    code_folder, _ = code_folder_and_target(
        REPO_ROOT / row["folder_path"] / row["file_name"]
    )
    order = (
        CODE_FOLDER_ORDER.index(code_folder)
        if code_folder in CODE_FOLDER_ORDER
        else len(CODE_FOLDER_ORDER)
    )
    return order, row["file_name"], row["id"]


def id_problems(rows: list[dict[str, str]]) -> list[Problem]:
    """Confirm every id has the right shape and belongs to a listed suite.

    The id carries no meaning beyond its suite, so there is nothing else about it
    to confirm.

    Args:
        rows: The rows about to be written.

    Returns:
        One problem per rule an id breaks, or nothing when every id is in order.
    """
    problems: list[Problem] = []
    for row in rows:
        check_id = row["id"]
        where = f"{row['folder_path']}/{row['file_name']}: {row['name']}"
        # A missing marker is already reported where the check was read, so it is
        # not reported a second time here.
        if not check_id:
            continue
        if not ID_SHAPE.fullmatch(check_id):
            problems.append(
                Problem(
                    f"{where} has the id {check_id!r}, which is not S, a capital "
                    "letter and five digits, such as SA00042",
                    18,
                )
            )
        elif check_id[:2] not in SUITES:
            problems.append(
                Problem(
                    f"{where} has the id {check_id}, and {check_id[:2]} is not one "
                    f"of the suites {', '.join(SUITES)}",
                    18,
                )
            )
    return problems


def status_problems(
    rows: list[dict[str, str]], live: dict[str, tuple[str, str]], filed: bool
) -> list[Problem]:
    """Confirm the hand-kept columns of every row follow their rules.

    It can run on the rows the generator is about to write or on the inventory on
    disk, which is what --check-status does. The rules are these:
      - a status is one of the five in STATUSES;
      - superseded_by names at least one check exactly when the status is
        superseded, and each one it names is another row of the inventory,
        whatever that row's status;
      - status_reason says why exactly when the status is one of NEEDS_REASON;
      - a version is a whole number from 1 up;
      - a row whose check is in no check file is superseded or retired, once a
        validation report has been filed. Before that, such a row is dropped
        when the inventory is regenerated, so it is not refused;
      - a superseded or retired row's check is no longer in the check files;
      - a new check does not carry the id of a superseded or retired row.

    Args:
        rows: The inventory's rows.
        live: The checks in the check files now, each id with the check file and
            the name of the check that carries it.
        filed: Whether a validation report has been filed, as report_filed() says.

    Returns:
        One problem per rule broken, naming the check and what is wrong, each
        carrying exit code 45.
    """
    ids = {row["id"] for row in rows}
    reasons = f"{', '.join(NEEDS_REASON[:-1])} and {NEEDS_REASON[-1]}"
    messages: list[str] = []
    for row in rows:
        check_id, status = row["id"], row["status"]
        successors = [s.strip() for s in row["superseded_by"].split(";") if s.strip()]

        if status not in STATUSES:
            messages.append(
                f"{check_id} has status {status!r}, which is not one of "
                f"{', '.join(STATUSES)}"
            )
        if status == "superseded" and not successors:
            messages.append(
                f"{check_id} is superseded but superseded_by names no check"
            )
        if status != "superseded" and successors:
            messages.append(
                f"{check_id} names checks in superseded_by but is {status}, "
                "not superseded"
            )
        # A successor may itself have been superseded or retired since. The row
        # is history, so it keeps the check that took over at the time, and a
        # reader follows the chain from there.
        for successor in successors:
            if successor == check_id:
                messages.append(
                    f"{check_id} names itself in superseded_by; name the checks "
                    "that took over from it"
                )
            elif successor not in ids:
                messages.append(
                    f"{check_id} is superseded by {successor}, which is not a check "
                    "in the inventory"
                )
        if status in NEEDS_REASON and not row["status_reason"].strip():
            messages.append(
                f"{check_id} is {status} but status_reason does not say why"
            )
        if status not in NEEDS_REASON and row["status_reason"].strip():
            messages.append(
                f"{check_id} has a status_reason but is {status}, and only "
                f"{reasons} checks say why they do not run"
            )
        if not row["version"].isdigit() or int(row["version"]) < 1:
            messages.append(
                f"{check_id} has version {row['version']!r}, which is not a whole "
                "number from 1 up"
            )
        messages.extend(_presence_problems(row, live, filed))
    return [Problem(message, 45) for message in messages]


def _presence_problems(
    row: dict[str, str], live: dict[str, tuple[str, str]], filed: bool
) -> list[str]:
    """Hold a row's status to whether its check is still in the check files.

    Once a validation report has been filed, a check is taken out of use by marking
    its row superseded or retired before its function is removed, because the
    report may name it. So a row whose check has gone and is marked anything else
    lost its check by mistake. While no report has been filed, such a row is
    dropped when the inventory is regenerated, so it is not refused. A superseded
    or retired check cannot still be in the check files, where every run would run
    it. When a check carrying that id is there, it is either the old check left
    behind, found by its file and name, or a new check given an id that is already
    spent.

    Args:
        row: One inventory row.
        live: The checks in the check files now, each id with the check file and
            the name of the check that carries it.
        filed: Whether a validation report has been filed, as report_filed() says.

    Returns:
        The message for the rule broken, or nothing.
    """
    check_id, status = row["id"], row["status"]
    if check_id not in live:
        if status in OUT_OF_USE or not filed:
            return []
        return [
            f"{check_id} is {status}, but no check file holds a check with that id. "
            "A validation report has been filed, so before a check is removed, its "
            "row is marked retired or superseded; mark it so, or put the check back"
        ]
    if status not in OUT_OF_USE:
        return []
    check_file, check_name = live[check_id]
    if (f"{row['folder_path']}/{row['file_name']}", row["name"]) == (
        check_file,
        check_name,
    ):
        return [
            f"{check_id} is {status} but is still in the check files; remove the "
            "check or change its status"
        ]
    return [
        f"{check_file}: {check_name} carries {check_id}, which already belongs to a "
        f"{status} check. Every id is used only once, so give {check_name} the next "
        "free id"
    ]


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


def exit_code(problems: list[Problem]) -> int:
    """Pick the exit code for a run that found problems.

    Args:
        problems: Every problem found, at least one.

    Returns:
        The first code in EXIT_PRECEDENCE that any problem carries.
    """
    codes = {problem.code for problem in problems}
    return next(code for code in EXIT_PRECEDENCE if code in codes)


def main(argv: list[str] | None = None) -> int:
    """Read every check, then write the inventory or confirm it is current.

    Problems are collected across every file before returning, so one run names
    every check that needs fixing rather than stopping at the first. The exception
    is a check file that fails to load, or no check file at all, which stops the
    run at once.

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
        help="confirm only the hand-kept columns of the inventory on disk; write nothing",
    )
    mode.add_argument(
        "--python-changed",
        action="store_true",
        help="record new fingerprints for the rows another Python version made",
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

    found, problems = read_checks()
    stopping = [p for p in problems if p.code in STOPPING]
    if stopping:
        for problem in stopping:
            say(problem.message)
        say("Inventory not written.")
        return exit_code(stopping)
    live = {
        check.check_id: (check.check_file, check.check_name)
        for _, _, check in found
        if check.check_id
    }
    filed = report_filed()

    if args.check_status:
        if not INVENTORY_PATH.is_file():
            say(f"{inventory} is missing. Run: build_inventory")
            return 16
        status = status_problems(list(existing_rows().values()), live, filed)
        for problem in status:
            say(problem.message)
        if status:
            return exit_code(status)
        say(f"{inventory}: the hand-kept columns are in order")
        return 0

    previous = existing_rows()
    # A new Python can move every fingerprint at once. Once a report has been filed,
    # that would refuse every check, so the run stops here with one message instead,
    # unless the person has said the Python changed.
    others = other_pythons(previous)
    if filed and others and not args.python_changed:
        say(
            f"The fingerprints in {inventory} were made by Python "
            f"{' and '.join(others)}, and this is Python {RUNNING_PYTHON}. A new "
            "Python can write a check's code out differently, so every fingerprint "
            "may move although no check changed. Run build_inventory "
            "--python-changed to record new fingerprints, and commit the result "
            "alone, in a commit that changes nothing else."
        )
        say("Inventory not written.")
        return 62
    rows, row_problems = build_rows(found, previous, filed, args.python_changed)
    problems.extend(row_problems)
    status = status_problems(rows, live, filed)
    for problem in problems + status:
        say(problem.message)
    if problems or status:
        # Each kind of problem needs a different fix, so each carries its own code,
        # and the most basic one found decides the exit code.
        say("Inventory not written.")
        return exit_code(problems + status)

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
        say(f"{inventory} is stale. Run: build_inventory")
        return 16

    INVENTORY_PATH.write_text(text, encoding="utf-8", newline="")
    say(f"{inventory} written, {len(rows)} check(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
