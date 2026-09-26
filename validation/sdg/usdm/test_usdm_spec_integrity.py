"""
Script:      test_usdm_spec_integrity.py
Description: The integrity checks for src/sdg/usdm/usdm_spec.py. The technical checks are
             in test_usdm_spec_technical.py, beside this file.

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

from sdg.usdm import usdm_spec
from sdgval.labels import category, code, needs_fixture, objective
from validation.shared.usdm_model import FIXTURE, FIXTURE_CLASSES, needs_pinned_file

#######################################################################################
### The integrity checks ###


@code("SA00155")
@category("repository")
@objective("correctness")
@needs_pinned_file
@needs_fixture("usdm_three_classes.yml")
def test_fixture_classes_are_identical_to_pinned():
    """Each class in the small fixture file matches the same class in the pinned model
    entry for entry, so the checks that ran on the fixture ran on real USDM shapes."""
    pinned = usdm_spec.load()
    sample = usdm_spec.load(FIXTURE, verify=False)
    for name in FIXTURE_CLASSES:
        assert sample[name] == pinned[name], name
