"""
Script:      conftest.py
Description: Supplies the setups the test_*.py files under validation/ share. pytest
             reads this file automatically before any test file under validation/
             runs, and requires it to be named conftest.py.

             It adds these fixtures for the test files to ask for by name:
               - manifest_dir points the manifest reader,
                 src/sdg/sources/read_manifests.py, at a temporary folder,
               - manifest_recording writes one manifest entry for one file,
               - file_on_disk writes the staged pinned bytes to one file,
               - part_file writes one staged download under its .part name, and
                 placed moves it into place,
               - fake_repo builds a throwaway repo with pyproject.toml, manifests/
                 and inputs/,
               - server installs the fake download server from
                 validation/shared/fake_server.py, and completed runs one download
                 it completes,
               - recorded_file stages one file in the fake repo with a correct
                 entry for it,
               - real_manifests reads every real manifest,
               - staged_suite runs a throwaway suite of checks in a separate pytest
                 process and reads back the report it writes, for the checks of
                 the validation package's own plugins.

             The fixtures stage the data so the real manifests/ and inputs/ are never
             touched.

             It also enables pytest's own pytester helper, which staged_suite is
             built on.

             The machinery that runs the checks is not here. It is the validation
             package, src/sdgval/, which pytest loads through the pytest11 entry
             point in pyproject.toml: the labels, the selection options, the skip
             rules and the report.

Inputs:      manifests/*.json (read-only; real_manifests only). Every other fixture
             writes to pytest's own temporary folder.

Outputs:     Nothing outside pytest's own temporary folder.

Usage:       pytest
                 read on its own before any check under validation/ runs

Exit codes:  None of its own. It runs inside pytest.

Date:        2026-09-04
Owner:       Jason Delosh
"""

from __future__ import annotations

import contextlib
import csv
import hashlib
import json
import subprocess
import textwrap
from pathlib import Path

import pytest

from validation.shared.fake_server import CHUNKS, URL, Completed, FakeResponse
from validation.shared.staged_downloads import CONTENT as DOWNLOADED
from validation.shared.staged_downloads import Staged
from validation.shared.staged_manifests import CONTENT, LOCAL

# pytest has a helper called pytester that lets a test run a small, separate
# test suite of its own. It is switched off unless a file asks for it. The
# staged_suite fixture below is built on it.
pytest_plugins = ["pytester"]


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
# serves the tests of src/sdg/sources/ and of the tools in src/sdgtools/, which need a
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
def file_on_disk(tmp_path):
    """Writes the staged pinned bytes, CONTENT from validation/shared/staged_manifests.py,
    to a file in a temporary folder and gives back its path."""
    path = tmp_path / "file.txt"
    path.write_bytes(CONTENT)
    return path


@pytest.fixture
def part_file(tmp_path) -> Staged:
    """Writes one .part file, holding the bytes of
    validation/shared/staged_downloads.py, with nothing at its final name."""
    from sdg.sources.fetch_file import partial_path

    final = tmp_path / "file.pdf"
    partial = partial_path(final)
    partial.write_bytes(DOWNLOADED)
    return Staged(partial, final)


@pytest.fixture
def placed(part_file) -> tuple[Path, Staged]:
    """Places the staged .part file and gives back what place() handed back,
    with the staging."""
    from sdg.sources.finalize_file import place

    return place(part_file.partial), part_file


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


@pytest.fixture
def server(monkeypatch):
    """Gives a check a function for staging the fake server.

    Calling the function with a FakeResponse serves that response. Calling it
    with an exception makes the connection itself fail, before any response
    arrives. The function replaces httpx.stream for the length of the check and
    gives back a record that is filled in with the method, url and settings
    fetch() used when the call happens."""
    from sdg.sources import fetch_file

    record = {}

    def stage(behavior):
        """Install a fake httpx.stream that behaves as given.

        Args:
            behavior: A FakeResponse to serve, or an error to raise when the connection
                is opened.

        Returns:
            The record of what fetch() asked for, filled in when it runs.
        """

        @contextlib.contextmanager
        def fake_stream(method, url, **settings):
            """Record the request, then fail the connection or yield the staged response."""
            record.update(method=method, url=url, **settings)
            if isinstance(behavior, Exception):
                raise behavior
            yield behavior

        monkeypatch.setattr(fetch_file.httpx, "stream", fake_stream)
        return record

    return stage


@pytest.fixture
def completed(tmp_path, server) -> Completed:
    """Runs one download that the fake server completes, to a destination
    several folders deep that does not exist yet."""
    from sdg.sources.fetch_file import fetch

    request = server(FakeResponse(CHUNKS))
    destination = tmp_path / "inputs" / "standards" / "cdisc" / "file.pdf"
    partial = fetch(URL, destination)
    return Completed(partial, destination, request)


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


@pytest.fixture
def recorded_file(fake_repo):
    """Stages one file in the fake repo, at LOCAL from
    validation/shared/staged_manifests.py, with a correct entry for it, and gives back
    the file's full path."""
    path = fake_repo.file(LOCAL, CONTENT)
    fake_repo.manifest("set_a", [fake_repo.entry(LOCAL)])
    return path


@pytest.fixture
def real_manifests():
    """Reads every real manifest, the hand-written ones and any study manifests, and
    gives them back as a list."""
    from sdg.sources.read_manifests import manifests

    return manifests()


class StagedSuite:
    """A throwaway suite of checks, run in a separate pytest process.

    The suite is laid out like the real repo: its test file sits in a validation/
    folder under the temporary root, because the validation package finds
    validation/ from pytest's root folder. The package's plugins are loaded in the
    separate process through their entry point, as they are for a real run.
    """

    def __init__(self, pytester: pytest.Pytester):
        """Hold the pytester the suite is staged with.

        Args:
            pytester: pytest's helper for running a separate suite.
        """
        self.pytester = pytester
        self.root = pytester.path
        self.validation = pytester.path / "validation"
        self.test_file = self.validation / "test_suite.py"
        self.report_dir = pytester.path / "reports_out"

    def write(self, test_source: str) -> Path:
        """Write the suite's one test file into its validation/ folder.

        Args:
            test_source: The source of the test file.

        Returns:
            The test file's path.
        """
        self.validation.mkdir(exist_ok=True)
        self.test_file.write_text(textwrap.dedent(test_source), encoding="utf-8")
        return self.test_file

    # A report is written only when an aspect's command has left its aspect in
    # pytest's stash. The report writer's own checks run plain pytest, so the suite
    # carries this conftest, which leaves the aspect the way the command does.
    ASPECT_CONFTEST = (
        "from sdgval.report import REPORT_ASPECT\n\n\n"
        "def pytest_configure(config):\n"
        '    config.stash[REPORT_ASPECT] = "technical"\n'
    )

    def run(self, test_source: str, *extra_args: str):
        """Write the suite and run it with a report asked for.

        The suite's root gets a conftest that leaves the technical aspect in pytest's
        stash, standing in for the aspect's command.

        Args:
            test_source: The source of the test file.
            *extra_args: Any further pytest arguments.

        Returns:
            pytest's result and the technical folder inside the report folder, where
            the report is written.
        """
        self.write(test_source)
        (self.root / "conftest.py").write_text(self.ASPECT_CONFTEST, encoding="utf-8")
        result = self.pytester.runpytest_subprocess(
            "--validation-report",
            "--validation-report-dir",
            str(self.report_dir),
            *extra_args,
        )
        return result, self.report_dir / "technical"

    @staticmethod
    def report(folder: Path) -> list[dict[str, str]]:
        """Read the one report a run wrote.

        Args:
            folder: Where the report was written.

        Returns:
            The report's rows, one record per check, each a dict keyed by column name.
        """
        reports = list(folder.glob("*.csv"))
        assert len(reports) == 1, [r.name for r in reports]
        with reports[0].open(encoding="utf-8", newline="") as fh:
            return list(csv.DictReader(fh))

    @staticmethod
    def row(rows: list[dict[str, str]], check_name: str) -> dict[str, str]:
        """Pick the one row for a named check.

        Args:
            rows: The report's rows.
            check_name: The check's function name.

        Returns:
            That check's row.
        """
        matches = [r for r in rows if r["name"] == check_name]
        assert len(matches) == 1, [r["name"] for r in rows]
        return matches[0]

    def commit(self, test_source: str) -> str:
        """Write the suite and commit it as a git repository.

        pytest's own cache, the files pytester writes for itself and Python's
        bytecode folders are ignored in the repository, so only the suite's own files
        count as changes. A notes file is committed too, for a check that needs a
        tracked file it can change without the run writing it back.

        Args:
            test_source: The source of the test file.

        Returns:
            The short hash of the commit.
        """
        self.write(test_source)
        # The conftest run() writes is committed too, so writing it again unchanged
        # does not count as an uncommitted change.
        (self.root / "conftest.py").write_text(self.ASPECT_CONFTEST, encoding="utf-8")
        (self.root / ".gitignore").write_text(
            ".pytest_cache/\n__pycache__/\nrunpytest-*\nstdout\nstderr\n",
            encoding="utf-8",
        )
        (self.root / "notes.txt").write_text("kept\n", encoding="utf-8")
        identity = ["-c", "user.name=Check", "-c", "user.email=check@example.invalid"]
        for args in (["init", "-q"], ["add", "-A"], ["commit", "-q", "-m", "staged"]):
            subprocess.run(
                ["git", *identity, *args],
                cwd=self.root,
                check=True,
                capture_output=True,
            )
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=self.root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()


@pytest.fixture
def staged_suite(pytester) -> StagedSuite:
    """Give a check a throwaway suite to write, run and read the report of.

    Returns:
        The staged suite.
    """
    return StagedSuite(pytester)
