"""
Script:      test_acquire_sources.py
Description: Automated checks for src/sdg/sources/acquire_sources.py, the
             workflow that fetches every recorded file not yet on disk and
             confirms every file already on disk still matches its entry. Each
             check stages one state of a small corpus in a pretend repo, runs
             the workflow's main() in-process with an argument list, and
             compares the exit code and the report lines to what the header
             promises.

             No check touches the network. The workflow's one download step,
             fetch, is replaced for each check by a fake that writes the bytes
             the check chose under the .part name, or raises FetchError, per
             url. A check that must not download installs a fake that fails the
             check if it is called.

Inputs:      none from the repo

Outputs:     Writes nothing to disk. Temporary files go to pytest's own folder.

Usage:       pytest tests/sources/test_acquire_sources.py
                 run these checks
             pytest tests/sources/test_acquire_sources.py -v
                 one line per check with its result

Exit codes:  pytest's own: 0 all passed, 1 some failed

Date:        2026-09-04
Owner:       Jason Delosh
"""

from __future__ import annotations

import hashlib

import pytest

from sdg.sources import acquire_sources
from sdg.sources.fetch_file import FetchError, partial_path

positive = pytest.mark.positive
negative = pytest.mark.negative

# The one staged file most checks use, its bytes, and the url its entry carries.
# The url is the one FakeRepo.entry builds for a file of that name.
LOCAL = "inputs/set_a/file.txt"
CONTENT = b"pinned bytes\n"
URL = "https://example.invalid/file.txt"


#######################################################################################
### Shared helpers ###
#
# One helper builds an entry for a file that is not on disk yet; the other runs
# the workflow.


def recorded(repo, local: str, content: bytes) -> dict:
    """Builds a manifest entry for a file that may not be on disk yet, with the
    size and sha256 the given bytes would have."""
    return repo.entry(
        local, bytes=len(content), sha256=hashlib.sha256(content).hexdigest()
    )


def run(*argv: str) -> int:
    """Runs the workflow in-process with the given arguments and gives back its
    exit code."""
    return acquire_sources.main(list(argv))


#######################################################################################
### The fake network ###
#
# The workflow downloads through one function, fetch, which it imported by name.
# Replacing that name on the workflow's module is enough to keep every check off
# the network.


@pytest.fixture
def network(monkeypatch):
    """Gives a check a function for staging the fake download step.

    Called with a dict of url to bytes, it replaces the workflow's fetch with a
    fake that writes those bytes under the .part name for a url in the dict,
    and raises FetchError for any other url, the way a dead address would.
    Called with nothing, it installs a fake that fails the check if any
    download is attempted."""

    def stage(served: dict[str, bytes] | None = None) -> None:
        """Installs the fake download step, serving the given bytes per url."""

        def fake_fetch(url, destination):
            """Writes the staged bytes under the .part name, or raises the way
            the real step would for a url it cannot reach."""
            if served is None:
                raise AssertionError(f"the network was used for {url}")
            if url not in served:
                raise FetchError(f"{url}\n  cause -> no such host")
            partial = partial_path(destination)
            partial.parent.mkdir(parents=True, exist_ok=True)
            partial.write_bytes(served[url])
            return partial

        monkeypatch.setattr(acquire_sources, "fetch", fake_fetch)

    return stage


#######################################################################################
### Positive checks ###
#
# A corpus in good order is completed or confirmed, and each command-line option
# does what the header says.


@positive
def test_missing_file_is_downloaded_verified_and_placed(fake_repo, network, capsys):
    """A recorded file not on disk is fetched, hash-checked and placed under its
    final name, with no .part file left and exit 0."""
    fake_repo.manifest("set_a", [recorded(fake_repo, LOCAL, CONTENT)])
    network({URL: CONTENT})

    assert run() == 0

    final = fake_repo.root / LOCAL
    assert final.read_bytes() == CONTENT
    assert not partial_path(final).exists()
    out = capsys.readouterr().out
    assert "fetching" in out
    assert "1 fetched, 0 present and matching" in out


@positive
def test_present_and_matching_file_is_not_fetched(fake_repo, network, capsys):
    """A file already on disk that matches its entry is counted as present, and
    the network is not touched."""
    fake_repo.file(LOCAL, CONTENT)
    fake_repo.manifest("set_a", [fake_repo.entry(LOCAL)])
    network(None)

    assert run() == 0
    assert "0 fetched, 1 present and matching" in capsys.readouterr().out


@positive
def test_dry_run_lists_what_it_would_fetch_and_writes_nothing(fake_repo, network, capsys):
    """--dry-run names each missing file as would fetch, touches neither the
    network nor the disk, and exits 1 because the corpus is incomplete."""
    fake_repo.manifest("set_a", [recorded(fake_repo, LOCAL, CONTENT)])
    network(None)

    assert run("--dry-run") == 1

    final = fake_repo.root / LOCAL
    assert not final.exists()
    assert not partial_path(final).exists()
    out = capsys.readouterr().out
    assert "would fetch  file.txt" in out
    assert "1 to fetch, 0 present and matching" in out


@positive
def test_dry_run_on_a_complete_corpus_exits_0(fake_repo, network, capsys):
    """--dry-run on a corpus with every file present and matching exits 0, so
    --dry-run --quiet answers whether the corpus is complete from the exit code
    alone."""
    fake_repo.file(LOCAL, CONTENT)
    fake_repo.manifest("set_a", [fake_repo.entry(LOCAL)])
    network(None)

    assert run("--dry-run", "--quiet") == 0
    assert capsys.readouterr().out == ""


@positive
def test_quiet_prints_nothing(fake_repo, network, capsys):
    """--quiet prints nothing at all, even when a file is fetched."""
    fake_repo.manifest("set_a", [recorded(fake_repo, LOCAL, CONTENT)])
    network({URL: CONTENT})

    assert run("--quiet") == 0
    assert capsys.readouterr().out == ""


@positive
def test_set_narrows_to_one_manifest(fake_repo, network, capsys):
    """--set names one manifest, and only that manifest's files are fetched or
    checked; the other manifest is not read."""
    fake_repo.manifest("set_a", [recorded(fake_repo, "inputs/set_a/a.txt", CONTENT)])
    # The other manifest is unreadable. If the workflow read it, the run would
    # stop with exit 3 instead of finishing set_a.
    fake_repo.manifest("set_b", "{ not json")
    network({"https://example.invalid/a.txt": CONTENT})

    assert run("--set", "set_a") == 0

    assert (fake_repo.root / "inputs/set_a/a.txt").exists()
    assert "set_b" not in capsys.readouterr().out


#######################################################################################
### Negative checks ###
#
# Each check stages one bad state of the corpus. Two things are asserted: the
# exit code the header gives that state, and the report line that names it. A
# file already on disk is never touched, whatever is wrong with it.


@negative
def test_present_but_changed_file_is_left_alone_exits_2(fake_repo, network, capsys):
    """A file on disk that no longer matches its entry is reported as a MISMATCH
    and is neither replaced nor deleted, exit 2."""
    # These bytes have the same length as CONTENT, so only the sha256 differs.
    changed = b"PINNED bytes\n"
    fake_repo.file(LOCAL, changed)
    fake_repo.manifest(
        "set_a", [fake_repo.entry(LOCAL, sha256=hashlib.sha256(CONTENT).hexdigest())]
    )
    network(None)

    assert run() == 2

    assert (fake_repo.root / LOCAL).read_bytes() == changed
    out = capsys.readouterr().out
    assert f"MISMATCH  {LOCAL}: sha256" in out
    assert "left alone" in out
    assert "disagree with their entry" in out


@negative
def test_download_with_wrong_hash_is_discarded_exits_1(fake_repo, network, capsys):
    """A download whose bytes do not match the entry is discarded, never appears
    under the final name, leaves no .part file, and exits 1."""
    fake_repo.manifest("set_a", [recorded(fake_repo, LOCAL, CONTENT)])
    network({URL: b"something else entirely\n"})

    assert run() == 1

    final = fake_repo.root / LOCAL
    assert not final.exists()
    assert not partial_path(final).exists()
    out = capsys.readouterr().out
    assert "DISCARDED" in out
    assert "1 fetch(es) failed" in out


@negative
def test_network_failure_is_reported_exits_1(fake_repo, network, capsys):
    """A url that cannot be fetched is reported as FAILED with the cause, and
    the run exits 1.

    That no .part file is left is the fetch step's promise, proven in
    test_fetch_file.py."""
    fake_repo.manifest("set_a", [recorded(fake_repo, LOCAL, CONTENT)])
    network({})

    assert run() == 1

    out = capsys.readouterr().out
    assert "FAILED" in out
    assert "no such host" in out


@negative
def test_failure_outranks_disagreement(fake_repo, network, capsys):
    """With one file changed on disk and another that cannot be fetched, both
    are reported and the exit code is 1, because a missing file is worse than a
    changed one."""
    # These bytes have the same length as CONTENT, so only the sha256 differs.
    changed = b"PINNED bytes\n"
    fake_repo.file("inputs/set_a/a.txt", changed)
    fake_repo.manifest(
        "set_a",
        [
            fake_repo.entry(
                "inputs/set_a/a.txt", sha256=hashlib.sha256(CONTENT).hexdigest()
            ),
            recorded(fake_repo, "inputs/set_a/b.txt", CONTENT),
        ],
    )
    network({})

    assert run() == 1

    out = capsys.readouterr().out
    assert "MISMATCH" in out
    assert "FAILED" in out


@negative
def test_dry_run_missing_file_outranks_disagreement(fake_repo, network, capsys):
    """In a dry run too, a file that would need fetching outranks a changed
    file: both are reported and the exit code is 1, not 2."""
    # These bytes have the same length as CONTENT, so only the sha256 differs.
    changed = b"PINNED bytes\n"
    fake_repo.file("inputs/set_a/a.txt", changed)
    fake_repo.manifest(
        "set_a",
        [
            fake_repo.entry(
                "inputs/set_a/a.txt", sha256=hashlib.sha256(CONTENT).hexdigest()
            ),
            recorded(fake_repo, "inputs/set_a/b.txt", CONTENT),
        ],
    )
    network(None)

    assert run("--dry-run") == 1

    out = capsys.readouterr().out
    assert "MISMATCH" in out
    assert "would fetch  b.txt" in out


@negative
def test_locked_file_at_a_recorded_path_is_reported_exits_2(fake_repo, network, capsys, monkeypatch):
    """A recorded file that is on disk but cannot be opened, as a workbook Excel
    has locked, is reported as CANNOT READ with the cause and left alone, exit
    2, rather than ending the run with a traceback."""
    fake_repo.file(LOCAL, CONTENT)
    fake_repo.manifest("set_a", [fake_repo.entry(LOCAL)])
    network(None)

    # The workflow compares through one function it imported by name. Making
    # that function fail the way the operating system does for a locked file
    # stages the lock without needing another program to hold the file.
    def locked(_path, _entry):
        """Fails the way opening a locked file fails."""
        raise PermissionError("locked by another program")

    monkeypatch.setattr(acquire_sources, "compare", locked)

    assert run() == 2

    out = capsys.readouterr().out
    assert "CANNOT READ" in out
    assert "locked by another program" in out
    assert "left alone" in out


@negative
def test_folder_at_a_recorded_path_is_reported_exits_2(fake_repo, network, capsys):
    """A folder where a recorded file should be is reported as CANNOT READ and
    left alone, exit 2, rather than ending the run with a traceback."""
    (fake_repo.root / LOCAL).mkdir(parents=True)
    fake_repo.manifest("set_a", [recorded(fake_repo, LOCAL, CONTENT)])
    network(None)

    assert run() == 2

    out = capsys.readouterr().out
    assert "CANNOT READ" in out
    assert "a folder, not a file" in out


@negative
def test_entry_missing_a_field_stops_the_run_exits_3(fake_repo, network, capsys):
    """An entry lacking a required field is a manifest problem: the run stops
    with exit 3 and the message names the field."""
    fake_repo.file(LOCAL, CONTENT)
    fake_repo.manifest("set_a", [fake_repo.entry(LOCAL, url=None)])
    network(None)

    assert run() == 3
    assert "lacks url" in capsys.readouterr().out


@negative
def test_unreadable_manifest_exits_3(fake_repo, network, capsys):
    """A manifest that is not valid JSON stops the run with exit 3 and names the
    file."""
    fake_repo.manifest("set_a", "{ not json")
    network(None)

    assert run() == 3
    assert "set_a.json: cannot read" in capsys.readouterr().out


@negative
def test_set_with_no_match_exits_3(fake_repo, network, capsys):
    """--set naming a manifest that does not exist exits 3 and names it."""
    fake_repo.manifest("set_a", [])
    network(None)

    assert run("--set", "set_b") == 3
    assert "no manifest named set_b" in capsys.readouterr().out


@negative
def test_not_inside_the_repo_exits_6(fake_repo, network, capsys):
    """A package not running from inside its repo exits 6 with the install
    command, before any manifest is read."""
    (fake_repo.root / "pyproject.toml").write_text(
        "[project]\nname = 'other'\n", encoding="utf-8"
    )
    # The one manifest is unreadable. If the workflow read manifests before
    # checking the repo, this check would see exit 3 instead.
    fake_repo.manifest("set_a", "{ not json")
    network(None)

    assert run() == 6
    assert "pip install -e ." in capsys.readouterr().out
