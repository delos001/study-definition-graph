"""
Script:      test_read_manifests_conformance.py
Description: The conformance checks for src/sdg/sources/read_manifests.py. The operation checks are
             in test_read_manifests_operation.py, beside this file.

Inputs:      See each check. A check that reads a real pinned file names it with
             @needs_pinned.

Outputs:     Writes nothing to disk. Temporary files go to pytest's own folder.

Usage:       pytest validation/sdg/sources/test_read_manifests_conformance.py
                 run these checks
             pytest validation/sdg/sources/test_read_manifests_conformance.py -v
                 one line per check with its result

Exit codes:  pytest's own: 0 all passed, 1 some failed

Date:        2026-09-24
Owner:       Jason Delosh
"""

from __future__ import annotations

import pytest

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


@code("SA00078")
@category("repository")
@objective("conformance")
def test_every_manifest_lands_under_inputs(real_manifests):
    """Every real manifest, wherever it sits under manifests/, says its files land
    under inputs/."""
    for manifest in real_manifests:
        assert manifest.local_dir.startswith("inputs/"), manifest.name


@code("SA00079")
@category("repository")
@objective("conformance")
def test_every_entry_carries_the_five_required_fields(real_manifests):
    """Every entry in every real manifest has a name, a url, a local path under
    inputs/, a size above zero, and a 64-character sha256."""
    for manifest in real_manifests:
        assert manifest.entries, manifest.name
        for entry in manifest.entries:
            assert entry.name
            assert entry.url
            assert entry.local.startswith("inputs/")
            assert entry.bytes > 0
            assert len(entry.sha256) == 64
