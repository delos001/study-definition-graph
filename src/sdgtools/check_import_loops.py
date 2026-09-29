"""
Script:      check_import_loops.py
Description: Confirms that no two files of the project's packages import each
             other, directly or through other files, and names the files in each
             loop it finds.

             A loop means one of its files is always half loaded when another in
             the loop needs it, so the code works only by the order the files
             happen to be imported in. The pre-commit hook runs this tool, so a
             commit that adds a loop is refused before it lands.

             It reads the imports with grimp, an established library that maps
             which file of a package imports which, rather than with a reader of
             the project's own. An import written inside a function counts,
             because it still makes a loop. It covers the three packages under
             src/: sdg, sdgtools and sdgval. The check files under validation/
             and the Claude Code hooks are left out, because nothing in the
             packages imports them.

Inputs:      src/sdg/**/*.py, src/sdgtools/**/*.py and src/sdgval/**/*.py
                                        (read-only, parsed by grimp, never run)

Outputs:     Nothing on disk, and no cache for grimp either. Prints one line per
             loop, starting with its sub-code, and an exit line, or nothing when
             there is no loop.

Usage:       check_import_loops
                 confirm the packages have no import loop, and name each one found
             check_import_loops --quiet
                 print nothing; use the exit code

Exit codes:  0   SUCCEEDED  the command succeeded (no two files import each
                 other)
             1   UNHANDLED-ERROR  Python stopped on an error that nothing
                 handled
             2   COMMAND-LINE-REFUSED  the argument parser refused the command
                 line
             24  IMPORT-LOOP  two or more files import each other, directly or
                 through other files
             The wording is the table in docs/exit_codes.csv.

Date:        2026-09-29
Owner:       Jason Delosh
"""

from __future__ import annotations

import argparse
import sys
from collections import deque

# grimp is declared in environment.yml. It reads a package's import statements
# without running any of its code.
import grimp

from sdg.exit_codes import finish, problem_line

#######################################################################################
### Settings ###

# The packages whose files may not import each other in a loop.
PACKAGES = ("sdg", "sdgtools", "sdgval")


#######################################################################################
### Finding the loops ###


def import_map(packages: tuple[str, ...]) -> dict[str, set[str]]:
    """Read which file of the packages imports which.

    Args:
        packages: The names of the packages to read.

    Returns:
        Each file, named as Python names it, such as sdgval.labels, with the files
            of the same packages it imports.
    """
    # With no cache folder, grimp writes nothing to disk.
    graph = grimp.build_graph(*packages, cache_dir=None)
    return {
        module: set(graph.find_modules_directly_imported_by(module))
        for module in graph.modules
    }


def loop_groups(imports: dict[str, set[str]]) -> list[list[str]]:
    """Find each set of files that reach one another through their imports.

    Two files are in the same set when each can be reached from the other by
    following imports. Every set of more than one file holds a loop, and so does a
    file that imports itself. This is Tarjan's method for finding such sets, which
    looks at each import once.

    Args:
        imports: Each file with the files it imports.

    Returns:
        Each set that holds a loop, its files sorted, the sets sorted by their
            first file.
    """
    index_of: dict[str, int] = {}
    lowest: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    groups: list[list[str]] = []

    def visit(module: str) -> None:
        """Walk the imports from one file, closing a set when the walk returns to it.

        Args:
            module: The file to walk from.
        """
        index_of[module] = lowest[module] = len(index_of)
        stack.append(module)
        on_stack.add(module)
        for imported in sorted(imports.get(module, ())):
            if imported not in index_of:
                visit(imported)
                lowest[module] = min(lowest[module], lowest[imported])
            elif imported in on_stack:
                lowest[module] = min(lowest[module], index_of[imported])
        if lowest[module] == index_of[module]:
            group = []
            while True:
                member = stack.pop()
                on_stack.discard(member)
                group.append(member)
                if member == module:
                    break
            if len(group) > 1 or module in imports.get(module, ()):
                groups.append(sorted(group))

    for module in sorted(imports):
        if module not in index_of:
            visit(module)
    return sorted(groups)


def one_loop(group: list[str], imports: dict[str, set[str]]) -> list[str]:
    """Trace one loop through a set of files that reach one another.

    The loop starts and ends at the set's first file and takes the fewest steps,
    so the line a person reads is as short as it can be.

    Args:
        group: A set of files that reach one another, sorted.
        imports: Each file with the files it imports.

    Returns:
        The files in the order they import each other, the first file repeated at
            the end.
    """
    start = group[0]
    members = set(group)
    came_from: dict[str, str] = {}
    queue = deque([start])
    while queue:
        module = queue.popleft()
        for imported in sorted(imports.get(module, set()) & members):
            if imported == start:
                path = [module]
                while path[-1] != start:
                    path.append(came_from[path[-1]])
                return [*reversed(path), start]
            if imported not in came_from:
                came_from[imported] = module
                queue.append(imported)
    return [start, start]


#######################################################################################
### Command line ###


def main(argv: list[str] | None = None) -> int:
    """Read the packages' imports and name each loop, unless --quiet.

    Args:
        argv: The command-line arguments, or None to read the real ones.

    Returns:
        The exit code, as the header block lists them.
    """
    parser = argparse.ArgumentParser(
        description="Confirm that no two files of the project's packages import each other."
    )
    parser.add_argument(
        "--quiet", action="store_true", help="print nothing; use the exit code"
    )
    args = parser.parse_args(argv)

    def say(message: str) -> None:
        """Print a line, unless --quiet was given."""
        if not args.quiet:
            print(message)

    imports = import_map(PACKAGES)
    groups = loop_groups(imports)
    for group in groups:
        say(
            problem_line(
                "IMPORT-LOOP",
                " -> ".join(one_loop(group, imports))
                + "\n  fix -> move what both files need into a file of its own, "
                "which each can import",
            )
        )
    if groups:
        return finish(say, 24, "IMPORT-LOOP")
    return 0


if __name__ == "__main__":
    sys.exit(main())
