"""
Script:      validation_groups.py
Description: Reads the real groups file, validation/validation_groups.yml, for the
             checks that confirm the groups are right. It is shared by the
             conformance and integrity checks of src/sdgval/select_checks.py, so it
             lives in validation/shared/ rather than in either check file.

Inputs:      validation/validation_groups.yml (read-only)

Outputs:     Nothing on disk. Hands back the groups by name.

Usage:       from validation.shared.validation_groups import read_groups
                 use in a check of src/sdgval/select_checks.py

Exit codes:  None of its own. It is imported by the checks.

Date:        2026-09-29
Owner:       Jason Delosh
"""

from __future__ import annotations

import yaml

from sdgval.build_inventory import REPO_ROOT

#######################################################################################
### The groups file ###


def read_groups() -> dict[str, dict]:
    """Read the real groups file.

    Returns:
        The groups by name, as the file writes them.
    """
    path = REPO_ROOT / "validation" / "validation_groups.yml"
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
