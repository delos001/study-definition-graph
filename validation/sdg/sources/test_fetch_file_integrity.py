"""
Script:      test_fetch_file_integrity.py
Description: The integrity checks for src/sdg/sources/fetch_file.py. The operation checks are
             in test_fetch_file_operation.py, beside this file.

Inputs:      See each check. A check that reads a real pinned file names it with
             @needs_pinned.

Outputs:     Writes nothing to disk. Temporary files go to pytest's own folder.

Usage:       pytest validation/sdg/sources/test_fetch_file_integrity.py
                 run these checks
             pytest validation/sdg/sources/test_fetch_file_integrity.py -v
                 one line per check with its result

Exit codes:  pytest's own: 0 all passed, 1 some failed

Date:        2026-09-24
Owner:       Jason Delosh
"""

from __future__ import annotations

import pytest
from validation.shared.fake_server import CHUNKS

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
### The integrity checks ###


@code("SA00035")
@category("repository")
@objective("correctness")
@positive
def test_download_holds_the_bytes_the_server_sent(completed):
    """The .part file holds exactly the bytes the server sent, in order."""
    assert completed.partial.read_bytes() == b"".join(CHUNKS)
