"""
Script:      test_fingerprint_file_integrity.py
Description: The integrity checks for src/sdg/sources/fingerprint_file.py, the step
             that measures a file's size and sha256. Each check confirms that a
             measurement equals the true value, measured independently of the
             code under test.

             Files are written to a temporary folder by the fixtures in
             validation/sdg/sources/conftest.py.

Inputs:      none from the repo

Outputs:     Writes nothing to disk. Temporary files go to pytest's own folder.

Usage:       pytest validation/sdg/sources/test_fingerprint_file_integrity.py
                 run these checks
             pytest validation/sdg/sources/test_fingerprint_file_integrity.py -v
                 one line per check with its result

Exit codes:  pytest's own: 0 all passed, 1 some failed

Date:        2026-09-24
Owner:       Jason Delosh
"""

from __future__ import annotations

import hashlib

import pytest
from validation.shared.staged_manifests import CONTENT

from sdg.sources import fingerprint_file
from sdg.sources.fingerprint_file import fingerprint

positive = pytest.mark.positive
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
### Measurements ###
#
# A file is measured correctly.


@code("SA00065")
@category("repository")
@objective("correctness")
@positive
def test_fingerprint_measures_the_size(file_on_disk):
    """fingerprint() gives back the file's size in bytes."""
    assert fingerprint(file_on_disk).bytes == len(CONTENT)


@code("SA00066")
@category("repository")
@objective("correctness")
@positive
def test_fingerprint_measures_the_sha256(file_on_disk):
    """fingerprint() gives back the file's sha256, the same as an independent
    hash of the same bytes."""
    assert fingerprint(file_on_disk).sha256 == hashlib.sha256(CONTENT).hexdigest()


@code("SA00067")
@category("repository")
@objective("correctness")
@positive
def test_reading_in_pieces_loses_nothing(tmp_path):
    """A file bigger than the piece fingerprint_file.py reads at a time hashes the same
    as a hash of the whole file."""
    content = b"x" * (fingerprint_file.CHUNK_BYTES * 2 + 17)
    path = tmp_path / "big.bin"
    path.write_bytes(content)
    assert fingerprint(path).sha256 == hashlib.sha256(content).hexdigest()
