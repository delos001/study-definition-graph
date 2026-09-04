"""
Script:      test_verify_manifests.py
Description: Automated checks for scripts/verify_manifests.py, the hand-run
             check that every pinned file matches its manifest and that nothing
             sits under data/raw/ unrecorded. Each check stages one state of the
             corpus in a throwaway repo (the fake_repo fixture in conftest.py),
             runs the script's main() in-process, and asserts the exit code and
             the report line the header promises for that state.

Inputs:      Nothing real. Every file and manifest is written to pytest's own
             temporary folder; data/ is never read.

Outputs:     Writes nothing to disk. Temporary files go to pytest's own folder.

Usage:       pytest tests/test_verify_manifests.py
                 run these checks
             pytest tests/test_verify_manifests.py -v
                 one line per check with its result

Exit codes:  pytest's own: 0 all passed, 1 some failed

Date:        2026-09-04
Owner:       Jason Delosh
"""

from __future__ import annotations

import pytest

import verify_manifests as vm

positive = pytest.mark.positive
negative = pytest.mark.negative

CONTENT = b"pinned bytes\n"


#######################################################################################
### Helpers ###


@pytest.fixture
def repo(fake_repo, monkeypatch):
    """Produces the fake repo with the script's own copies of the three
    locations (bound at import time) repointed at it, and one good pinned file
    already recorded, so each check stages only its own difference."""
    monkeypatch.setattr(vm, "REPO_ROOT", fake_repo.root)
    monkeypatch.setattr(vm, "MANIFEST_DIR", fake_repo.root / "data" / "manifests")
    monkeypatch.setattr(vm, "RAW_DIR", fake_repo.root / "data" / "raw")
    fake_repo.raw("data/raw/set_a/good.txt", CONTENT)
    fake_repo.manifest("raw_set_a", [fake_repo.entry("data/raw/set_a/good.txt")])
    return fake_repo


#######################################################################################
### A clean corpus ###


@positive
def test_clean_corpus_exits_0(repo, capsys):
    """Every recorded file present and matching, nothing unrecorded: exit 0 and
    a summary saying so."""
    assert vm.main([]) == 0
    out = capsys.readouterr().out
    assert "OK    raw_set_a.json" in out
    assert "1 file(s) verified, 0 problem(s), 0 unrecorded." in out


@positive
def test_verbose_lists_passing_files(repo, capsys):
    """--verbose adds one 'ok' line per file that passed."""
    assert vm.main(["--verbose"]) == 0
    assert "ok        data/raw/set_a/good.txt" in capsys.readouterr().out


@positive
def test_quiet_prints_nothing(repo, capsys):
    """--quiet prints nothing at all; the exit code is the whole report."""
    assert vm.main(["--quiet"]) == 0
    assert capsys.readouterr().out == ""


@positive
def test_placeholder_and_lock_files_are_not_unrecorded(repo):
    """A .gitkeep placeholder and an Excel ~$ lock file under data/raw/ are
    editor and git artifacts, not data, and are not reported as unrecorded."""
    repo.raw("data/raw/empty_dir/.gitkeep", b"")
    repo.raw("data/raw/set_a/~$good.xlsx", b"lock")
    assert vm.main([]) == 0


#######################################################################################
### Problems, one exit code each ###


@negative
def test_missing_file_exits_1(repo, capsys):
    """A recorded file that is not on disk is reported MISSING with its path,
    exit 1."""
    (repo.root / "data/raw/set_a/good.txt").unlink()
    assert vm.main([]) == 1
    out = capsys.readouterr().out
    assert "FAIL  raw_set_a.json" in out
    assert "MISSING   data/raw/set_a/good.txt" in out


@negative
def test_changed_content_exits_1(repo, capsys):
    """A file whose bytes changed but whose size did not is reported as a
    sha256 MISMATCH showing both fingerprints, exit 1."""
    repo.raw("data/raw/set_a/good.txt", b"PINNED bytes\n")  # same length
    assert vm.main([]) == 1
    out = capsys.readouterr().out
    assert "MISMATCH  data/raw/set_a/good.txt: sha256" in out
    assert "manifest says" in out


@negative
def test_unrecorded_file_exits_2(repo, capsys):
    """A file under data/raw/ that no manifest records is listed by path with
    the reminder that it cannot be restored from a clone, exit 2."""
    repo.raw("data/raw/set_a/stray.txt", b"nobody wrote me down")
    assert vm.main([]) == 2
    out = capsys.readouterr().out
    assert "Present under data/raw/ but not in any manifest:" in out
    assert "    data/raw/set_a/stray.txt" in out
    assert "cannot be restored" in out


@negative
def test_mismatch_outranks_unrecorded(repo):
    """With both a corrupted pin and an unrecorded file, the exit code is 1:
    a corrupted pin is the worse problem."""
    repo.raw("data/raw/set_a/good.txt", b"changed")
    repo.raw("data/raw/set_a/stray.txt", b"stray")
    assert vm.main([]) == 1


@negative
def test_malformed_entry_is_a_problem(repo, capsys):
    """A manifest entry with no sha256 verifies nothing and is reported as
    MALFORMED rather than skipped, exit 1."""
    repo.manifest("raw_set_a", [repo.entry("data/raw/set_a/good.txt", sha256=None)])
    assert vm.main([]) == 1
    assert "MALFORMED" in capsys.readouterr().out


@negative
def test_unreadable_manifest_exits_3(repo, capsys):
    """A manifest that is not valid JSON is reported MANIFEST UNREADABLE and
    the run exits 3, even though every other manifest was still checked."""
    repo.manifest("raw_broken", "{not json")
    assert vm.main([]) == 3
    out = capsys.readouterr().out
    assert "MANIFEST UNREADABLE  raw_broken.json" in out
    assert "OK    raw_set_a.json" in out


@negative
def test_no_manifests_exits_3(repo, capsys):
    """An empty manifests folder exits 3 and names the folder it looked in."""
    (repo.root / "data/manifests/raw_set_a.json").unlink()
    assert vm.main([]) == 3
    assert "No manifests found in" in capsys.readouterr().out


@negative
def test_not_inside_the_repo_exits_6(repo, monkeypatch, tmp_path, capsys):
    """When the package is not running from inside its repo, the run exits 6
    with the install command instead of reporting 'no manifests found'."""
    from sdg import pinned as pinned_mod

    monkeypatch.setattr(pinned_mod, "REPO_ROOT", tmp_path / "elsewhere")
    assert vm.main([]) == 6
    assert "pip install -e ." in capsys.readouterr().out


#######################################################################################
### Narrowing to one set ###


@positive
def test_set_checks_one_manifest_and_skips_the_unrecorded_scan(repo, capsys):
    """--set checks only the named manifest and does not run the unrecorded
    scan, since every other set's files would otherwise be reported as
    unrecorded. Accepts the stem with or without .json."""
    repo.raw("data/raw/set_b/other.txt", b"other")
    repo.manifest("raw_set_b", [repo.entry("data/raw/set_b/other.txt")])
    repo.raw("data/raw/set_a/stray.txt", b"stray")
    assert vm.main(["--set", "raw_set_a"]) == 0
    out = capsys.readouterr().out
    assert "raw_set_b" not in out
    assert "1 file(s) verified, 0 problem(s), 0 unrecorded." in out
    assert vm.main(["--set", "raw_set_a.json"]) == 0
