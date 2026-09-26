"""
Script:      test_check_sources_map_integrity.py
Description: The integrity checks for src/sdgtools/check_sources_map.py. The technical checks are
             in test_check_sources_map_technical.py, beside this file.

Inputs:      See each check. A check that reads a real pinned file names it with
             @needs_pinned.

Outputs:     Writes nothing to disk. Temporary files go to pytest's own folder.

Usage:       pytest validation/sdgtools/test_check_sources_map_integrity.py
                 run these checks
             pytest validation/sdgtools/test_check_sources_map_integrity.py -v
                 one line per check with its result

Exit codes:  pytest's own: 0 all passed, 1 some failed

Date:        2026-09-24
Owner:       Jason Delosh
"""

from __future__ import annotations

from sdgtools import check_sources_map as script
from sdgval.labels import category, code, objective

#######################################################################################
### The integrity checks ###


@code("SA00330")
@category("repository")
@objective("completeness")
def test_the_real_map_and_manifests_agree():
    """Nothing is absent from either side of the repo's own sources map,
    docs/sources_index.md: no file a manifest records is left without a heading that
    covers it, and no location the map names is one that no manifest records a file
    in. Either way something that should be accounted for is not."""
    assert script.main(["--quiet"]) == 0
