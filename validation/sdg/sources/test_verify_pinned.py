"""
Script:      test_verify_pinned.py
Description: Automated checks for src/sdg/sources/verify_pinned.py, the workflow
             that proves a pinned file is the recorded one and hands it back
             with its identity. Each check proves one promise from that module's
             header: one part of the identity handed back, or one cause of
             refusal with the message and remedy the header gives it.

             Most checks stage a small pretend repo in a temporary folder
             through the fake_repo fixture in conftest.py, so the real
             manifests/ and inputs/ are never written. The one check that reads
             the real repo is the stability check, which runs once per recorded
             file and skips a file that has not been downloaded.

Inputs:      manifests/*.json    (read-only; every recorded file's entry)
             inputs/**           (read-only; measured, and skipped when absent)

Outputs:     Writes nothing to disk. Temporary files go to pytest's own folder.

Usage:       pytest validation/sdg/sources/test_verify_pinned.py
                 run these checks
             pytest validation/sdg/sources/test_verify_pinned.py -v
                 one line per check with its result

Exit codes:  pytest's own: 0 all passed, 1 some failed

Date:        2026-09-04
Owner:       Jason Delosh
"""

from __future__ import annotations

import hashlib

import pytest

from sdg.sources import (
    IntegrityError,
    ManifestError,
    NotInRepoError,
    PinnedFile,
    UnrecordedFileError,
    read_manifests,
    verify_pinned,
)

positive = pytest.mark.positive
negative = pytest.mark.negative
# Every check carries a @code line: its short, permanent id in
# validation/validation_inventory.csv, assigned once and never reused.
code = pytest.mark.code
# Every check carries an @objective line: what the check confirms about its category,
# one of the objectives validation/validation_inventory_dictionary.md defines.
objective = pytest.mark.objective
# Every check carries a @category line: what kind of thing the check confirms, one
# of the categories validation/validation_inventory_dictionary.md defines.
category = pytest.mark.category


def pinned_locals() -> list[str]:
    """List every file the real manifests record, when the checks are collected.

    A manifest that cannot be read gives no files here. The checks of the manifest
    reader, in validation/sdg/sources/test_read_manifests.py, report that problem.

    Returns:
        The recorded paths, as the manifests write them.
    """
    try:
        return [
            entry.local
            for manifest in read_manifests.manifests()
            for entry in manifest.entries
        ]
    except (ManifestError, NotInRepoError):
        return []


# The one staged file every staged check uses, and its bytes.
LOCAL = "inputs/set_a/file.txt"
CONTENT = b"pinned bytes\n"
SHA256 = hashlib.sha256(CONTENT).hexdigest()


#######################################################################################
### Shared staging ###
#
# Each fixture stages one situation. Each check then asserts one thing about
# what verify_pinned() handed back or how it refused.


@pytest.fixture
def recorded_file(fake_repo):
    """Stages one file in the fake repo with a correct entry for it, and gives
    back the file's full path."""
    path = fake_repo.file(LOCAL, CONTENT)
    fake_repo.manifest("set_a", [fake_repo.entry(LOCAL)])
    return path


@pytest.fixture
def mismatch_message(fake_repo) -> str:
    """Stages a file whose bytes differ from its entry at the same size, tries
    to verify it, and gives back the refusal message."""
    # These bytes have the same length as CONTENT, so only the sha256 differs.
    fake_repo.file(LOCAL, b"PINNED bytes\n")
    fake_repo.manifest("set_a", [fake_repo.entry(LOCAL, sha256=SHA256)])
    with pytest.raises(IntegrityError) as caught:
        verify_pinned(LOCAL)
    return str(caught.value)


def refused_with(error, target=LOCAL) -> str:
    """Try to verify the target and expect it to be refused.

    Args:
        error: The error type expected.
        target: The file to verify, the recorded one unless a check says otherwise.

    Returns:
        The error's message.
    """
    with pytest.raises(error) as caught:
        verify_pinned(target)
    return str(caught.value)


#######################################################################################
### Every pinned file is unchanged ###
#
# One check per pinned file, so a report names the file that changed. It is the only
# check that fails for a changed pinned file; every other check that reads one is
# skipped as blocked by validation/conftest.py.


@code("SRC0128")
@category("sources")
@objective("stability")
@pytest.mark.parametrize("local", pinned_locals())
def test_pinned_file_is_unchanged(local):
    """A pinned file on disk has the size and sha256 its manifest entry records, so it
    is unchanged since it was pinned. A file not downloaded is skipped."""
    try:
        verify_pinned(local)
    except FileNotFoundError:
        pytest.skip(f"not downloaded: {local}; run acquire_sources")


#######################################################################################
### Positive checks against a staged repo ###
#
# A recorded file that matches its entry comes back with its identity and reads.


@code("SRC0100")
@category("repository")
@objective("correctness")
@positive
def test_recorded_file_carries_its_identity(recorded_file):
    """A file whose entry is correct comes back with the sha256, url and
    manifest name its entry records."""
    got = verify_pinned(LOCAL)
    assert isinstance(got, PinnedFile)
    assert got.sha256 == SHA256
    assert got.url == "https://example.invalid/file.txt"
    assert got.manifest == "set_a.json"


@code("SRC0101")
@category("repository")
@objective("correctness")
@positive
def test_recorded_file_path_is_the_file_on_this_machine(recorded_file):
    """A verified file's path is the full path of the file on this machine, and
    its local path is the one the manifest writes."""
    got = verify_pinned(LOCAL)
    assert got.local == LOCAL
    assert got.path == recorded_file


@code("SRC0102")
@category("repository")
@objective("correctness")
@positive
def test_recorded_file_content_reads(recorded_file):
    """read_text() on a verified file gives its content."""
    assert verify_pinned(LOCAL).read_text() == CONTENT.decode()


@code("SRC0103")
@category("repository")
@objective("functionality")
@positive
def test_staged_record_is_the_same_by_string_or_path(recorded_file):
    """The repo-relative string a manifest writes, the same string with
    backslashes, and a full Path all give the same record."""
    by_string = verify_pinned(LOCAL)
    assert by_string == verify_pinned(LOCAL.replace("/", "\\"))
    assert by_string == verify_pinned(recorded_file)


#######################################################################################
### Negative checks ###
#
# A file that cannot be proven is refused. Each cause has its own message and
# remedy, and each check asserts the message names that cause and not another,
# because a wrong remedy would send a person to re-download a file that is fine
# or to edit a manifest that is not the problem.


@code("SRC0104")
@category("repository")
@objective("functionality")
@negative
def test_not_in_repo_error_passes_through_unwrapped(recorded_file, fake_repo):
    """When the sdg package is not running from inside its repo, verify_pinned()
    raises NotInRepoError with the install command, not an IntegrityError."""
    (fake_repo.root / "pyproject.toml").write_text(
        "[project]\nname = 'other'\n", encoding="utf-8"
    )
    assert "pip install -e ." in refused_with(NotInRepoError)


@code("SRC0105")
@category("repository")
@objective("functionality")
@negative
def test_recorded_but_absent_file_raises_file_not_found(fake_repo):
    """A file that a manifest records but that is not on disk raises
    FileNotFoundError naming the path, a different failure from a file that
    cannot be verified."""
    fake_repo.manifest(
        "set_a", [fake_repo.entry(LOCAL, bytes=len(CONTENT), sha256=SHA256)]
    )
    message = refused_with(FileNotFoundError)
    assert str(fake_repo.root / LOCAL) in message


@code("SRC0127")
@category("repository")
@objective("functionality")
@negative
def test_locked_file_passes_the_operating_systems_error_through(
    recorded_file, monkeypatch
):
    """A recorded file that is on disk but cannot be opened raises PermissionError
    unchanged, naming the path, rather than being wrapped as a mismatch or a missing
    file.

    The operating system's refusal is staged by replacing the file open, since a
    real lock cannot be made reliably inside a check."""
    import pathlib

    real_open = pathlib.Path.open

    def refuse(self, *args, **kwargs):
        """Refuse to open the recorded file, and open any other file as usual."""
        if self == recorded_file:
            raise PermissionError(f"{self}: locked by another program")
        return real_open(self, *args, **kwargs)

    monkeypatch.setattr(pathlib.Path, "open", refuse)
    message = refused_with(PermissionError)
    assert "locked by another program" in message
    assert str(recorded_file) in message


@code("SRC0106")
@category("repository")
@objective("functionality")
@negative
def test_unrecorded_file_is_refused_as_unrecorded(recorded_file, fake_repo):
    """A file that no manifest records is refused with a message saying so and
    the remedy of adding an entry."""
    fake_repo.file("inputs/set_a/stray.txt", CONTENT)
    message = refused_with(UnrecordedFileError, "inputs/set_a/stray.txt")
    assert "no manifest entry records it" in message
    assert "add its manifest entry" in message


@code("SRC0107")
@category("repository")
@objective("functionality")
@negative
def test_unrecorded_file_does_not_get_the_mismatch_remedy(recorded_file, fake_repo):
    """The message for an unrecorded file does not carry the mismatch remedy,
    which would send a person to re-download a file that was never recorded."""
    fake_repo.file("inputs/set_a/stray.txt", CONTENT)
    message = refused_with(UnrecordedFileError, "inputs/set_a/stray.txt")
    assert "manifest says" not in message
    assert "acquire_sources" not in message


@code("SRC0108")
@category("repository")
@objective("functionality")
@negative
def test_unreadable_manifest_is_reported_as_a_manifest_problem(fake_repo):
    """A manifest that cannot be read is passed through as the manifest reader's
    own error from src/sdg/sources/read_manifests.py, naming the manifest file and the git restore remedy."""
    fake_repo.file(LOCAL, CONTENT)
    fake_repo.manifest("set_a", "{ not json")
    message = refused_with(ManifestError)
    assert message.startswith("set_a.json: cannot read")
    assert "git checkout" in message


@code("SRC0109")
@category("repository")
@objective("functionality")
@negative
def test_unreadable_manifest_does_not_get_the_mismatch_remedy(fake_repo):
    """The message for an unreadable manifest does not carry the mismatch
    remedy, because the file is not the problem."""
    fake_repo.file(LOCAL, CONTENT)
    fake_repo.manifest("set_a", "{ not json")
    assert "manifest says" not in refused_with(ManifestError)


@code("SRC0110")
@category("repository")
@objective("functionality")
@negative
def test_no_manifests_is_reported_as_none_found(fake_repo):
    """When the manifests folder is empty, the refusal says no manifests were
    found and says to restore them with git."""
    fake_repo.file(LOCAL, CONTENT)
    message = refused_with(ManifestError)
    assert "no manifests found" in message
    assert "git checkout" in message


@code("SRC0111")
@category("repository")
@objective("functionality")
@negative
def test_entry_missing_sha256_is_reported_as_lacking_it(fake_repo):
    """An entry with no sha256 is refused as lacking that field, with the
    repair remedy, so a person repairs the entry rather than re-downloading."""
    fake_repo.file(LOCAL, CONTENT)
    fake_repo.manifest("set_a", [fake_repo.entry(LOCAL, sha256=None)])
    message = refused_with(ManifestError)
    assert "lacks sha256" in message
    assert "repair that entry" in message


@code("SRC0112")
@category("repository")
@objective("functionality")
@negative
def test_mismatch_shows_both_sha256_values(mismatch_message):
    """When the bytes differ from the entry at the same size, the message shows
    the start of the file's sha256 and of the manifest's."""
    changed = hashlib.sha256(b"PINNED bytes\n").hexdigest()
    assert mismatch_message.startswith(f"{LOCAL}: sha256 {changed[:16]}")
    assert f"manifest says {SHA256[:16]}" in mismatch_message


@code("SRC0113")
@category("repository")
@objective("functionality")
@negative
def test_mismatch_names_the_manifest_that_records_the_file(mismatch_message):
    """The mismatch message names the manifest the file is recorded in."""
    assert "(recorded in set_a.json)" in mismatch_message


@code("SRC0114")
@category("repository")
@objective("functionality")
@negative
def test_mismatch_offers_the_three_ways_back(mismatch_message):
    """The mismatch message offers the three ways back: re-fetch, read
    unverified once, or re-pin."""
    assert "acquire_sources" in mismatch_message
    assert "--allow-unpinned" in mismatch_message
    assert "re-pin" in mismatch_message


@code("SRC0115")
@category("repository")
@objective("functionality")
@negative
def test_size_mismatch_is_reported_as_size_with_both_numbers(fake_repo):
    """When the size differs from the entry, the refusal reports a size
    difference with the file's size and the manifest's."""
    fake_repo.file(LOCAL, CONTENT)
    fake_repo.manifest("set_a", [fake_repo.entry(LOCAL, bytes=len(CONTENT) + 3)])
    message = refused_with(IntegrityError)
    assert f"size {len(CONTENT)} bytes, manifest says {len(CONTENT) + 3}" in message
