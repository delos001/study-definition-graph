"""
Script:      test_fingerprint_file_operation.py
Description: The operation checks for src/sdg/sources/fingerprint_file.py, the step
             that measures a file's size and sha256 and says whether the file
             matches its manifest entry. Each check proves one promise from that
             module's header: one measurement, one comparison result, or one
             kind of path that is refused.

             Files are written to a temporary folder. Manifest entries are built
             in memory, because compare() takes an Entry and never opens a
             manifest itself.

Inputs:      none from the repo

Outputs:     Writes nothing to disk. Temporary files go to pytest's own folder.

Usage:       pytest validation/sdg/sources/test_fingerprint_file_operation.py
                 run these checks
             pytest validation/sdg/sources/test_fingerprint_file_operation.py -v
                 one line per check with its result

Exit codes:  pytest's own: 0 all passed, 1 some failed

Date:        2026-09-10
Owner:       Jason Delosh
"""

from __future__ import annotations

import hashlib

import pytest

from sdg.sources import fingerprint_file
from sdg.sources.fingerprint_file import Comparison, compare, fingerprint
from validation.shared.staged_manifests import CONTENT, entry_for_bytes

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

#######################################################################################
### Positive checks ###
#
# A file that matches its entry says so.


@code("SA00068")
@category("repository")
@objective("functionality")
@positive
def test_matching_file_compares_as_matched(file_on_disk):
    """A file whose size and sha256 equal its entry's compares as matched."""
    assert compare(
        file_on_disk,
        entry_for_bytes(CONTENT),
    ) == Comparison(matched=True, detail="matched")


#######################################################################################
### Negative checks ###
#
# A file that does not match is reported with the value that differed, and a
# path that cannot be measured is refused.


@code("SA00069")
@category("repository")
@objective("functionality")
@negative
def test_size_difference_is_reported_with_both_numbers(file_on_disk):
    """When the size differs from the entry, the result is not matched and the
    detail gives the file's size and the manifest's."""
    got = compare(
        file_on_disk,
        entry_for_bytes(
            CONTENT,
            bytes=len(CONTENT) + 5,
        ),
    )
    assert got.matched is False
    assert got.detail == f"size {len(CONTENT)} bytes, manifest says {len(CONTENT) + 5}"


@code("SA00070")
@category("repository")
@objective("functionality")
@negative
def test_size_difference_skips_the_hash(file_on_disk, monkeypatch):
    """When the size differs, the sha256 is not computed at all."""

    # compare() reaches fingerprint() through the module, so replacing it here
    # proves the hash step is never reached when the size already differs.
    def refuse(_path):
        """Fails the check if the hash step is reached."""
        raise AssertionError("sha256 was computed for a file whose size differs")

    monkeypatch.setattr(fingerprint_file, "fingerprint", refuse)
    compare(
        file_on_disk,
        entry_for_bytes(
            CONTENT,
            bytes=len(CONTENT) + 5,
        ),
    )


@code("SA00071")
@category("repository")
@objective("functionality")
@negative
def test_same_size_different_bytes_is_reported_as_sha256_difference(tmp_path):
    """When the size matches but the bytes differ, the result is not matched
    and the detail shows the start of both sha256 values."""
    # These bytes have the same length as CONTENT, so only the sha256 differs.
    changed = b"PINNED bytes\n"
    path = tmp_path / "file.txt"
    path.write_bytes(changed)
    entry = entry_for_bytes(CONTENT)

    got = compare(path, entry)

    assert got.matched is False
    assert got.detail.startswith(f"sha256 {hashlib.sha256(changed).hexdigest()[:16]}")
    assert f"manifest says {entry.sha256[:16]}" in got.detail


@code("SA00072")
@category("repository")
@objective("functionality")
@negative
def test_fingerprint_refuses_a_missing_file(tmp_path):
    """fingerprint() raises FileNotFoundError naming the path when the file
    does not exist."""
    missing = tmp_path / "missing.txt"
    with pytest.raises(FileNotFoundError) as caught:
        fingerprint(missing)
    assert str(missing) in str(caught.value)


@code("SA00073")
@category("repository")
@objective("functionality")
@negative
def test_compare_refuses_a_missing_file(tmp_path):
    """compare() raises FileNotFoundError naming the path when the file does
    not exist."""
    missing = tmp_path / "missing.txt"
    with pytest.raises(FileNotFoundError) as caught:
        compare(
            missing,
            entry_for_bytes(CONTENT),
        )
    assert str(missing) in str(caught.value)


@code("SA00074")
@category("repository")
@objective("functionality")
@negative
def test_fingerprint_refuses_a_folder(tmp_path):
    """fingerprint() raises FileNotFoundError naming the path when a folder
    sits at the path, because only a file can be measured."""
    folder = tmp_path / "folder"
    folder.mkdir()
    with pytest.raises(FileNotFoundError) as caught:
        fingerprint(folder)
    assert str(folder) in str(caught.value)


@code("SA00075")
@category("repository")
@objective("functionality")
@negative
def test_compare_refuses_a_folder(tmp_path):
    """compare() raises FileNotFoundError naming the path when a folder sits
    at the path."""
    folder = tmp_path / "folder"
    folder.mkdir()
    with pytest.raises(FileNotFoundError) as caught:
        compare(
            folder,
            entry_for_bytes(CONTENT),
        )
    assert str(folder) in str(caught.value)
