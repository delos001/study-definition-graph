"""
Script:      test_select_checks_conformance.py
Description: The conformance checks for src/sdgval/select_checks.py. They confirm
             that the real groups file it reads, validation/validation_groups.yml,
             follows its rules. The technical checks are in
             test_select_checks_technical.py, and the integrity checks in
             test_select_checks_integrity.py, beside this file.

Inputs:      validation/validation_groups.yml     (read-only)
             validation/validation_inventory.csv (read-only)

Outputs:     Writes nothing to disk.

Usage:       pytest validation/sdgval/test_select_checks_conformance.py
                 run these checks
             pytest validation/sdgval/test_select_checks_conformance.py -v
                 one line per check with its result

Exit codes:  None of its own. It runs inside pytest.

Date:        2026-09-26
Owner:       Jason Delosh
"""

from __future__ import annotations

import csv
from pathlib import Path

from sdgval.build_inventory import INVENTORY_PATH, OUT_OF_USE
from sdgval.labels import category, code, objective
from validation.shared.validation_groups import read_groups

#######################################################################################
### The conformance checks ###


@code("SA00511")
@category("repository")
@objective("conformance")
def test_every_group_lists_only_ids_the_inventory_holds():
    """Every id each group in validation/validation_groups.yml lists is a check
    validation/validation_inventory.csv lists as in use, so no group names a check
    that does not exist."""
    with Path(INVENTORY_PATH).open(encoding="utf-8", newline="") as fh:
        known = {
            row["id"]
            for row in csv.DictReader(fh)
            if row.get("status") not in OUT_OF_USE
        }
    unknown = {
        name: sorted(set(map(str, group.get("ids") or [])) - known)
        for name, group in read_groups().items()
    }
    assert not {name: ids for name, ids in unknown.items() if ids}
