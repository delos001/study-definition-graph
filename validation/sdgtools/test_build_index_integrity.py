"""
Script:      test_build_index_integrity.py
Description: The integrity checks for src/sdgtools/build_index.py. The operation checks are
             in test_build_index_operation.py, beside this file.

Inputs:      See each check. A check that reads a real pinned file names it with
             @needs_pinned.

Outputs:     Writes nothing to disk. Temporary files go to pytest's own folder.

Usage:       pytest validation/sdgtools/test_build_index_integrity.py
                 run these checks
             pytest validation/sdgtools/test_build_index_integrity.py -v
                 one line per check with its result

Exit codes:  pytest's own: 0 all passed, 1 some failed

Date:        2026-09-24
Owner:       Jason Delosh
"""

from __future__ import annotations

import pytest

from sdgtools import build_index as bi

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


@code("SA00256")
@category("repository")
@objective("correctness")
def test_real_index_is_current():
    """src/sdgtools/README.md matches the headers of the real scripts, which is the
    check the pre-commit hook runs."""
    assert bi.main(["--check", "--quiet"]) == 0
