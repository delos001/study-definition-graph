"""
Script:      test_check_import_loops_technical.py
Description: Checks for src/sdgtools/check_import_loops.py, the repo tool the
             pre-commit hook runs to refuse a commit in which two files of the
             project's packages import each other. Each check writes a small
             package into pytest's own temporary folder, points the tool at it,
             runs main() in-process, and asserts the exit code or what was
             printed. The run over the real packages is in
             test_check_import_loops_conformance.py, beside this file.

Inputs:      Nothing real. Each staged package is written to pytest's own
             temporary folder.

Outputs:     Writes nothing outside pytest's own temporary folder.

Usage:       pytest validation/sdgtools/test_check_import_loops_technical.py
                 run these checks
             pytest validation/sdgtools/test_check_import_loops_technical.py -v
                 one line per check with its result

Exit codes:  None of its own. It runs inside pytest.

Date:        2026-09-29
Owner:       Jason Delosh
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from sdg.exit_codes import exit_line
from sdgtools import check_import_loops as script
from sdgval.labels import category, code, negative, objective, positive

#######################################################################################
### Shared staging ###
#
# One fixture writes a small package whose files import one another as a check
# chooses, puts its folder where Python looks for packages, and points the tool at it.


@dataclass(frozen=True)
class Outcome:
    """What one run of the tool produced."""

    exit_code: int
    printed: str


@pytest.fixture
def package(tmp_path, monkeypatch):
    """Give a check a function for writing a staged package the tool reads.

    Returns:
        The staging function, which takes source text keyed by file name and writes
            each file into a package called staged_pkg.
    """
    folder = tmp_path / "staged_pkg"
    folder.mkdir()
    (folder / "__init__.py").write_text("", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setattr(script, "PACKAGES", ("staged_pkg",))

    def make(files: dict[str, str]) -> None:
        """Write the given files into the staged package.

        Args:
            files: The files to write, source text keyed by file name.
        """
        for name, source in files.items():
            (folder / name).write_text(source, encoding="utf-8")

    return make


def run(capsys: pytest.CaptureFixture[str], *argv: str) -> Outcome:
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


@code("SA00667")
@category("repository")
@objective("functionality")
@positive
def test_a_package_with_no_loop_exits_0_and_prints_nothing(package, capsys):
    """A package whose files import one another only in one direction makes the run
    exit 0, and nothing is printed."""
    package(
        {
            "a.py": "from staged_pkg import b\n",
            "b.py": "from staged_pkg import c\n",
            "c.py": "VALUE = 1\n",
        }
    )
    outcome = run(capsys)
    assert outcome.exit_code == 0
    assert outcome.printed == ""


#######################################################################################
### Negative checks ###
#
# Each staged package holds one loop, and the run names the files in it, in the order
# they import each other.


@code("SA00668")
@category("repository")
@objective("functionality")
@negative
@pytest.mark.parametrize(
    ("files", "loop"),
    [
        (
            {
                "a.py": "from staged_pkg import b\n",
                "b.py": "from staged_pkg import a\n",
            },
            "staged_pkg.a -> staged_pkg.b -> staged_pkg.a",
        ),
        (
            {
                "a.py": "from staged_pkg import b\n",
                "b.py": "from staged_pkg import c\n",
                "c.py": "from staged_pkg import a\n",
            },
            "staged_pkg.a -> staged_pkg.b -> staged_pkg.c -> staged_pkg.a",
        ),
        (
            {
                "a.py": "from staged_pkg import b\n",
                "b.py": "def later():\n    from staged_pkg import a\n",
            },
            "staged_pkg.a -> staged_pkg.b -> staged_pkg.a",
        ),
    ],
    ids=["two files", "through a third file", "an import inside a function"],
)
def test_a_loop_exits_24_naming_its_files(package, capsys, files, loop):
    """A package holding an import loop makes the run exit 24, and the line names the
    files of the loop in the order they import each other and says how to break it. It
    runs once for two files importing each other, once for a loop through a third file,
    and once for a loop made by an import written inside a function."""
    package(files)
    outcome = run(capsys)
    assert outcome.exit_code == 24
    assert exit_line(24, "IMPORT-LOOP") in outcome.printed
    assert f"IMPORT-LOOP  {loop}" in outcome.printed
    assert "move what both files need into a file of its own" in outcome.printed


@code("SA00669")
@category("repository")
@objective("functionality")
@negative
def test_quiet_loop_exits_24_and_prints_nothing(package, capsys):
    """With the quiet option, a package holding an import loop still makes the run exit
    24, and nothing is printed."""
    package(
        {"a.py": "from staged_pkg import b\n", "b.py": "from staged_pkg import a\n"}
    )
    outcome = run(capsys, "--quiet")
    assert outcome.exit_code == 24
    assert outcome.printed == ""
