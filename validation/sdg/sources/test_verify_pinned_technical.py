"""
Script:      test_verify_pinned_technical.py
Description: Automated checks for src/sdg/sources/verify_pinned.py, the workflow
             that proves a pinned file is the recorded one and hands it back
             with its identity. All but one of the checks prove one promise each
             from that module's header. The promise is one part of the identity
             handed back, or one cause of refusal with the message and remedy
             the header gives it. They stage a small pretend repo in a temporary
             folder through the fake_repo fixture in conftest.py, so the real
             manifests/ and inputs/ are never written.

             The other check confirms the helper the stability check takes its
             list of files from. The
             stability check itself, which reads the real pinned files, is in
             test_verify_pinned_integrity.py, beside this file.

Inputs:      manifests/*.json  (read-only; read when the stability check's file
                 is imported for its helper)

Outputs:     Writes nothing to disk. Temporary files go to pytest's own folder.

Usage:       pytest validation/sdg/sources/test_verify_pinned_technical.py
                 run these checks
             pytest validation/sdg/sources/test_verify_pinned_technical.py -v
                 one line per check with its result

Exit codes:  None of its own. It runs inside pytest.

Date:        2026-09-04
Owner:       Jason Delosh
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import IO, Any, cast

import pytest

from sdg.sources import (
    IntegrityError,
    ManifestError,
    ManifestUnparseableError,
    NotInRepoError,
    UnrecordedFileError,
    read_manifests,
    verify_pinned,
)
from sdgval.labels import category, code, negative, objective, positive
from validation.sdg.sources import test_verify_pinned_integrity as integrity
from validation.shared.staged_manifests import CONTENT, LOCAL, SHA256

#######################################################################################
### Shared staging ###
#
# Each fixture stages one situation. Each check then asserts one thing about
# what verify_pinned() handed back or how it refused.


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


def refused_with(error: type[Exception], target: str | Path = LOCAL) -> str:
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
### Positive checks against a staged repo ###
#
# A recorded file that matches its entry comes back with its identity and reads.


@code("SA00110")
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


@code("SA00111")
@category("repository")
@objective("functionality")
@negative
def test_not_in_repo_error_passes_through_unwrapped(recorded_file, fake_repo):
    """When the sdg package is not running from inside its repo, verifying a file is
    refused with the install command, not reported as a mismatch."""
    (fake_repo.root / "pyproject.toml").write_text(
        "[project]\nname = 'other'\n", encoding="utf-8"
    )
    assert "pip install -e ." in refused_with(NotInRepoError)


@code("SA00112")
@category("repository")
@objective("functionality")
@negative
def test_recorded_but_absent_file_raises_file_not_found(fake_repo):
    """A file a manifest records that is not on disk is refused as missing, and the
    message names the path. That is a different failure from a file that cannot be
    verified."""
    fake_repo.manifest(
        "set_a", [fake_repo.entry(LOCAL, bytes=len(CONTENT), sha256=SHA256)]
    )
    message = refused_with(FileNotFoundError)
    assert str(fake_repo.root / LOCAL) in message


@code("SA00113")
@category("repository")
@objective("functionality")
@negative
def test_locked_file_passes_the_operating_systems_error_through(
    recorded_file, monkeypatch
):
    """A recorded file on disk that cannot be opened is refused as not permitted, and
    the message names the path. It is not reported as a mismatch or a missing file.

    The operating system's refusal is staged by replacing the file open, since a
    real lock cannot be made reliably inside a check."""
    import pathlib

    real_open = pathlib.Path.open

    def refuse(self: pathlib.Path, *args: Any, **kwargs: Any) -> IO[Any]:
        """Refuse to open the recorded file, and open any other file as usual."""
        if self == recorded_file:
            raise PermissionError(f"{self}: locked by another program")
        return real_open(self, *args, **kwargs)

    monkeypatch.setattr(pathlib.Path, "open", refuse)
    message = refused_with(PermissionError)
    assert "locked by another program" in message
    assert str(recorded_file) in message


@code("SA00114")
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


@code("SA00115")
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


@code("SA00116")
@category("repository")
@objective("functionality")
@negative
def test_unreadable_manifest_is_reported_as_a_manifest_problem(fake_repo):
    """A manifest that cannot be read is reported with the manifest reader's own
    message, naming the manifest file and saying to restore it from git."""
    fake_repo.file(LOCAL, CONTENT)
    fake_repo.manifest("set_a", "{ not json")
    message = refused_with(ManifestUnparseableError)
    assert message.startswith("set_a.json: is not valid JSON")
    assert "git checkout" in message


@code("SA00117")
@category("repository")
@objective("functionality")
@negative
def test_unreadable_manifest_does_not_get_the_mismatch_remedy(fake_repo):
    """The message for an unreadable manifest does not carry the mismatch
    remedy, because the file is not the problem."""
    fake_repo.file(LOCAL, CONTENT)
    fake_repo.manifest("set_a", "{ not json")
    assert "manifest says" not in refused_with(ManifestError)


@code("SA00118")
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


@code("SA00119")
@category("repository")
@objective("functionality")
@negative
def test_entry_missing_sha256_is_reported_as_lacking_it(fake_repo):
    """An entry with no fingerprint is refused as missing that field, and the message
    says to repair the entry rather than download the file again."""
    fake_repo.file(LOCAL, CONTENT)
    fake_repo.manifest("set_a", [fake_repo.entry(LOCAL, sha256=None)])
    message = refused_with(ManifestError)
    assert "lacks sha256" in message
    assert "repair that entry" in message


@code("SA00120")
@category("repository")
@objective("functionality")
@negative
def test_mismatch_shows_both_sha256_values(mismatch_message):
    """When a file is the right size but its contents differ from its record, the
    message shows the start of both fingerprints."""
    changed = hashlib.sha256(b"PINNED bytes\n").hexdigest()
    assert mismatch_message.startswith(f"{LOCAL}: sha256 {changed[:16]}")
    assert f"manifest says {SHA256[:16]}" in mismatch_message


@code("SA00121")
@category("repository")
@objective("functionality")
@negative
def test_mismatch_names_the_manifest_that_records_the_file(mismatch_message):
    """The mismatch message names the manifest the file is recorded in."""
    assert "(recorded in set_a.json)" in mismatch_message


@code("SA00122")
@category("repository")
@objective("functionality")
@negative
def test_mismatch_offers_the_three_ways_back(mismatch_message):
    """The mismatch message offers three ways back. They are to fetch the file again,
    read it once unverified, or pin it again."""
    assert "acquire_sources" in mismatch_message
    assert "--allow-unpinned" in mismatch_message
    assert "re-pin" in mismatch_message


@code("SA00123")
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


#######################################################################################
### The stability check's own helper ###
#
# The stability check in test_verify_pinned_integrity.py takes its list of files from
# a helper in that file. This check confirms the helper keeps a broken manifest from
# leaving the stability check running zero times.


@code("SA00500")
@category("repository")
@objective("functionality")
@negative
def test_unreadable_manifests_make_the_stability_check_fail_once(monkeypatch):
    """When the manifests cannot be read, the stability check runs once and fails
    with the manifest reader's own message, so a broken manifest can never leave the
    check running zero times and passing quietly."""

    def unreadable() -> list:
        raise ManifestError("set_a.json: cannot read (staged)")

    monkeypatch.setattr(read_manifests, "manifests", unreadable)
    (only,) = integrity.pinned_locals()
    # The one run is pytest's parameter wrapper, whose first value is the stand-in
    # the stability check receives. pytest does not export the wrapper's type, so
    # the run is read without one.
    stand_in = cast(Any, only).values[0]
    with pytest.raises(pytest.fail.Exception, match=r"set_a\.json: cannot read"):
        integrity.test_pinned_file_is_unchanged(stand_in)
