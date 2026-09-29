"""
Script:      test_deny_pinned_edits_conformance.py
Description: The conformance checks for the Claude Code hooks in .claude/hooks/,
             beginning with deny_pinned_edits.py, the only hook so far. pytest and
             mypy put .claude/hooks/ on the import path, so a hook is imported by
             its bare file name. A hook named like another Python module, such as
             yaml.py, would hide that module from every check, or be hidden by it.
             The check here confirms that no hook's name is taken. It runs once for
             every hook in the folder, so a new hook is covered without an edit
             here. The technical checks are in test_deny_pinned_edits_technical.py,
             beside this file.

Inputs:      The file names in .claude/hooks/, and the Python import path of the
             running interpreter   (read-only)

Outputs:     Writes nothing to disk.

Usage:       pytest validation/claude_hooks/test_deny_pinned_edits_conformance.py
                 run these checks
             pytest validation/claude_hooks/test_deny_pinned_edits_conformance.py -v
                 one line per check with its result

Exit codes:  None of its own. It runs inside pytest.

Date:        2026-09-28
Owner:       Jason Delosh
"""

from __future__ import annotations

import os
import sys
from importlib.machinery import PathFinder
from pathlib import Path

import pytest

from sdgval.labels import category, code, objective

HOOKS_DIR = Path(__file__).resolve().parents[2] / ".claude" / "hooks"


def same_folder(entry: str, folder: Path) -> bool:
    """Say whether one entry of the import path is the given folder.

    Args:
        entry: One entry of sys.path. An empty entry means the current folder.
        folder: The folder to compare it with.

    Returns:
        True when both name the same folder, whatever the case of the letters.
    """
    resolved = Path(entry or ".").resolve()
    return os.path.normcase(resolved) == os.path.normcase(folder.resolve())


#######################################################################################
### The conformance checks ###


@code("SA00542")
@category("repository")
@objective("conformance")
@pytest.mark.parametrize("name", sorted(p.stem for p in HOOKS_DIR.glob("*.py")))
def test_no_other_module_has_a_hooks_name(name):
    """No built-in or standard library module, and no module anywhere else on the
    import path, has the same name as a hook in .claude/hooks/, so importing the hook
    by its bare name finds the hook and nothing else. It runs once for each hook,
    named by its file name without the .py ending."""
    elsewhere = [entry for entry in sys.path if not same_folder(entry, HOOKS_DIR)]
    assert name not in sys.builtin_module_names
    assert name not in sys.stdlib_module_names
    assert PathFinder.find_spec(name, elsewhere) is None
