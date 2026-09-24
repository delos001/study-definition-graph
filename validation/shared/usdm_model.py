"""
Script:      usdm_model.py
Description: Names the two USDM model files the checks of the model loader read: the
             small stand-in model in validation/fixtures/, and the real pinned
             model file, which a check reading it names with @needs_pinned.

Inputs:      Nothing on disk.

Outputs:     Nothing on disk.

Usage:       from validation.shared.usdm_model import FIXTURE, needs_pinned_file
                 use in a check of src/sdg/usdm/usdm_spec.py

Exit codes:  None of its own. It is imported by the checks.

Date:        2026-09-24
Owner:       Jason Delosh
"""

from __future__ import annotations

from pathlib import Path

import pytest

#######################################################################################
### The model files ###

# The small stand-in model, and the classes it holds.
FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "usdm_three_classes.yml"
FIXTURE_CLASSES = ("Condition", "Identifier", "StudyIdentifier")

# The real-file checks read the pinned model file. src/sdgval/skip_rules.py skips them
# when it is not downloaded, as on a fresh clone, or when it no longer matches its
# manifest entry, rather than fail and hide the logic checks' results.
needs_pinned_file = pytest.mark.needs_pinned(
    "inputs/standards/cdisc/usdm_v4/dataStructure.yml"
)
