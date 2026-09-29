"""
Script:      test_check_python_files_conformance.py
Description: The conformance checks for src/sdgtools/check_python_files.py. One
             runs the tool on the real repo, the same run the pre-commit hook
             makes, so a commit the hook refused for style or types can be
             diagnosed with pytest --group hook_conformance. The other confirms
             that each tool which holds the Python files to the rule covers the
             folders the rule names. The technical checks are in
             test_check_python_files_technical.py, beside this file.

Inputs:      src/**, validation/**, .claude/hooks/**   (read-only; ruff formats in
                 check mode, so nothing is rewritten)
             .claude/rules/writing_python_files.md and pyproject.toml   (read-only)

Outputs:     Writes nothing to disk.

Usage:       pytest validation/sdgtools/test_check_python_files_conformance.py
                 run these checks
             pytest --group hook_integrity,hook_conformance
                 run them with the rest of what the pre-commit hook enforces

Exit codes:  None of its own. It runs inside pytest.

Date:        2026-09-26
Owner:       Jason Delosh
"""

from __future__ import annotations

import tomllib

import pytest
import yaml

from sdgtools import check_python_files as script
from sdgtools import verify_headers
from sdgval.labels import category, code, objective

RULE = script.REPO_ROOT / ".claude" / "rules" / "writing_python_files.md"
PYPROJECT = script.REPO_ROOT / "pyproject.toml"

#######################################################################################
### The conformance checks ###


@code("SA00538")
@category("repository")
@objective("conformance")
def test_every_python_file_passes_the_style_and_type_tools(capsys):
    """Every Python file in the real repo passes the formatter in check mode, the
    style rules and the type checker, which is the run the pre-commit hook makes."""
    assert script.main([]) == 0, capsys.readouterr().out


#######################################################################################
### The tools cover the folders the rule names ###
#
# .claude/rules/writing_python_files.md opens with a paths list, which says which
# Python files the rule covers. Each tool that holds those files to the rule keeps
# its own list of folders, in pyproject.toml or in its own code. The check reads the
# rule's list as the reference and compares each tool's list with it.


def rule_patterns() -> set[str]:
    """Read the file patterns the rule covers from its opening block.

    Returns:
        The patterns, such as src/**/*.py.
    """
    front_matter = RULE.read_text(encoding="utf-8").split("---")[1]
    return set(yaml.safe_load(front_matter)["paths"])


def folder_of(pattern: str) -> str:
    """Give the folder a pattern such as src/**/*.py starts from.

    Args:
        pattern: A file pattern or a folder name.

    Returns:
        The folder, written with forward slashes and no trailing slash.
    """
    return pattern.split("/**")[0].rstrip("/")


def tool_folders(tool: str) -> set[str]:
    """Read the folders one tool covers, from pyproject.toml or from its code.

    Args:
        tool: The name of the setting to read, as the check's run names it.

    Returns:
        The folders that setting covers, written relative to the repo root.
    """
    settings = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["tool"]
    if tool == "ruff include":
        return set(settings["ruff"]["include"])
    if tool == "ruff src":
        return {folder_of(f) for f in settings["ruff"]["src"]}
    if tool == "mypy files":
        return {folder_of(f) for f in settings["mypy"]["files"]}
    if tool == "coverage source":
        return {folder_of(f) for f in settings["coverage"]["run"]["source"]}
    return {
        folder.relative_to(script.REPO_ROOT).as_posix()
        for folder in verify_headers.CHECKED_FOLDERS
    }


def expected_folders(tool: str) -> set[str]:
    """Say what one tool's list should hold, given the rule's paths list.

    ruff's include setting holds the rule's patterns themselves. coverage leaves out
    validation/, for the reason the comment beside its source setting in
    pyproject.toml gives. Every other list holds the rule's folders.

    Args:
        tool: The name of the setting, as the check's run names it.

    Returns:
        The patterns or folders the setting should hold.
    """
    if tool == "ruff include":
        return rule_patterns()
    folders = {folder_of(pattern) for pattern in rule_patterns()}
    if tool == "coverage source":
        return folders - {"validation"}
    return folders


@code("SA00541")
@category("repository")
@objective("conformance")
@pytest.mark.parametrize(
    "tool",
    ["ruff include", "ruff src", "mypy files", "verify_headers", "coverage source"],
)
def test_each_tool_covers_the_folders_the_rule_names(tool):
    """Each tool that holds the Python files to .claude/rules/writing_python_files.md
    covers the folders in the rule's paths list, and no others, so a file the rule
    covers is never missed and no other file is judged by it. It runs once for each
    tool setting: ruff's include and src settings, mypy's files, the folders
    verify_headers reads, and coverage's source, which leaves out validation/."""
    assert tool_folders(tool) == expected_folders(tool)
