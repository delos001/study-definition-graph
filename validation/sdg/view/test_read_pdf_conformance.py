"""
Script:      test_read_pdf_conformance.py
Description: The conformance checks for src/sdg/view/read_pdf.py. They confirm that
             the real list of documents it can open, src/sdg/view/lookup_documents.yml,
             follows its rules. The technical checks are in test_read_pdf_technical.py,
             beside this file.

Inputs:      src/sdg/view/lookup_documents.yml (read-only)
             manifests/*.json                  (read-only)

Outputs:     Writes nothing to disk.

Usage:       pytest validation/sdg/view/test_read_pdf_conformance.py
                 run these checks
             pytest validation/sdg/view/test_read_pdf_conformance.py -v
                 one line per check with its result

Exit codes:  None of its own. It runs inside pytest.

Date:        2026-09-26
Owner:       Jason Delosh
"""

from __future__ import annotations

import yaml

from sdg.sources import read_manifests
from sdg.view import read_pdf
from sdgval.labels import category, code, objective

#######################################################################################
### The conformance checks ###


@code("SA00513")
@category("repository")
@objective("conformance")
def test_every_listed_document_is_recorded_by_a_manifest():
    """Every file src/sdg/view/lookup_documents.yml lists is recorded by a manifest, as
    the list's own rules require, so read_pdf never meets an entry it cannot find."""
    listed = yaml.safe_load(read_pdf.REGISTRY_FILE.read_text(encoding="utf-8"))
    recorded = {
        entry.name
        for manifest in read_manifests.manifests()
        for entry in manifest.entries
    }
    missing = [
        doc["file"] for doc in listed["documents"] if doc["file"] not in recorded
    ]
    assert not missing
