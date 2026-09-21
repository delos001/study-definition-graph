"""
Script:      select_checks.py
Description: A pytest plugin that selects checks in the inventory's own terms.
             pytest's own selection is by path and by words in names. This adds
             four options, --category, --objective, --id and --group, spelled as
             the columns of validation/validation_inventory.csv are. Each keeps
             only the checks whose marker matches, and --group keeps the checks a
             named group in validation/validation_groups.yml lists. Categories
             and objectives narrow each other, ids and groups add up, and a check
             is kept only when it matches every option given. The rest are
             deselected before the run, so they neither run nor appear in a
             validation report.

             A value that names no category, objective, group or collected check
             stops the run with pytest's usage error rather than running nothing,
             so a typo cannot pass for a clean run.

             It is a plugin rather than part of conftest.py because pytest reads
             the command line before it loads a conftest below the root folder.
             An option a conftest adds is unknown at that moment, and its value is
             taken for a path. pyproject.toml loads this file at startup with
             -p validation.select_checks, so the options are known from the start.

             It also holds the readers for the code, category and objective
             markers, which conftest.py uses when it writes the report.

Inputs:      validation/validation_groups.yml (read-only; only with --group)

Outputs:     Nothing on disk.

Usage:       pytest --category sources
                 run only the checks with that category
             pytest --category sources --objective stability
                 run only the checks with that category and that objective
             pytest --id SRC0128,HRS0018
                 run only the checks with those ids; a comma-separated list, or
                 a repeated option, means any of them
             pytest --group pinned
                 run the checks the named group lists

Exit codes:  pytest's own: 4 bad command line, when a value names no category,
             objective, group or collected check

Date:        2026-09-21
Owner:       Jason Delosh
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from build_inventory import CATEGORIES, OBJECTIVES

#######################################################################################
### Settings ###

# Where the named groups live, under pytest's root folder, which is the repo root
# for a real run and a temporary folder for the plugin's own checks.
GROUPS_RELATIVE = Path("validation") / "validation_groups.yml"

# The options, in the order the report's selection column records them.
SELECTORS = ("category", "objective", "id", "group")


#######################################################################################
### Reading a check's markers ###


def _marker_value(item: pytest.Item, name: str) -> str:
    """Read the text a marker such as @code("XYZ0001") was given.

    Args:
        item: The check.
        name: The marker's name.

    Returns:
        The text, or an empty string when the check carries no such marker.
    """
    marker = item.get_closest_marker(name)
    return str(marker.args[0]) if marker and marker.args else ""


def code_of(item: pytest.Item) -> str:
    """Read a check's permanent id off its code marker.

    Args:
        item: The check.

    Returns:
        The id, or an empty string when the check carries no code marker.
    """
    return _marker_value(item, "code")


def category_of(item: pytest.Item) -> str:
    """Read a check's category off its category marker.

    Args:
        item: The check.

    Returns:
        The category, or an empty string when the check carries no category marker.
    """
    return _marker_value(item, "category")


def objective_of(item: pytest.Item) -> str:
    """Read a check's objective off its objective marker.

    Args:
        item: The check.

    Returns:
        The objective, or an empty string when the check carries no objective marker.
    """
    return _marker_value(item, "objective")


#######################################################################################
### The options ###


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add the four selection options to the pytest command line.

    Each takes a value. Repeating an option, or giving a comma-separated list, means
    any of the values.

    Args:
        parser: pytest's command-line parser.
    """
    for name, meaning in (
        ("category", "run only the checks with this category"),
        ("objective", "run only the checks with this objective"),
        ("id", "run only the check with this id"),
        ("group", "run only the checks the named group lists"),
    ):
        parser.addoption(
            f"--{name}",
            action="append",
            default=None,
            metavar="VALUE",
            help=f"{meaning}; repeat, or give a comma-separated list, for several",
        )


def wanted(config: pytest.Config, name: str) -> list[str]:
    """Read one selection option's values, however they were given.

    Args:
        config: pytest's configuration for the run.
        name: The option's name without its dashes.

    Returns:
        The values in the order given, or an empty list when the option was not used.
    """
    given = config.getoption(name) or []
    return [v.strip() for item in given for v in item.split(",") if v.strip()]


def groups(config: pytest.Config) -> dict[str, dict]:
    """Read the named groups from validation/validation_groups.yml.

    Args:
        config: pytest's configuration for the run, which knows the root folder.

    Returns:
        The groups by name, each with its purpose and its ids.

    Raises:
        pytest.UsageError: The file is missing.
    """
    path = config.rootpath / GROUPS_RELATIVE
    if not path.is_file():
        raise pytest.UsageError(
            f"--group needs {GROUPS_RELATIVE.as_posix()} under {config.rootpath}, "
            "and it is missing"
        )
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


#######################################################################################
### Keeping only the checks asked for ###


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Keep only the checks the selection options ask for.

    Runs after pytest has collected every check the paths allow. A value that names
    nothing is an error rather than an empty run, so a typo cannot pass for a clean
    report of nothing.

    Args:
        config: pytest's configuration for the run.
        items: The collected checks, trimmed in place.
    """
    categories = wanted(config, "category")
    objectives = wanted(config, "objective")
    ids = wanted(config, "id")
    names = wanted(config, "group")
    if not (categories or objectives or ids or names):
        return

    for value in categories:
        if value not in CATEGORIES:
            raise pytest.UsageError(
                f"--category {value}: not one of {', '.join(CATEGORIES)}"
            )
    for value in objectives:
        if value not in OBJECTIVES:
            raise pytest.UsageError(
                f"--objective {value}: not one of {', '.join(OBJECTIVES)}"
            )
    if names:
        defined = groups(config)
        for name in names:
            if name not in defined:
                raise pytest.UsageError(
                    f"--group {name}: no such group in {GROUPS_RELATIVE.as_posix()}; "
                    f"the groups are {', '.join(defined)}"
                )
            ids.extend(str(member) for member in defined[name].get("ids") or [])
    collected = {code_of(item) for item in items}
    missing = sorted(set(ids) - collected)
    if missing:
        raise pytest.UsageError(
            f"no collected check carries the id {', '.join(missing)}"
        )

    kept: list[pytest.Item] = []
    dropped: list[pytest.Item] = []
    for item in items:
        keep = (
            (not categories or category_of(item) in categories)
            and (not objectives or objective_of(item) in objectives)
            and (not ids or code_of(item) in ids)
        )
        (kept if keep else dropped).append(item)
    if dropped:
        config.hook.pytest_deselected(items=dropped)
        items[:] = kept
