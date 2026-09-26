"""
Script:      test_check_python_files_conformance.py
Description: The conformance checks for src/sdgtools/check_python_files.py. They run
             the tool on the real repo, the same run the pre-commit hook makes, so a
             commit the hook refused for style or types can be diagnosed with
             pytest --group hook. The technical checks are in
             test_check_python_files_technical.py, beside this file.

Inputs:      src/**, validation/**, .claude/hooks/**   (read-only; ruff formats in
                 check mode, so nothing is rewritten)

Outputs:     Writes nothing to disk.

Usage:       pytest validation/sdgtools/test_check_python_files_conformance.py
                 run these checks
             pytest --group hook
                 run them with the rest of what the pre-commit hook enforces

Exit codes:  pytest's own: 0 all passed, 1 some failed

Date:        2026-09-26
Owner:       Jason Delosh
"""

from __future__ import annotations

from sdgtools import check_python_files as script
from sdgval.labels import category, code, objective

#######################################################################################
### The conformance checks ###


@code("SA00538")
@category("repository")
@objective("conformance")
def test_every_python_file_passes_the_style_and_type_tools(capsys):
    """Every Python file in the real repo passes the formatter in check mode, the
    style rules and the type checker, which is the run the pre-commit hook makes."""
    assert script.main([]) == 0, capsys.readouterr().out
