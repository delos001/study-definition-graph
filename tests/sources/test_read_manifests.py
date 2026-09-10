"""
Script:      test_read_manifests.py
Description: Automated checks for src/sdg/sources/read_manifests.py, the step that
             reads the manifests and hands back what they say. Each check stages
             one situation, calls the reader, and compares what happened to what
             the module's header promises: the manifests and their entries on
             success, and on failure an error that names that cause and not
             another.

             Most checks stage a small pretend repo in a temporary folder through
             the fake_repo fixture in conftest.py, so the real manifests/ is never
             written. Two checks read the real manifests/ as they are; they need
             no download, because they read the records and not the files the
             records point at.

Inputs:      manifests/*.json   (read-only; two checks)

Outputs:     Writes nothing to disk. Temporary files go to pytest's own folder.

Usage:       pytest tests/sources/test_read_manifests.py
                 run these checks
             pytest tests/sources/test_read_manifests.py -v
                 one line per check with its result

Exit codes:  pytest's own: 0 all passed, 1 some failed

Date:        2026-09-10
Owner:       Jason Delosh
"""

from __future__ import annotations

import shutil

import pytest

from sdg.sources import read_manifests
from sdg.sources.read_manifests import (
    Entry,
    ManifestError,
    NotInRepoError,
    as_local,
    entry_for,
    manifests,
    require_repo,
)

positive = pytest.mark.positive
negative = pytest.mark.negative

# The six manifests written by hand, one per pinned set. A study-document fetch,
# not yet written, will add study manifests later, so the real-repo checks look
# for these six and do not assume they are the only ones.
HAND_WRITTEN = {
    "cdisc_biomedical_concepts",
    "cdisc_usdm_v4",
    "crosswalks",
    "ich_e9r1",
    "ich_m11_step4",
    "usdm_examples",
}

# The bytes every staged file holds. What the file says does not matter to the
# reader; only that an entry can be built for it.
CONTENT = b"pinned bytes\n"


#######################################################################################
### Positive checks against the real repo ###
#
# These checks read the real manifests/ folder as it is. They need no download,
# because they read the records and not the files the records point at.


@positive
def test_running_from_inside_the_repo():
    """require_repo() accepts this checkout and gives back its root, the folder
    that holds pyproject.toml."""
    root = require_repo()
    assert root == read_manifests.REPO_ROOT
    assert (root / "pyproject.toml").is_file()


@positive
def test_every_hand_written_manifest_reads():
    """manifests() reads the six hand-written manifests, each with its name, a
    landing folder under inputs/, and entries that carry all five required
    fields and remember which manifest they came from."""
    found = {manifest.name: manifest for manifest in manifests()}
    assert HAND_WRITTEN <= set(found)
    for name in HAND_WRITTEN:
        manifest = found[name]
        assert manifest.local_dir.startswith("inputs/")
        assert manifest.entries
        for entry in manifest.entries:
            assert entry.name and entry.url
            assert entry.local.startswith("inputs/")
            assert entry.bytes > 0
            assert len(entry.sha256) == 64
            assert entry.manifest == f"{name}.json"


#######################################################################################
### Positive checks against a staged repo ###
#
# Reading manifests and finding entries works, against a pretend repo in a
# temporary folder.


@positive
def test_study_manifests_read_alongside(fake_repo):
    """A manifest under manifests/study_documents/ is read in the same call as
    the top-level ones, and is listed after them."""
    fake_repo.file("inputs/set_a/a.txt", CONTENT)
    fake_repo.file("inputs/study_documents/NCT1/protocol.pdf", CONTENT)
    fake_repo.manifest("set_a", [fake_repo.entry("inputs/set_a/a.txt")])
    fake_repo.manifest(
        "NCT1",
        [fake_repo.entry("inputs/study_documents/NCT1/protocol.pdf")],
        study=True,
    )
    assert [manifest.name for manifest in manifests()] == ["set_a", "NCT1"]


@positive
def test_listing_order_is_by_path_and_stable(fake_repo):
    """Manifests come back sorted by path, whatever order they were written in,
    and two calls give the same order."""
    for name in ("zeta", "alpha", "mid"):
        fake_repo.file(f"inputs/{name}/f.txt", CONTENT)
        fake_repo.manifest(name, [fake_repo.entry(f"inputs/{name}/f.txt")])
    first = [manifest.name for manifest in manifests()]
    assert first == ["alpha", "mid", "zeta"]
    assert [manifest.name for manifest in manifests()] == first


@positive
def test_one_manifest_by_name_with_or_without_suffix(fake_repo):
    """Asking for one manifest by name gives only that one, whether the name is
    given with or without its .json suffix."""
    for name in ("set_a", "set_b"):
        fake_repo.file(f"inputs/{name}/f.txt", CONTENT)
        fake_repo.manifest(name, [fake_repo.entry(f"inputs/{name}/f.txt")])
    assert [manifest.name for manifest in manifests("set_a")] == ["set_a"]
    assert [manifest.name for manifest in manifests("set_a.json")] == ["set_a"]


@positive
def test_entry_for_finds_a_recorded_file_by_string_or_path(fake_repo):
    """entry_for() gives the same entry for a repo-relative string, the same
    string with backslashes, and a full Path, and the entry's path is the
    file's full path on this machine."""
    path = fake_repo.file("inputs/set_a/a.txt", CONTENT)
    fake_repo.manifest("set_a", [fake_repo.entry("inputs/set_a/a.txt")])

    found = entry_for("inputs/set_a/a.txt")
    assert isinstance(found, Entry)
    assert found == entry_for("inputs\\set_a\\a.txt")
    assert found == entry_for(path)
    assert found.path == path
    assert found.bytes == len(CONTENT)
    assert found.manifest == "set_a.json"


@positive
def test_entry_for_gives_none_for_an_unrecorded_file(fake_repo):
    """A file that no manifest records gives None, not an error."""
    fake_repo.file("inputs/set_a/a.txt", CONTENT)
    fake_repo.manifest("set_a", [fake_repo.entry("inputs/set_a/a.txt")])
    fake_repo.file("inputs/set_a/stray.txt", CONTENT)
    assert entry_for("inputs/set_a/stray.txt") is None


@positive
def test_as_local_gives_an_outside_path_back_unchanged(fake_repo, tmp_path):
    """A path outside the repo comes back from as_local() as its full path,
    unchanged, so a message about it can show where it is."""
    outside = tmp_path / "elsewhere" / "file.txt"
    assert as_local(outside) == str(outside.resolve())


#######################################################################################
### Negative checks ###
#
# Bad input is refused with the right error and message. Every refusal is
# checked for two things:
#   - the right error type,
#   - a message that names this cause and its remedy rather than another.
# A wrong remedy would send a person to fix the wrong thing.


@negative
def test_not_inside_the_repo_names_the_install_fix(fake_repo):
    """A pyproject.toml that does not name the sdg package is refused as not
    running from inside the repo, with the pip install -e . remedy, before any
    manifest is looked for."""
    (fake_repo.root / "pyproject.toml").write_text(
        "[project]\nname = 'other'\n", encoding="utf-8"
    )
    # The one manifest is unreadable. If the reader looked at manifests before
    # checking the repo, this check would see a ManifestError instead.
    fake_repo.manifest("set_a", "{ not json")
    with pytest.raises(NotInRepoError) as caught:
        manifests()
    assert "pip install -e ." in str(caught.value)


@negative
def test_no_manifests_folder_names_the_restore_remedy(fake_repo):
    """A missing manifests/ folder is reported by name, with the git restore
    remedy."""
    shutil.rmtree(fake_repo.root / "manifests")
    with pytest.raises(ManifestError) as caught:
        manifests()
    message = str(caught.value)
    assert "no manifests folder" in message
    assert "git checkout" in message


@negative
def test_empty_manifests_folder_says_none_found(fake_repo):
    """A manifests/ folder with no manifest in it is reported as no manifests
    found, with the git restore remedy."""
    with pytest.raises(ManifestError) as caught:
        manifests()
    message = str(caught.value)
    assert "no manifests found" in message
    assert "git checkout" in message


@negative
def test_named_manifest_that_does_not_exist_is_named(fake_repo):
    """Asking for a manifest by a name no file has is refused with that name in
    the message."""
    fake_repo.manifest("set_a", [])
    with pytest.raises(ManifestError, match="no manifest named set_b"):
        manifests("set_b")


@negative
def test_unreadable_manifest_names_the_file(fake_repo):
    """A manifest that is not valid JSON stops the read with an error naming
    that file and the restore remedy, rather than being skipped."""
    fake_repo.manifest("good", [])
    fake_repo.manifest("broken", "{ not json")
    with pytest.raises(ManifestError) as caught:
        manifests()
    message = str(caught.value)
    assert message.startswith("broken.json: cannot read")
    assert "git checkout" in message


@negative
def test_entry_missing_fields_lists_all_of_them(fake_repo):
    """An entry lacking required fields is refused with the manifest, the entry
    and every missing field named in one message, and the repair remedy."""
    fake_repo.file("inputs/set_a/a.txt", CONTENT)
    fake_repo.manifest(
        "set_a", [fake_repo.entry("inputs/set_a/a.txt", url=None, sha256=None)]
    )
    with pytest.raises(ManifestError) as caught:
        manifests()
    message = str(caught.value)
    assert message.startswith("set_a.json: entry a.txt lacks url, sha256")
    assert "repair that entry in manifests/set_a.json" in message


@negative
def test_size_that_is_not_a_whole_number_is_quoted(fake_repo):
    """A size written as "12,345" is refused as not a whole number, with the
    value quoted as written so a person sees their own typo."""
    fake_repo.file("inputs/set_a/a.txt", CONTENT)
    fake_repo.manifest("set_a", [fake_repo.entry("inputs/set_a/a.txt", bytes="12,345")])
    with pytest.raises(ManifestError) as caught:
        manifests()
    message = str(caught.value)
    assert 'has bytes "12,345", which is not a whole number' in message
    assert "repair that entry in manifests/set_a.json" in message


@negative
def test_sha256_that_is_not_lowercase_hex_is_quoted(fake_repo):
    """A sha256 in uppercase is refused as not 64 lowercase hex characters, with
    the value quoted as written."""
    fake_repo.file("inputs/set_a/a.txt", CONTENT)
    fake_repo.manifest(
        "set_a", [fake_repo.entry("inputs/set_a/a.txt", sha256="A" * 64)]
    )
    with pytest.raises(ManifestError) as caught:
        manifests()
    message = str(caught.value)
    assert f'has sha256 "{"A" * 64}", which is not 64 lowercase hex characters' in message
    assert "repair that entry in manifests/set_a.json" in message
