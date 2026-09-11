"""
Script:      conftest.py
Description: Supplies the conditions for the test_*.py files under tests/ to run in a
             controlled environment. This file is read automatically before any test
             script under tests/ runs. pytest requires this file to be named
             conftest.py.

             When pytest loads conftest.py it adds the following for the test_*.py
             scripts to use:
               - the --validation-report flag,
               - three fixtures:
                    - manifest_dir points the manifest reader at a temporary folder,
                    - manifest_recording writes one manifest entry for one file,
                    - fake_repo builds a throwaway repo with pyproject.toml, manifests/
                      and inputs/.

             The --validation-report flag enables the writing of validation records, one
             Markdown record per test file, into tests/validation/.

             The fixtures stage the data so the real manifests/ and inputs/ are never
             touched.

             A record is meant to be auditable, so it identifies what was tested, how,
             when, by whom, and with what outcome.
               - What was tested is the component, the test file and its sha256, the
                 fixture files and their sha256s, the code commit (flagged if
                 uncommitted changes were present), and the pinned USDM data version
                 (the manifest's recorded url and sha256, and whether the file was
                 present).
               - How is the exact command line, the Python and pytest versions, and the
                 operating system.
               - When is the local timestamp with its zone, and by whom is the git user
                 name.
               - The outcome is pytest's own exit status, the pass/fail/error/skip
                 counts, the duration, and one row per test with its kind, what it
                 proves (its docstring's first paragraph) and its result.

             The verdict is PASS only when pytest itself exited 0. pytest's exit
             status already accounts for every kind of failure:
               - a test's own checks,
               - its set-up,
               - its clean-up,
               - a file that fails to load,
               - an internal error.
             Therefore the record can never say PASS when the terminal said otherwise.
             The per-test rows are the detail; the exit status is the verdict. When
             pytest fails before any test ran, a record is still written, saying so.

             It registers two markers the tests use to show which kind of test each is:
               - @positive means the right thing works,
               - @negative means the broken thing fails for the right reason.

             It also enables pytest's own "pytester" helper, which the record-writer's
             tests use to run small throwaway suites.

Inputs:      git (for the commit hash, dirty flag and user name; read-only)
             manifests/cdisc_usdm_v4.json (read-only; the pinned data version)
             inputs/standards/cdisc/usdm_v4/dataStructure.yml (existence checked only)
             tests/fixtures/* (read-only; hashed)

Outputs:     Nothing, unless --validation-report is given. Then it writes:
                - tests/validation/<folder>_<component>_<YYYY-MM-DD>_<commit>.md,
                - one per test file, where <folder> is the test file's subfolder
                  (sources, usdm, scripts; none for a top-level file),
                - or run_<date>_<commit>.md if no test ran.
             An existing name is never overwritten; it gets a numeric suffix.

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

# These two lines name the pinned model file and the manifest that records it.
# They are written here as literals rather than imported from the loader, so
# the test setup does not depend on a module the tests themselves are meant to
# prove. The loader's test, once rewritten, is where the two are checked against
# each other.
PINNED_LOCAL = "inputs/standards/cdisc/usdm_v4/dataStructure.yml"
MANIFEST = REPO_ROOT / "manifests" / "cdisc_usdm_v4.json"

# pytest has a helper called pytester that lets a test run a small, separate
# test suite of its own. It is switched off unless a file asks for it. The
# record-writer's tests, in tests/test_validation_report.py, use it to run a
# throwaway suite and then read the record that comes out.
pytest_plugins = ["pytester"]

# pytest ends every run with a number that says how the run went. The record
# prints that number together with its meaning, in these words.
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
# A fixture is a piece of setup that a test asks for by name. pytest builds it
# before the test runs and clears it away afterwards. The three fixtures here
# stage a pretend copy of the repo's manifests and pinned files in a folder that
# pytest creates and deletes for each test, so no test ever reads or writes the
# real manifests/ or inputs/.
#
# The first two fixtures serve the model loader's tests, which stage one
# manifest with one entry, broken in one chosen way. The third, fake_repo,
# serves the tests of the sources package and of the scripts, which need a
# whole small repo to walk.


@pytest.fixture
def manifest_dir(tmp_path, monkeypatch):
    """Give a check a function for staging one manifest.

    The function takes manifest text and writes it as cdisc_usdm_v4.json in a temporary
    folder. Passing None writes nothing, which stages the case where no manifest exists.
    Before the function is handed over, the manifest reader is pointed at that folder,
    and its study manifests folder is pointed at a subfolder that does not exist, so
    nothing real is read. monkeypatch puts both settings back when the check ends.

    Returns:
        The staging function.
    """
    from sdg.sources import read_manifests

    monkeypatch.setattr(read_manifests, "MANIFEST_DIR", tmp_path)
    monkeypatch.setattr(
        read_manifests, "STUDY_MANIFEST_DIR", tmp_path / "study_documents"
    )

    def make(text: str | None) -> None:
        """Write the given text as the one manifest, or nothing when None.

        Args:
            text: The manifest's text, or None to stage no manifest at all.
        """
        if text is not None:
            (tmp_path / "cdisc_usdm_v4.json").write_text(text, encoding="utf-8")

    return make


@pytest.fixture
def manifest_recording():
    """Give a check a function for writing one manifest entry with one chosen fault.

    The function takes the path of a file and produces manifest text with a single entry
    for it. The entry's size is right and its sha256 is a placeholder of zeros. A check
    can change any field by naming it, or remove a field by passing None for it. That is
    how a check stages exactly one thing wrong, such as a wrong sha256, a wrong size or
    a missing field, and nothing else.

    Returns:
        The writing function.
    """
    from sdg.sources import read_manifests

    def make(path: Path, **overrides) -> str:
        """Build the entry for the given file, apply the overrides, and give back the
        manifest as JSON text.

        Args:
            path: The file the entry records.
            **overrides: Any field to change, or None for a field to leave out.

        Returns:
            The manifest text.
        """
        entry = {
            "name": "fixture",
            "url": "https://example.invalid/fixture",
            "local": path.relative_to(read_manifests.REPO_ROOT).as_posix(),
            "sha256": "0" * 64,
            "bytes": path.stat().st_size,
        }
        # A value of None means leave this field out, which stages a missing
        # field. Any other value replaces the field.
        for key, value in overrides.items():
            if value is None:
                entry.pop(key)
            else:
                entry[key] = value
        return json.dumps({"files": [entry]})

    return make


class FakeRepo:
    """A small pretend repo on disk, for checks that need to walk a whole one.

    It has the three things the manifest reader looks for: a pyproject.toml, a
    manifests/ folder with its study_documents/ subfolder, and an inputs/ folder. The
    methods put files and manifests into it. Every path a check gives is relative to the
    fake repo's root and is written with forward slashes, the same way a manifest writes
    it.
    """

    def __init__(self, root: Path):
        """Create the fake repo's folders and its pyproject.toml under the root.

        Args:
            root: The temporary folder the fake repo lives in.
        """
        self.root = root
        (root / "manifests" / "study_documents").mkdir(parents=True)
        (root / "inputs").mkdir(parents=True)
        # The manifest reader checks that it is running inside its own repo by
        # looking for this exact line in pyproject.toml. The fake repo has to
        # carry the same line, or every test would be refused as running from
        # the wrong place.
        (root / "pyproject.toml").write_text(
            '[project]\nname = "sdg"\n', encoding="utf-8"
        )

    def file(self, local: str, content: bytes) -> Path:
        """Write one file into the fake repo.

        Any folders on the way are created. Checks use this for pinned files under
        inputs/ and for anything else they want on disk.

        Args:
            local: The file's path relative to the fake root.
            content: The bytes to write.

        Returns:
            The file's full path.
        """
        path = self.root / local
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def entry(self, local: str, **overrides: object) -> dict[str, object]:
        """Build one manifest entry for a file in the fake repo.

        The entry is correct by default: when the file exists, its size and sha256 are
        measured from it. A check can then change any field by naming it, or remove a
        field by passing None, so that exactly one thing is wrong.

        Args:
            local: The file's path relative to the fake root.
            **overrides: Any field to change, or None for a field to leave out.

        Returns:
            The entry, as the JSON reader would hand it back.
        """
        path = self.root / local
        # The size is a number and the rest are text, so the entry's values are
        # typed as anything.
        entry: dict[str, object] = {
            "name": Path(local).name,
            "url": f"https://example.invalid/{Path(local).name}",
            "local": local,
        }
        # Size and sha256 are measured only when a file is there. A test that
        # wants an entry for a file not yet on disk, or for a path where a
        # folder sits instead of a file, gets one without them and sets them
        # itself.
        if path.is_file():
            entry["bytes"] = path.stat().st_size
            entry["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        # A value of None means leave this field out, which stages a missing
        # field. Any other value replaces the field.
        for key, value in overrides.items():
            if value is None:
                entry.pop(key, None)
            else:
                entry[key] = value
        return entry

    def manifest(
        self, name: str, entries: list[dict] | str, study: bool = False
    ) -> Path:
        """Write one manifest file into the fake repo.

        Args:
            name: The manifest's file name.
            entries: The entries as a list, written as proper JSON, or raw text, written
                as it is so a check can stage a manifest that cannot be read.
            study: True to put the file under manifests/study_documents/ instead of
                manifests/.

        Returns:
            The manifest's full path.
        """
        folder = self.root / "manifests"
        if study:
            folder = folder / "study_documents"
        path = folder / f"{name}.json"
        text = entries if isinstance(entries, str) else json.dumps({"files": entries})
        path.write_text(text, encoding="utf-8")
        return path


@pytest.fixture
def fake_repo(tmp_path, monkeypatch) -> FakeRepo:
    """Give a check a FakeRepo and point the manifest reader at it.

    The reader keeps three locations: the repo root, the manifests folder and the study
    manifests folder. All three are pointed at the fake repo for the length of the
    check, and monkeypatch puts them back afterwards. A script that copied one of those
    locations when it was first loaded, such as find_unrecorded_files with its
    PINNED_DIR, is not covered by this; the test file for that script has its own
    fixture to repoint it.

    Returns:
        The fake repo.
    """
    from sdg.sources import read_manifests

    repo = FakeRepo(tmp_path / "repo")
    monkeypatch.setattr(read_manifests, "REPO_ROOT", repo.root)
    monkeypatch.setattr(read_manifests, "MANIFEST_DIR", repo.root / "manifests")
    monkeypatch.setattr(
        read_manifests,
        "STUDY_MANIFEST_DIR",
        repo.root / "manifests" / "study_documents",
    )
    return repo


#######################################################################################
### Command line and markers ###


def pytest_addoption(parser):
    """Add two options to the pytest command line.

    --validation-report is off unless given. With it, a record is written after the run.
    --validation-report-dir says which folder the record goes in. It defaults to
    tests/validation; the record-writer's own checks point it at a temporary folder
    instead.

    Args:
        parser: pytest's command-line parser.
    """
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
    """Tell pytest about the markers the checks use: positive, negative and code.

    A marker is a label a check carries. pytest warns about a label it has not been told
    about, so each is declared here with a sentence saying what it means.

    Args:
        config: pytest's configuration.
    """
    config.addinivalue_line("markers", "positive: proves the right thing works")
    config.addinivalue_line(
        "markers", "negative: proves the broken thing fails, and for the right reason"
    )
    # The code is the check's short, permanent id in tests/validation_inventory.csv:
    # a type prefix and four digits, such as SRC0042, assigned once and never
    # reused.
    config.addinivalue_line(
        "markers", "code(id): the check's id in tests/validation_inventory.csv"
    )


#######################################################################################
### Collecting outcomes ###
#
# pytest runs each test in three steps: set-up, the test itself (pytest calls
# this the call step), and clean-up. It reports on each step separately. One
# row per test is kept here, and a later step may make the row worse but never
# better: a test whose checks passed but whose clean-up failed ends up as an
# error, which is also what pytest prints on the terminal. Nothing here decides
# whether the run passed. That verdict comes from pytest's own exit number, in
# pytest_sessionfinish below.

# One row per test, keyed by the id pytest gives the test.
_outcomes: dict[str, dict] = {}


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
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
        outcome = report.outcome
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
    # A clean-up error replaces an earlier pass. No step ever makes a row
    # better than it was.
    if outcome == "error" or row["outcome"] in ("passed", ""):
        row["outcome"] = outcome
    if report.when == "teardown" and outcome == "error":
        row["reason"] = "clean-up failed"
    if outcome == "skipped":
        # For a skip, pytest stores the reason as the third item of a tuple of
        # file, line and reason. The reason is what a reader needs, usually
        # that the pinned file is not downloaded.
        reason = (
            report.longrepr[2]
            if isinstance(report.longrepr, tuple)
            else str(report.longrepr)
        )
        row["reason"] = reason.removeprefix("Skipped: ")


def _kind(item) -> str:
    """Read a check's kind off its marker.

    Args:
        item: The check.

    Returns:
        positive, negative, or unmarked when it carries neither.
    """
    if item.get_closest_marker("positive"):
        return "positive"
    if item.get_closest_marker("negative"):
        return "negative"
    return "unmarked"


def _first_paragraph(doc: str | None) -> str:
    """Give a check's docstring's first paragraph as one line.

    That paragraph is the plain statement of what the check proves, and it is what the
    record shows for the check.

    Args:
        doc: The docstring, or None when the check has none.

    Returns:
        The first paragraph as one line, or an empty string when there is no docstring.
    """
    if not doc:
        return "(no docstring)"
    first = doc.strip().split("\n\n", 1)[0]
    return " ".join(line.strip() for line in first.splitlines())


#######################################################################################
### Writing the record ###


def _git(*args: str) -> str:
    """Run one git command in the repo.

    If git is not installed or the command fails, the result is '(unknown)' instead of
    an error, so a record can still be written.

    Args:
        *args: The git command's arguments.

    Returns:
        The command's output, trimmed, or '(unknown)'.
    """
    try:
        return subprocess.run(
            ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "(unknown)"


def _sha256(path: Path) -> str:
    """Measure a file's sha256.

    The record names the exact bytes of the test code and fixtures it ran on, and this
    is how.

    Args:
        path: The file to measure.

    Returns:
        The sha256 as hex.
    """
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _pinned_data_version() -> str:
    """Say which version of the pinned model file was on the machine at run time.

    The line holds the url from the manifest, which carries the DDF-RA commit, the
    recorded sha256, and whether the file was present on disk. If the manifest cannot be
    read, the line says so instead, and the record is still written.

    Returns:
        One line for the record.
    """
    present = (
        "present"
        if (REPO_ROOT / PINNED_LOCAL).exists()
        else "absent (real-file checks skipped)"
    )
    # The manifest is read directly here rather than through the package, so a
    # broken package cannot stop the record from being written.
    try:
        entries = json.loads(MANIFEST.read_text(encoding="utf-8")).get("files", [])
        entry = next(e for e in entries if e.get("local") == PINNED_LOCAL)
        return f"{entry.get('url', '(no url)')}, sha256 `{entry.get('sha256', '?')}`, {present}"
    except (OSError, ValueError, StopIteration):
        return f"(manifest entry not readable), {present}"


def _unique(path: Path) -> Path:
    """Find a file name that is not in use yet.

    If the path already exists, -2, -3 and so on are added to the name, so a second
    record on the same day and commit never overwrites the first.

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


# The moment the run started, so the record can say how long the run took.
_started_at = 0.0


def pytest_sessionstart(session):
    """Note the moment the run started.

    Args:
        session: The pytest run.
    """
    global _started_at
    _started_at = time.monotonic()


def pytest_sessionfinish(session, exitstatus):
    """Write the records after the whole run, if asked.

    Nothing is written unless --validation-report was given. The verdict is PASS only
    when pytest's own exit number is 0.

    Args:
        session: The pytest run.
        exitstatus: pytest's exit number for the run.
    """
    if not session.config.getoption("--validation-report"):
        return

    # Everything the record states about the run is gathered once here and
    # shared by every record written below.
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
        "<br>".join(
            f"`tests/fixtures/{p.name}` sha256 `{_sha256(p)}`" for p in fixtures
        )
        or "(none)"
    )
    dirty_note = " (uncommitted changes present at run time)" if dirty else ""

    # One record is written per test file, so the rows are grouped by the file
    # each test came from.
    by_file: dict[Path, list[dict]] = {}
    for row in _outcomes.values():
        by_file.setdefault(row["file"], []).append(row)

    report_dir = Path(session.config.getoption("--validation-report-dir"))
    report_dir.mkdir(parents=True, exist_ok=True)
    terminal = session.config.pluginmanager.get_plugin("terminalreporter")

    def write(
        name: str, component_line: str, test_file_line: str, rows: list[dict]
    ) -> None:
        """Write one record file.

        Used both for the normal case, one record per test file, and for the case where
        no check ran at all.

        Args:
            name: The record's file name.
            component_line: The line saying which code file was tested.
            test_file_line: The line saying which test file ran.
            rows: One row per check, with its name, kind, what it proves and its
                outcome.
        """
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
                lines.append(
                    f"| `{r['name']}` | {r['kind']} | {r['proves']} | {outcome} |"
                )
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

    # No outcome was collected, so pytest failed before any test ran. One
    # record is written saying so.
    if not by_file:
        write("run", "(none: no test ran)", "(none)", [])
        return

    for file, rows in by_file.items():
        # tests/ mirrors the code. A test file in tests/scripts/ tests the
        # script of the same name in scripts/. A test file in any other
        # subfolder tests the file of the same name in that folder under
        # src/sdg/. A test file at the top level has no code file to mirror;
        # the one there, test_validation_report.py, tests the record-writer in
        # this file, so its record names the test file itself.
        relative = file.relative_to(TESTS_DIR)
        folder = relative.parent.as_posix()
        component = file.stem.removeprefix("test_")
        if folder == ".":
            mirrored = None
        elif folder == "scripts":
            mirrored = REPO_ROOT / "scripts" / f"{component}.py"
        else:
            mirrored = REPO_ROOT / "src" / "sdg" / folder / f"{component}.py"

        if mirrored is None:
            component_line = f"`tests/{relative.as_posix()}` itself"
        elif mirrored.exists():
            component_line = f"`{mirrored.relative_to(REPO_ROOT).as_posix()}`"
        else:
            # The mirrored file is not there. The record still names it, and
            # says it was not found, rather than hiding the gap.
            component_line = f"`{mirrored.relative_to(REPO_ROOT).as_posix()}` (not found at run time)"

        test_file_line = f"`tests/{relative.as_posix()}` sha256 `{_sha256(file)}`"
        # The record's file name carries the subfolder, so two folders can each
        # hold a test file of the same name without their records colliding.
        record_name = (
            component if folder == "." else f"{folder.replace('/', '_')}_{component}"
        )
        write(record_name, component_line, test_file_line, rows)
