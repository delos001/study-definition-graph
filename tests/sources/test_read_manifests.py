"""
Script:      test_read_manifests.py
Description: Automated checks for src/sdg/sources/read_manifests.py, the step that
             reads the manifests and hands back what they say. Each check proves
             one promise from that module's header or docstrings: one fact about
             what is read, or one way a bad manifest is refused with a message
             naming the cause and the remedy.

             Five checks read the real manifests/ folder as it is. They need no
             download, because they read the records and not the files the
             records point at. The rest stage a small pretend repo in a
             temporary folder through the fake_repo fixture in conftest.py, so
             the real manifests/ is never written.

Inputs:      manifests/*.json   (read-only; the checks against the real repo)

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

# The one staged file most staged checks use, and its bytes. What the file says
# does not matter to the reader; only that an entry can be built for it.
LOCAL = "inputs/set_a/a.txt"
CONTENT = b"pinned bytes\n"


#######################################################################################
### Shared staging ###
#
# Each fixture stages one situation that several checks look at from different
# angles. Each check then asserts one thing about it.


@pytest.fixture
def real_manifests():
    """Reads the real manifests once and gives them back keyed by name."""
    return {manifest.name: manifest for manifest in manifests()}


@pytest.fixture
def one_recorded_file(fake_repo):
    """Stages one file in the fake repo with a correct entry for it, and gives
    back the file's full path."""
    path = fake_repo.file(LOCAL, CONTENT)
    fake_repo.manifest("set_a", [fake_repo.entry(LOCAL)])
    return path


@pytest.fixture
def three_sets(fake_repo):
    """Stages three manifests, written in an order that is not alphabetical."""
    for name in ("zeta", "alpha", "mid"):
        fake_repo.file(f"inputs/{name}/f.txt", CONTENT)
        fake_repo.manifest(name, [fake_repo.entry(f"inputs/{name}/f.txt")])


@pytest.fixture
def top_level_and_study_sets(fake_repo):
    """Stages one top-level manifest and one study manifest under
    manifests/study_documents/."""
    fake_repo.file(LOCAL, CONTENT)
    fake_repo.file("inputs/study_documents/NCT1/protocol.pdf", CONTENT)
    fake_repo.manifest("set_a", [fake_repo.entry(LOCAL)])
    fake_repo.manifest(
        "NCT1",
        [fake_repo.entry("inputs/study_documents/NCT1/protocol.pdf")],
        study=True,
    )


def refused_with(error, *args) -> str:
    """Calls manifests() with the given arguments, expects it to raise the
    given error, and gives back the error's message."""
    with pytest.raises(error) as caught:
        manifests(*args)
    return str(caught.value)


#######################################################################################
### Positive checks against the real repo ###
#
# These checks read the real manifests/ folder as it is.


@positive
def test_repo_root_is_the_folder_holding_pyproject():
    """require_repo() gives back the folder that holds pyproject.toml."""
    root = require_repo()
    assert root == read_manifests.REPO_ROOT
    assert (root / "pyproject.toml").is_file()


@positive
def test_every_hand_written_manifest_is_read(real_manifests):
    """manifests() reads all six hand-written manifests."""
    assert HAND_WRITTEN <= set(real_manifests)


@positive
def test_every_hand_written_manifest_lands_under_inputs(real_manifests):
    """Every hand-written manifest says its files land under inputs/."""
    for name in HAND_WRITTEN:
        assert real_manifests[name].local_dir.startswith("inputs/")


@positive
def test_every_entry_carries_the_five_required_fields(real_manifests):
    """Every entry in the hand-written manifests has a name, a url, a local
    path under inputs/, a size above zero, and a 64-character sha256."""
    for name in HAND_WRITTEN:
        assert real_manifests[name].entries
        for entry in real_manifests[name].entries:
            assert entry.name
            assert entry.url
            assert entry.local.startswith("inputs/")
            assert entry.bytes > 0
            assert len(entry.sha256) == 64


@positive
def test_every_entry_names_the_manifest_it_came_from(real_manifests):
    """Every entry remembers which manifest file it was read from."""
    for name in HAND_WRITTEN:
        for entry in real_manifests[name].entries:
            assert entry.manifest == f"{name}.json"


#######################################################################################
### Positive checks against a staged repo ###
#
# Reading manifests and finding entries works, against a pretend repo in a
# temporary folder.


@positive
def test_study_manifest_is_read_with_the_top_level_ones(top_level_and_study_sets):
    """A manifest under manifests/study_documents/ is read in the same call as
    the top-level manifests."""
    assert "NCT1" in [manifest.name for manifest in manifests()]


@positive
def test_study_manifests_are_listed_after_the_top_level_ones(top_level_and_study_sets):
    """The study manifests come after the top-level ones in the list."""
    assert [manifest.name for manifest in manifests()] == ["set_a", "NCT1"]


@positive
def test_manifests_are_listed_in_path_order(three_sets):
    """Manifests come back sorted by path, whatever order they were written in."""
    assert [manifest.name for manifest in manifests()] == ["alpha", "mid", "zeta"]


@positive
def test_listing_order_is_the_same_on_every_call(three_sets):
    """Two calls give the manifests in the same order."""
    first = [manifest.name for manifest in manifests()]
    second = [manifest.name for manifest in manifests()]
    assert first == second


@positive
def test_one_manifest_can_be_read_by_name(three_sets):
    """Asking for a manifest by name gives only that one."""
    assert [manifest.name for manifest in manifests("mid")] == ["mid"]


@positive
def test_the_name_may_carry_the_json_suffix(three_sets):
    """Asking by the file name with its .json suffix gives that same one
    manifest."""
    assert [manifest.name for manifest in manifests("mid.json")] == ["mid"]


@positive
def test_entry_for_finds_a_recorded_file(one_recorded_file):
    """entry_for() gives back the entry that records a file, given the
    repo-relative path a manifest writes."""
    found = entry_for(LOCAL)
    assert isinstance(found, Entry)
    assert found.local == LOCAL


@positive
def test_entry_for_accepts_backslashes(one_recorded_file):
    """A repo-relative path written with backslashes finds the same entry."""
    assert entry_for("inputs\\set_a\\a.txt") == entry_for(LOCAL)


@positive
def test_entry_for_accepts_a_full_path(one_recorded_file):
    """A full Path to the file finds the same entry."""
    assert entry_for(one_recorded_file) == entry_for(LOCAL)


@positive
def test_entry_path_is_the_file_on_this_machine(one_recorded_file):
    """An entry's path is the full path of its file on this machine."""
    assert entry_for(LOCAL).path == one_recorded_file


@positive
def test_entry_for_gives_none_for_an_unrecorded_file(one_recorded_file, fake_repo):
    """A file that no manifest records gives None, not an error."""
    fake_repo.file("inputs/set_a/stray.txt", CONTENT)
    assert entry_for("inputs/set_a/stray.txt") is None


@positive
def test_as_local_leaves_an_outside_path_unchanged(fake_repo, tmp_path):
    """A path outside the repo comes back from as_local() as its full path, so
    a message about it can show where it is."""
    outside = tmp_path / "elsewhere" / "file.txt"
    assert as_local(outside) == str(outside.resolve())


#######################################################################################
### Negative checks ###
#
# Bad input is refused with the right error and a message that names this
# cause and its remedy rather than another. A wrong remedy would send a person
# to fix the wrong thing.


@negative
def test_wrong_package_name_is_refused_with_the_install_command(fake_repo):
    """When pyproject.toml does not name the sdg package, manifests() raises
    NotInRepoError and the message gives the pip install -e . command."""
    (fake_repo.root / "pyproject.toml").write_text(
        "[project]\nname = 'other'\n", encoding="utf-8"
    )
    fake_repo.manifest("set_a", [])
    assert "pip install -e ." in refused_with(NotInRepoError)


@negative
def test_repo_check_runs_before_any_manifest_is_read(fake_repo):
    """With a wrong package name and an unreadable manifest, the error is about
    the package, which shows the repo check came first."""
    (fake_repo.root / "pyproject.toml").write_text(
        "[project]\nname = 'other'\n", encoding="utf-8"
    )
    fake_repo.manifest("set_a", "{ not json")
    refused_with(NotInRepoError)


@negative
def test_missing_manifests_folder_is_named_with_the_restore_remedy(fake_repo):
    """When manifests/ is missing, the error names the folder and says to
    restore it with git."""
    shutil.rmtree(fake_repo.root / "manifests")
    message = refused_with(ManifestError)
    assert "no manifests folder" in message
    assert "git checkout" in message


@negative
def test_empty_manifests_folder_is_reported_as_none_found(fake_repo):
    """When manifests/ holds no manifest, the error says none were found and
    says to restore them with git."""
    message = refused_with(ManifestError)
    assert "no manifests found" in message
    assert "git checkout" in message


@negative
def test_unknown_manifest_name_is_refused_by_name(fake_repo):
    """Asking for a manifest by a name no file has gives an error that quotes
    the name."""
    fake_repo.manifest("set_a", [])
    assert "no manifest named set_b" in refused_with(ManifestError, "set_b")


@negative
def test_unreadable_manifest_stops_the_read_and_names_the_file(fake_repo):
    """A manifest that is not valid JSON stops the whole read, even when
    another manifest is fine, with an error naming the bad file and the git
    restore remedy."""
    fake_repo.manifest("good", [])
    fake_repo.manifest("broken", "{ not json")
    message = refused_with(ManifestError)
    assert message.startswith("broken.json: cannot read")
    assert "git checkout" in message


@negative
def test_entry_missing_fields_has_every_missing_field_named(fake_repo):
    """An entry lacking required fields is refused with one message that names
    the manifest, the entry, every missing field, and the repair remedy."""
    fake_repo.file(LOCAL, CONTENT)
    fake_repo.manifest("set_a", [fake_repo.entry(LOCAL, url=None, sha256=None)])
    message = refused_with(ManifestError)
    assert message.startswith("set_a.json: entry a.txt lacks url, sha256")
    assert "repair that entry in manifests/set_a.json" in message


@negative
def test_size_that_is_not_a_whole_number_is_quoted_as_written(fake_repo):
    """A size written as "12,345" is refused as not a whole number, quoting the
    value as written, with the repair remedy."""
    fake_repo.file(LOCAL, CONTENT)
    fake_repo.manifest("set_a", [fake_repo.entry(LOCAL, bytes="12,345")])
    message = refused_with(ManifestError)
    assert 'has bytes "12,345", which is not a whole number' in message
    assert "repair that entry in manifests/set_a.json" in message


@negative
def test_sha256_that_is_not_lowercase_hex_is_quoted_as_written(fake_repo):
    """A sha256 in uppercase is refused as not 64 lowercase hex characters,
    quoting the value as written, with the repair remedy."""
    fake_repo.file(LOCAL, CONTENT)
    fake_repo.manifest("set_a", [fake_repo.entry(LOCAL, sha256="A" * 64)])
    message = refused_with(ManifestError)
    assert f'has sha256 "{"A" * 64}", which is not 64 lowercase hex characters' in message
    assert "repair that entry in manifests/set_a.json" in message
