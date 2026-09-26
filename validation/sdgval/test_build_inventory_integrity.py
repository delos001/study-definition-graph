"""
Script:      test_build_inventory_integrity.py
Description: The integrity checks for src/sdgval/build_inventory.py. The technical checks are
             in test_build_inventory_technical.py, beside this file.

Inputs:      See each check. A check that reads a real pinned file names it with
             @needs_pinned.

Outputs:     Writes nothing to disk. Temporary files go to pytest's own folder.

Usage:       pytest validation/sdgval/test_build_inventory_integrity.py
                 run these checks
             pytest validation/sdgval/test_build_inventory_integrity.py -v
                 one line per check with its result

Exit codes:  pytest's own: 0 all passed, 1 some failed

Date:        2026-09-24
Owner:       Jason Delosh
"""

from __future__ import annotations

from sdgval import build_inventory as script
from sdgval.labels import category, code, objective

#######################################################################################
### The integrity checks ###


@code("SA00391")
@category("repository")
@objective("correctness")
def test_real_inventory_is_current():
    """validation/validation_inventory.csv matches the checks in the real test files,
    which is the run the pre-commit hook makes."""
    assert script.main(["--check", "--quiet"]) == 0
