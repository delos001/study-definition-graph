"""
Script:      check_python_files.py
Description: Runs the three tool checks every Python file must pass, in order:
             ruff format in check mode, ruff check, and mypy. Each tool's own
             output is printed as it runs, so a failure names the file and the
             line. All three are configured in pyproject.toml; this script adds
             nothing to what they confirm.

             The git pre-commit hook runs it. ruff and mypy live in the sdg
             conda environment, so when they are not on the path, as in a
             terminal where that environment is not active, each is run through
             conda instead, which is slower but needs no set-up.

             Before any tool runs, each one is asked for its version. A tool
             that cannot answer is reported as one that could not be run, so a
             missing tool or environment is never mistaken for a problem in the
             code.

             ruff is pointed at the whole repo, and the include setting in
             pyproject.toml limits it to the Python files in the three folders
             below. mypy takes the same folders from its files setting there.

Inputs:      pyproject.toml and every Python file under src/, validation/ and
             .claude/hooks/   (read-only)

Outputs:     Nothing on disk. Prints each tool's report, then one line per tool
             saying whether it passed.

Usage:       check_python_files
                 run all three checks, report each, exit non-zero if any failed
             check_python_files --quiet
                 print only the tools' own reports and the final verdict lines

Exit codes:  0   the command succeeded (every tool passed)
             1   Python stopped on an error that nothing handled
             2   the argument parser refused the command line
             21  ruff or mypy reported a problem
             22  a tool could not be run at all (neither it nor conda is on
                 the path, or it did not answer when asked for its version)
             The numbers are the repo-wide table in
             docs/exit_codes.csv.

Date:        2026-09-11
Owner:       Jason Delosh
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

#######################################################################################
### Where the tools are ###
#
# The three commands, and how to reach them when the sdg environment is not
# the active one.

REPO_ROOT = Path(__file__).resolve().parents[2]

# Each entry is the tool's name and the arguments it is run with. ruff is given
# the repo root, and the include setting in pyproject.toml narrows it to the code
# folders. mypy takes its file list from pyproject.toml, so it needs none here.
CHECKS: tuple[tuple[str, list[str]], ...] = (
    ("ruff format", ["ruff", "format", "--check", "."]),
    ("ruff check", ["ruff", "check", "."]),
    ("mypy", ["mypy"]),
)


def command_for(argv: list[str]) -> list[str] | None:
    """Work out how to run one tool from this terminal.

    Args:
        argv: The tool's command line, starting with the tool's name.

    Returns:
        The command line to run: the tool itself when it is on the path, or the
        same command wrapped in conda run when it is not. None when neither the
        tool nor conda can be found.
    """
    if shutil.which(argv[0]):
        return argv
    # Not on the path, so the sdg environment is not active. conda run
    # activates it for one command without changing this terminal.
    if shutil.which("conda"):
        return ["conda", "run", "-n", "sdg", "--no-capture-output", *argv]
    return None


def can_start(program: str) -> bool:
    """Confirm that one tool starts, by asking it for its version.

    A tool that is missing from the sdg environment, or an environment that does not
    exist, makes conda run fail. Without this question that failure would look the
    same as a tool that found a problem in the code.

    Args:
        program: The tool's command name, such as ruff or mypy.

    Returns:
        True when the tool answered with its version, False when it could not be
        started or answered with an error.
    """
    command = command_for([program, "--version"])
    if command is None:
        return False
    # A program that the system cannot launch at all raises OSError. That is the
    # same answer as a tool that fails to report its version, so it gives False.
    try:
        result = subprocess.run(command, cwd=REPO_ROOT, capture_output=True)
    except OSError:
        return False
    return result.returncode == 0


#######################################################################################
### Run the checks ###


def main(argv: list[str] | None = None) -> int:
    """Run the three tools in order and report each one's verdict.

    Every tool is confirmed to start before any of them runs. Every tool then
    runs even after one fails, so a single run shows everything that needs fixing
    rather than the first problem alone.

    Args:
        argv: The command-line arguments, or None to read the real ones.

    Returns:
        The exit code, as the header block lists them: 0 when every tool passed,
        21 when any reported a problem, 22 when a tool could not be run at all.
    """
    parser = argparse.ArgumentParser(
        description="Run ruff format, ruff check and mypy over the repo."
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="print only the tools' own reports and the verdict lines",
    )
    args = parser.parse_args(argv)

    # Every tool is found and confirmed to start before any runs, so a tool that
    # cannot start stops the run before a report is half printed. ruff appears
    # twice in CHECKS, and it is asked for its version once.
    commands: list[tuple[str, list[str]]] = []
    started: dict[str, bool] = {}
    for name, tool_argv in CHECKS:
        program = tool_argv[0]
        command = command_for(tool_argv)
        if command is None:
            print(f"{name}: cannot run; neither {program} nor conda is on the path")
            print("  fix -> conda activate sdg, or install conda")
            return 22
        if program not in started:
            started[program] = can_start(program)
        if not started[program]:
            print(
                f"{name}: cannot run; {program} did not answer when asked for its version"
            )
            print(
                "  fix -> confirm the sdg environment exists and holds the tool, or recreate it from environment.yml"
            )
            return 22
        commands.append((name, command))

    failed: list[str] = []
    for name, command in commands:
        if not args.quiet:
            print(f"--- {name}")
        # The tool prints straight to this terminal, so its report is not
        # buffered or reshaped; only the exit code is read here.
        result = subprocess.run(command, cwd=REPO_ROOT)
        if result.returncode != 0:
            failed.append(name)

    for name, _ in CHECKS:
        verdict = "FAILED" if name in failed else "passed"
        print(f"{name}: {verdict}")

    return 21 if failed else 0


#######################################################################################
### Command line ###

if __name__ == "__main__":
    sys.exit(main())
