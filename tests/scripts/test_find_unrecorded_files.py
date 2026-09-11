"""
Script:      test_find_unrecorded_files.py
Description: Checks for scripts/find_unrecorded_files.py, the hand-run script
             that lists every file under inputs/ that no manifest records. Each
             check stages one state of a throwaway repo, the fake_repo fixture
             in conftest.py with the script's own folder locations repointed at
             it, runs the script's main() in-process, and asserts the exit code
             or the report line the header promises for that state.

Inputs:      Nothing real. Every file and manifest is written to pytest's own
             temporary folder; inputs/ and manifests/ are never read.

Outputs:     Writes nothing to disk. Temporary files go to pytest's own folder.

Usage:       pytest tests/scripts/test_find_unrecorded_files.py
                 run these checks
             pytest tests/scripts/test_find_unrecorded_files.py -v
                 one line per check with its result

Exit codes:  pytest's own: 0 all passed, 1 some failed

Date:        2026-09-04
Owner:       Jason Delosh
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

import find_unrecorded_files as script

positive = pytest.mark.positive
negative = pytest.mark.negative
# Every check carries a @code line: its short, permanent id in
# tests/validation_inventory.csv, assigned once and never reused.
code = pytest.mark.code

CONTENT = b"pinned bytes\n"
RECORDED = "inputs/set_a/good.txt"


#######################################################################################
### Shared staging ###
#
# One fixture builds the repo every check starts from: a fake repo with one recorded
# file on disk, and the script's own copies of the repo locations pointed at it. The
# other fixtures stage one situation each and run the script, so the checks that look
# at the same situation share one run.


@dataclass(frozen=True)
class Outcome:
    """What one run of the script produced."""

    exit_code: int
    printed: str


@pytest.fixture
def repo(fake_repo, monkeypatch):
    """Give a check the fake repo with one recorded file on disk.

    The script copies the repo root and the pinned folder when it is first loaded,
    so the fake_repo fixture's repointing of the manifest reader does not reach them.
    Both are repointed here for the length of the check.

    Returns:
        The fake repo, with the recorded file and its manifest in place.
    """
    monkeypatch.setattr(script, "REPO_ROOT", fake_repo.root)
    monkeypatch.setattr(script, "PINNED_DIR", fake_repo.root / "inputs")
    fake_repo.file(RECORDED, CONTENT)
    fake_repo.manifest("set_a", [fake_repo.entry(RECORDED)])
    return fake_repo


def run(capsys, *argv: str) -> Outcome:
    """Run the script in-process with the given arguments.

    Args:
        capsys: pytest's capture of what was printed.
        *argv: The command-line arguments to hand the script.

    Returns:
        The exit code and what was printed, as an Outcome.
    """
    exit_code = script.main(list(argv))
    return Outcome(exit_code, capsys.readouterr().out)


@pytest.fixture
def clean(repo, capsys) -> Outcome:
    """Run the script over a repo where every file under inputs/ is recorded."""
    return run(capsys)


@pytest.fixture
def stray(repo, capsys) -> Outcome:
    """Stage one file under inputs/ that no manifest records, and run the script."""
    repo.file("inputs/set_a/stray.txt", b"nobody wrote me down")
    return run(capsys)


@pytest.fixture
def stray_quiet(repo, capsys) -> Outcome:
    """Stage one unrecorded file, and run the script with --quiet."""
    repo.file("inputs/set_a/stray.txt", b"nobody wrote me down")
    return run(capsys, "--quiet")


#######################################################################################
### Positive checks ###
#
# The right thing works: a recorded corpus passes, the project's own files are not
# mistaken for pinned ones, and --quiet leaves the exit code to speak.


@code("HRS0032")
@positive
def test_recorded_files_only_exits_0(clean):
    """When every file under inputs/ is recorded, the run exits 0."""
    assert clean.exit_code == 0


@code("HRS0033")
@positive
def test_recorded_files_only_prints_nothing(clean):
    """When every file under inputs/ is recorded, nothing is printed."""
    assert clean.printed == ""


@code("HRS0021")
@positive
def test_quiet_prints_nothing(stray_quiet):
    """With the quiet option, nothing at all is printed, even when a file is
    unrecorded."""
    assert stray_quiet.printed == ""


@code("HRS0034")
@positive
def test_quiet_keeps_the_exit_code(stray_quiet):
    """With the quiet option, the exit code still reports the unrecorded file."""
    assert stray_quiet.exit_code == 1


@code("HRS0035")
@positive
def test_own_files_are_not_reported(repo, capsys):
    """A README.md and a .gitkeep under inputs/ are the project's own files and are
    not reported as unrecorded."""
    repo.file("inputs/README.md", b"what lives here")
    repo.file("inputs/empty_dir/.gitkeep", b"")
    assert run(capsys).exit_code == 0


@code("HRS0036")
@positive
def test_lock_file_is_not_reported(repo, capsys):
    """An Excel ~$ lock file beside a workbook under inputs/ is not data and is not
    reported as unrecorded."""
    repo.file("inputs/set_a/~$good.xlsx", b"lock")
    assert run(capsys).exit_code == 0


@code("HRS0037")
@positive
def test_missing_inputs_folder_is_clean(fake_repo, monkeypatch, capsys):
    """A repo with no inputs/ folder at all has nothing unrecorded and exits 0, as
    on a fresh clone before anything is downloaded."""
    monkeypatch.setattr(script, "REPO_ROOT", fake_repo.root)
    monkeypatch.setattr(script, "PINNED_DIR", fake_repo.root / "inputs")
    fake_repo.manifest(
        "set_a", [fake_repo.entry(RECORDED, bytes=len(CONTENT), sha256="0" * 64)]
    )
    assert run(capsys).exit_code == 0


#######################################################################################
### Negative checks ###
#
# The wrong thing is refused, and the message names the cause: an unrecorded file,
# an unfinished download, a manifest that cannot be read, no manifests at all, and a
# package not running from its repo.


@code("HRS0038")
@negative
def test_unrecorded_file_exits_1(stray):
    """A file under inputs/ that no manifest records makes the run exit 1."""
    assert stray.exit_code == 1


@code("HRS0039")
@negative
def test_unrecorded_file_is_listed_by_path(stray):
    """An unrecorded file is printed by its repo-relative path."""
    assert "inputs/set_a/stray.txt" in stray.printed


@code("HRS0040")
@negative
def test_unrecorded_file_summary_says_it_cannot_be_restored(stray):
    """The summary counts the unrecorded files and says they cannot be restored from
    a clone."""
    assert "1 file(s) no manifest records" in stray.printed
    assert "cannot be restored" in stray.printed


@code("HRS0041")
@negative
def test_part_file_is_reported(repo, capsys):
    """An unfinished .part download under inputs/ is reported as unrecorded, since
    the acquire workflow did not get to finish it."""
    repo.file("inputs/set_a/other.txt.part", b"half")
    outcome = run(capsys)
    assert outcome.exit_code == 1
    assert "inputs/set_a/other.txt.part" in outcome.printed


@code("HRS0028")
@negative
def test_unreadable_manifest_exits_3(repo, capsys):
    """A manifest that is not valid JSON makes the run exit 3, and the message names
    the file and says it cannot be read."""
    repo.manifest("broken", "{not json")
    outcome = run(capsys)
    assert outcome.exit_code == 3
    assert "broken.json: cannot read" in outcome.printed


@code("HRS0029")
@negative
def test_no_manifests_exits_3(repo, capsys):
    """An empty manifests folder makes the run exit 3, and the message says no
    manifests were found and how to restore them."""
    (repo.root / "manifests" / "set_a.json").unlink()
    outcome = run(capsys)
    assert outcome.exit_code == 3
    assert "no manifests found" in outcome.printed
    assert "git checkout" in outcome.printed


@code("HRS0030")
@negative
def test_not_inside_the_repo_exits_6(repo, monkeypatch, tmp_path, capsys):
    """When the package is not running from inside its repo, the run exits 6 with
    the install command, instead of reporting that no manifests were found."""
    from sdg.sources import read_manifests

    monkeypatch.setattr(read_manifests, "REPO_ROOT", tmp_path / "elsewhere")
    outcome = run(capsys)
    assert outcome.exit_code == 6
    assert "pip install -e ." in outcome.printed
    assert "no manifests found" not in outcome.printed
