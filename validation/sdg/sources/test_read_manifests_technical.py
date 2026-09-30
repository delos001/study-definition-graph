"""
Script:      test_read_manifests_technical.py
Description: Automated checks for src/sdg/sources/read_manifests.py, the step that
             reads the manifests and hands back what they say. Each check proves
             one promise from that module's header or docstrings: one fact about
             what is read, or one way a bad manifest is refused with a message
             naming the cause and the remedy.

             Some checks read the real manifests/ folder as it is. They need no
             download, because they read the records and not the files the
             records point at. The rest stage a small pretend repo in a
             temporary folder through the fake_repo fixture in conftest.py, so
             the real manifests/ is never written.

Inputs:      every manifest, read through src/sdg/sources/read_manifests.py
             (read-only; the checks against the real repo)

Outputs:     Writes nothing to disk. Temporary files go to pytest's own folder.

Usage:       pytest validation/sdg/sources/test_read_manifests_technical.py
                 run these checks
             pytest validation/sdg/sources/test_read_manifests_technical.py -v
                 one line per check with its result

Exit codes:  None of its own. It runs inside pytest.

Date:        2026-09-10
Owner:       Jason Delosh
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from sdg.sources import read_manifests
from sdg.sources.read_manifests import (
    AmbiguousNameError,
    Entry,
    ManifestError,
    ManifestUnparseableError,
    NotInRepoError,
    OutsideInputsError,
    as_local,
    entry_for,
    entry_named,
    manifests,
    require_repo,
)
from sdgval.labels import category, code, negative, objective, positive
from validation.shared.staged_manifests import CONTENT, LOCAL

#######################################################################################
### Shared staging ###
#
# Each fixture stages one situation that several checks look at from different
# angles. Each check then asserts one thing about it.


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


def refused_with(error: type[Exception], *args: str | None) -> str:
    """Call manifests() with the given arguments and expect it to refuse.

    Args:
        error: The error type expected.
        *args: The arguments to hand manifests().

    Returns:
        The error's message.
    """
    with pytest.raises(error) as caught:
        manifests(*args)
    return str(caught.value)


#######################################################################################
### Checks against the real repo ###
#
# These checks read the real manifests/ folder as it is.


@code("SA00076")
@category("repository")
@objective("functionality")
def test_repo_root_is_the_folder_holding_pyproject():
    """The repo root found is the folder that holds pyproject.toml."""
    root = require_repo()
    assert root == read_manifests.REPO_ROOT
    assert (root / "pyproject.toml").is_file()


@code("SA00077")
@category("repository")
@objective("functionality")
def test_every_entry_names_the_manifest_it_came_from(real_manifests):
    """Every entry remembers which manifest file it was read from."""
    for manifest in real_manifests:
        for entry in manifest.entries:
            assert entry.manifest == f"{manifest.name}.json"


#######################################################################################
### Positive checks against a staged repo ###
#
# Reading manifests and finding entries works, against a pretend repo in a
# temporary folder.


@code("SA00080")
@category("repository")
@objective("functionality")
@positive
def test_study_manifest_is_read_with_the_top_level_ones(top_level_and_study_sets):
    """A manifest under manifests/study_documents/ is read along with the top-level
    manifests."""
    assert "NCT1" in [manifest.name for manifest in manifests()]


@code("SA00081")
@category("repository")
@objective("functionality")
@positive
def test_study_manifests_are_listed_after_the_top_level_ones(top_level_and_study_sets):
    """The study manifests come after the top-level ones in the list."""
    assert [manifest.name for manifest in manifests()] == ["set_a", "NCT1"]


@code("SA00082")
@category("repository")
@objective("functionality")
@positive
def test_manifests_are_listed_in_path_order(three_sets):
    """Manifests come back sorted by path, whatever order they were written in."""
    assert [manifest.name for manifest in manifests()] == ["alpha", "mid", "zeta"]


@code("SA00084")
@category("repository")
@objective("functionality")
@positive
def test_one_manifest_can_be_read_by_name(three_sets):
    """Asking for a manifest by name gives only that one."""
    assert [manifest.name for manifest in manifests("mid")] == ["mid"]


@code("SA00085")
@category("repository")
@objective("functionality")
@positive
def test_the_name_may_carry_the_json_suffix(three_sets):
    """Asking by the file name with its .json suffix gives that same one
    manifest."""
    assert [manifest.name for manifest in manifests("mid.json")] == ["mid"]


@code("SA00086")
@category("repository")
@objective("functionality")
@positive
def test_entry_for_finds_a_recorded_file(recorded_file):
    """Given the path a manifest writes, the entry that records that file is found."""
    found = entry_for(LOCAL)
    assert isinstance(found, Entry)
    assert found.local == LOCAL


@code("SA00087")
@category("repository")
@objective("functionality")
@positive
def test_entry_for_accepts_backslashes(recorded_file):
    """A repo-relative path written with backslashes finds the same entry."""
    found = entry_for("inputs\\set_a\\file.txt")
    assert found is not None
    assert found == entry_for(LOCAL)


@code("SA00088")
@category("repository")
@objective("functionality")
@positive
def test_entry_for_accepts_a_full_path(recorded_file):
    """A full Path to the file finds the same entry."""
    found = entry_for(recorded_file)
    assert found is not None
    assert found == entry_for(LOCAL)


@code("SA00089")
@category("repository")
@objective("functionality")
@positive
def test_entry_path_is_the_file_on_this_machine(recorded_file):
    """An entry's path is the full path of its file on this machine."""
    entry = entry_for(LOCAL)
    assert entry is not None
    assert entry.path == recorded_file


@code("SA00090")
@category("repository")
@objective("functionality")
@positive
def test_entry_for_gives_none_for_an_unrecorded_file(recorded_file, fake_repo):
    """A file that no manifest records gives None, not an error."""
    fake_repo.file("inputs/set_a/stray.txt", CONTENT)
    assert entry_for("inputs/set_a/stray.txt") is None


@code("SA00091")
@category("repository")
@objective("functionality")
@positive
def test_entry_named_finds_a_recorded_file_by_its_name(recorded_file):
    """Given a file name, the entry for that file is found, so a caller holding only the
    name never writes the path down a second time."""
    found = entry_named("file.txt")
    assert isinstance(found, Entry)
    assert found.local == LOCAL


@code("SA00092")
@category("repository")
@objective("functionality")
@positive
def test_entry_named_gives_none_for_a_name_no_manifest_records(recorded_file):
    """A file name that no manifest records finds nothing, and is not an error."""
    assert entry_named("nobody_recorded_this.txt") is None


@code("SA00093")
@category("repository")
@objective("functionality")
@positive
def test_a_relative_path_is_read_from_the_repo_root(
    recorded_file, monkeypatch, tmp_path
):
    """A relative Path finds the same entry as the repo-relative string, whichever folder
    the program was started from, so a command run from elsewhere never reports a
    recorded file as unrecorded."""
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    found = entry_for(Path(LOCAL))
    assert found is not None
    assert found == entry_for(LOCAL)


@code("SA00094")
@category("repository")
@objective("functionality")
@positive
def test_as_local_leaves_an_outside_path_unchanged(fake_repo, tmp_path):
    """A path outside the repo is shown as its full path, so a message about it can show
    where it is."""
    outside = tmp_path / "elsewhere" / "file.txt"
    assert as_local(outside) == str(outside.resolve())


#######################################################################################
### Negative checks ###
#
# Bad input is refused with the right error and a message that names this
# cause and its remedy rather than another. A wrong remedy would send a person
# to fix the wrong thing.


@code("SA00095")
@category("repository")
@objective("functionality")
@negative
def test_wrong_package_name_is_refused_with_the_install_command(fake_repo):
    """When pyproject.toml does not name the sdg package, reading the manifests is
    refused, and the message gives the command to install from the repo."""
    (fake_repo.root / "pyproject.toml").write_text(
        "[project]\nname = 'other'\n", encoding="utf-8"
    )
    fake_repo.manifest("set_a", [])
    assert "pip install -e ." in refused_with(NotInRepoError)


@code("SA00096")
@category("repository")
@objective("functionality")
@negative
def test_repo_check_runs_before_any_manifest_is_read(fake_repo):
    """With a wrong package name and an unreadable manifest, the error is about
    the sdg package, which shows the repo check came first."""
    (fake_repo.root / "pyproject.toml").write_text(
        "[project]\nname = 'other'\n", encoding="utf-8"
    )
    fake_repo.manifest("set_a", "{ not json")
    refused_with(NotInRepoError)


@code("SA00097")
@category("repository")
@objective("functionality")
@negative
def test_missing_manifests_folder_is_named_with_the_restore_remedy(fake_repo):
    """When manifests/ is missing, the error names the folder and says to
    restore it with git."""
    shutil.rmtree(fake_repo.root / "manifests")
    message = refused_with(ManifestError)
    assert "no manifests folder" in message
    assert "git checkout" in message


@code("SA00098")
@category("repository")
@objective("functionality")
@negative
def test_empty_manifests_folder_is_reported_as_none_found(fake_repo):
    """When manifests/ holds no manifest, the error says none were found and
    says to restore them with git."""
    message = refused_with(ManifestError)
    assert "no manifests found" in message
    assert "git checkout" in message


@code("SA00099")
@category("repository")
@objective("functionality")
@negative
def test_unknown_manifest_name_is_refused_by_name(fake_repo):
    """Asking for a manifest by a name no file has gives an error that quotes
    the name."""
    fake_repo.manifest("set_a", [])
    assert "no manifest named set_b" in refused_with(ManifestError, "set_b")


@code("SA00100")
@category("repository")
@objective("functionality")
@negative
def test_unreadable_manifest_stops_the_read_and_names_the_file(fake_repo):
    """A manifest that is not valid JSON stops the whole read, even when another
    manifest is fine. The message names the bad file and says to restore it from git."""
    fake_repo.manifest("good", [])
    fake_repo.manifest("broken", "{ not json")
    message = refused_with(ManifestUnparseableError)
    assert message.startswith("broken.json: is not valid JSON")
    assert "git checkout" in message


@code("SA00101")
@category("repository")
@objective("functionality")
@negative
def test_manifest_that_is_a_list_is_refused_naming_the_file(fake_repo):
    """A manifest whose JSON is a list rather than an object is refused as unreadable.
    The message names the file and says to restore it from git."""
    fake_repo.manifest("broken", "[1, 2, 3]")
    message = refused_with(ManifestError)
    assert message.startswith("broken.json: cannot read")
    assert "not a manifest object" in message
    assert "git checkout" in message


@code("SA00102")
@category("repository")
@objective("functionality")
@negative
def test_entry_that_is_not_an_object_is_refused_naming_the_file(fake_repo):
    """A manifest whose files list holds a bare value rather than an entry object is
    refused as unreadable, naming the file and the git restore remedy."""
    fake_repo.manifest("broken", '{"files": ["not an entry"]}')
    message = refused_with(ManifestError)
    assert message.startswith("broken.json: cannot read")
    assert "list of entry objects" in message
    assert "git checkout" in message


@code("SA00103")
@category("repository")
@objective("functionality")
@negative
def test_entry_missing_fields_has_every_missing_field_named(fake_repo):
    """An entry lacking required fields is refused with one message that names
    the manifest, the entry, every missing field, and the repair remedy."""
    fake_repo.file(LOCAL, CONTENT)
    fake_repo.manifest("set_a", [fake_repo.entry(LOCAL, url=None, sha256=None)])
    message = refused_with(ManifestError)
    assert message.startswith("set_a.json: entry file.txt lacks url, sha256")
    assert "repair that entry in manifests/set_a.json" in message


@code("SA00104")
@category("repository")
@objective("functionality")
@negative
def test_size_that_is_not_a_whole_number_is_quoted_as_written(fake_repo):
    """A size written as "12,345" is refused as not a whole number, quoting the
    value as written, with the repair remedy."""
    fake_repo.file(LOCAL, CONTENT)
    fake_repo.manifest("set_a", [fake_repo.entry(LOCAL, bytes="12,345")])
    message = refused_with(ManifestError)
    assert 'has bytes "12,345", which is not a whole number' in message
    assert "repair that entry in manifests/set_a.json" in message


@code("SA00105")
@category("repository")
@objective("functionality")
@negative
def test_sha256_that_is_not_lowercase_hex_is_quoted_as_written(fake_repo):
    """A fingerprint written in capitals is refused as not well formed, and the message
    quotes it as written and says how to repair it."""
    fake_repo.file(LOCAL, CONTENT)
    fake_repo.manifest("set_a", [fake_repo.entry(LOCAL, sha256="A" * 64)])
    message = refused_with(ManifestError)
    assert (
        f'has sha256 "{"A" * 64}", which is not 64 lowercase hex characters' in message
    )
    assert "repair that entry in manifests/set_a.json" in message


#######################################################################################
### Checks on a name two entries share and a location outside inputs/ ###


@code("SA00604")
@category("repository")
@objective("functionality")
@negative
def test_a_name_two_entries_record_is_refused_naming_both(fake_repo):
    """A file name that two entries record is refused rather than answered with either
    one. The message names the location of both, says the two pinned files share the
    name, and says the code asking for it has to choose one version.

    The two entries record one publisher's file name in two folders, the way a second
    pinned version of a document would."""
    second = "inputs/set_b/file.txt"
    fake_repo.file(LOCAL, CONTENT)
    fake_repo.file(second, CONTENT)
    fake_repo.manifest("set_a", [fake_repo.entry(LOCAL)])
    fake_repo.manifest("set_b", [fake_repo.entry(second)])
    with pytest.raises(AmbiguousNameError) as caught:
        entry_named("file.txt")
    message = str(caught.value)
    assert LOCAL in message and second in message
    assert "two pinned files share this name" in message
    assert "has to choose one version of the file" in message


@code("SA00608")
@category("repository")
@objective("functionality")
@pytest.mark.parametrize(
    "local",
    ["/inputs/set_a/file.txt", "inputs/../src/file.txt"],
    ids=["a location opening with a slash", "a location stepping back out of inputs"],
)
@negative
def test_a_location_that_leaves_inputs_is_refused(fake_repo, local):
    """An entry whose local location does not stay under inputs/ once resolved is
    refused, and the message quotes the location and says how to write it. It runs
    once for a location opening with a slash, which replaces the repo root, and once
    for one that steps back out of inputs/ with .., which the first four characters
    alone would let through."""
    fake_repo.manifest(
        "set_a", [fake_repo.entry(local, bytes=len(CONTENT), sha256="0" * 64)]
    )
    message = refused_with(OutsideInputsError)
    assert f'has local "{local}", which does not stay under inputs/' in message
    assert "as a path under inputs/" in message
