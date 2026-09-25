"""
Script:      test_check_python_files_technical.py
Description: Checks for src/sdgtools/check_python_files.py, the tool the pre-commit
             hook runs to hold every Python file to ruff format, ruff check and
             mypy. Each check stands in for the two things the tool reaches
             outside itself, the search for a tool on the path and the running
             of a command, so that what each tool would have reported is
             decided by the check. It then runs the tool's main() in-process
             and asserts the exit code, the verdict lines, or the commands that
             would have run.

             No check runs ruff or mypy for real, so the checks are fast and do
             not depend on which environment is active.

Inputs:      Nothing real. The tool search and the command runner are replaced by
             stand-ins.

Outputs:     Writes nothing to disk.

Usage:       pytest validation/sdgtools/test_check_python_files_technical.py
                 run these checks
             pytest validation/sdgtools/test_check_python_files_technical.py -v
                 one line per check with its result

Exit codes:  pytest's own: 0 all passed, 1 some failed

Date:        2026-09-16
Owner:       Jason Delosh
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace

import pytest

from sdgtools import check_python_files as script

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

TOOLS = ("ruff format", "ruff check", "mypy")


#######################################################################################
### Shared staging ###
#
# One fixture replaces the tool search and the command runner with stand-ins that a
# check controls: which programs are on the path, and which tools report a problem.
# The stand-in records every command so a check can see what would have run.


@dataclass
class Stage:
    """What a check told the stand-ins, and what the tool then did."""

    on_path: set[str]
    failing: set[str] = field(default_factory=set)
    commands: list[list[str]] = field(default_factory=list)
    cwds: list[object] = field(default_factory=list)


@dataclass(frozen=True)
class Outcome:
    """What one run of the tool produced."""

    exit_code: int
    printed: str


def tool_of(command: list[str]) -> str:
    """Name the tool a command runs, whether or not it is wrapped in conda run.

    Args:
        command: The command line the tool would have run.

    Returns:
        One of the three tool names.
    """
    if "mypy" in command:
        return "mypy"
    return "ruff format" if "format" in command else "ruff check"


@pytest.fixture
def stage(monkeypatch) -> Stage:
    """Replace the tool search and the command runner with stand-ins.

    By default every program is on the path and every tool passes. A check changes
    the stage's sets before running the tool.

    Returns:
        The stage, which the check adjusts and then reads.
    """
    staged = Stage(on_path={"ruff", "mypy", "conda"})

    def which(name: str) -> str | None:
        """Say where a tool is, for the tools the check staged as being on the path."""
        return f"/bin/{name}" if name in staged.on_path else None

    def run(command: list[str], cwd=None):
        """Record the command instead of running it, and answer with the staged result."""
        staged.commands.append(list(command))
        staged.cwds.append(cwd)
        failed = tool_of(command) in staged.failing
        return SimpleNamespace(returncode=1 if failed else 0)

    monkeypatch.setattr(script.shutil, "which", which)
    monkeypatch.setattr(script.subprocess, "run", run)
    return staged


def run_tool(capsys, *argv: str) -> Outcome:
    """Run the tool in-process with the given arguments.

    Args:
        capsys: pytest's capture of what was printed.
        *argv: The command-line arguments to hand the tool.

    Returns:
        The exit code and what was printed, as an Outcome.
    """
    exit_code = script.main(list(argv))
    return Outcome(exit_code, capsys.readouterr().out)


#######################################################################################
### Positive checks ###
#
# The right thing works: three passing tools give exit 0 with a verdict line each, the
# tools run in the set order from the repo root, a tool that is not on the path is
# reached through conda, and the quiet option drops only the progress lines.


@code("SA00307")
@category("repository")
@objective("functionality")
@positive
def test_all_passing_exits_0(stage, capsys):
    """When every tool passes, the run exits 0."""
    assert run_tool(capsys).exit_code == 0


@code("SA00308")
@category("repository")
@objective("functionality")
@positive
def test_each_tool_gets_a_verdict_line(stage, capsys):
    """Every tool gets its own line saying it passed."""
    printed = run_tool(capsys).printed
    for name in TOOLS:
        assert f"{name}: passed" in printed


@code("SA00309")
@category("repository")
@objective("functionality")
@positive
def test_the_tools_run_in_the_set_order(stage, capsys):
    """The three tools run in the order ruff format, ruff check, mypy, so the
    formatter's report comes before the linter's and the type checker's."""
    run_tool(capsys)
    assert [tool_of(command) for command in stage.commands] == list(TOOLS)


@code("SA00310")
@category("repository")
@objective("functionality")
@positive
def test_the_tools_run_from_the_repo_root(stage, capsys):
    """Every tool runs from the repo root, so pyproject.toml is found whichever folder
    the tool was started from."""
    run_tool(capsys)
    assert stage.cwds == [script.REPO_ROOT] * len(TOOLS)


@code("SA00311")
@category("repository")
@objective("functionality")
@positive
def test_a_tool_off_the_path_is_run_through_conda(stage, capsys):
    """When ruff and mypy are not on the path but conda is, each runs through conda
    in the sdg environment instead."""
    stage.on_path = {"conda"}
    assert run_tool(capsys).exit_code == 0
    for command in stage.commands:
        assert command[:5] == ["conda", "run", "-n", "sdg", "--no-capture-output"]


@code("SA00312")
@category("repository")
@objective("functionality")
@positive
def test_quiet_keeps_the_verdicts_and_drops_the_progress_lines(stage, capsys):
    """With the quiet option, the line announcing each tool is left out but the
    verdict lines stay."""
    printed = run_tool(capsys, "--quiet").printed
    assert "---" not in printed
    for name in TOOLS:
        assert f"{name}: passed" in printed


#######################################################################################
### Negative checks ###
#
# The wrong thing is refused: a tool that reports a problem fails the run and is named,
# the other tools still run so one pass shows everything, and a tool that cannot be
# run at all is its own exit code with the fix.


@code("SA00313")
@category("repository")
@objective("functionality")
@negative
def test_a_failing_tool_exits_21_and_is_named(stage, capsys):
    """When one tool reports a problem, the run exits 21 and that tool's verdict line
    says FAILED while the others say passed."""
    stage.failing = {"ruff check"}
    outcome = run_tool(capsys)
    assert outcome.exit_code == 21
    assert "ruff check: FAILED" in outcome.printed
    assert "ruff format: passed" in outcome.printed
    assert "mypy: passed" in outcome.printed


@code("SA00314")
@category("repository")
@objective("functionality")
@negative
def test_every_tool_still_runs_after_one_fails(stage, capsys):
    """When the first tool fails, the other two still run, so one run shows everything
    that needs fixing."""
    stage.failing = {"ruff format"}
    run_tool(capsys)
    assert [tool_of(command) for command in stage.commands] == list(TOOLS)


@code("SA00315")
@category("repository")
@objective("functionality")
@negative
def test_no_tool_and_no_conda_exits_22(stage, capsys):
    """When neither the tool nor conda is on the path, the run exits 22, names the
    tool, gives the fix, and runs nothing."""
    stage.on_path = set()
    outcome = run_tool(capsys)
    assert outcome.exit_code == 22
    assert "ruff format: cannot run" in outcome.printed
    assert "conda activate sdg" in outcome.printed
    assert stage.commands == []
