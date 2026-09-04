"""
Script:      test_fetch_sources.py
Description: Automated checks for scripts/fetch_sources.py, the hand-run
             downloader that fetches every pinned file its manifests name and
             puts each in place only after its sha256 matches. Each check stages
             one state (a file missing, present, present but changed, a
             download that arrives wrong, a dead url) in a throwaway repo, runs
             main() in-process against a fake network, and asserts the exit
             code, the report line, and what is or is not left on disk.

             The network is faked by replacing httpx.stream with a function
             that serves bytes, or raises, per url. No check touches the real
             network, and a check that must not download at all installs a
             fake that fails the test if called.

Inputs:      Nothing real. Every file and manifest is written to pytest's own
             temporary folder; data/ is never read and no url is ever fetched.

Outputs:     Writes nothing to disk. Temporary files go to pytest's own folder.

Usage:       pytest tests/test_fetch_sources.py
                 run these checks
             pytest tests/test_fetch_sources.py -v
                 one line per check with its result

Exit codes:  pytest's own: 0 all passed, 1 some failed

Date:        2026-09-04
Owner:       Jason Delosh
"""

from __future__ import annotations

import contextlib
import hashlib

import httpx
import pytest

import fetch_sources as fs

positive = pytest.mark.positive
negative = pytest.mark.negative

CONTENT = b"the pinned bytes\n"
SHA = hashlib.sha256(CONTENT).hexdigest()
LOCAL = "data/raw/set_a/file.txt"
URL = "https://example.invalid/file.txt"


#######################################################################################
### Helpers ###


@pytest.fixture
def repo(fake_repo, monkeypatch):
    """Produces the fake repo with the script's own copy of the repo root
    (bound at import time) repointed at it, and one manifest recording LOCAL
    at URL with the correct sha256 and size, but the file itself not yet on
    disk: the fresh-clone state."""
    monkeypatch.setattr(fs, "REPO_ROOT", fake_repo.root)
    fake_repo.manifest(
        "raw_set_a",
        [fake_repo.entry(LOCAL, url=URL, sha256=SHA, bytes=len(CONTENT))],
    )
    return fake_repo


@pytest.fixture
def network(monkeypatch):
    """Produces a function that takes {url: bytes or Exception} and installs a
    fake httpx.stream serving exactly that: bytes are streamed in two chunks,
    an Exception is raised, and any url not listed fails the test, so a check
    that expects no download proves it."""

    def install(responses: dict):
        @contextlib.contextmanager
        def stream(method, url, **kwargs):
            assert url in responses, f"unexpected download of {url}"
            body = responses[url]
            if isinstance(body, Exception):
                raise body

            class Response:
                def raise_for_status(self):
                    pass

                def iter_bytes(self):
                    yield body[:4]
                    yield body[4:]

            yield Response()

        monkeypatch.setattr(fs.httpx, "stream", stream)

    return install


def no_partials(root) -> bool:
    """Takes the fake repo root and reports whether no .part file was left
    anywhere under it."""
    return not list(root.rglob("*.part"))


#######################################################################################
### Fetching ###


@positive
def test_missing_file_is_downloaded_verified_and_placed(repo, network, capsys):
    """A recorded file not on disk is downloaded, its sha256 checked, and only
    then renamed into place; exit 0, no .part left behind."""
    network({URL: CONTENT})
    assert fs.main([]) == 0
    assert (repo.root / LOCAL).read_bytes() == CONTENT
    assert no_partials(repo.root)
    out = capsys.readouterr().out
    assert "fetching     file.txt" in out
    assert "1 downloaded, 0 already present and matching" in out


@positive
def test_present_and_matching_file_is_not_fetched(repo, network, capsys):
    """A file already on disk that matches its manifest is counted as present
    and the network is never touched; exit 0."""
    repo.raw(LOCAL, CONTENT)
    network({})  # any download would fail the test
    assert fs.main([]) == 0
    assert "0 downloaded, 1 already present and matching" in capsys.readouterr().out


@positive
def test_dry_run_lists_and_writes_nothing(repo, network, capsys):
    """--dry-run says what it would fetch, touches no network, writes no file;
    exit 0."""
    network({})
    assert fs.main(["--dry-run"]) == 0
    assert not (repo.root / LOCAL).exists()
    out = capsys.readouterr().out
    assert "would fetch  file.txt" in out
    assert "1 to fetch, 0 already present and matching" in out


@positive
def test_quiet_prints_nothing(repo, network, capsys):
    """--quiet prints nothing; the exit code is the whole report."""
    network({URL: CONTENT})
    assert fs.main(["--quiet"]) == 0
    assert capsys.readouterr().out == ""


#######################################################################################
### Refusing, one exit code each ###


@negative
def test_present_but_changed_file_is_left_alone_exits_2(repo, network, capsys):
    """A file on disk whose sha256 disagrees with its manifest is reported and
    not touched (data/raw/ is immutable; a human decides), exit 2."""
    repo.raw(LOCAL, b"something else")
    network({})
    assert fs.main([]) == 2
    assert (repo.root / LOCAL).read_bytes() == b"something else"
    out = capsys.readouterr().out
    assert "on disk but does not match its manifest, left alone" in out
    assert "Delete deliberately, then re-run." in out


@negative
def test_download_with_wrong_hash_is_discarded_exits_1(repo, network, capsys):
    """A download whose bytes do not match the recorded sha256 never reaches
    its final name: reported as HASH MISMATCH, discarded, exit 1."""
    network({URL: b"not the pinned bytes"})
    assert fs.main([]) == 1
    assert not (repo.root / LOCAL).exists()
    assert no_partials(repo.root)
    assert "HASH MISMATCH" in capsys.readouterr().out


@negative
def test_network_failure_is_reported_exits_1(repo, network, capsys):
    """A url that cannot be fetched is reported FAILED, leaves no .part file,
    and the run exits 1."""
    network({URL: httpx.HTTPError("connection refused")})
    assert fs.main([]) == 1
    assert not (repo.root / LOCAL).exists()
    assert no_partials(repo.root)
    assert "FAILED  connection refused" in capsys.readouterr().out


@negative
def test_failure_outranks_disagreement(repo, network):
    """With one download failing and another file disagreeing on disk, the exit
    code is 1: an incomplete corpus is worse than a known-but-wrong file."""
    repo.raw("data/raw/set_a/changed.txt", b"changed")
    repo.manifest(
        "raw_set_a",
        [
            repo.entry(LOCAL, url=URL, sha256=SHA, bytes=len(CONTENT)),
            repo.entry("data/raw/set_a/changed.txt", sha256="0" * 64),
        ],
    )
    network({URL: httpx.HTTPError("down")})
    assert fs.main([]) == 1


@negative
def test_entry_missing_a_field_counts_as_disagreement(repo, network, capsys):
    """A manifest entry with no url cannot be acted on and is reported as a
    defect in the manifest, exit 2, rather than skipped silently."""
    repo.manifest("raw_set_a", [repo.entry(LOCAL, sha256=SHA, url=None)])
    network({})
    assert fs.main([]) == 2
    assert "manifest entry has no local, url or sha256" in capsys.readouterr().out


@negative
def test_unreadable_manifest_exits_3(repo, network, capsys):
    """A manifest that is not valid JSON stops the run with exit 3, since
    every file location downstream of it is unknown."""
    repo.manifest("raw_broken", "{not json")
    network({})
    assert fs.main([]) == 3
    assert "manifest error: raw_broken.json" in capsys.readouterr().out


@negative
def test_set_with_no_match_exits_3(repo, network, capsys):
    """--set naming a manifest that does not exist exits 3 and says so."""
    network({})
    assert fs.main(["--set", "raw_nothing"]) == 3
    assert "no manifests found matching --set raw_nothing" in capsys.readouterr().out


@negative
def test_not_inside_the_repo_exits_6(repo, network, monkeypatch, tmp_path, capsys):
    """When the package is not running from inside its repo, the run exits 6
    with the install command instead of reporting 'no manifests found'."""
    from sdg import pinned as pinned_mod

    monkeypatch.setattr(pinned_mod, "REPO_ROOT", tmp_path / "elsewhere")
    network({})
    assert fs.main([]) == 6
    assert "pip install -e ." in capsys.readouterr().out
