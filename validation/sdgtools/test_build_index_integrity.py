"""
Script:      test_build_index_integrity.py
Description: The integrity checks for src/sdgtools/build_index.py. The technical checks are
             in test_build_index_technical.py, beside this file.

Inputs:      See each check. A check that reads a real pinned file names it with
             @needs_pinned.

Outputs:     Writes nothing to disk. Temporary files go to pytest's own folder.

Usage:       pytest validation/sdgtools/test_build_index_integrity.py
                 run these checks
             pytest validation/sdgtools/test_build_index_integrity.py -v
                 one line per check with its result

Exit codes:  None of its own. It runs inside pytest.

Date:        2026-09-24
Owner:       Jason Delosh
"""

from __future__ import annotations

from sdgtools import build_index as bi
from sdgval.labels import category, code, objective

#######################################################################################
### The integrity checks ###


@code("SA00256")
@category("repository")
@objective("correctness")
def test_real_index_is_current():
    """docs/commands.md matches the headers of the real commands that pyproject.toml
    installs, which is the run the pre-commit hook makes."""
    assert bi.main(["--check", "--quiet"]) == 0
