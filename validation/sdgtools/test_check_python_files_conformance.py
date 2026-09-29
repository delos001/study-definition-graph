"""
Script:      test_check_python_files_conformance.py
Description: The conformance checks for src/sdgtools/check_python_files.py. One
             runs the tool on the real repo, the same run the pre-commit hook
             makes, so a commit the hook refused for style or types can be
             diagnosed with pytest --group hook_conformance. Another confirms
             that each tool which holds the Python files to the rule covers the
             folders the rule names. The third confirms the part of the type
             hint rule that mypy cannot, which is that every function in a check
             file or in validation/conftest.py carries its hints unless it is a
             check or a pytest fixture. The technical checks are in
             test_check_python_files_technical.py, beside this file.

Inputs:      src/**, validation/**, .claude/hooks/**   (read-only; ruff formats in
                 check mode, so nothing is rewritten, and pytest only collects
                 the checks under validation/, running none of them)
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

import ast
import tomllib
from pathlib import Path

import pytest
import yaml

from sdgtools import check_python_files as script
from sdgtools import verify_headers
from sdgval import build_inventory
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


#######################################################################################
### Helper functions in check files carry type hints ###
#
# The rule gives every function a hint on each argument and on its return, and
# exempts checks and pytest fixtures. mypy cannot tell a check or a fixture from
# any other function, so pyproject.toml lets code under validation/ leave its hints
# out, and the check below holds every other function there to the rule instead.
# pytest says which functions are checks, through the same collection
# build_inventory makes. A fixture is a function carrying the pytest.fixture
# decorator. Functions nested inside another function, and the methods of a class,
# count as helpers too.

CONFTEST = script.REPO_ROOT / "validation" / "conftest.py"


def collected_checks() -> tuple[list[Path], set[tuple[Path, str]]]:
    """Ask pytest which files under validation/ are check files and which of their
    functions are checks, running none of them.

    Returns:
        Every check file pytest opened, and each check as its file and its function's
        name.
    """
    record, status, printed = build_inventory.collect()
    assert status == 0, printed
    checks = {
        (item.path.resolve(), item.originalname)
        for item in record.items
        if isinstance(item, pytest.Function)
    }
    return [path.resolve() for path in record.files], checks


def is_fixture(function: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Say whether a function carries the pytest.fixture decorator.

    Args:
        function: The function as Python's parser read it.

    Returns:
        True when the decorator is there, with or without arguments.
    """
    for decorator in function.decorator_list:
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        if ast.unparse(target) == "pytest.fixture":
            return True
    return False


def missing_hints(
    function: ast.FunctionDef | ast.AsyncFunctionDef, in_class: bool
) -> list[str]:
    """Name each argument of a function that has no hint, and its return when that has
    none.

    Args:
        function: The function as Python's parser read it.
        in_class: Whether the function is written directly in a class, as a method.

    Returns:
        The names of the arguments without a hint, followed by return when the
        return has none. The list is empty when every hint is there.
    """
    arguments = function.args
    positional = [*arguments.posonlyargs, *arguments.args]
    # A method's first argument is the object or the class it is called on, which
    # takes no hint. A static method has no such argument.
    static = any(ast.unparse(d) == "staticmethod" for d in function.decorator_list)
    if in_class and not static:
        positional = positional[1:]
    others = [arguments.vararg, *arguments.kwonlyargs, arguments.kwarg]
    named = positional + [argument for argument in others if argument is not None]
    missing = [argument.arg for argument in named if argument.annotation is None]
    if function.returns is None:
        missing.append("return")
    return missing


def helpers_without_hints(path: Path, checks: set[tuple[Path, str]]) -> list[str]:
    """Find each function in one file that is neither a check nor a fixture and lacks
    a hint.

    Args:
        path: The check file or conftest.py to read.
        checks: Each check pytest collected, as its file and its function's name.

    Returns:
        One line for each function that lacks a hint, naming the file, the line, the
        function and what has no hint.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    name = path.relative_to(script.REPO_ROOT).as_posix()
    found: list[str] = []

    def visit(node: ast.AST, top_level: bool, in_class: bool) -> None:
        """Look at every function below one point in the file.

        Args:
            node: The part of the file to look inside.
            top_level: Whether that part sits at the top level of the file, where
                checks and fixtures are written.
            in_class: Whether that part is the body of a class.
        """
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                visit(child, False, True)
                continue
            if not isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
                visit(child, top_level, in_class)
                continue
            exempt = top_level and ((path, child.name) in checks or is_fixture(child))
            missing = [] if exempt else missing_hints(child, in_class)
            if missing:
                found.append(
                    f"{name}:{child.lineno} {child.name} has no hint on "
                    + ", ".join(missing)
                )
            visit(child, False, False)

    visit(tree, True, False)
    return found


@code("SA00650")
@category("repository")
@objective("conformance")
def test_helper_functions_in_check_files_carry_type_hints():
    """Every function in a check file or in validation/conftest.py that is neither a
    check nor a pytest fixture carries a type hint on each argument and on its return,
    as .claude/rules/writing_python_files.md requires. That includes a function nested
    inside another and the method of a class."""
    check_files, checks = collected_checks()
    found = [
        line
        for path in [*sorted(check_files), CONFTEST.resolve()]
        for line in helpers_without_hints(path, checks)
    ]
    assert found == [], "\n".join(found)
