"""
Script:      build_index.py
Description: Generates docs/commands.md, the page that says what every installed
             command does and how to run it, from the header block of the file
             each command runs, so the page is derived rather than maintained.

             A hand-written index is a second place the same facts live, and it
             disagrees with reality the first time someone edits a script and
             forgets it. The same reasoning produced check_facts.py, which
             re-derives every stated number, and acquire_sources, which
             replaced a README code block that nothing executed.

             The commands are the ones pyproject.toml installs, listed in its
             [project.scripts] table. Each one names a module and a function,
             such as sdg.sources.acquire_sources:main, and the module's file
             under src/ holds the header block. The page groups the commands
             under a heading for each package, in the order COMMAND_GROUPS
             gives: the pipeline commands from src/sdg/, the repo tools from
             src/sdgtools/ and the validation commands from src/sdgval/. A
             package with no command gets no heading. A file that no command
             runs, such as a pytest plugin in src/sdgval/, is not on the page.

             It refuses to write the page when pyproject.toml names a command
             the page cannot place, or when a command's header block is missing
             or lacks a field, because a page built from either would be wrong.
             Holding every header to the rule in
             .claude/rules/writing_python_files.md is the job of verify_headers,
             which reads a header with the parser in this file.

             Only the Description and Usage fields reach the page, and only the
             first paragraph of Description. The page is a directory pointing at
             the files, not a copy of them, and the full header stays the single
             place to read the detail.

Inputs:      pyproject.toml        (read-only, the [project.scripts] table)
             the file under src/ that each command runs
                                   (read-only, parsed rather than imported)

Outputs:     docs/commands.md, overwritten in full on every run.
             Writes nothing under --check.

Usage:       build_index
                 regenerate docs/commands.md
             build_index --check
                 report whether the file on disk is current; write nothing.
                 The pre-commit hook runs it this way.
             build_index --quiet
                 print nothing; use the exit code

Exit codes:  0   the command succeeded (the page was written, or --check found
                 it current)
             1   Python stopped on an error that nothing handled
             2   the argument parser refused the command line
             13  a file on disk cannot be read (pyproject.toml)
             15  docs/commands.md is stale or missing (--check only)
             17  a header block is missing, incomplete, out of order, or has a
                 bad Date (here only a missing or incomplete block; field order
                 and the Date are confirmed by verify_headers)
             19  a Python file could not be parsed (it is not valid Python, or
                 is not saved as UTF-8 text)
             20  no files were found to work on (pyproject.toml installs no
                 command)
             64  a required file was read but holds the wrong content
                 (pyproject.toml cannot be parsed, its [project.scripts] table
                 is not a list of commands, or it names a command whose file
                 does not exist or whose package has no heading on the page)
             64 outranks 19, 19 outranks 17, and 17 outranks 15. The list of
             commands decides which headers are read, and a page generated
             from a wrong list or an incomplete header would be wrong rather
             than merely out of date.
             The numbers are the repo-wide table in
             docs/exit_codes.csv.

Date:        2026-08-24
Owner:       Jason Delosh
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

# Resolved from this file's own location rather than the working directory, so
# the page is the same whichever folder the command is run from. This file sits in
# src/sdgtools/, two folders below the repo root.
REPO_ROOT = Path(__file__).resolve().parents[2]

# The page, the settings file that lists the commands, and the folder their code is
# in, each relative to the repo root. They are joined to REPO_ROOT when the command
# runs, so a check can point the command at a staged repo by changing REPO_ROOT
# alone.
INDEX_NAME = "docs/commands.md"
PYPROJECT_NAME = "pyproject.toml"
SOURCE_NAME = "src"


#######################################################################################
### Settings ###

# Every field .claude/rules/writing_python_files.md requires. Presence is confirmed
# for all of them, though only Description and Usage are printed. Confirming the full
# set is the point: a script that documents what it does but not what it writes still
# fails.
REQUIRED_FIELDS = (
    "Script",
    "Description",
    "Inputs",
    "Outputs",
    "Usage",
    "Exit codes",
    "Date",
    "Owner",
)

# The heading each installed package's commands appear under, in the order the page
# shows them. A command from a package missing here is refused, so a new package
# is given its heading before its commands can reach the page.
COMMAND_GROUPS = {
    "sdg": "Pipeline commands",
    "sdgtools": "Repo tools",
    "sdgval": "Validation commands",
}

# A field starts at column 0 with a capitalised label and a colon. Continuation
# lines are indented, which is what separates a real field from a colon
# appearing inside prose.
FIELD_RE = re.compile(r"^([A-Z][A-Za-z ]*):[ \t]*(.*)$")

# Written into the generated file so nobody edits it by hand and loses the edit
# on the next run.
GENERATED_NOTICE = (
    "This page is generated by `build_index` from the header block of each "
    "command's file. An edit made here is lost on the next run, so change the "
    "header block and run `build_index` instead."
)


#######################################################################################
### Header parsing ###


@dataclass(frozen=True)
class HeaderProblem:
    """One reason a script's header block cannot be read, with the exit code it carries.

    The code travels with the message from where the problem is found, so the exit
    code never depends on how the message is worded.
    """

    message: str
    code: int


def parse_header(
    path: Path,
) -> tuple[dict[str, list[str]] | None, HeaderProblem | None]:
    """Read one script's header block.

    The file is parsed with ast rather than imported, so reading a script never runs it.
    That matters because these scripts touch the network and the filesystem, and
    building an index must not. Field values are kept as lists of raw lines with the
    common indent stripped, because Usage relies on relative indentation to show which
    explanation belongs to which invocation.

    Args:
        path: The script to read.

    Returns:
        A pair of the fields and the problem found, exactly one of which is None. The
            fields map each header field to its lines. A file that cannot be parsed
            carries exit code 19, and a file with no docstring carries 17.
    """
    # A file that will not parse is reported rather than raised, so that one bad
    # script does not hide the state of the rest. A file saved in another text
    # encoding fails while it is decoded, before Python reads it, and is reported
    # the same way, because its fix is also to repair the file itself.
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError as exc:
        return None, HeaderProblem(
            f"cannot parse, because it is not saved as UTF-8 text ({exc})", 19
        )
    except (SyntaxError, OSError) as exc:
        return None, HeaderProblem(f"cannot parse ({exc})", 19)

    docstring = ast.get_docstring(tree, clean=False)

    if not docstring:
        return None, HeaderProblem("no module docstring, so no header block", 17)

    fields: dict[str, list[str]] = {}
    current: str | None = None

    for line in docstring.splitlines():
        match = FIELD_RE.match(line)

        if match:
            current = match.group(1)
            fields[current] = [match.group(2)]
            continue

        # Anything else belongs to the field above it. Lines before the first
        # field are dropped; there are none in this repo's convention, but a
        # stray line should not become a phantom field.
        if current is not None:
            fields[current].append(line)

    return fields, None


def dedent_value(lines: list[str]) -> list[str]:
    """Strip the common leading indent from a field's continuation lines.

    The header aligns continuations under the value column, so every line after the
    first carries the same wide indent. Removing exactly that much preserves the extra
    indentation that Usage uses to attach an explanation to the invocation above it.

    Args:
        lines: The field's lines, the first one already stripped.

    Returns:
        The same lines with the common indent removed.
    """
    # The first line already has its indent consumed by the field label, so it
    # is excluded when measuring.
    continuations = [line for line in lines[1:] if line.strip()]

    if not continuations:
        return [lines[0].rstrip()]

    common = min(len(line) - len(line.lstrip()) for line in continuations)

    dedented = [lines[0].rstrip()] + [line[common:].rstrip() for line in lines[1:]]

    # Trailing blanks come from the blank line separating this field from the
    # next one in the source header. They would render as an empty line inside
    # the generated code block.
    while dedented and not dedented[-1]:
        dedented.pop()

    return dedented


def first_paragraph(lines: list[str]) -> str:
    """Give a field's first paragraph as one unwrapped line.

    Descriptions are hard-wrapped in the source header and run to several paragraphs.
    The index wants the opening one only, joined back into a single line, because this
    repo's markdown is one paragraph per line so that grep can match a phrase.

    Args:
        lines: The field's lines.

    Returns:
        The first paragraph as one line.
    """
    paragraph: list[str] = []

    for line in lines:
        if not line.strip():
            # A blank line ends the first paragraph, but only once something has
            # been collected, so a header that starts with a blank line is fine.
            if paragraph:
                break
            continue

        paragraph.append(line.strip())

    return " ".join(paragraph)


#######################################################################################
### Reading the list of commands ###


@dataclass(frozen=True)
class Command:
    """One installed command, with the package it belongs to and the file it runs."""

    name: str
    package: str
    path: Path


def read_commands() -> tuple[list[Command], list[HeaderProblem]]:
    """Read the installed commands from the [project.scripts] table of pyproject.toml.

    Each entry maps a command's name to the module and function it runs, as in
    sdg.sources.acquire_sources:main. The module's file is found by turning the dots
    of its name into folders under src/. Every entry is looked at before returning, so
    one run names every command the page cannot place rather than stopping at the
    first.

    Returns:
        A pair of the commands, in name order, and the problems found. A
            pyproject.toml that cannot be read carries exit code 13. One that cannot
            be parsed, or that names a command the page cannot place, carries 64.
    """
    pyproject = REPO_ROOT / PYPROJECT_NAME

    # A missing or unreadable file and a file whose content is not TOML, the
    # settings format pyproject.toml is written in, have different fixes, so each
    # is reported with its own exit code.
    try:
        settings = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as exc:
        return [], [HeaderProblem(f"{PYPROJECT_NAME} cannot be read ({exc})", 13)]
    except tomllib.TOMLDecodeError as exc:
        return [], [HeaderProblem(f"{PYPROJECT_NAME} cannot be parsed ({exc})", 64)]

    scripts = settings.get("project", {}).get("scripts", {})

    if not isinstance(scripts, dict) or not all(
        isinstance(target, str) for target in scripts.values()
    ):
        return [], [
            HeaderProblem(
                f"the [project.scripts] table of {PYPROJECT_NAME} must name each "
                "command with the module and function it runs, as in "
                "sdg.sources.acquire_sources:main",
                64,
            )
        ]

    commands: list[Command] = []
    problems: list[HeaderProblem] = []

    for name in sorted(scripts):
        module = scripts[name].split(":")[0].strip()
        package = module.split(".")[0]
        path = REPO_ROOT / SOURCE_NAME / Path(*module.split(".")).with_suffix(".py")

        if package not in COMMAND_GROUPS:
            problems.append(
                HeaderProblem(
                    f"{PYPROJECT_NAME} installs {name} from the package {package}, "
                    "which has no heading on the page. Add the package to "
                    "COMMAND_GROUPS in src/sdgtools/build_index.py.",
                    64,
                )
            )
            continue

        if not path.is_file():
            problems.append(
                HeaderProblem(
                    f"{PYPROJECT_NAME} installs {name} from {module}, but "
                    f"{_shown(path)} does not exist. Correct the entry in "
                    f"{PYPROJECT_NAME} or restore the file.",
                    64,
                )
            )
            continue

        commands.append(Command(name, package, path))

    return commands, problems


def _shown(path: Path) -> str:
    """Write a path the way a message shows it, relative to the repo root.

    Args:
        path: A path inside the repo.

    Returns:
        The path from the repo root, written with forward slashes.
    """
    return path.relative_to(REPO_ROOT).as_posix()


#######################################################################################
### Rendering ###


def render(entries: list[tuple[Command, dict[str, list[str]]]]) -> str:
    """Build the whole of docs/commands.md from the parsed headers.

    The text is handed back rather than written, so that --check can compare it against
    the file on disk without a temporary file.

    Args:
        entries: One pair per command, the command and its header fields, in name
            order.

    Returns:
        The complete markdown text of the page.
    """
    out = [
        "# Commands",
        "",
        GENERATED_NOTICE,
        "",
        f"Every command below is listed in `{PYPROJECT_NAME}` and is installed with "
        "the project into the `sdg` conda environment, so a person can run it from "
        "the repo root. The pre-commit hook, whose steps are in "
        "`.pre-commit-config.yaml`, runs some of them, and the checks under "
        "`validation/` run others.",
        "",
        "Each entry gives the first paragraph of the Description in the command's "
        "header block, and the header's Usage field. The header block is the full "
        "account of the command's inputs, outputs and exit codes.",
        "",
    ]

    # The groups follow the order COMMAND_GROUPS gives, and a group with no command
    # gets no heading, so the page never shows an empty section.
    for package, heading in COMMAND_GROUPS.items():
        group = [entry for entry in entries if entry[0].package == package]

        if not group:
            continue

        out.append(f"## {heading}")
        out.append("")

        for command, fields in group:
            out.append(f"### {command.name}")
            out.append("")
            out.append(first_paragraph(dedent_value(fields["Description"])))
            out.append("")
            out.append(f"Its header block is in `{_shown(command.path)}`.")
            out.append("")
            out.append("```")
            out.extend(line for line in dedent_value(fields["Usage"]))
            out.append("```")
            out.append("")

    # Exactly one trailing newline, so a regenerated file compares equal to
    # itself and --check does not fail on whitespace.
    return "\n".join(out).rstrip("\n") + "\n"


#######################################################################################
### Command line ###


def main(argv: list[str] | None = None) -> int:
    """Read the list of commands and each header, then write the page or compare it on disk.

    Problems are collected across all commands before returning, so one run names
    every command that needs fixing rather than stopping at the first.

    Args:
        argv: The command-line arguments, or None to read the real ones.

    Returns:
        The exit code, as the header block lists them.
    """
    parser = argparse.ArgumentParser(
        description="Generate docs/commands.md from each command's header block."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="report whether the page is current; write nothing",
    )
    parser.add_argument(
        "--quiet", action="store_true", help="print nothing; use the exit code"
    )
    args = parser.parse_args(argv)

    def say(message: str = "") -> None:
        """Print the message, unless the run is quiet.

        Args:
            message: The line to print. Empty prints a blank line.
        """
        if not args.quiet:
            print(message)

    commands, listing = read_commands()

    # A pyproject.toml that cannot be read leaves no list to work from, so the run
    # stops there.
    if any(problem.code == 13 for problem in listing):
        say(listing[0].message)
        return 13

    if not commands and not listing:
        say(f"{PYPROJECT_NAME} installs no commands")
        return 20

    entries: list[tuple[Command, dict[str, list[str]]]] = []
    unparseable: list[str] = []
    incomplete: list[str] = []

    for command in commands:
        fields, error = parse_header(command.path)

        if error:
            # A file that cannot be parsed is a broken file, and a missing
            # docstring is a broken header. They are kept apart because they need
            # different fixes, and the exit code each carries says which it is.
            (unparseable if error.code == 19 else incomplete).append(
                f"{_shown(command.path)}: {error.message}"
            )
            continue

        # parse_header hands back either the fields or an error, never neither,
        # so once the error is handled the fields are present. mypy cannot see the
        # two halves of the pair move together, hence the assertion.
        assert fields is not None

        missing = [field for field in REQUIRED_FIELDS if field not in fields]

        if missing:
            incomplete.append(
                f"{_shown(command.path)}: header missing {', '.join(missing)}"
            )
            continue

        entries.append((command, fields))

    for message in [problem.message for problem in listing] + unparseable + incomplete:
        say(message)

    if listing:
        return 64

    if unparseable:
        return 19

    if incomplete:
        say()
        say(
            "The rule in .claude/rules/writing_python_files.md requires the full header block on every script. Page not written."
        )
        return 17

    generated = render(entries)
    index_path = REPO_ROOT / INDEX_NAME

    if args.check:
        current = (
            index_path.read_text(encoding="utf-8") if index_path.exists() else None
        )

        if current == generated:
            say(f"{INDEX_NAME} is current, {len(entries)} command(s)")
            return 0

        say(f"{INDEX_NAME} is stale. Run: build_index")
        return 15

    # Written with a bare line feed (LF) ending each line, as
    # validation/validation_inventory.csv is and as git stores it, so the file does
    # not flip line endings with whichever machine last regenerated it.
    index_path.write_text(generated, encoding="utf-8", newline="\n")
    say(f"{INDEX_NAME} written, {len(entries)} command(s)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
