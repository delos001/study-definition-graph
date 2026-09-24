"""
Script:      test_verify_headers_conformance.py
Description: The conformance checks for src/sdgtools/verify_headers.py. The operation checks are
             in test_verify_headers_operation.py, beside this file.

Inputs:      See each check. A check that reads a real pinned file names it with
             @needs_pinned.

Outputs:     Writes nothing to disk. Temporary files go to pytest's own folder.

Usage:       pytest validation/sdgtools/test_verify_headers_conformance.py
                 run these checks
             pytest validation/sdgtools/test_verify_headers_conformance.py -v
                 one line per check with its result

Exit codes:  pytest's own: 0 all passed, 1 some failed

Date:        2026-09-24
Owner:       Jason Delosh
"""

from __future__ import annotations

import pytest

from sdgtools import verify_headers as script

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
    opens with the wording validation/exit_codes.csv gives it, and each code main()
    returns as a plain number is listed."""
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
    """The checker covers the three folders .claude/rules/writing_python_files.md names,
    so a file added under any of them is held to the header block like any other. The
    check compares with its own copy of the three, not with the rule file itself."""
    covered = {
        folder.relative_to(script.REPO_ROOT).as_posix()
        for folder in script.CHECKED_FOLDERS
    }
    assert covered == {"src", "validation", ".claude/hooks"}
