"""
Script:      test_verify_pinned_integrity.py
Description: The integrity checks for src/sdg/sources/verify_pinned.py. The operation checks are
             in test_verify_pinned_operation.py, beside this file.

Inputs:      See each check. A check that reads a real pinned file names it with
             @needs_pinned.

Outputs:     Writes nothing to disk. Temporary files go to pytest's own folder.

Usage:       pytest validation/sdg/sources/test_verify_pinned_integrity.py
                 run these checks
             pytest validation/sdg/sources/test_verify_pinned_integrity.py -v
                 one line per check with its result

Exit codes:  pytest's own: 0 all passed, 1 some failed

Date:        2026-09-24
Owner:       Jason Delosh
"""

from __future__ import annotations

import pytest

from sdg.sources import (
    ManifestError,
    NotInRepoError,
    PinnedFile,
    read_manifests,
    verify_pinned,
)
from validation.shared.staged_manifests import CONTENT, LOCAL, SHA256

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
    reader, in validation/sdg/sources/test_read_manifests_operation.py, report that
    problem.

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


#######################################################################################
### The integrity checks ###


@code("SA00106")
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


@code("SA00107")
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
    """read_text() on a verified file gives its content."""
    assert verify_pinned(LOCAL).read_text() == CONTENT.decode()
