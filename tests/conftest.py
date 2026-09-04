"""
Script:      conftest.py
Description: pytest's per-folder setup file, read automatically before any test
             in tests/ runs. It adds the --validation-report flag, and two
             fixtures (manifest_dir, manifest_recording) that test_pinned.py and
             test_usdm_spec.py both use to stage a manifest of their own in a
             temporary folder.

             Without the flag, a test run prints to the terminal and writes
             nothing, which is what development wants. With the flag, the run
             also writes one Markdown record per test file into
             tests/validation/. That record is the proof that the component was
             validated at that point; commit it.

             A record is meant to be auditable, so it identifies:
             - what was tested: the component, the test file and its sha256, the
               fixture files and their sha256s, the code commit (flagged if
               uncommitted changes were present), and the pinned USDM data
               version (the manifest's recorded url and sha256, and whether the
               file was present);
             - how: the exact command line, Python and pytest versions, OS;
             - when and by whom: local timestamp with zone, git user name;
             - the outcome: pytest's own exit status, pass/fail/error/skip
               counts, duration, and one row per test with its kind, what it
               proves (its docstring's first paragraph) and its result.

             The verdict is PASS only when pytest itself exited 0. pytest's exit
             status already accounts for every kind of failure (a test's own
             checks, its set-up, its clean-up, a file that fails to load, an
             internal error), so the record can never say PASS when the terminal
             said otherwise. The per-test rows are the detail; the exit status
             is the verdict. When pytest fails before any test ran, a record is
             still written, saying so.

             It also registers the two markers the tests use, @positive (the
             right thing works) and @negative (the broken thing fails for the
             right reason), so the record can show which kind each test is, and
             enables pytest's own "pytester" helper, which the record-writer's
             tests use to run small throwaway suites.

Inputs:      git (for the commit hash, dirty flag and user name; read-only)
             data/manifests/raw_usdm_v4.json (read-only; the pinned data version)
             data/raw/usdm_v4/uml/dataStructure.yml (existence checked only)
             tests/fixtures/* (read-only; hashed)

Outputs:     Nothing, unless --validation-report is given: then
             tests/validation/<component>_<YYYY-MM-DD>_<commit>.md, one per
             test file (or run_<date>_<commit>.md if no test ran). Never
             overwrites: an existing name gets a numeric suffix.

Usage:       pytest
                 run every test, write nothing
             pytest --validation-report
                 run every test and write the record(s) to tests/validation/
             pytest --validation-report --validation-report-dir <folder>
                 same, writing to another folder (the record-writer's own
                 tests use this to write into a temporary folder)

Exit codes:  pytest's own: 0 all passed, 1 some failed, 2 interrupted,
             3 internal error, 4 bad command line, 5 no tests collected

Date:        2026-09-04
Owner:       Jason Delosh
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import platform
import subprocess
import time
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
FIXTURE_DIR = TESTS_DIR / "fixtures"
MANIFEST = REPO_ROOT / "data" / "manifests" / "raw_usdm_v4.json"
PINNED_LOCAL = "data/raw/usdm_v4/uml/dataStructure.yml"

# pytest's helper for running a throwaway test suite inside a test. Off by
# default; tests/test_validation_report.py needs it.
pytest_plugins = ["pytester"]

# What each pytest exit status means, in the words the record uses.
EXIT_MEANING = {
    0: "all tests passed",
    1: "one or more tests failed or errored",
    2: "the run was interrupted",
    3: "pytest hit an internal error",
    4: "pytest was given a bad command line",
    5: "no tests were collected",
}


#######################################################################################
### Shared fixtures ###
#
# Two helpers both test_pinned.py and test_usdm_spec.py need to stage a manifest
# of their own: one that points the package at a temporary manifests folder, and
# one that writes a manifest entry with exactly one chosen defect.


@pytest.fixture
def manifest_dir(tmp_path, monkeypatch):
    """Produces a function that takes manifest JSON text (or None for no manifest
    at all), writes it as raw_usdm_v4.json in a temporary folder, and points
    sdg.pinned at that folder for the rest of the test. monkeypatch puts the real
    folder back afterwards."""
    from sdg import pinned as pinned_mod

    monkeypatch.setattr(pinned_mod, "MANIFEST_DIR", tmp_path)

    def make(text: str | None) -> None:
        if text is not None:
            (tmp_path / "raw_usdm_v4.json").write_text(text, encoding="utf-8")

    return make


@pytest.fixture
def manifest_recording():
    """Produces a function that takes a file path and gives back manifest JSON
    with one entry for it, correct in size, with any field overridden (a wrong
    sha256, a wrong size, a different local path, a missing key via None) so a
    test can stage exactly one defect."""
    from sdg import pinned as pinned_mod

    def make(path: Path, **overrides) -> str:
        entry = {
            "name": "fixture",
            "url": "https://example.invalid/fixture",
            "local": path.relative_to(pinned_mod.REPO_ROOT).as_posix(),
            "sha256": "0" * 64,
            "bytes": path.stat().st_size,
        }
        for key, value in overrides.items():
            if value is None:
                entry.pop(key)
            else:
                entry[key] = value
        return json.dumps({"files": [entry]})

    return make


#######################################################################################
### Command line and markers ###


def pytest_addoption(parser):
    """Adds --validation-report (off by default) and --validation-report-dir
    (default tests/validation) to pytest's command line."""
    parser.addoption(
        "--validation-report",
        action="store_true",
        default=False,
        help="after the run, write a validation record per test file",
    )
    parser.addoption(
        "--validation-report-dir",
        default=str(TESTS_DIR / "validation"),
        help="folder the records are written to (default: tests/validation)",
    )


def pytest_configure(config):
    """Declares the positive/negative markers so pytest does not warn about them."""
    config.addinivalue_line("markers", "positive: proves the right thing works")
    config.addinivalue_line(
        "markers", "negative: proves the broken thing fails, and for the right reason"
    )


#######################################################################################
### Collecting outcomes ###
#
# pytest reports each test in three phases: setup, call (the test itself) and
# teardown (its clean-up). One row per test is kept here, keyed by test id, and a
# later phase may worsen it: a test whose call passed but whose teardown failed
# ends as "error", which is also what pytest's terminal says. Nothing here decides
# the verdict; that comes from pytest's exit status in pytest_sessionfinish.

_outcomes: dict[str, dict] = {}


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Records the outcome of one test phase into that test's row."""
    result = yield
    report = result.get_result()

    if report.when == "call":
        outcome = report.outcome  # passed, failed or skipped
    elif report.passed:
        return  # a clean setup or teardown says nothing on its own
    elif report.skipped:
        outcome = "skipped"  # a skip decided at setup (a skipif marker)
    else:
        outcome = "error"  # setup or teardown broke; pytest's own word for it

    row = _outcomes.setdefault(
        item.nodeid,
        {
            "file": Path(str(item.fspath)),
            "name": item.name,
            "kind": _kind(item),
            "proves": _first_paragraph(item.obj.__doc__),
            "outcome": outcome,
            "reason": "",
        },
    )
    # A teardown error overrides an earlier pass; a phase never upgrades a row.
    if outcome == "error" or row["outcome"] in ("passed", ""):
        row["outcome"] = outcome
    if report.when == "teardown" and outcome == "error":
        row["reason"] = "clean-up failed"
    if outcome == "skipped":
        # For a skip, longrepr is (file, line, reason); the reason is what the
        # reader needs (usually "pinned file not downloaded").
        reason = (
            report.longrepr[2]
            if isinstance(report.longrepr, tuple)
            else str(report.longrepr)
        )
        row["reason"] = reason.removeprefix("Skipped: ")


def _kind(item) -> str:
    """Reads the positive/negative marker off a test; 'unmarked' if it has neither."""
    if item.get_closest_marker("positive"):
        return "positive"
    if item.get_closest_marker("negative"):
        return "negative"
    return "unmarked"


def _first_paragraph(doc: str | None) -> str:
    """Takes a docstring and produces its first paragraph as one line, which is
    the plain-terms statement of what the test proves."""
    if not doc:
        return "(no docstring)"
    first = doc.strip().split("\n\n", 1)[0]
    return " ".join(line.strip() for line in first.splitlines())


#######################################################################################
### Writing the record ###


def _git(*args: str) -> str:
    """Runs one git command in the repo and produces its trimmed output, or
    '(unknown)' if git is unavailable, so a report can still be written."""
    try:
        return subprocess.run(
            ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "(unknown)"


def _sha256(path: Path) -> str:
    """Takes a file path and produces its hex sha256, so the record names the
    exact test code and fixture bytes it ran on."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _pinned_data_version() -> str:
    """Reads the manifest entry for dataStructure.yml and produces one line naming
    the pinned version (its url, which carries the DDF-RA commit, and recorded
    sha256) and whether the file is on disk. Falls back to a plain note if the
    manifest cannot be read, so the record is still written."""
    present = (
        "present"
        if (REPO_ROOT / PINNED_LOCAL).exists()
        else "absent (real-file checks skipped)"
    )
    try:
        entries = json.loads(MANIFEST.read_text(encoding="utf-8")).get("files", [])
        entry = next(e for e in entries if e.get("local") == PINNED_LOCAL)
        return f"{entry.get('url', '(no url)')}, sha256 `{entry.get('sha256', '?')}`, {present}"
    except (OSError, ValueError, StopIteration):
        return f"(manifest entry not readable), {present}"


def _unique(path: Path) -> Path:
    """Takes a target path and produces one that does not exist yet, adding -2,
    -3, ... so a second report on the same day and commit never overwrites the first."""
    candidate, n = path, 1
    while candidate.exists():
        n += 1
        candidate = path.with_name(f"{path.stem}-{n}{path.suffix}")
    return candidate


_started_at = 0.0


def pytest_sessionstart(session):
    """Notes the wall-clock start so the record can state the run's duration."""
    global _started_at
    _started_at = time.monotonic()


def pytest_sessionfinish(session, exitstatus):
    """After the whole run, writes the record(s) if the flag was given. The
    verdict is PASS only when pytest's own exit status is 0."""
    if not session.config.getoption("--validation-report"):
        return

    now = dt.datetime.now().astimezone()
    duration = time.monotonic() - _started_at
    status = int(exitstatus)
    verdict = "PASS" if status == 0 else "FAIL"
    commit = _git("rev-parse", "--short", "HEAD")
    dirty = bool(_git("status", "--porcelain"))
    user = _git("config", "user.name")
    command = "pytest " + " ".join(session.config.invocation_params.args)
    fixtures = (
        sorted(p for p in FIXTURE_DIR.glob("*") if p.is_file())
        if FIXTURE_DIR.exists()
        else []
    )
    fixture_note = (
        "<br>".join(f"`tests/fixtures/{p.name}` sha256 `{_sha256(p)}`" for p in fixtures)
        or "(none)"
    )
    dirty_note = " (uncommitted changes present at run time)" if dirty else ""

    by_file: dict[Path, list[dict]] = {}
    for row in _outcomes.values():
        by_file.setdefault(row["file"], []).append(row)

    report_dir = Path(session.config.getoption("--validation-report-dir"))
    report_dir.mkdir(parents=True, exist_ok=True)
    terminal = session.config.pluginmanager.get_plugin("terminalreporter")

    def write(name: str, component_line: str, test_file_line: str, rows: list[dict]) -> None:
        """Takes the record's file stem, its two identity lines and its test rows,
        and writes the record. Shared by the per-file and the no-tests-ran cases."""
        counts = {
            k: sum(1 for r in rows if r["outcome"] == k)
            for k in ("passed", "failed", "error", "skipped")
        }
        lines = [
            f"# Validation record: {name}",
            "",
            f"Written by `pytest --validation-report` on {now:%Y-%m-%d %H:%M %Z}. "
            "Design and rationale for these tests: `tests/README.md`.",
            "",
            "| | |",
            "| --- | --- |",
            f"| Verdict | **{verdict}**: pytest exit status {status} "
            f"({EXIT_MEANING.get(status, 'unknown status')}) |",
            f"| Counts | {counts['passed']} passed, {counts['failed']} failed, "
            f"{counts['error']} error, {counts['skipped']} skipped, in {duration:.1f} s |",
            f"| Component | {component_line} |",
            f"| Code commit | `{commit}`{dirty_note} |",
            f"| Test file | {test_file_line} |",
            f"| Fixtures | {fixture_note} |",
            f"| Pinned USDM data | {_pinned_data_version()} |",
            f"| Command | `{command}` |",
            f"| Run by | {user} |",
            f"| When | {now:%Y-%m-%d %H:%M:%S %Z} |",
            f"| Python / pytest | {platform.python_version()} / {pytest.__version__} |",
            f"| Platform | {platform.platform()} |",
            "",
        ]
        if rows:
            lines += ["| Test | Kind | Proves | Outcome |", "| --- | --- | --- | --- |"]
            for r in rows:
                outcome = r["outcome"] + (f" ({r['reason']})" if r["reason"] else "")
                lines.append(f"| `{r['name']}` | {r['kind']} | {r['proves']} | {outcome} |")
        else:
            lines.append(
                "No test outcomes were recorded: pytest failed before any test ran "
                "(a test file that would not load, or an internal error). "
                "See the terminal output of the command above."
            )
        target = _unique(report_dir / f"{name}_{now:%Y-%m-%d}_{commit}.md")
        target.write_text("\n".join(lines) + "\n", encoding="utf-8")
        if terminal is not None:
            terminal.write_line(f"validation record written: {target.as_posix()}")

    if not by_file:
        write("run", "(none: no test ran)", "(none)", [])
        return

    for file, rows in by_file.items():
        component = file.stem.removeprefix("test_")
        src = REPO_ROOT / "src" / "sdg" / f"{component}.py"
        component_line = f"`src/sdg/{component}.py`" if src.exists() else f"`tests/{file.name}` itself"
        test_file_line = f"`tests/{file.name}` sha256 `{_sha256(file)}`"
        write(component, component_line, test_file_line, rows)
