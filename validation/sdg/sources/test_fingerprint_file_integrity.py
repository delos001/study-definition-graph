"""
Script:      test_fingerprint_file_integrity.py
Description: The integrity checks for src/sdg/sources/fingerprint_file.py, the step
             that measures a file's size and sha256. Each check confirms that a
             measurement equals the true value, measured independently of the
             code under test.

             Files are written to a temporary folder, by the file_on_disk
             fixture in validation/conftest.py or by the check itself.

Inputs:      none from the repo

Outputs:     Writes nothing to disk. Temporary files go to pytest's own folder.

Usage:       pytest validation/sdg/sources/test_fingerprint_file_integrity.py
                 run these checks
             pytest validation/sdg/sources/test_fingerprint_file_integrity.py -v
                 one line per check with its result

Exit codes:  None of its own. It runs inside pytest.

Date:        2026-09-24
Owner:       Jason Delosh
"""

from __future__ import annotations

import hashlib

from sdg.sources import fingerprint_file
from sdg.sources.fingerprint_file import fingerprint
from sdgval.labels import category, code, objective, positive
from validation.shared.staged_manifests import CONTENT

#######################################################################################
### Measurements ###
#
# A file is measured correctly.


@code("SA00065")
@category("repository")
@objective("correctness")
@positive
def test_fingerprint_measures_the_size(file_on_disk):
    """A file's fingerprint gives its size in bytes."""
    assert fingerprint(file_on_disk).bytes == len(CONTENT)


@code("SA00066")
@category("repository")
@objective("correctness")
@positive
def test_fingerprint_measures_the_sha256(file_on_disk):
    """A file's fingerprint is the same as one worked out separately from the same
    bytes."""
    assert fingerprint(file_on_disk).sha256 == hashlib.sha256(CONTENT).hexdigest()


@code("SA00067")
@category("repository")
@objective("correctness")
@positive
def test_reading_in_pieces_loses_nothing(tmp_path):
    """A file bigger than the piece read at a time has the same fingerprint as one
    worked out from the whole file."""
    content = b"x" * (fingerprint_file.CHUNK_BYTES * 2 + 17)
    path = tmp_path / "big.bin"
    path.write_bytes(content)
    assert fingerprint(path).sha256 == hashlib.sha256(content).hexdigest()
