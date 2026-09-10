"""
Script:      test_fingerprint_file.py
Description: Automated checks for src/sdg/sources/fingerprint_file.py, the step
             that measures a file's size and sha256 and says whether the file
             matches its manifest entry. Each check stages one file and one
             entry, calls fingerprint() or compare(), and compares what happened
             to what the module's header promises: the two measurements, a
             matched result, or a result that names which value differed and
             how.

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

import pytest

from sdg.sources import fingerprint_file
from sdg.sources.fingerprint_file import Comparison, Fingerprint, compare, fingerprint
from sdg.sources.read_manifests import Entry

positive = pytest.mark.positive
negative = pytest.mark.negative

# The bytes most checks write. Short, so a check that changes them can show the
# change in one line.
CONTENT = b"pinned bytes\n"


#######################################################################################
### Shared helpers ###
#
# One helper builds the manifest entry a check compares a file against.


def entry_for_bytes(content: bytes, **overrides) -> Entry:
    """Builds a manifest entry whose size and sha256 match the given bytes, with
    any field overridden so a check can stage exactly one difference."""
    fields = dict(
        name="file.txt",
        url="https://example.invalid/file.txt",
        local="inputs/file.txt",
        bytes=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
        manifest="set_a.json",
    )
    fields.update(overrides)
    return Entry(**fields)


#######################################################################################
### Positive checks ###
#
# A file is measured correctly, and a file that matches its entry says so.


@positive
def test_fingerprint_measures_size_and_sha256(tmp_path):
    """fingerprint() gives back one object holding two values, the size in bytes
    and the sha256, and both agree with an independent measurement."""
    path = tmp_path / "file.txt"
    path.write_bytes(CONTENT)

    got = fingerprint(path)

    assert isinstance(got, Fingerprint)
    assert got.bytes == len(CONTENT)
    assert got.sha256 == hashlib.sha256(CONTENT).hexdigest()


@positive
def test_file_larger_than_one_piece_hashes_correctly(tmp_path):
    """A file bigger than the piece size the module reads in is hashed the same
    as a whole-file hash, so reading in pieces loses nothing."""
    content = b"x" * (fingerprint_file.CHUNK_BYTES * 2 + 17)
    path = tmp_path / "big.bin"
    path.write_bytes(content)

    got = fingerprint(path)

    assert got.bytes == len(content)
    assert got.sha256 == hashlib.sha256(content).hexdigest()


@positive
def test_matching_file_compares_as_matched(tmp_path):
    """A file whose size and sha256 equal its entry's compares as matched."""
    path = tmp_path / "file.txt"
    path.write_bytes(CONTENT)

    got = compare(path, entry_for_bytes(CONTENT))

    assert got == Comparison(matched=True, detail="matched")


#######################################################################################
### Negative checks ###
#
# A file that does not match is reported with the value that differed, and a
# path that cannot be measured is refused.


@negative
def test_size_difference_is_reported_first_and_hash_is_not_computed(tmp_path, monkeypatch):
    """A file whose size differs from its entry is reported as a size difference
    showing both numbers, and the sha256 is not computed at all."""
    path = tmp_path / "file.txt"
    path.write_bytes(CONTENT)
    entry = entry_for_bytes(CONTENT, bytes=len(CONTENT) + 5)

    # compare() reaches fingerprint() through the module, so replacing it here
    # proves the hash step is never reached when the size already differs.
    def refuse(_path):
        """Fails the check if the hash step is reached."""
        raise AssertionError("sha256 was computed for a file whose size differs")

    monkeypatch.setattr(fingerprint_file, "fingerprint", refuse)

    got = compare(path, entry)

    assert got.matched is False
    assert got.detail == f"size {len(CONTENT)} bytes, manifest says {len(CONTENT) + 5}"


@negative
def test_same_size_different_content_is_reported_as_sha256(tmp_path):
    """A file with the right size but different bytes is reported as a sha256
    difference, showing the start of both values."""
    # These bytes have the same length as CONTENT, so only the sha256 differs.
    changed = b"PINNED bytes\n"
    path = tmp_path / "file.txt"
    path.write_bytes(changed)
    entry = entry_for_bytes(CONTENT)

    got = compare(path, entry)

    assert got.matched is False
    assert got.detail.startswith(f"sha256 {hashlib.sha256(changed).hexdigest()[:16]}")
    assert f"manifest says {entry.sha256[:16]}" in got.detail


@negative
def test_missing_file_raises_file_not_found(tmp_path):
    """Both functions raise FileNotFoundError naming the path for a path that
    does not exist."""
    missing = tmp_path / "missing.txt"

    with pytest.raises(FileNotFoundError) as caught:
        fingerprint(missing)
    assert str(missing) in str(caught.value)
    with pytest.raises(FileNotFoundError) as caught:
        compare(missing, entry_for_bytes(CONTENT))
    assert str(missing) in str(caught.value)


@negative
def test_folder_is_refused_like_a_missing_file(tmp_path):
    """A folder at the path is refused with FileNotFoundError naming the path,
    because only a file can be measured."""
    folder = tmp_path / "folder"
    folder.mkdir()

    with pytest.raises(FileNotFoundError) as caught:
        fingerprint(folder)
    assert str(folder) in str(caught.value)
    with pytest.raises(FileNotFoundError) as caught:
        compare(folder, entry_for_bytes(CONTENT))
    assert str(folder) in str(caught.value)
