"""
Script:      test_pinned.py
Description: Automated checks for src/sdg/pinned.py, the one way to obtain a
             pinned file verified against its manifest. Each check stages one
             situation (a good entry, a wrong fingerprint, a manifest that will
             not parse, a package installed the wrong way), calls pinned(), and
             compares what happened to what the module's documentation
             promises: the file and its identity on success, and on failure a
             message that names that cause and not another.

             Manifests for the failure cases are written to a temporary folder
             and the module is pointed at it for the duration of the check, so
             the real data/manifests/ is never touched. The file being checked
             is tests/fixtures/usdm_three_classes.yml, which no real manifest
             records; the one check against the real pinned USDM file skips
             when data/ is not downloaded.

Inputs:      tests/fixtures/usdm_three_classes.yml         (read-only)
             data/manifests/raw_usdm_v4.json                (read-only)
             data/raw/usdm_v4/uml/dataStructure.yml         (read-only; one
                                                             check, skips if absent)

Outputs:     Writes nothing to disk. Temporary files go to pytest's own folder.

Usage:       pytest tests/test_pinned.py
                 run these checks
             pytest tests/test_pinned.py -v
                 one line per check with its result

Exit codes:  pytest's own: 0 all passed, 1 some failed

Date:        2026-09-04
Owner:       Jason Delosh
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sdg import pinned as pinned_mod
from sdg.pinned import IntegrityError, NotInRepoError, PinnedFile, pinned

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "usdm_three_classes.yml"
FIXTURE_LOCAL = "tests/fixtures/usdm_three_classes.yml"
PINNED_LOCAL = "data/raw/usdm_v4/uml/dataStructure.yml"

needs_pinned_file = pytest.mark.skipif(
    not (pinned_mod.REPO_ROOT / PINNED_LOCAL).exists(),
    reason="pinned dataStructure.yml not downloaded; run scripts/fetch_sources.py",
)

positive = pytest.mark.positive
negative = pytest.mark.negative


#######################################################################################
### Obtaining a pinned file ###


@positive
def test_running_from_inside_the_repo():
    """require_repo() accepts this checkout: the folder the package takes to be
    the repo holds pyproject.toml and data/manifests/."""
    assert pinned_mod.require_repo() == pinned_mod.REPO_ROOT
    assert (pinned_mod.REPO_ROOT / "pyproject.toml").exists()


@needs_pinned_file
@positive
def test_real_pinned_file_comes_back_with_its_identity():
    """The pinned USDM model file verifies and comes back with the fingerprint
    and url its manifest records, and its content is readable."""
    manifest = json.loads(
        (pinned_mod.MANIFEST_DIR / "raw_usdm_v4.json").read_text(encoding="utf-8")
    )
    entry = next(e for e in manifest["files"] if e["local"] == PINNED_LOCAL)

    got = pinned(PINNED_LOCAL)
    assert isinstance(got, PinnedFile)
    assert got.sha256 == entry["sha256"]
    assert got.url == entry["url"]
    assert got.manifest == "raw_usdm_v4.json"
    assert got.path == pinned_mod.REPO_ROOT / PINNED_LOCAL
    assert got.read_text().startswith("Abbreviation:")


@needs_pinned_file
@positive
def test_string_and_path_name_the_same_file():
    """pinned() accepts the repo-relative string a manifest writes or a full
    Path to the same file, and produces the same record for both."""
    assert pinned(PINNED_LOCAL) == pinned(pinned_mod.REPO_ROOT / PINNED_LOCAL)


@positive
def test_recorded_fixture_verifies(manifest_dir, manifest_recording):
    """A file whose manifest entry carries the right size and fingerprint comes
    back as a PinnedFile whose content reads correctly."""
    manifest_dir(manifest_recording(FIXTURE, sha256=pinned_mod.sha256_of(FIXTURE)))
    got = pinned(FIXTURE)
    assert got.local == FIXTURE_LOCAL
    assert got.sha256 == pinned_mod.sha256_of(FIXTURE)
    assert "Condition:" in got.read_text()


#######################################################################################
### Refusing, one message per cause ###
#
# Each check stages exactly one way the verification can fail and asserts the
# message names that cause, with its remedy, and not another cause's remedy.


@negative
def test_not_inside_the_repo_names_the_install_fix(monkeypatch, tmp_path):
    """When the package is not running from inside its repo (the folder it takes
    to be the repo has no pyproject.toml), pinned() refuses with a message that
    says where the package was found and gives the install command."""
    monkeypatch.setattr(pinned_mod, "REPO_ROOT", tmp_path)
    with pytest.raises(NotInRepoError) as caught:
        pinned(FIXTURE_LOCAL)
    message = str(caught.value)
    assert "not running from inside its repo" in message
    assert "pip install -e ." in message


@negative
def test_recorded_but_not_downloaded_raises_filenotfound(manifest_dir, manifest_recording):
    """A file that a manifest records but that is not on disk raises
    FileNotFoundError, the same failure a missing download gives everywhere."""
    manifest_dir(manifest_recording(FIXTURE, local="tests/fixtures/not_downloaded.yml"))
    with pytest.raises(FileNotFoundError):
        pinned("tests/fixtures/not_downloaded.yml")


@negative
def test_unrecorded_file_says_no_entry_records_it():
    """A file no manifest entry records (this fixture, against the real
    manifests) is refused with a message saying exactly that, not with the
    fingerprint-mismatch remedy."""
    with pytest.raises(IntegrityError) as caught:
        pinned(FIXTURE)
    message = str(caught.value)
    assert "no manifest entry records it" in message
    assert "manifest says" not in message and "fetch_sources" not in message


@negative
def test_unreadable_manifest_says_unreadable(manifest_dir):
    """A manifest that is not valid JSON is reported as unreadable, with the
    remedy pointing at the manifests folder, not at re-downloading the file."""
    manifest_dir("{not json")
    with pytest.raises(IntegrityError) as caught:
        pinned(FIXTURE)
    message = str(caught.value)
    assert "a manifest is unreadable" in message and "git checkout" in message
    assert "fetch_sources" not in message


@negative
def test_no_manifests_at_all_says_so(manifest_dir):
    """An empty manifests folder is reported as 'no manifests found', with the
    same restore remedy."""
    manifest_dir(None)
    with pytest.raises(IntegrityError, match="no manifests found"):
        pinned(FIXTURE)


@negative
def test_entry_without_sha256_says_malformed(manifest_dir, manifest_recording):
    """A manifest entry for the file that carries no sha256 is reported as
    malformed, with the remedy pointing at that entry."""
    manifest_dir(manifest_recording(FIXTURE, sha256=None))
    with pytest.raises(IntegrityError, match="manifest entry is malformed"):
        pinned(FIXTURE)


@negative
def test_fingerprint_mismatch_shows_both_values_and_recovery(manifest_dir, manifest_recording):
    """A recorded sha256 that differs from the file's is reported with both
    values, the manifest that records it, and the three recovery paths."""
    manifest_dir(manifest_recording(FIXTURE))  # sha256 is the all-zero placeholder
    with pytest.raises(IntegrityError) as caught:
        pinned(FIXTURE)
    message = str(caught.value)
    assert "sha256" in message and "manifest says 0000" in message
    assert "(recorded in raw_usdm_v4.json)" in message
    assert "--allow-unpinned" in message and "fetch_sources" in message


@negative
def test_size_mismatch_is_reported_as_size(manifest_dir, manifest_recording):
    """A recorded byte count that differs from the file's is reported as a size
    difference (checked before the hash, since it usually means a truncated
    download), with the same recovery paths."""
    manifest_dir(manifest_recording(FIXTURE, bytes=1))
    with pytest.raises(IntegrityError, match="size .* bytes, manifest says 1"):
        pinned(FIXTURE)
