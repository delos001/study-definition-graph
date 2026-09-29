"""
Script:      test_verify_pinned_integrity.py
Description: The integrity checks for src/sdg/sources/verify_pinned.py. The technical checks are
             in test_verify_pinned_technical.py, beside this file.

Inputs:      See each check. A check that reads a real pinned file names it with
             @needs_pinned.

Outputs:     Writes nothing to disk. Temporary files go to pytest's own folder.

Usage:       pytest validation/sdg/sources/test_verify_pinned_integrity.py
                 run these checks
             pytest validation/sdg/sources/test_verify_pinned_integrity.py -v
                 one line per check with its result

Exit codes:  None of its own. It runs inside pytest.

Date:        2026-09-24
Owner:       Jason Delosh
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from sdg.sources import (
    ManifestError,
    NotInRepoError,
    PinnedFile,
    read_manifests,
    verify_pinned,
)
from sdgval.labels import category, code, objective, positive
from validation.shared.staged_manifests import CONTENT, LOCAL, SHA256


@dataclass(frozen=True)
class ManifestsUnreadable:
    """Stands in for the pinned files when the manifests could not be read.

    It carries the manifest reader's own message, which names the manifest, the
    problem and the fix, so the stability check can fail with it.
    """

    message: str


def pinned_locals() -> list[str | object]:
    """List every file the real manifests record, when the checks are collected.

    When the manifests cannot be read, the list holds one stand-in carrying the
    reader's message instead. The stability check then runs once and fails with that
    message, rather than running zero times and passing quietly. The error is not
    let through here, because a check file that fails to load stops every check in
    the run, not only this one.

    Returns:
        The recorded paths, as the manifests write them, or one run that carries
        why the manifests could not be read.
    """
    try:
        return [
            entry.local
            for manifest in read_manifests.manifests()
            for entry in manifest.entries
        ]
    except (ManifestError, NotInRepoError) as exc:
        return [
            pytest.param(
                ManifestsUnreadable(str(exc)), id="manifests could not be read"
            )
        ]


#######################################################################################
### The integrity checks ###


@code("SA00106")
@category("sources")
@objective("stability")
@pytest.mark.parametrize("local", pinned_locals())
def test_pinned_file_is_unchanged(local):
    """A pinned file on disk has the size and fingerprint its manifest entry records, so
    it is unchanged since it was pinned. It runs once for each file the manifests
    record."""
    if isinstance(local, ManifestsUnreadable):
        pytest.fail(local.message, pytrace=False)
    try:
        verify_pinned(local)
    except FileNotFoundError:
        pytest.skip(f"not downloaded: {local}; run acquire_sources")


@code("SA00107")
@category("repository")
@objective("correctness")
@positive
def test_recorded_file_carries_its_identity(recorded_file):
    """A file whose entry is correct comes back with the fingerprint, address and
    manifest name its entry records."""
    got = verify_pinned(LOCAL)
    assert isinstance(got, PinnedFile)
    assert got.sha256 == SHA256
    assert got.url == "https://example.invalid/file.txt"
    assert got.manifest == "set_a.json"


@code("SA00108")
@category("repository")
@objective("correctness")
@positive
def test_recorded_file_path_is_the_file_on_this_machine(recorded_file):
    """A verified file's path is the full path of the file on this machine, and
    its local path is the one the manifest writes."""
    got = verify_pinned(LOCAL)
    assert got.local == LOCAL
    assert got.path == recorded_file


@code("SA00109")
@category("repository")
@objective("correctness")
@positive
def test_recorded_file_content_reads(recorded_file):
    """A verified file's content can be read."""
    assert verify_pinned(LOCAL).read_text() == CONTENT.decode()
