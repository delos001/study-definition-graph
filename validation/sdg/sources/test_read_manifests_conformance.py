"""
Script:      test_read_manifests_conformance.py
Description: The conformance checks for src/sdg/sources/read_manifests.py. The technical checks are
             in test_read_manifests_technical.py, beside this file.

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

from sdgval.labels import category, code, objective

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
    """Every entry in every real manifest has a name, an address, a local path under
    inputs/, a size above zero and a well-formed fingerprint."""
    for manifest in real_manifests:
        assert manifest.entries, manifest.name
        for entry in manifest.entries:
            assert entry.name
            assert entry.url
            assert entry.local.startswith("inputs/")
            assert entry.bytes > 0
            assert len(entry.sha256) == 64
