"""
Script:      test_verify_headers_conformance.py
Description: The conformance checks for src/sdgtools/verify_headers.py. The technical checks are
             in test_verify_headers_technical.py, beside this file.

Inputs:      See each check. A check that reads a real pinned file names it with
             @needs_pinned.

Outputs:     Writes nothing to disk. Temporary files go to pytest's own folder.

Usage:       pytest validation/sdgtools/test_verify_headers_conformance.py
                 run these checks
             pytest validation/sdgtools/test_verify_headers_conformance.py -v
                 one line per check with its result

Exit codes:  None of its own. It runs inside pytest.

Date:        2026-09-24
Owner:       Jason Delosh
"""

from __future__ import annotations

from sdgtools import verify_headers as script
from sdgval.labels import category, code, objective

#######################################################################################
### The conformance checks ###


@code("SA00373")
@category("repository")
@objective("conformance")
def test_real_headers_follow_the_rule():
    """Every Python file in the real code folders has a header block with the eight
    fields in order and a valid Date, as .claude/rules/writing_python_files.md
    requires."""
    table = script.exit_code_table()
    problems = {
        path.relative_to(script.REPO_ROOT).as_posix(): script.problems_in(path, table)[
            0
        ]
        for path in script.files_to_check()
    }
    assert {name: found for name, found in problems.items() if found} == {}


@code("SA00374")
@category("repository")
@objective("conformance")
def test_real_exit_codes_agree_with_the_table_and_main():
    """In every Python file in the real code folders, each exit code the header lists
    has the number, sub-code and wording docs/exit_codes.csv gives it, each exit number
    and sub-code the code names together is a row of that table, and each one a command
    ends on is listed in its header."""
    table = script.exit_code_table()
    problems = {
        path.relative_to(script.REPO_ROOT).as_posix(): script.problems_in(path, table)[
            1
        ]
        for path in script.files_to_check()
    }
    assert {name: found for name, found in problems.items() if found} == {}


@code("SA00375")
@category("repository")
@objective("conformance")
def test_every_code_folder_is_checked():
    """The header tool covers the three folders .claude/rules/writing_python_files.md
    names, so a file added under any of them is held to the header rule. The check holds
    its own copy of the three."""
    covered = {
        folder.relative_to(script.REPO_ROOT).as_posix()
        for folder in script.CHECKED_FOLDERS
    }
    assert covered == {"src", "validation", ".claude/hooks"}
