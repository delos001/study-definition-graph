"""
Script:      conftest.py
Description: Supplies the conditions for the test_*.py files under validation/ to run in a
             controlled environment. This file is read automatically before any test
             script under validation/ runs. pytest requires this file to be named
             conftest.py.

             When pytest loads conftest.py it adds the following for the test_*.py
             scripts to use:
               - the --validation-report flag,
               - the fixtures:
                    - manifest_dir points the manifest reader, src/sdg/sources/read_manifests.py, at a temporary folder,
                    - manifest_recording writes one manifest entry for one file,
                    - fake_repo builds a throwaway repo with pyproject.toml, manifests/
                      and inputs/.

             The --validation-report flag enables the writing of a validation report:
             one CSV file per run, one row per check, into validation/reports/.

             The fixtures stage the data so the real manifests/ and inputs/ are never
             touched.

             A report is meant to be auditable, so it identifies what was tested, how,
             when, by whom, and with what outcome. The run's own details are repeated
             on every row, so each file is complete on its own and any row can be
             joined to validation/validation_inventory.csv by its check code.
               - What was tested is the target file, the file of checks and its sha256,
                 the fixture files and their sha256s, the code commit, and the pinned
                 USDM data version (the manifest's recorded sha256, and whether the
                 file was present). The commit is the parent of the commit that adds
                 the report, since the report is written first.
               - How is which checks were selected, and, at the far right of each row,
                 the Python and pytest versions and the operating system.
               - When is the local timestamp with its zone, and by whom is the git user
                 name.
               - The outcome is the run's verdict, from pytest's own exit status, and
                 one row per check. A row holds the check's id, its category, its
                 objective, its case when it is a correctness check that staged
                 its own situation, its expected result,
                 which is its docstring's first paragraph, its own outcome, and the
                 reason when that is not passed: the assertion message, the step
                 that broke, or why it was skipped.

             The verdict is PASS only when pytest itself exited 0. pytest's exit
             status already accounts for every kind of failure:
               - a test's own checks,
               - its set-up,
               - its clean-up,
               - a file that fails to load,
               - an internal error.
             Therefore the report can never say PASS when the terminal said otherwise.
             The rows are the detail; the exit status is the verdict. When pytest
             fails before any test ran, a report is still written, with one row
             saying that no check ran.

             It registers the markers the tests carry:
               - @code carries the check's permanent id from validation/validation_inventory.csv,
               - @category carries what kind of thing the check confirms, one of
                 the categories validation/validation_inventory_dictionary.md
                 defines,
               - @objective carries what the check confirms about its category,
                 one of the objectives the same dictionary defines,
               - @positive, on a correctness check, means a staged working
                 situation where the code is expected to succeed,
               - @negative, on a correctness check, means a staged broken
                 situation where the code is expected to refuse for the right
                 reason,
               - @needs_pinned names the real pinned files a check reads.

             Before a check marked @needs_pinned runs, each pinned file it names is
             looked at. The check is skipped, with the reason recorded, when a file
             is not downloaded or when it no longer matches its manifest entry. The
             second case is called blocked. Only the stability check for that file
             fails, so one changed file is reported as one failure, not as a
             failure of every check that reads it.

             It also enables pytest's own "pytester" helper, which the report-writer's
             tests use to run small throwaway suites.

Inputs:      git (for the commit hash and user name; read-only)
             manifests/*.json (read-only; the pinned data version, and the entries
                 the @needs_pinned files are looked up in)
             inputs/** (read-only; only the files a @needs_pinned check names, which
                 are measured)
             validation/fixtures/* (read-only; hashed)

Outputs:     Nothing, unless --validation-report is given. Then it writes one file,
             validation/reports/run_<YYYY-MM-DD>_<commit>.csv, with one row per check.
             An existing name is never overwritten; it gets a numeric suffix.

Usage:       pytest
                 run every test, write nothing
             pytest --validation-report
                 run every test and write the report to validation/reports/
             pytest --validation-report --validation-report-dir <folder>
                 same, writing to another folder (the report-writer's own
                 tests use this to write into a temporary folder)

Exit codes:  pytest's own: 0 all passed, 1 some failed, 2 interrupted,
             3 internal error, 4 bad command line, 5 no tests collected

Date:        2026-09-04
Owner:       Jason Delosh
"""

from __future__ import annotations

import csv
import datetime as dt
import fnmatch
import functools
import hashlib
import json
import platform
import subprocess
import time
from pathlib import Path

import pytest

# The rule that says which code file a check file proves lives in the inventory
# generator, repo_tools/build_inventory.py, which fills the same column of the
# inventory. Importing it means the
# inventory and a report can never disagree. pyproject.toml puts repo_tools/ on
# pytest's import path, and the generator uses only the standard library, so this
# import cannot fail because the sdg package is broken.
from build_inventory import split_path, type_and_target

VALIDATION_DIR = Path(__file__).resolve().parent
REPO_ROOT = VALIDATION_DIR.parent
FIXTURE_DIR = VALIDATION_DIR / "fixtures"

# These two lines name the pinned model file and the manifest that records it.
# They are written here as literals rather than imported from the loader, src/sdg/usdm/usdm_spec.py, so
# the test setup does not depend on a module the tests themselves are meant to
# prove. The loader's test, once rewritten, is where the two are checked against
# each other.
PINNED_LOCAL = "inputs/standards/cdisc/usdm_v4/dataStructure.yml"
MANIFEST = REPO_ROOT / "manifests" / "cdisc_usdm_v4.json"

# pytest has a helper called pytester that lets a test run a small, separate
# test suite of its own. It is switched off unless a file asks for it. The
# report-writer's tests, in validation/test_validation_report.py, use it to run a
# throwaway suite and then read the report that comes out.
pytest_plugins = ["pytester"]

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


#######################################################################################
### Shared fixtures ###
#
# A fixture is a piece of setup that a test asks for by name. pytest builds it
# before the test runs and clears it away afterwards. The fixtures here
# stage a pretend copy of the repo's manifests and pinned files in a folder that
# pytest creates and deletes for each test, so no test ever reads or writes the
# real manifests/ or inputs/.
#
# The first two fixtures serve the tests of the model loader, src/sdg/usdm/usdm_spec.py, which stage one
# manifest with one entry, broken in one chosen way. The third, fake_repo,
# serves the tests of src/sdg/sources/ and of the tools in repo_tools/, which need a
# whole small repo to walk.


@pytest.fixture
def manifest_dir(tmp_path, monkeypatch):
    """Give a check a function for staging one manifest.

    The function takes manifest text and writes it as cdisc_usdm_v4.json in a temporary
    folder. Passing None writes nothing, which stages the case where no manifest exists.
    Before the function is handed over, the manifest reader, src/sdg/sources/read_manifests.py, is pointed at that folder,
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

    It has what the manifest reader, src/sdg/sources/read_manifests.py, looks for: a pyproject.toml, a
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
        # The manifest reader, src/sdg/sources/read_manifests.py, checks that it is running inside its own repo by
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
    """Give a check a FakeRepo and point the manifest reader, src/sdg/sources/read_manifests.py, at it.

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
    """Add the report options to the pytest command line.

    --validation-report is off unless given. With it, one report is written after the
    run. --validation-report-dir says which folder the report goes in. It defaults to
    validation/reports; the report-writer's own checks point it at a temporary folder
    instead.

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
        default=str(VALIDATION_DIR / "reports"),
        help="folder the report is written to (default: validation/reports)",
    )


def pytest_configure(config):
    """Tell pytest about the markers the checks use: code, category, objective,
    positive, negative and needs_pinned.

    A marker is a label a check carries. pytest warns about a label it has not been told
    about, so each is declared here with a sentence saying what it means.

    Args:
        config: pytest's configuration.
    """
    config.addinivalue_line(
        "markers",
        "category(name): what kind of thing the check confirms, one of the categories "
        "in validation/validation_inventory_dictionary.md",
    )
    config.addinivalue_line(
        "markers",
        "objective(name): what the check confirms about its category, one of the "
        "objectives in validation/validation_inventory_dictionary.md",
    )
    config.addinivalue_line(
        "markers",
        "positive: a correctness check of a staged working situation, expected to "
        "succeed",
    )
    config.addinivalue_line(
        "markers",
        "negative: a correctness check of a staged broken situation, expected to "
        "refuse for the right reason",
    )
    # The code is the check's short, permanent id in validation/validation_inventory.csv:
    # a type prefix and four digits, such as SRC0042, assigned once and never
    # reused.
    config.addinivalue_line(
        "markers", "code(id): the check's id in validation/validation_inventory.csv"
    )
    config.addinivalue_line(
        "markers",
        "needs_pinned(*paths): the real pinned files the check reads, each written as "
        "a manifest writes it, where * stands for any run of characters",
    )


#######################################################################################
### Pinned files a check depends on ###
#
# A check that reads real pinned files names them with @needs_pinned. Before the check
# runs, every file that matches is looked at, and the check is skipped with the
# reason when one is not downloaded or no longer matches its manifest entry. A
# skipped check is recorded as skipped in a report, with that reason. The stability
# check for each pinned file, in validation/sources/test_verify_pinned.py, is the only
# check that fails for a changed file, so the change is reported once. A marker that
# names a file no manifest records is a mistake in the check, so that check errors
# rather than skips, and the run fails.


class UnmatchedPatternError(Exception):
    """A @needs_pinned marker names a file that no manifest records."""


def pinned_skip_reason(pattern: str) -> str | None:
    """Say why a check that reads the pinned files matching a pattern cannot run.

    The pattern is a path as a manifest writes it, where * stands for any run of
    characters. Each manifest entry whose path matches is looked at in turn, and the
    first problem found is the answer.

    Args:
        pattern: The pinned file or files the check reads.

    Returns:
        None when every matching file is on disk and matches its entry. Otherwise the
        reason: a file is not downloaded, or a file no longer matches its entry,
        which is reported as blocked.

    Raises:
        UnmatchedPatternError: No manifest records a file matching the pattern.
        NotInRepoError: The sdg package is not running from inside its repo.
        ManifestError: A manifest is missing or cannot be read.
    """
    # Imported here rather than at the top, so the report can still be written when
    # the sdg package itself is broken.
    from sdg.sources.fingerprint_file import compare
    from sdg.sources.read_manifests import manifests

    matched = [
        entry
        for manifest in manifests()
        for entry in manifest.entries
        if fnmatch.fnmatchcase(entry.local, pattern)
    ]
    if not matched:
        raise UnmatchedPatternError(
            f"no manifest records a file matching {pattern}; "
            "correct the @needs_pinned marker"
        )
    for entry in matched:
        if not entry.path.is_file():
            return f"not downloaded: {entry.local}; run acquire_sources"
        if not compare(entry.path, entry).matched:
            return (
                f"blocked: {entry.local} does not match its manifest entry; "
                "see the stability check for that file"
            )
    return None


# Each pattern is looked at once per run, since a pinned file does not change while
# the checks run and measuring it again for every check would only cost time.
_cached_skip_reason = functools.cache(pinned_skip_reason)


def pytest_runtest_setup(item):
    """Skip a check whose pinned files are not downloaded or no longer match.

    pytest calls this before it sets up each check, so the pinned files are looked at
    before any fixture could point the manifest reader somewhere else. A marker naming
    a file no manifest records makes the check's set-up fail instead, which pytest
    reports as an error.

    Args:
        item: The check about to run.
    """
    for marker in item.iter_markers("needs_pinned"):
        for pattern in marker.args:
            # A pattern that matches nothing is not a state of the repo to skip on,
            # so it is turned into a set-up failure with the message kept.
            try:
                reason = _cached_skip_reason(pattern)
            except UnmatchedPatternError as exc:
                pytest.fail(str(exc), pytrace=False)
            if reason:
                pytest.skip(reason)


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
            "code": _code(item),
            "name": item.name,
            "category": _category(item),
            "objective": _objective(item),
            "case": _case(item),
            "expected_result": _first_paragraph(item.obj.__doc__),
            "outcome": outcome,
            "reason": "",
        },
    )
    # A clean-up error replaces an earlier pass. No step ever makes a row
    # better than it was.
    if outcome == "error" or row["outcome"] in ("passed", ""):
        row["outcome"] = outcome
    if outcome == "error":
        row["reason"] = (
            "clean-up failed" if report.when == "teardown" else "set-up failed"
        )
    if outcome == "failed":
        # pytest keeps the one-line message of the failure, usually the
        # assertion, on the report; that is what a reader needs first.
        crash = getattr(report.longrepr, "reprcrash", None)
        row["reason"] = crash.message.splitlines()[0] if crash else "failed"
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


def _code(item) -> str:
    """Read a check's permanent id off its code marker.

    Args:
        item: The check.

    Returns:
        The id, or an empty string when the check carries no code marker.
    """
    marker = item.get_closest_marker("code")
    return str(marker.args[0]) if marker and marker.args else ""


def _category(item) -> str:
    """Read a check's category off its category marker.

    Args:
        item: The check.

    Returns:
        The category, or an empty string when the check carries no category marker.
    """
    marker = item.get_closest_marker("category")
    return str(marker.args[0]) if marker and marker.args else ""


def _objective(item) -> str:
    """Read a check's objective off its objective marker.

    Args:
        item: The check.

    Returns:
        The objective, or an empty string when the check carries no objective marker.
    """
    marker = item.get_closest_marker("objective")
    return str(marker.args[0]) if marker and marker.args else ""


def _case(item) -> str:
    """Read a correctness check's case off its marker.

    Args:
        item: The check.

    Returns:
        positive, negative, or an empty string when it carries neither, as a check of
        any objective other than correctness does, and as a correctness check that
        looked at something real rather than staging a situation does.
    """
    if item.get_closest_marker("positive"):
        return "positive"
    if item.get_closest_marker("negative"):
        return "negative"
    return ""


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


def _git(*args: str) -> str:
    """Run one git command in the repo.

    If git is not installed or the command fails, the result is '(unknown)' instead of
    an error, so a report can still be written.

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

    The report names the exact bytes of the test code and fixtures it ran on, and this
    is how.

    Args:
        path: The file to measure.

    Returns:
        The sha256 as hex.
    """
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _pinned_data_version() -> tuple[str, str]:
    """Say which version of the pinned model file was on the machine at run time.

    The recorded sha256 identifies the version. If the manifest cannot be read, the
    first value says so instead, and the report is still written.

    Returns:
        The recorded sha256, and whether the file was present.
    """
    present = "present" if (REPO_ROOT / PINNED_LOCAL).exists() else "absent"
    # The manifest is read directly here rather than through the sdg package, so a
    # broken package cannot stop the report from being written.
    try:
        entries = json.loads(MANIFEST.read_text(encoding="utf-8")).get("files", [])
        entry = next(e for e in entries if e.get("local") == PINNED_LOCAL)
        return entry.get("sha256", "?"), present
    except (OSError, ValueError, StopIteration):
        return "(manifest entry not readable)", present


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


def pytest_sessionstart(session):
    """Note the moment the run started.

    Args:
        session: The pytest run.
    """
    global _started_at
    _started_at = time.monotonic()


# The columns of a report, in the order they are written: what each check proved
# comes first, then what the run was, then the technical details a reader needs
# only to reproduce a failure. The check columns carry the same names as
# validation/validation_inventory.csv, so a row joins to it by id.
REPORT_COLUMNS = (
    "run_id",
    "run_verdict",
    "id",
    "name",
    "category",
    "objective",
    "staged_case",
    "expected_result",
    "check_outcome",
    "outcome_reason",
    "folder_path",
    "file_name",
    "target_folder_path",
    "target_file_name",
    "pytest_exit_status",
    "exit_meaning",
    "started",
    "commit",
    "run_by",
    "selection",
    "check_file_sha256",
    "fixture_sha256s",
    "pinned_usdm_sha256",
    "pinned_usdm_present",
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
        The paths and node ids typed, and the -k or -m filters given, joined with
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
    return " ".join(kept) or "all"


def _target_of(test_file: Path) -> tuple[str, str]:
    """Name the code file a test file proves.

    The rule is the inventory generator's, repo_tools/build_inventory.py, imported above, so the report's target
    columns and the inventory's agree by construction.

    Args:
        test_file: The test file's path.

    Returns:
        The target's folder and its file name, the name marked when the file was not
        found at run time.
    """
    _, path = type_and_target(test_file, VALIDATION_DIR)
    folder, name = split_path(path)
    # The mirrored file is named even when it is not there, so the gap shows.
    if not (REPO_ROOT / path).exists():
        name = f"{name} (not found at run time)"
    return folder, name


def pytest_sessionfinish(session, exitstatus):
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

    # Everything the report states about the run is gathered once here and
    # written on every row.
    now = dt.datetime.now().astimezone()
    started = now - dt.timedelta(seconds=time.monotonic() - _started_at)
    status = int(exitstatus)
    commit = _git("rev-parse", "--short", "HEAD")
    sha256, present = _pinned_data_version()
    fixtures = (
        sorted(p for p in FIXTURE_DIR.glob("*") if p.is_file())
        if FIXTURE_DIR.exists()
        else []
    )
    run = {
        "run_id": f"{now:%Y-%m-%d}_{commit}",
        "run_verdict": "PASS" if status == 0 else "FAIL",
        "pytest_exit_status": status,
        "exit_meaning": EXIT_MEANING.get(status, "unknown status"),
        "started": f"{started:%Y-%m-%d %H:%M:%S %z}",
        "commit": commit,
        "run_by": _git("config", "user.name"),
        "selection": _selection(session.config),
        "python_version": platform.python_version(),
        "pytest_version": pytest.__version__,
        "platform": platform.platform(),
        "pinned_usdm_sha256": sha256,
        "pinned_usdm_present": present,
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
                f"validation/{file.relative_to(VALIDATION_DIR).as_posix()}"
            )
            target_folder, target_file = _target_of(file)
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
                        "category": outcome["category"],
                        "objective": outcome["objective"],
                        "staged_case": outcome["case"],
                        "expected_result": outcome["expected_result"],
                        "check_outcome": outcome["outcome"],
                        "outcome_reason": outcome["reason"],
                    }
                )
    else:
        # No outcome was collected, so pytest failed before any check ran. One
        # row is written saying so, so a broken run still leaves a report.
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
                "category": "",
                "objective": "",
                "staged_case": "",
                "expected_result": "",
                "check_outcome": "none",
                "outcome_reason": "no check ran: pytest failed before any test ran",
            }
        )

    report_dir = Path(session.config.getoption("--validation-report-dir"))
    report_dir.mkdir(parents=True, exist_ok=True)
    target = _unique(report_dir / f"run_{now:%Y-%m-%d}_{commit}.csv")
    with target.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=REPORT_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    terminal = session.config.pluginmanager.get_plugin("terminalreporter")
    if terminal is not None:
        terminal.write_line(f"validation report written: {target.as_posix()}")
