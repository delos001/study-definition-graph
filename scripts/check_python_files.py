"""
Script:      check_python_files.py
Description: Runs the three tool checks every Python file must pass, in order:
             ruff format in check mode, ruff check, and mypy. Each tool's own
             output is printed as it runs, so a failure names the file and the
             line. All three are configured in pyproject.toml; this script adds
             nothing to what they check.

             The git pre-commit hook runs it. ruff and mypy live in the sdg
             conda environment, so when they are not on the path, as in a
             terminal where that environment is not active, each is run through
             conda instead, which is slower but needs no set-up.

Inputs:      pyproject.toml and every Python file under src/, scripts/ and
             tests/   (read-only)

Outputs:     Nothing on disk. Prints each tool's report, then one line per tool
             saying whether it passed.

Usage:       python scripts/check_python_files.py
                 run all three checks, report each, exit non-zero if any failed
             python scripts/check_python_files.py --quiet
                 print only the tools' own reports and the final verdict lines

Exit codes:  0  every tool passed
             1  at least one tool reported a problem
             2  a tool could not be run at all, neither on the path nor
                through conda

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

REPO_ROOT = Path(__file__).resolve().parents[1]

# Each entry is the tool's name and the arguments it is run with. mypy takes
# its file list from pyproject.toml, so it needs none here.
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


#######################################################################################
### Run the checks ###


def main(argv: list[str] | None = None) -> int:
    """Run the three tools in order and report each one's verdict.

    Every tool runs even after one fails, so a single run shows everything
    that needs fixing rather than the first problem alone.

    Args:
        argv: The command-line arguments, or None to read the real ones.

    Returns:
        The exit code: 0 when every tool passed, 1 when any reported a
        problem, 2 when a tool could not be run at all.
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

    failed: list[str] = []
    for name, tool_argv in CHECKS:
        command = command_for(tool_argv)
        if command is None:
            print(
                f"{name}: cannot run; neither {tool_argv[0]} nor conda is on the path"
            )
            print("  fix -> conda activate sdg, or install conda")
            return 2
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

    return 1 if failed else 0


#######################################################################################
### Command line ###

if __name__ == "__main__":
    sys.exit(main())
