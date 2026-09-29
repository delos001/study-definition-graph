"""
Script:      test_check_python_files_technical.py
Description: Checks for src/sdgtools/check_python_files.py, the tool the pre-commit
             hook runs to hold every Python file to ruff format, ruff check and
             mypy. Each check stands in for the two things the tool reaches
             outside itself, the search for a tool on the path and the running
             of a command, so that whether each tool starts and what it would
             have reported are decided by the check. It then runs the tool's main() in-process
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

Exit codes:  None of its own. It runs inside pytest.

Date:        2026-09-16
Owner:       Jason Delosh
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace

import pytest

from sdg.exit_codes import exit_line
from sdgtools import check_python_files as script
from sdgval.labels import category, code, negative, objective, positive

TOOLS = ("ruff format", "ruff check", "mypy")


#######################################################################################
### Shared staging ###
#
# One fixture replaces the tool search and the command runner with stand-ins that a
# check controls. A check decides which programs are on the path, which programs fail
# to start, and which tools report a problem. The stand-in records every command so
# a check can see what would have run. It keeps the version questions the tool asks
# before running anything apart from the tool runs themselves.


@dataclass
class Stage:
    """What a check told the stand-ins, and what the tool then did."""

    on_path: set[str]
    failing: set[str] = field(default_factory=set)
    not_answering: set[str] = field(default_factory=set)
    not_launching: set[str] = field(default_factory=set)
    commands: list[list[str]] = field(default_factory=list)
    cwds: list[object] = field(default_factory=list)
    version_questions: list[list[str]] = field(default_factory=list)


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

    By default every program is on the path, starts, and passes. A check changes
    the stage's sets before running the tool.

    Returns:
        The stage, which the check adjusts and then reads.
    """
    staged = Stage(on_path={"ruff", "mypy", "conda"})

    def which(name: str) -> str | None:
        """Say where a tool is, for the tools the check staged as being on the path."""
        return f"/bin/{name}" if name in staged.on_path else None

    def run(
        command: list[str], cwd: Path | None = None, capture_output: bool = False
    ) -> SimpleNamespace:
        """Record the command instead of running it, and answer with the staged result."""
        if "--version" in command:
            staged.version_questions.append(list(command))
            program = command[command.index("--version") - 1]
            if program in staged.not_launching:
                raise FileNotFoundError(program)
            return SimpleNamespace(
                returncode=1 if program in staged.not_answering else 0
            )
        staged.commands.append(list(command))
        staged.cwds.append(cwd)
        failed = tool_of(command) in staged.failing
        return SimpleNamespace(returncode=1 if failed else 0)

    monkeypatch.setattr(script.shutil, "which", which)
    monkeypatch.setattr(script.subprocess, "run", run)
    return staged


def run_tool(capsys: pytest.CaptureFixture[str], *argv: str) -> Outcome:
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


@code("SA00625")
@category("repository")
@objective("functionality")
@positive
def test_the_formatter_runs_in_check_mode(stage, capsys):
    """The formatter runs in check mode, so a file that is not formatted is reported
    and never rewritten."""
    run_tool(capsys)
    (formatter,) = [c for c in stage.commands if tool_of(c) == "ruff format"]
    assert "--check" in formatter


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
def test_a_failing_tool_exits_15_and_is_named(stage, capsys):
    """When one tool reports a problem, the run exits 15, and that tool's line says
    FAILED while the others say passed."""
    stage.failing = {"ruff check"}
    outcome = run_tool(capsys)
    assert outcome.exit_code == 15
    assert exit_line(15, "RUFF-OR-MYPY-PROBLEM") in outcome.printed
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
def test_no_tool_and_no_conda_exits_6(stage, capsys):
    """When neither the tool nor conda is on the path, the run exits 6, names the
    tool, gives the fix, and runs nothing."""
    stage.on_path = set()
    outcome = run_tool(capsys)
    assert outcome.exit_code == 6
    assert exit_line(6, "TOOL-NOT-FOUND") in outcome.printed
    assert "ruff format: cannot run" in outcome.printed
    assert "conda activate sdg" in outcome.printed
    assert stage.commands == []


# Each way a tool on the path, or reached through conda, can fail to start. Each
# entry holds the programs on the path, the program that does not answer when asked
# for its version, and the program the system cannot launch at all.
FAILED_STARTS = [
    pytest.param({"conda"}, {"mypy"}, set(), id="conda run cannot start mypy in sdg"),
    pytest.param(
        {"ruff", "mypy", "conda"},
        {"ruff"},
        set(),
        id="ruff on the path answers with an error",
    ),
    pytest.param(
        {"ruff", "mypy", "conda"},
        set(),
        {"mypy"},
        id="mypy on the path cannot be launched",
    ),
]


@code("SA00539")
@category("repository")
@objective("functionality")
@negative
@pytest.mark.parametrize(("on_path", "not_answering", "not_launching"), FAILED_STARTS)
def test_a_tool_that_does_not_start_exits_7_and_is_named(
    stage, capsys, on_path, not_answering, not_launching
):
    """When a tool does not answer when asked for its version, the run exits 7,
    names that tool and says to confirm or recreate the sdg environment. Each run
    stages one way a tool can fail to start: through conda, on the path with an
    error, or not launchable at all."""
    stage.on_path = on_path
    stage.not_answering = not_answering
    stage.not_launching = not_launching
    program = next(iter(not_answering | not_launching))
    outcome = run_tool(capsys)
    assert outcome.exit_code == 7
    assert exit_line(7, "TOOL-FAILED-TO-START") in outcome.printed
    assert f"cannot run; {program} did not answer" in outcome.printed
    assert "recreate it from environment.yml" in outcome.printed


@code("SA00540")
@category("repository")
@objective("functionality")
@negative
def test_no_tool_runs_when_one_does_not_start(stage, capsys):
    """When mypy, the last tool, does not start, neither ruff run is made, so a report
    is never half printed."""
    stage.not_answering = {"mypy"}
    run_tool(capsys)
    assert stage.commands == []
