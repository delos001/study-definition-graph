"""
Script:      test_check_import_loops_conformance.py
Description: Confirms the real packages under src/ follow the rule that no two
             files import each other, by running the same reading of the imports
             src/sdgtools/check_import_loops.py makes when the pre-commit hook runs
             it. The staged checks of the tool itself are in
             test_check_import_loops_technical.py, beside this file.

Inputs:      src/sdg/**/*.py, src/sdgtools/**/*.py and src/sdgval/**/*.py
                                        (read-only, parsed by grimp, never run)

Outputs:     Writes nothing to disk.

Usage:       pytest validation/sdgtools/test_check_import_loops_conformance.py
                 run this check

Exit codes:  None of its own. It runs inside pytest.

Date:        2026-09-29
Owner:       Jason Delosh
"""

from __future__ import annotations

from sdgtools import check_import_loops as script
from sdgval.labels import category, code, objective

#######################################################################################
### The conformance check ###


@code("SA00670")
@category("repository")
@objective("conformance")
def test_the_real_packages_have_no_import_loop():
    """No two files of the packages under src/ import each other, directly or through
    other files."""
    imports = script.import_map(script.PACKAGES)
    assert [
        script.one_loop(group, imports) for group in script.loop_groups(imports)
    ] == []
