"""
Script:      test_fingerprint_file.py
Description: Automated checks for src/sdg/sources/fingerprint_file.py, the step
             that measures a file's size and sha256 and says whether the file
             matches its manifest entry. Each check proves one promise from that
             module's header: one measurement, one comparison result, or one
             kind of path that is refused.

             Files are written to a temporary folder. Manifest entries are built
             in memory, because compare() takes an Entry and never opens a
             manifest itself.

Inputs:      none from the repo

Outputs:     Writes nothing to disk. Temporary files go to pytest's own folder.

Usage:       pytest tests/sources/test_fingerprint_file.py
                 run these checks
             pytest tests/sources/test_fingerprint_file.py -v
                 one line per check with its result

Exit codes:  pytest's own: 0 all passed, 1 some failed

Date:        2026-09-10
Owner:       Jason Delosh
"""

from __future__ import annotations

import hashlib
from typing import Any

import pytest

from sdg.sources import fingerprint_file
from sdg.sources.fingerprint_file import Comparison, compare, fingerprint
from sdg.sources.read_manifests import Entry

positive = pytest.mark.positive
negative = pytest.mark.negative
# Every check carries a @code line: its short, permanent id in
# tests/validation_inventory.csv, assigned once and never reused.
code = pytest.mark.code

# The bytes most checks write. Short, so a check that changes them can show the
# change in one line.
CONTENT = b"pinned bytes\n"


#######################################################################################
### Shared staging ###
#
# One helper builds the manifest entry a check compares a file against. One
# fixture writes the file most checks measure.


def entry_for_bytes(content: bytes, **overrides: Any) -> Entry:
    """Build a manifest entry whose size and sha256 match the given bytes.

    Args:
        content: The bytes the entry describes.
        **overrides: Any field to change, so a check can stage exactly one difference.

    Returns:
        The entry.
    """
    # Typed as Any so the fields can be handed to Entry by name, which takes
    # one text and one number.
    fields: dict[str, Any] = dict(
        name="file.txt",
        url="https://example.invalid/file.txt",
        local="inputs/file.txt",
        bytes=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
        manifest="set_a.json",
    )
    fields.update(overrides)
    return Entry(**fields)


@pytest.fixture
def file_on_disk(tmp_path):
    """Writes CONTENT to a file in a temporary folder and gives back its path."""
    path = tmp_path / "file.txt"
    path.write_bytes(CONTENT)
    return path


#######################################################################################
### Positive checks ###
#
# A file is measured correctly, and a file that matches its entry says so.


@code("SRC0059")
@positive
def test_fingerprint_measures_the_size(file_on_disk):
    """fingerprint() gives back the file's size in bytes."""
    assert fingerprint(file_on_disk).bytes == len(CONTENT)


@code("SRC0060")
@positive
def test_fingerprint_measures_the_sha256(file_on_disk):
    """fingerprint() gives back the file's sha256, the same as an independent
    hash of the same bytes."""
    assert fingerprint(file_on_disk).sha256 == hashlib.sha256(CONTENT).hexdigest()


@code("SRC0061")
@positive
def test_reading_in_pieces_loses_nothing(tmp_path):
    """A file bigger than the piece the module reads at a time hashes the same
    as a hash of the whole file."""
    content = b"x" * (fingerprint_file.CHUNK_BYTES * 2 + 17)
    path = tmp_path / "big.bin"
    path.write_bytes(content)
    assert fingerprint(path).sha256 == hashlib.sha256(content).hexdigest()


@code("SRC0062")
@positive
def test_matching_file_compares_as_matched(file_on_disk):
    """A file whose size and sha256 equal its entry's compares as matched."""
    assert compare(file_on_disk, entry_for_bytes(CONTENT)) == Comparison(
        matched=True, detail="matched"
    )


#######################################################################################
### Negative checks ###
#
# A file that does not match is reported with the value that differed, and a
# path that cannot be measured is refused.


@code("SRC0063")
@negative
def test_size_difference_is_reported_with_both_numbers(file_on_disk):
    """When the size differs from the entry, the result is not matched and the
    detail gives the file's size and the manifest's."""
    got = compare(file_on_disk, entry_for_bytes(CONTENT, bytes=len(CONTENT) + 5))
    assert got.matched is False
    assert got.detail == f"size {len(CONTENT)} bytes, manifest says {len(CONTENT) + 5}"


@code("SRC0064")
@negative
def test_size_difference_skips_the_hash(file_on_disk, monkeypatch):
    """When the size differs, the sha256 is not computed at all."""

    # compare() reaches fingerprint() through the module, so replacing it here
    # proves the hash step is never reached when the size already differs.
    def refuse(_path):
        """Fails the check if the hash step is reached."""
        raise AssertionError("sha256 was computed for a file whose size differs")

    monkeypatch.setattr(fingerprint_file, "fingerprint", refuse)
    compare(file_on_disk, entry_for_bytes(CONTENT, bytes=len(CONTENT) + 5))


@code("SRC0065")
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


@code("SRC0066")
@negative
def test_fingerprint_refuses_a_missing_file(tmp_path):
    """fingerprint() raises FileNotFoundError naming the path when the file
    does not exist."""
    missing = tmp_path / "missing.txt"
    with pytest.raises(FileNotFoundError) as caught:
        fingerprint(missing)
    assert str(missing) in str(caught.value)


@code("SRC0067")
@negative
def test_compare_refuses_a_missing_file(tmp_path):
    """compare() raises FileNotFoundError naming the path when the file does
    not exist."""
    missing = tmp_path / "missing.txt"
    with pytest.raises(FileNotFoundError) as caught:
        compare(missing, entry_for_bytes(CONTENT))
    assert str(missing) in str(caught.value)


@code("SRC0068")
@negative
def test_fingerprint_refuses_a_folder(tmp_path):
    """fingerprint() raises FileNotFoundError naming the path when a folder
    sits at the path, because only a file can be measured."""
    folder = tmp_path / "folder"
    folder.mkdir()
    with pytest.raises(FileNotFoundError) as caught:
        fingerprint(folder)
    assert str(folder) in str(caught.value)


@code("SRC0069")
@negative
def test_compare_refuses_a_folder(tmp_path):
    """compare() raises FileNotFoundError naming the path when a folder sits
    at the path."""
    folder = tmp_path / "folder"
    folder.mkdir()
    with pytest.raises(FileNotFoundError) as caught:
        compare(folder, entry_for_bytes(CONTENT))
    assert str(folder) in str(caught.value)
