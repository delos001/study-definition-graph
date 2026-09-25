"""
Script:      test_usdm_spec_conformance.py
Description: The conformance checks for src/sdg/usdm/usdm_spec.py. The technical checks are
             in test_usdm_spec_technical.py, beside this file.

Inputs:      See each check. A check that reads a real pinned file names it with
             @needs_pinned.

Outputs:     Writes nothing to disk. Temporary files go to pytest's own folder.

Usage:       pytest validation/sdg/usdm/test_usdm_spec_conformance.py
                 run these checks
             pytest validation/sdg/usdm/test_usdm_spec_conformance.py -v
                 one line per check with its result

Exit codes:  pytest's own: 0 all passed, 1 some failed

Date:        2026-09-24
Owner:       Jason Delosh
"""

from __future__ import annotations

import pytest

from sdg.usdm import usdm_spec
from validation.shared.usdm_model import needs_pinned_file

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
### The conformance checks ###


@code("SA00153")
@category("sources")
@objective("conformance")
@needs_pinned_file
def test_pinned_file_is_shaped_the_way_the_loader_expects():
    """The pinned dataStructure.yml passes the loader's two shape checks, so what
    src/sdg/usdm/usdm_spec.py expects of USDM v4 matches the real file. The file is
    read without the checksum step, which the stability check for it covers."""
    assert usdm_spec.load(verify=False)


@code("SA00154")
@category("sources")
@objective("conformance")
@needs_pinned_file
def test_pinned_file_types_are_classes_or_five_primitives():
    """Every attribute type in the pinned model is a class in the model or one of
    the five primitives the docstring of targets() names, and exactly four
    attributes reference more than one type. The check compares with its own copy of
    the five and the four, not with the docstring itself."""
    spec = usdm_spec.load()
    primitives = set()
    multi = []
    for cname, body in spec.items():
        for aname, attr in body["Attributes"].items():
            refs = usdm_spec.targets(attr)
            if len(refs) > 1:
                multi.append(f"{cname}.{aname}")
            primitives.update(r for r in refs if r not in spec)
    assert primitives == {"string", "boolean", "integer", "float", "date"}
    assert sorted(multi) == [
        "Condition.appliesToIds",
        "Condition.contextIds",
        "ProductOrganizationRole.appliesToIds",
        "StudyRole.appliesToIds",
    ]
