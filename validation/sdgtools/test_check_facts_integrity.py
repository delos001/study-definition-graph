"""
Script:      test_check_facts_integrity.py
Description: The integrity checks for src/sdgtools/check_facts.py. The technical checks are
             in test_check_facts_technical.py, beside this file.

Inputs:      See each check. A check that reads a real pinned file names it with
             @needs_pinned.

Outputs:     Writes nothing to disk. Temporary files go to pytest's own folder.

Usage:       pytest validation/sdgtools/test_check_facts_integrity.py
                 run these checks
             pytest validation/sdgtools/test_check_facts_integrity.py -v
                 one line per check with its result

Exit codes:  None of its own. It runs inside pytest.

Date:        2026-09-24
Owner:       Jason Delosh
"""

from __future__ import annotations

import pytest

from sdg.usdm.usdm_spec import PINNED_LOCAL
from sdgtools import check_facts as cf
from sdgval.labels import category, code, objective

# The real run reads the pinned files its measurements need: the USDM model file, the
# USDM export under each worked example, and the concepts workbook.
# src/sdgval/skip_rules.py skips the real-run check when any of them is not downloaded
# or no longer matches its manifest entry.
needs_pinned_file = pytest.mark.needs_pinned(
    PINNED_LOCAL,
    "inputs/worked_examples/*/*.json",
    "inputs/standards/cdisc/biomedical_concepts_*/cdisc_biomedical_concepts.xlsx",
)


#######################################################################################
### The integrity checks ###


@code("SA00283")
@category("repository")
@objective("correctness")
@needs_pinned_file
def test_real_documents_match_real_corpus():
    """Against the pinned files and the committed documents, every stated figure is
    measured again and matches, and the run exits 0. It is skipped as blocked when a
    pinned file it reads has changed."""
    assert cf.main([]) == 0
