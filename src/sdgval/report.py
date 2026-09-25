"""
Script:      report.py
Description: A pytest plugin that collects how each check ended and, when asked,
             writes a validation report: one CSV file per run, one row per check.

             A report is meant to be auditable, so it identifies what was tested, how,
             when, by whom, and with what outcome. The run's own details are repeated
             on every row, so each file is complete on its own and any row can be
             joined to validation/validation_inventory.csv by its check's id.
               - What was tested is the target file, the file of checks and its sha256,
                 the fixture files and their sha256s, and the code commit. The
                 working folder must match that commit
                 exactly, so a run asked for a report refuses to start when there
                 are uncommitted changes, before any check runs, and says which
                 files they are. The commit it would have named would not have
                 described the code that ran.
               - How is which checks were selected, how many the run set out to
                 cover and how many it reports on, and, at the far right of each
                 row, the Python and pytest versions and the operating system. The
                 two counts differ when checks were dropped or the run stopped
                 early, so a partial run cannot read as a whole one. They are
                 counted from what happened rather than from the options typed,
                 because an option this file does not know about narrows a run
                 just the same.
               - When is the local timestamp with its zone, and by whom is the git user
                 name.
               - The outcome is the run's verdict, from pytest's own exit status, and
                 one row per check. A row holds the check's id, its name, its
                 parameter when it has one, its category, its aspect of quality,
                 its objective, its case when it staged its own situation, its
                 expected result, which is its docstring's first paragraph, its own
                 outcome, and the reason when that is not passed: the assertion
                 message, the step that broke, or why it was skipped. A check that
                 goes wrong twice, failing and then breaking in its clean-up,
                 keeps both reasons in the order the steps ran.

             The verdict is PASS only when pytest itself exited 0. pytest's exit
             status already accounts for every kind of failure:
               - a test's own checks,
               - its set-up,
               - its clean-up,
               - a file that fails to load,
               - an internal error.
             Therefore the report can never say PASS when the terminal said otherwise.
             The rows are the detail; the exit status is the verdict. When no check
             ran at all, a report is still written, with one row saying so. Why no
             check ran is in that row's exit_meaning, because the exit status is
             all the writer knows about the cause.

             Every location is read from pytest's root folder, which is the repo
             root for a real run and a temporary folder for this plugin's own
             checks, so a staged suite reports on itself rather than on the repo.

Inputs:      git (for the commit hash and user name; read-only)
             validation/**/test_*.py and validation/fixtures/* (read-only; hashed)

Outputs:     Nothing, unless --validation-report is given. Then it writes one file,
             validation/reports/<aspect>_<YYYY-MM-DD>_<commit>.csv, with one row per
             check. The aspect is the one an aspect's command, such as
             src/sdgval/validate_technical.py, leaves in pytest's stash.
             An existing name is never overwritten; it gets a numeric suffix. A run
             whose command line pytest refused writes nothing, because it
             validated nothing, and neither does a listing run, --collect-only,
             because it ran nothing.

Usage:       validate_technical --validation-report
                 an aspect's command runs its checks and this writer writes the
                 report; plain pytest --validation-report is refused
             validate_technical --validation-report --validation-report-dir <folder>
                 same, writing the report to another folder

Exit codes:  None of its own. It runs inside pytest, and a report asked for without
             an aspect's command, or on uncommitted changes, is refused with
             pytest's own 4, a bad command line.

Date:        2026-09-24
Owner:       Jason Delosh
"""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import platform
import subprocess
import time
from collections.abc import Generator
from pathlib import Path

import pluggy
import pytest

# The rule that says which code file a check file proves lives in the inventory
# generator, src/sdgval/build_inventory.py, which fills the same column of the
# inventory. Importing it means the inventory and a report can never disagree.
from sdgval.build_inventory import ASPECT_OF, code_folder_and_target, split_path
from sdgval.labels import case_of, category_of, code_of, objective_of
from sdgval.select_checks import SELECTORS, wanted

#######################################################################################
### Settings ###

# Where an aspect's command leaves its aspect for this writer, in pytest's stash,
# the store pytest gives each run for plugins to share values. The report's file
# name starts with the aspect, and a report asked for with no aspect left there is
# refused, because a report comes only from an aspect's command.
REPORT_ASPECT = pytest.StashKey[str]()

# pytest ends every run with a number that says how the run went. The report
# prints that number together with its meaning, in these words.
EXIT_MEANING = {
    0: "all tests passed",
    1: "one or more tests failed or errored",
    2: "the run was interrupted",
    3: "pytest hit an internal error",
    4: "pytest was given a bad command line",
    5: "no tests were collected",
}


def _validation_dir(config: pytest.Config) -> Path:
    """Name the validation folder under pytest's root folder.

    Args:
        config: pytest's configuration for the run.

    Returns:
        The folder the checks, their fixtures and their reports live in.
    """
    return config.rootpath / "validation"


def _report_dir(config: pytest.Config) -> Path:
    """Name the folder the report goes in.

    Args:
        config: pytest's configuration for the run.

    Returns:
        The folder --validation-report-dir names, or validation/reports under
        pytest's root folder when it names none.
    """
    given = config.getoption("--validation-report-dir")
    return Path(given) if given else _validation_dir(config) / "reports"


#######################################################################################
### Command line ###


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add the report options to the pytest command line.

    --validation-report is off unless given. With it, one report is written after the
    run. --validation-report-dir says which folder the report goes in. It defaults to
    validation/reports under pytest's root folder; the report's own checks point it at
    a temporary folder instead.

    Args:
        parser: pytest's command-line parser.
    """
    parser.addoption(
        "--validation-report",
        action="store_true",
        default=False,
        help="after the run, write one validation report, one row per check",
    )
    parser.addoption(
        "--validation-report-dir",
        default=None,
        help="folder the report is written to (default: validation/reports)",
    )


#######################################################################################
### Collecting outcomes ###
#
# pytest runs each test in three steps: set-up, the test itself (pytest calls
# this the call step), and clean-up. It reports on each step separately. One
# row per test is kept here, and a later step may make the row worse but never
# better: a test whose checks passed but whose clean-up failed ends up as an
# error, which is also what pytest prints on the terminal. The reason is added to
# rather than replaced, so a test that fails and then breaks in its clean-up keeps
# both reasons instead of the second hiding the first. Nothing here decides
# whether the run passed. That verdict comes from pytest's own exit number, in
# pytest_sessionfinish below.

# One row per test, keyed by the id pytest gives the test.
_outcomes: dict[str, dict] = {}


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(
    item: pytest.Item, call: pytest.CallInfo[None]
) -> Generator[None, pluggy.Result[pytest.TestReport], None]:
    """Record the outcome of one step of one check into that check's row.

    pytest calls this after each of the three steps. The row is created by the first
    step that has something to say and updated by the later ones.

    Args:
        item: The check.
        call: The step that just ran and how it ended.
    """
    result = yield
    report = result.get_result()

    if report.when == "call":
        # The test itself ran. Its outcome is passed, failed or skipped.
        # Typed as plain text, because the outcome recorded here can also be
        # error, a word pytest's own outcome never takes.
        outcome: str = report.outcome
    elif report.passed:
        # Set-up or clean-up went fine. That says nothing about the test on
        # its own, so there is nothing to record.
        return
    elif report.skipped:
        # The test was skipped before it ran, by a skipif marker on it.
        outcome = "skipped"
    else:
        # Set-up or clean-up broke. pytest's own word for that is error.
        outcome = "error"

    function = getattr(item, "obj", None)
    row = _outcomes.setdefault(
        item.nodeid,
        {
            "file": Path(str(item.fspath)),
            "code": code_of(item),
            # A check is a test function, which pytest describes with its original
            # name and the function itself. They are read with getattr, because the
            # hook is declared for any kind of test item.
            "name": getattr(item, "originalname", item.name),
            "parameter": _parameter(item),
            "category": category_of(item),
            "objective": objective_of(item),
            "case": case_of(item),
            "expected_result": _first_paragraph(
                function.__doc__ if function is not None else None
            ),
            "outcome": outcome,
            "reason": "",
        },
    )
    # A clean-up error replaces an earlier pass. No step ever makes a row
    # better than it was.
    if outcome == "error" or row["outcome"] in ("passed", ""):
        row["outcome"] = outcome
    if outcome == "error":
        _add_reason(
            row, "clean-up failed" if report.when == "teardown" else "set-up failed"
        )
    if outcome == "failed":
        # pytest keeps the one-line message of the failure, usually the
        # assertion, on the report; that is what a reader needs first.
        crash = getattr(report.longrepr, "reprcrash", None)
        _add_reason(row, crash.message.splitlines()[0] if crash else "failed")
    if outcome == "skipped":
        # For a skip, pytest stores the reason as the third item of a tuple of
        # file, line and reason. The reason is what a reader needs, usually
        # that the pinned file is not downloaded.
        reason = (
            report.longrepr[2]
            if isinstance(report.longrepr, tuple)
            else str(report.longrepr)
        )
        _add_reason(row, reason.removeprefix("Skipped: "))


def _add_reason(row: dict, reason: str) -> None:
    """Add one step's reason to a check's row, keeping what earlier steps said.

    A check can go wrong twice, failing its own assertion and then breaking in its
    clean-up. Replacing the reason would drop the assertion message and leave the
    row reading as though only the clean-up broke, which is the row getting better
    rather than worse.

    Args:
        row: The check's row.
        reason: What this step has to say.
    """
    if reason and reason not in row["reason"].split("; "):
        row["reason"] = f"{row['reason']}; {reason}" if row["reason"] else reason


def _parameter(item: pytest.Item) -> str:
    """Read the parameter pytest ran a check with.

    A parametrized check runs once per value, and pytest names each run with the
    value in brackets after the function name. The report keeps the function name
    in its own column, the same as the inventory's, and the value here, so a reader
    can filter on either.

    Args:
        item: The check.

    Returns:
        pytest's id for the parameter, or an empty string when the check has none.
    """
    callspec = getattr(item, "callspec", None)
    return str(callspec.id) if callspec is not None else ""


def _first_paragraph(doc: str | None) -> str:
    """Give a check's docstring's first paragraph as one line.

    That paragraph is the check's expected result, and it is what the report shows for
    the check.

    Args:
        doc: The docstring, or None when the check has none.

    Returns:
        The first paragraph as one line, or the words (no docstring) when the check has none.
    """
    if not doc:
        return "(no docstring)"
    first = doc.strip().split("\n\n", 1)[0]
    return " ".join(line.strip() for line in first.splitlines())


#######################################################################################
### Writing the report ###


def _git(*args: str, cwd: Path) -> str:
    """Run one git command in the repo.

    If git is not installed or the command fails, the result is '(unknown)' instead of
    an error, so a report can still be written.

    Args:
        *args: The git command's arguments.
        cwd: The folder to run in. pytest's root folder for a real run; the
            report-writer's own checks pass a temporary repository.

    Returns:
        The command's output, trimmed, or '(unknown)'.
    """
    try:
        return subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "(unknown)"


def uncommitted_changes(root: Path, report_dir: Path) -> list[str] | None:
    """List what git says is changed, staged or untracked under the root.

    The reports folder itself is left out, since the report about to be written, and
    any earlier one not yet committed, are not changes to the code being validated.

    Args:
        root: The repository's root folder.
        report_dir: The folder reports are written to.

    Returns:
        git's own one-line descriptions of the changes, or None when git did not
        answer, because it is not installed or the root is not a repository.
    """
    try:
        status = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return None
    try:
        reports = report_dir.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        reports = None
    changes = []
    for line in status.splitlines():
        if not line.strip():
            continue
        # A status line is two letters, a space, then the path.
        path = line[3:]
        if reports and (path == reports or path.startswith(reports + "/")):
            continue
        changes.append(line)
    return changes


def _sha256(path: Path) -> str:
    """Measure a file's sha256.

    The report names the exact bytes of the test code and fixtures it ran on, and this
    is how.

    Args:
        path: The file to measure.

    Returns:
        The sha256 as hex.
    """
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _unique(path: Path) -> Path:
    """Find a file name that is not in use yet.

    If the path already exists, -2, -3 and so on are added to the name, so a second
    report on the same day and commit never overwrites the first.

    Args:
        path: The name wanted.

    Returns:
        That path, or the first numbered variant of it that does not exist.
    """
    candidate, n = path, 1
    while candidate.exists():
        n += 1
        candidate = path.with_name(f"{path.stem}-{n}{path.suffix}")
    return candidate


# The moment the run started, so the report can say when the run began.
_started_at = 0.0

# How many checks were dropped before the run, counted from pytest's own hook rather
# than from the options that did the dropping. pytest fires that hook for every
# deselection whatever caused it, including its own --deselect, its -k and -m
# filters, and the options src/sdgval/select_checks.py adds, so the count stays
# right without this file knowing which options exist.
_deselected = 0


def pytest_deselected(items: list[pytest.Item]) -> None:
    """Count checks dropped from the run before it started.

    Args:
        items: The checks being dropped.
    """
    global _deselected
    _deselected += len(items)


def pytest_sessionstart(session: pytest.Session) -> None:
    """Note the moment the run started, and refuse a report that cannot be written.

    Both refusals happen here, before any check is collected, so they cost seconds
    rather than the whole run. A report comes only from an aspect's command, which
    leaves its aspect in pytest's stash before the run starts. A report also names
    the commit it validated, and a folder with uncommitted changes matches no commit.

    Args:
        session: The pytest run.

    Raises:
        pytest.UsageError: A report was asked for, and no aspect's command started
            the run, or the working folder has changes that are not committed.
    """
    global _started_at
    _started_at = time.monotonic()
    if not session.config.getoption("--validation-report"):
        return
    if REPORT_ASPECT not in session.config.stash:
        raise pytest.UsageError(
            "No checks were run and no validation report was written, because a "
            "report comes only from the command for one aspect of quality. Run "
            "validate_technical --validation-report instead of pytest "
            "--validation-report."
        )
    report_dir = _report_dir(session.config)
    changes = uncommitted_changes(session.config.rootpath, report_dir)
    if changes:
        listed = "\n".join(f"  {change}" for change in changes)
        raise pytest.UsageError(
            "No checks were run and no validation report was written, because the "
            "working folder has changes that are not committed:\n"
            f"{listed}\n"
            "A report names the commit it validated, and these changes belong to no "
            "commit yet. Commit them, or set them aside with git stash, then run the "
            "report again."
        )


# The columns of a report, in the order they are written: which run, what it
# covered and how it went, then the inventory's columns in the inventory's own
# order with the parameter beside the name, then how the check ended, then the
# details a reader needs only to reproduce a failure. The inventory's columns
# carry its names, so a row joins to it by id.
REPORT_COLUMNS = (
    "run_id",
    "selection",
    "checks_collected",
    "checks_reported",
    "run_verdict",
    "pytest_exit_status",
    "exit_meaning",
    "category",
    "quality_aspect",
    "objective",
    "staged_case",
    "folder_path",
    "file_name",
    "name",
    "parameter",
    "id",
    "target_folder_path",
    "target_file_name",
    "expected_result",
    "outcome",
    "outcome_reason",
    "started",
    "commit",
    "run_by",
    "check_file_sha256",
    "fixture_sha256s",
    "python_version",
    "pytest_version",
    "platform",
)


def _selection(config: pytest.Config) -> str:
    """Say which checks the command line selected.

    The answer is read from pytest's own parsing rather than from the raw command
    line, so a node id, a path, or the value of any option is recorded for what it is.
    The paths and node ids count only when the person typed them; when pytest filled
    them in from its configured test paths, the whole suite was selected.

    Args:
        config: pytest's configuration for the run.

    Returns:
        The paths and node ids typed, the -k or -m filters given, and the
        --category, --objective, --id and --group options given, joined with
        spaces, or all when the whole suite was selected.
    """
    kept: list[str] = []
    if config.args_source == pytest.Config.ArgsSource.ARGS:
        kept.extend(config.args)
    keyword = config.getoption("keyword")
    if keyword:
        kept.append(f"-k {keyword}")
    markexpr = config.getoption("markexpr")
    if markexpr:
        kept.append(f"-m {markexpr}")
    for name in SELECTORS:
        values = wanted(config, name)
        if values:
            kept.append(f"--{name} {','.join(values)}")
    return " ".join(kept) or "all"


def _target_of(test_file: Path, root: Path) -> tuple[str, str]:
    """Name the code file a test file proves.

    The rule is the inventory generator's, src/sdgval/build_inventory.py, imported
    above, so the report's target columns and the inventory's agree by construction.

    Args:
        test_file: The test file's path.
        root: pytest's root folder.

    Returns:
        The target's folder and its file name, the name marked when the file was not
        found at run time.
    """
    _, path = code_folder_and_target(test_file, root / "validation")
    folder, name = split_path(path)
    # The mirrored file is named even when it is not there, so the gap shows.
    if not (root / path).exists():
        name = f"{name} (not found at run time)"
    return folder, name


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Write the report after the whole run, if asked.

    Nothing is written unless --validation-report was given. One CSV file is written
    per run, one row per check, with the run's own details repeated on every row so
    the file is complete on its own. The verdict is PASS only when pytest's own exit
    number is 0.

    Args:
        session: The pytest run.
        exitstatus: pytest's exit number for the run.
    """
    if not session.config.getoption("--validation-report"):
        return
    # A refused command line, such as a selection option naming nothing, ran no
    # check and validated nothing. The refusal is on the terminal, and a report
    # of it would only be a file to delete.
    if int(exitstatus) == int(pytest.ExitCode.USAGE_ERROR):
        return
    # A listing run, --collect-only, runs no check, so there is nothing to report.
    if session.config.getoption("collectonly"):
        return

    # Everything the report states about the run is gathered once here and
    # written on every row.
    now = dt.datetime.now().astimezone()
    started = now - dt.timedelta(seconds=time.monotonic() - _started_at)
    status = int(exitstatus)
    root = session.config.rootpath
    commit = _git("rev-parse", "--short", "HEAD", cwd=root)
    validation_dir = _validation_dir(session.config)
    fixture_dir = validation_dir / "fixtures"
    fixtures = (
        sorted(p for p in fixture_dir.glob("*") if p.is_file())
        if fixture_dir.exists()
        else []
    )
    # The file is named first, so the id in every row is the file's own name and
    # the two can never disagree, numbered suffix included.
    report_dir = _report_dir(session.config)
    report_dir.mkdir(parents=True, exist_ok=True)
    aspect = session.config.stash[REPORT_ASPECT]
    target = _unique(report_dir / f"{aspect}_{now:%Y-%m-%d}_{commit}.csv")
    run = {
        "run_id": target.stem,
        "run_verdict": "PASS" if status == 0 else "FAIL",
        "pytest_exit_status": status,
        "exit_meaning": EXIT_MEANING.get(status, "unknown status"),
        "started": f"{started:%Y-%m-%d %H:%M:%S %z}",
        "commit": commit,
        "run_by": _git("config", "user.name", cwd=root),
        "selection": _selection(session.config),
        # What the run set out to cover, against what it ended up reporting on. The
        # two differ when checks were dropped or the run stopped early, so a run
        # that covered part of the suite cannot read as one that covered all of it,
        # whatever narrowed it.
        "checks_collected": len(session.items) + _deselected,
        "checks_reported": len(_outcomes),
        "python_version": platform.python_version(),
        "pytest_version": pytest.__version__,
        "platform": platform.platform(),
        "fixture_sha256s": "; ".join(
            f"validation/fixtures/{p.name}={_sha256(p)}" for p in fixtures
        ),
    }

    rows: list[dict] = []
    if _outcomes:
        # Rows keep the order the checks ran in, grouped by test file. The
        # per-file values are worked out once per file, not once per row.
        by_file: dict[Path, list[dict]] = {}
        for outcome in _outcomes.values():
            by_file.setdefault(outcome["file"], []).append(outcome)
        for file, outcomes in by_file.items():
            validation_folder, validation_file = split_path(
                f"validation/{file.relative_to(validation_dir).as_posix()}"
            )
            target_folder, target_file = _target_of(file, root)
            per_file = {
                "folder_path": validation_folder,
                "file_name": validation_file,
                "check_file_sha256": _sha256(file),
                "target_folder_path": target_folder,
                "target_file_name": target_file,
            }
            for outcome in outcomes:
                rows.append(
                    {
                        **run,
                        **per_file,
                        "id": outcome["code"],
                        "name": outcome["name"],
                        "parameter": outcome["parameter"],
                        "category": outcome["category"],
                        "quality_aspect": ASPECT_OF.get(outcome["objective"], ""),
                        "objective": outcome["objective"],
                        "staged_case": outcome["case"],
                        "expected_result": outcome["expected_result"],
                        "outcome": outcome["outcome"],
                        "outcome_reason": outcome["reason"],
                    }
                )
    else:
        # No outcome was collected, so no check ran. The row says only that. Why
        # no check ran is already in the exit_meaning column, which is right for
        # every exit number, and the writer cannot know more than the number.
        rows.append(
            {
                **run,
                "folder_path": "",
                "file_name": "",
                "check_file_sha256": "",
                "target_folder_path": "",
                "target_file_name": "",
                "id": "",
                "name": "",
                "parameter": "",
                "category": "",
                "quality_aspect": "",
                "objective": "",
                "staged_case": "",
                "expected_result": "",
                "outcome": "none",
                "outcome_reason": "no check ran",
            }
        )

    with target.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=REPORT_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    terminal = session.config.pluginmanager.get_plugin("terminalreporter")
    if terminal is not None:
        terminal.write_line(f"validation report written: {target.as_posix()}")
