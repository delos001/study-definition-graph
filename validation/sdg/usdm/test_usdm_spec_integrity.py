"""
Script:      test_usdm_spec_integrity.py
Description: The integrity checks for src/sdg/usdm/usdm_spec.py. The operation checks are
             in test_usdm_spec_operation.py, beside this file.

Inputs:      See each check. A check that reads a real pinned file names it with
             @needs_pinned.

Outputs:     Writes nothing to disk. Temporary files go to pytest's own folder.

Usage:       pytest validation/sdg/usdm/test_usdm_spec_integrity.py
                 run these checks
             pytest validation/sdg/usdm/test_usdm_spec_integrity.py -v
                 one line per check with its result

Exit codes:  pytest's own: 0 all passed, 1 some failed

Date:        2026-09-24
Owner:       Jason Delosh
"""

from __future__ import annotations

import pytest
from validation.shared.usdm_model import FIXTURE, FIXTURE_CLASSES, needs_pinned_file

from sdg.usdm import usdm_spec

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


@code("SA00155")
@category("repository")
@objective("correctness")
@needs_pinned_file
def test_fixture_classes_are_identical_to_pinned():
    """Each class in the small fixture file is identical, key for key, to the same
    class in the pinned model, so the checks that ran on the fixture ran on real
    USDM shapes and not on an approximation of them."""
    pinned = usdm_spec.load()
    sample = usdm_spec.load(FIXTURE, verify=False)
    for name in FIXTURE_CLASSES:
        assert sample[name] == pinned[name], name
