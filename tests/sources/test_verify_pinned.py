"""
Script:      test_verify_pinned.py
Description: Automated checks for src/sdg/sources/verify_pinned.py, the workflow
             that proves a pinned file is the recorded one and hands it back
             with its identity. Each check stages one situation, calls
             verify_pinned(), and compares what happened to what the module's
             header promises: the file and its identity on success, and on
             failure an error that names that cause and its remedy, not another.
             The situations staged include:
               - a good entry,
               - a wrong fingerprint or a wrong size,
               - a manifest that will not read, or none at all,
               - an entry missing a field,
               - a file that no entry records,
               - a recorded file that is not on disk,
               - a package not running from inside its repo.

             Staged checks build a pretend repo in a temporary folder through
             the fake_repo fixture in conftest.py, so the real manifests/ and
             inputs/ are never written. The checks against the real pinned USDM
             model file skip when it has not been downloaded.

Inputs:      manifests/cdisc_usdm_v4.json                         (read-only)
             inputs/standards/cdisc/usdm_v4/dataStructure.yml    (read-only;
                                                                  skips if absent)

Outputs:     Writes nothing to disk. Temporary files go to pytest's own folder.

Usage:       pytest tests/sources/test_verify_pinned.py
                 run these checks
             pytest tests/sources/test_verify_pinned.py -v
                 one line per check with its result

Exit codes:  pytest's own: 0 all passed, 1 some failed

Date:        2026-09-04
Owner:       Jason Delosh
"""

from __future__ import annotations

import hashlib
import json

import pytest

from sdg.sources import IntegrityError, NotInRepoError, PinnedFile, read_manifests, verify_pinned

positive = pytest.mark.positive
negative = pytest.mark.negative

# The real pinned model file and the manifest that records it. The checks against
# them skip when the file is not downloaded, so a fresh clone still runs the rest.
PINNED_LOCAL = "inputs/standards/cdisc/usdm_v4/dataStructure.yml"
MANIFEST_NAME = "cdisc_usdm_v4.json"

needs_pinned_file = pytest.mark.skipif(
    not (read_manifests.REPO_ROOT / PINNED_LOCAL).exists(),
    reason="pinned dataStructure.yml not downloaded; run python -m sdg.sources.acquire_sources",
)

# The one staged file every staged check uses, and its bytes.
LOCAL = "inputs/set_a/file.txt"
CONTENT = b"pinned bytes\n"


#######################################################################################
### Shared helpers ###
#
# One helper stages the file and its entry that most checks start from.


def staged(repo, content: bytes = CONTENT, **overrides):
    """Puts one file into the fake repo with one manifest entry for it, correct
    unless a field is overridden, and gives back the file's full path."""
    path = repo.file(LOCAL, content)
    repo.manifest("set_a", [repo.entry(LOCAL, **overrides)])
    return path


#######################################################################################
### Positive checks against the real pinned model file ###
#
# The real model file verifies against its real manifest and comes back with the
# identity the manifest records. These checks skip when the file is not
# downloaded.


@needs_pinned_file
@positive
def test_real_pinned_file_comes_back_with_its_identity():
    """The pinned USDM model file verifies and comes back with the sha256 and
    url its manifest records, the manifest's name, its path on this machine,
    and readable content."""
    manifest = json.loads(
        (read_manifests.MANIFEST_DIR / MANIFEST_NAME).read_text(encoding="utf-8")
    )
    entry = next(e for e in manifest["files"] if e["local"] == PINNED_LOCAL)

    got = verify_pinned(PINNED_LOCAL)

    assert isinstance(got, PinnedFile)
    assert got.local == PINNED_LOCAL
    assert got.sha256 == entry["sha256"]
    assert got.url == entry["url"]
    assert got.manifest == MANIFEST_NAME
    assert got.path == read_manifests.REPO_ROOT / PINNED_LOCAL
    assert got.read_text().startswith("Abbreviation:")


@needs_pinned_file
@positive
def test_string_and_path_name_the_same_file():
    """The repo-relative string a manifest writes, the same string with
    backslashes, and a full Path all give the same record."""
    by_string = verify_pinned(PINNED_LOCAL)
    assert by_string == verify_pinned(PINNED_LOCAL.replace("/", "\\"))
    assert by_string == verify_pinned(read_manifests.REPO_ROOT / PINNED_LOCAL)


#######################################################################################
### Positive checks against a staged repo ###
#
# A recorded file that matches its entry comes back with its identity and reads.


@positive
def test_recorded_file_verifies_and_reads(fake_repo):
    """A file whose entry carries the right size and sha256 comes back as a
    PinnedFile with its path, sha256, url and manifest, and its content reads."""
    path = staged(fake_repo)

    got = verify_pinned(LOCAL)

    assert got.local == LOCAL
    assert got.path == path
    assert got.sha256 == hashlib.sha256(CONTENT).hexdigest()
    assert got.url == "https://example.invalid/file.txt"
    assert got.manifest == "set_a.json"
    assert got.read_text() == CONTENT.decode()


@positive
def test_staged_string_and_path_give_the_same_record(fake_repo):
    """In the staged repo too, a repo-relative string and a full Path to the
    same file give the same record."""
    path = staged(fake_repo)
    assert verify_pinned(LOCAL) == verify_pinned(path)


#######################################################################################
### Negative checks ###
#
# A file that cannot be proven is refused. Each cause has its own message and
# remedy, and each check asserts the message names that cause and not another,
# because a wrong remedy would send a person to re-download a file that is fine
# or to edit a manifest that is not the problem.


@negative
def test_not_inside_the_repo_is_passed_through(fake_repo):
    """A package not running from inside its repo is refused with NotInRepoError
    and the install command, not wrapped as an integrity problem."""
    staged(fake_repo)
    (fake_repo.root / "pyproject.toml").write_text(
        "[project]\nname = 'other'\n", encoding="utf-8"
    )

    with pytest.raises(NotInRepoError, match=r"pip install -e \."):
        verify_pinned(LOCAL)


@negative
def test_recorded_but_not_downloaded_raises_file_not_found(fake_repo):
    """A file that a manifest records but that is not on disk raises
    FileNotFoundError naming the path, which is a different failure from a
    file that cannot be verified."""
    fake_repo.manifest(
        "set_a",
        [
            fake_repo.entry(
                LOCAL, bytes=len(CONTENT), sha256=hashlib.sha256(CONTENT).hexdigest()
            )
        ],
    )

    with pytest.raises(FileNotFoundError) as caught:
        verify_pinned(LOCAL)
    assert str(fake_repo.root / LOCAL) in str(caught.value)


@negative
def test_unrecorded_file_says_no_entry_records_it(fake_repo):
    """A file that no manifest records is refused saying so, with the remedy of
    adding an entry, and without the mismatch remedy, which would be wrong."""
    staged(fake_repo)
    fake_repo.file("inputs/set_a/stray.txt", CONTENT)

    with pytest.raises(IntegrityError) as caught:
        verify_pinned("inputs/set_a/stray.txt")

    message = str(caught.value)
    assert "no manifest entry records it" in message
    assert "add its manifest entry" in message
    assert "manifest says" not in message
    assert "acquire_sources" not in message


@negative
def test_unreadable_manifest_is_a_manifest_problem(fake_repo):
    """A manifest that cannot be read is reported as that, naming the manifest
    file and the restore remedy, not as a problem with the pinned file."""
    fake_repo.file(LOCAL, CONTENT)
    fake_repo.manifest("set_a", "{ not json")

    with pytest.raises(IntegrityError) as caught:
        verify_pinned(LOCAL)

    message = str(caught.value)
    assert message.startswith(f"cannot verify {LOCAL}: set_a.json: cannot read")
    assert "git checkout" in message
    assert "manifest says" not in message


@negative
def test_no_manifests_at_all_says_so(fake_repo):
    """An empty manifests folder is reported as no manifests found, with the
    git restore remedy."""
    fake_repo.file(LOCAL, CONTENT)

    with pytest.raises(IntegrityError) as caught:
        verify_pinned(LOCAL)
    message = str(caught.value)
    assert "no manifests found" in message
    assert "git checkout" in message


@negative
def test_malformed_entry_names_the_missing_field(fake_repo):
    """An entry with no sha256 is reported as lacking that field, with the
    repair remedy, so a person repairs the entry rather than re-downloading the
    file."""
    staged(fake_repo, sha256=None)

    with pytest.raises(IntegrityError) as caught:
        verify_pinned(LOCAL)
    message = str(caught.value)
    assert "lacks sha256" in message
    assert "repair that entry" in message


@negative
def test_fingerprint_mismatch_shows_both_values_and_the_recovery_paths(fake_repo):
    """A file whose bytes differ from its entry at the same size is refused
    showing the start of both sha256 values, the manifest that records it, and
    the three ways back: re-fetch, read unverified once, or re-pin."""
    # These bytes have the same length as CONTENT, so only the sha256 differs.
    changed = b"PINNED bytes\n"
    fake_repo.file(LOCAL, changed)
    fake_repo.manifest(
        "set_a",
        [fake_repo.entry(LOCAL, sha256=hashlib.sha256(CONTENT).hexdigest())],
    )

    with pytest.raises(IntegrityError) as caught:
        verify_pinned(LOCAL)

    message = str(caught.value)
    assert message.startswith(f"{LOCAL}: sha256 {hashlib.sha256(changed).hexdigest()[:16]}")
    assert f"manifest says {hashlib.sha256(CONTENT).hexdigest()[:16]}" in message
    assert "(recorded in set_a.json)" in message
    assert "acquire_sources" in message
    assert "--allow-unpinned" in message
    assert "re-pin" in message


@negative
def test_size_mismatch_is_reported_as_size(fake_repo):
    """A file whose size differs from its entry is refused as a size difference
    showing both numbers, which points at a truncated or replaced download."""
    staged(fake_repo, bytes=len(CONTENT) + 3)

    with pytest.raises(IntegrityError) as caught:
        verify_pinned(LOCAL)

    assert f"size {len(CONTENT)} bytes, manifest says {len(CONTENT) + 3}" in str(caught.value)
