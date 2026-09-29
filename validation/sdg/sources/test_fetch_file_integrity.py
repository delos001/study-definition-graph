"""
Script:      test_fetch_file_integrity.py
Description: The integrity checks for src/sdg/sources/fetch_file.py. The technical checks are
             in test_fetch_file_technical.py, beside this file.

Inputs:      See each check. A check that reads a real pinned file names it with
             @needs_pinned.

Outputs:     Writes nothing to disk. Temporary files go to pytest's own folder.

Usage:       pytest validation/sdg/sources/test_fetch_file_integrity.py
                 run these checks
             pytest validation/sdg/sources/test_fetch_file_integrity.py -v
                 one line per check with its result

Exit codes:  None of its own. It runs inside pytest.

Date:        2026-09-24
Owner:       Jason Delosh
"""

from __future__ import annotations

from sdgval.labels import category, code, objective, positive
from validation.shared.fake_server import CHUNKS

#######################################################################################
### The integrity checks ###


@code("SA00035")
@category("repository")
@objective("correctness")
@positive
def test_download_holds_the_bytes_the_server_sent(completed):
    """The .part file holds exactly the bytes the server sent, in order."""
    assert completed.partial.read_bytes() == b"".join(CHUNKS)
