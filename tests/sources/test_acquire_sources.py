"""
Script:      test_acquire_sources.py
Description: Automated checks for src/sdg/sources/acquire_sources.py, the
             workflow that fetches every recorded file not yet on disk and
             confirms every file already on disk still matches its entry. Each
             check proves one promise from that module's header: one effect on
             disk, one report line, or one exit code for one state of the
             corpus.

             Each situation is staged once, in a fixture, by putting a small
             corpus in a pretend repo and running the workflow's main()
             in-process with an argument list. The checks that share a
             situation each look at one thing the run left behind.

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
from dataclasses import dataclass

import pytest

from sdg.sources import acquire_sources
from sdg.sources.fetch_file import FetchError, partial_path

positive = pytest.mark.positive
negative = pytest.mark.negative

# The one staged file most checks use, its bytes, and the url its entry carries.
# The url is the one FakeRepo.entry builds for a file of that name.
LOCAL = "inputs/set_a/file.txt"
CONTENT = b"pinned bytes\n"
SHA256 = hashlib.sha256(CONTENT).hexdigest()
URL = "https://example.invalid/file.txt"

# These bytes have the same length as CONTENT, so a file holding them differs
# from its entry only in its sha256.
CHANGED = b"PINNED bytes\n"


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
### Shared staging ###
#
# Two helpers build entries and run the workflow. Each fixture stages one state
# of the corpus, runs the workflow once, and gives back the exit code and the
# report so several checks can each look at one thing.


@dataclass(frozen=True)
class Outcome:
    """What one run of the workflow produced."""

    code: int  # the exit code main() gave back
    out: str  # everything the run printed


def recorded(repo, local: str, content: bytes) -> dict:
    """Builds a manifest entry for a file that may not be on disk yet, with the
    size and sha256 the given bytes would have."""
    return repo.entry(local, bytes=len(content), sha256=hashlib.sha256(content).hexdigest())


def run(capsys, *argv: str) -> Outcome:
    """Runs the workflow in-process with the given arguments and gives back the
    exit code and what it printed."""
    code = acquire_sources.main(list(argv))
    return Outcome(code, capsys.readouterr().out)


@pytest.fixture
def fetched(fake_repo, network, capsys) -> Outcome:
    """Stages one recorded file that is not on disk, serves it, and runs the
    workflow."""
    fake_repo.manifest("set_a", [recorded(fake_repo, LOCAL, CONTENT)])
    network({URL: CONTENT})
    return run(capsys)


@pytest.fixture
def present(fake_repo, network, capsys) -> Outcome:
    """Stages one recorded file that is on disk and matches, with no network,
    and runs the workflow."""
    fake_repo.file(LOCAL, CONTENT)
    fake_repo.manifest("set_a", [fake_repo.entry(LOCAL)])
    network(None)
    return run(capsys)


@pytest.fixture
def dry_run_missing(fake_repo, network, capsys) -> Outcome:
    """Stages one recorded file that is not on disk, with no network, and runs
    the workflow with --dry-run."""
    fake_repo.manifest("set_a", [recorded(fake_repo, LOCAL, CONTENT)])
    network(None)
    return run(capsys, "--dry-run")


@pytest.fixture
def changed(fake_repo, network, capsys) -> Outcome:
    """Stages one recorded file on disk whose bytes no longer match its entry,
    with no network, and runs the workflow."""
    fake_repo.file(LOCAL, CHANGED)
    fake_repo.manifest("set_a", [fake_repo.entry(LOCAL, sha256=SHA256)])
    network(None)
    return run(capsys)


@pytest.fixture
def wrong_hash(fake_repo, network, capsys) -> Outcome:
    """Stages one recorded file that is not on disk, serves the wrong bytes for
    it, and runs the workflow."""
    fake_repo.manifest("set_a", [recorded(fake_repo, LOCAL, CONTENT)])
    network({URL: b"something else entirely\n"})
    return run(capsys)


@pytest.fixture
def failed_fetch(fake_repo, network, capsys) -> Outcome:
    """Stages one recorded file that is not on disk, with a network that cannot
    reach its url, and runs the workflow."""
    fake_repo.manifest("set_a", [recorded(fake_repo, LOCAL, CONTENT)])
    network({})
    return run(capsys)


@pytest.fixture
def locked(fake_repo, network, capsys, monkeypatch) -> Outcome:
    """Stages one recorded file on disk that cannot be opened, as a workbook
    Excel has locked, and runs the workflow."""
    fake_repo.file(LOCAL, CONTENT)
    fake_repo.manifest("set_a", [fake_repo.entry(LOCAL)])
    network(None)

    # The workflow compares through one function it imported by name. Making
    # that function fail the way the operating system does for a locked file
    # stages the lock without needing another program to hold the file.
    def refuse(_path, _entry):
        """Fails the way opening a locked file fails."""
        raise PermissionError("locked by another program")

    monkeypatch.setattr(acquire_sources, "compare", refuse)
    return run(capsys)


@pytest.fixture
def folder(fake_repo, network, capsys) -> Outcome:
    """Stages a folder where a recorded file should be, with no network, and
    runs the workflow."""
    (fake_repo.root / LOCAL).mkdir(parents=True)
    fake_repo.manifest("set_a", [recorded(fake_repo, LOCAL, CONTENT)])
    network(None)
    return run(capsys)


#######################################################################################
### Positive checks ###
#
# A corpus in good order is completed or confirmed, and each command-line option
# does what the header says.


@positive
def test_missing_file_is_fetched_and_placed(fetched, fake_repo):
    """A recorded file not on disk ends up under its final name with the bytes
    the server sent, and the run exits 0."""
    assert fetched.code == 0
    assert (fake_repo.root / LOCAL).read_bytes() == CONTENT


@positive
def test_fetched_file_leaves_no_part_file(fetched, fake_repo):
    """After a file is fetched and placed, nothing is left under its .part
    name."""
    assert not partial_path(fake_repo.root / LOCAL).exists()


@positive
def test_fetch_is_reported(fetched):
    """The report names the file as fetching and counts it as fetched."""
    assert "fetching" in fetched.out
    assert "1 fetched, 0 present and matching" in fetched.out


@positive
def test_present_matching_file_is_not_fetched(present):
    """A file already on disk that matches its entry is not downloaded, and
    the run exits 0."""
    assert present.code == 0


@positive
def test_present_matching_file_is_counted_as_present(present):
    """The report counts a matching file as present and fetches nothing."""
    assert "0 fetched, 1 present and matching" in present.out


@positive
def test_dry_run_names_each_file_it_would_fetch(dry_run_missing):
    """--dry-run names each missing file as one it would fetch, and counts
    them."""
    assert "would fetch  file.txt" in dry_run_missing.out
    assert "1 to fetch, 0 present and matching" in dry_run_missing.out


@positive
def test_dry_run_touches_neither_network_nor_disk(dry_run_missing, fake_repo):
    """--dry-run downloads nothing and writes nothing."""
    final = fake_repo.root / LOCAL
    assert not final.exists()
    assert not partial_path(final).exists()


@positive
def test_dry_run_exits_1_when_a_file_is_missing(dry_run_missing):
    """--dry-run exits 1 when at least one file would need fetching, because
    the corpus is incomplete."""
    assert dry_run_missing.code == 1


@positive
def test_dry_run_exits_0_when_the_corpus_is_complete(fake_repo, network, capsys):
    """--dry-run exits 0 when every file is present and matching, so
    --dry-run --quiet answers whether the corpus is complete from the exit code
    alone."""
    fake_repo.file(LOCAL, CONTENT)
    fake_repo.manifest("set_a", [fake_repo.entry(LOCAL)])
    network(None)
    assert run(capsys, "--dry-run", "--quiet").code == 0


@positive
def test_quiet_prints_nothing(fake_repo, network, capsys):
    """--quiet prints nothing at all, even when a file is fetched."""
    fake_repo.manifest("set_a", [recorded(fake_repo, LOCAL, CONTENT)])
    network({URL: CONTENT})
    assert run(capsys, "--quiet").out == ""


@positive
def test_set_fetches_only_that_manifests_files(fake_repo, network, capsys):
    """--set names one manifest, and only that manifest's files are fetched."""
    fake_repo.manifest("set_a", [recorded(fake_repo, "inputs/set_a/a.txt", CONTENT)])
    fake_repo.manifest("set_b", [recorded(fake_repo, "inputs/set_b/b.txt", CONTENT)])
    network({"https://example.invalid/a.txt": CONTENT})
    assert run(capsys, "--set", "set_a").code == 0
    assert (fake_repo.root / "inputs/set_a/a.txt").exists()
    assert not (fake_repo.root / "inputs/set_b/b.txt").exists()


@positive
def test_set_does_not_read_the_other_manifests(fake_repo, network, capsys):
    """With --set, a manifest that was not named is not even read: an
    unreadable one does not stop the run."""
    fake_repo.manifest("set_a", [recorded(fake_repo, "inputs/set_a/a.txt", CONTENT)])
    fake_repo.manifest("set_b", "{ not json")
    network({"https://example.invalid/a.txt": CONTENT})
    outcome = run(capsys, "--set", "set_a")
    assert outcome.code == 0
    assert "set_b" not in outcome.out


#######################################################################################
### Negative checks ###
#
# Each situation stages one bad state of the corpus. The checks that share it
# each assert one thing: the report line that names the state, what was left
# alone on disk, or the exit code the header gives that state.


@negative
def test_changed_file_is_reported_as_a_mismatch(changed):
    """A file on disk that no longer matches its entry is reported as a
    MISMATCH on its sha256 and as left alone."""
    assert f"MISMATCH  {LOCAL}: sha256" in changed.out
    assert "left alone" in changed.out


@negative
def test_changed_file_is_left_alone(changed, fake_repo):
    """A changed file is neither replaced nor deleted; its bytes are as they
    were."""
    assert (fake_repo.root / LOCAL).read_bytes() == CHANGED


@negative
def test_changed_file_exits_2(changed):
    """A changed file on disk makes the run exit 2, and the summary says a
    person has to look."""
    assert changed.code == 2
    assert "disagree with their entry" in changed.out


@negative
def test_wrong_hash_download_is_discarded(wrong_hash, fake_repo):
    """A download whose bytes do not match the entry is reported as DISCARDED
    and appears under neither the final name nor the .part name."""
    final = fake_repo.root / LOCAL
    assert "DISCARDED" in wrong_hash.out
    assert not final.exists()
    assert not partial_path(final).exists()


@negative
def test_wrong_hash_download_exits_1(wrong_hash):
    """A discarded download makes the run exit 1 and is counted as a failed
    fetch."""
    assert wrong_hash.code == 1
    assert "1 fetch(es) failed" in wrong_hash.out


@negative
def test_failed_fetch_is_reported_with_its_cause(failed_fetch):
    """A url that cannot be fetched is reported as FAILED with the cause."""
    assert "FAILED" in failed_fetch.out
    assert "no such host" in failed_fetch.out


@negative
def test_failed_fetch_exits_1(failed_fetch):
    """A failed fetch makes the run exit 1."""
    assert failed_fetch.code == 1


@negative
def test_failure_outranks_disagreement(fake_repo, network, capsys):
    """With one file changed on disk and another that cannot be fetched, both
    are reported and the exit code is 1, because a missing file is worse than
    a changed one."""
    fake_repo.file("inputs/set_a/a.txt", CHANGED)
    fake_repo.manifest(
        "set_a",
        [
            fake_repo.entry("inputs/set_a/a.txt", sha256=SHA256),
            recorded(fake_repo, "inputs/set_a/b.txt", CONTENT),
        ],
    )
    network({})
    outcome = run(capsys)
    assert outcome.code == 1
    assert "MISMATCH" in outcome.out
    assert "FAILED" in outcome.out


@negative
def test_dry_run_missing_file_outranks_disagreement(fake_repo, network, capsys):
    """In a dry run too, a file that would need fetching outranks a changed
    file: both are reported and the exit code is 1, not 2."""
    fake_repo.file("inputs/set_a/a.txt", CHANGED)
    fake_repo.manifest(
        "set_a",
        [
            fake_repo.entry("inputs/set_a/a.txt", sha256=SHA256),
            recorded(fake_repo, "inputs/set_a/b.txt", CONTENT),
        ],
    )
    network(None)
    outcome = run(capsys, "--dry-run")
    assert outcome.code == 1
    assert "MISMATCH" in outcome.out
    assert "would fetch  b.txt" in outcome.out


@negative
def test_locked_file_is_reported_as_cannot_read_with_the_cause(locked):
    """A recorded file that cannot be opened is reported as CANNOT READ with
    the cause and as left alone, rather than ending the run with a
    traceback."""
    assert "CANNOT READ" in locked.out
    assert "locked by another program" in locked.out
    assert "left alone" in locked.out


@negative
def test_locked_file_exits_2(locked):
    """A recorded file that cannot be opened makes the run exit 2."""
    assert locked.code == 2


@negative
def test_folder_at_a_recorded_path_is_reported_as_cannot_read(folder):
    """A folder where a recorded file should be is reported as CANNOT READ, a
    folder not a file, and as left alone."""
    assert "CANNOT READ" in folder.out
    assert "a folder, not a file" in folder.out
    assert "left alone" in folder.out


@negative
def test_folder_at_a_recorded_path_exits_2(folder):
    """A folder where a recorded file should be makes the run exit 2."""
    assert folder.code == 2


@negative
def test_entry_missing_a_field_exits_3_naming_the_field(fake_repo, network, capsys):
    """An entry lacking a required field stops the run with exit 3, and the
    message names the field."""
    fake_repo.file(LOCAL, CONTENT)
    fake_repo.manifest("set_a", [fake_repo.entry(LOCAL, url=None)])
    network(None)
    outcome = run(capsys)
    assert outcome.code == 3
    assert "lacks url" in outcome.out


@negative
def test_unreadable_manifest_exits_3_naming_the_file(fake_repo, network, capsys):
    """A manifest that is not valid JSON stops the run with exit 3, and the
    message names the file."""
    fake_repo.manifest("set_a", "{ not json")
    network(None)
    outcome = run(capsys)
    assert outcome.code == 3
    assert "set_a.json: cannot read" in outcome.out


@negative
def test_unknown_set_exits_3_naming_it(fake_repo, network, capsys):
    """--set naming a manifest that does not exist exits 3, and the message
    names it."""
    fake_repo.manifest("set_a", [])
    network(None)
    outcome = run(capsys, "--set", "set_b")
    assert outcome.code == 3
    assert "no manifest named set_b" in outcome.out


@negative
def test_not_in_repo_exits_6_with_the_install_command(fake_repo, network, capsys):
    """A package not running from inside its repo exits 6, and the message
    gives the install command."""
    (fake_repo.root / "pyproject.toml").write_text(
        "[project]\nname = 'other'\n", encoding="utf-8"
    )
    fake_repo.manifest("set_a", [])
    network(None)
    outcome = run(capsys)
    assert outcome.code == 6
    assert "pip install -e ." in outcome.out


@negative
def test_repo_check_runs_before_any_manifest_is_read(fake_repo, network, capsys):
    """With a wrong package name and an unreadable manifest, the run exits 6
    and not 3, which shows the repo check came first."""
    (fake_repo.root / "pyproject.toml").write_text(
        "[project]\nname = 'other'\n", encoding="utf-8"
    )
    fake_repo.manifest("set_a", "{ not json")
    network(None)
    assert run(capsys).code == 6
