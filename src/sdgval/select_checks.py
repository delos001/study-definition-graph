"""
Script:      select_checks.py
Description: A pytest plugin that selects checks in the inventory's own terms.
             pytest's own selection is by path and by words in names. This adds
             five options, --category, --aspect, --objective, --id and --group.
             Each is spelled as the column it selects on, except --aspect, whose
             column is quality_aspect, because a dash or an underscore inside a
             flag reads badly on a command line. Each keeps only the checks whose
             value matches, and --group keeps the checks a named group in
             validation/validation_groups.yml lists. Categories, aspects and
             objectives narrow each other, ids and groups add up, and a check is
             kept only when it matches every option given. The rest are deselected
             before the run, so they neither run nor appear in a validation
             report.

             A run that would validate nothing stops with pytest's usage error
             rather than running nothing, so an empty run cannot pass for a clean
             one. That covers a value naming no category, objective, group or
             collected check, and it covers options that each name something real
             but leave no check between them. The refusal for the second case
             reports how many checks each option matched on its own, which names
             the option that is the odd one out. Under an aspect's command, the
             refusal never names the --aspect the command added. It says instead
             when the options match only checks of other aspects, or when an
             objective belongs to another aspect. A missing id is refused with the
             reason that fits it: no check has it, it lies outside the files the
             run was given, or a group lists it wrongly.

             It is a plugin rather than part of conftest.py because pytest reads
             the command line before it loads a conftest below the root folder.
             An option a conftest adds is unknown at that moment, and its value is
             taken for a path. pytest loads this file at startup through the
             pytest11 entry point in pyproject.toml, so the options are known from
             the start.

             The labels it selects on are read by labels.py. The aspect is not a
             label, so --aspect reads the objective and looks it up, which is how
             the inventory's quality_aspect column is filled too.

Inputs:      validation/validation_groups.yml (read-only; only with --group)
             validation/validation_inventory.csv (read-only; only when an id
                 asked for is missing)

Outputs:     Nothing on disk.

Usage:       pytest --category sources
                 run only the checks with that category
             pytest --aspect integrity
                 run only the checks asking an integrity question
             pytest --category sources --objective stability
                 run only the checks with that category and that objective
             pytest --aspect integrity --category sources
                 any options may be combined; each narrows the rest
             pytest --id SA00106,SA00283
                 run only the checks with those ids; a comma-separated list, or
                 a repeated option, means any of them
             pytest --group pinned
                 run the checks the named group lists

Exit codes:  pytest's own: 4 bad command line, when a value names no category,
             aspect, objective, group or collected check, or when the options
             together leave no check to run

Date:        2026-09-21
Owner:       Jason Delosh
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest
import yaml

from sdgval.build_inventory import (
    ASPECT_OF,
    CATEGORIES,
    OBJECTIVES,
    OBJECTIVES_BY_ASPECT,
)
from sdgval.labels import aspect_of, category_of, code_of, objective_of

#######################################################################################
### Settings ###

# Where the named groups and the inventory live, under pytest's root folder, which
# is the repo root for a real run and a temporary folder for the plugin's own checks.
GROUPS_RELATIVE = Path("validation") / "validation_groups.yml"
INVENTORY_RELATIVE = Path("validation") / "validation_inventory.csv"

# Where an aspect's command, through src/sdgval/aspect_run.py, leaves the aspect it
# holds the run to, in pytest's stash, the store pytest gives each run for plugins to
# share values. The report writer names its report with it, and the refusals below
# word themselves for the command rather than for an --aspect the person never typed.
RUN_ASPECT = pytest.StashKey[str]()

# The options this file adds. The report writer records the values of each.
SELECTORS = ("category", "aspect", "objective", "id", "group")


#######################################################################################
### Counting a check once ###


def check_key(item: pytest.Item) -> str:
    """Name one check, so that a check pytest runs once per value still counts once.

    Args:
        item: The check.

    Returns:
        The check's permanent id, or its node id without the value in brackets when
        it carries no code marker.
    """
    return code_of(item) or item.nodeid.split("[")[0]


#######################################################################################
### The options ###


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add the five selection options to the pytest command line.

    Each takes a value. Repeating an option, or giving a comma-separated list, means
    any of the values.

    Args:
        parser: pytest's command-line parser.
    """
    for name, meaning in (
        ("category", "run only the checks with this category"),
        ("aspect", "run only the checks with this aspect of quality"),
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
        The groups by name, each as the file writes it.

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


def inventory_ids(config: pytest.Config) -> set[str]:
    """Read every id validation/validation_inventory.csv lists.

    It tells an id that exists, but lies outside the files a run was given, apart
    from an id that no check has at all.

    Args:
        config: pytest's configuration for the run, which knows the root folder.

    Returns:
        The ids, or an empty set when there is no inventory under the root folder.
    """
    path = config.rootpath / INVENTORY_RELATIVE
    if not path.is_file():
        return set()
    with path.open(encoding="utf-8", newline="") as fh:
        return {row["id"] for row in csv.DictReader(fh)}


#######################################################################################
### Keeping only the checks asked for ###


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Keep only the checks the selection options ask for.

    Runs after pytest has collected every check the paths allow. A selection that
    would leave no check to run is an error rather than an empty run, so nothing
    that validated nothing can pass for a clean report.

    Args:
        config: pytest's configuration for the run.
        items: The collected checks, trimmed in place.

    Raises:
        pytest.UsageError: A value names no category, objective, group or collected
            check, or the options together leave no check to run.
    """
    categories = wanted(config, "category")
    aspects = wanted(config, "aspect")
    objectives = wanted(config, "objective")
    ids = wanted(config, "id")
    names = wanted(config, "group")
    if not (categories or aspects or objectives or ids or names):
        return
    # Which options supplied the ids, kept before --group expands into them, so the
    # refusal below names the option the reader typed rather than its expansion.
    id_label = " and ".join(
        label for label, used in (("--id", ids), ("--group", names)) if used
    )

    for value in categories:
        if value not in CATEGORIES:
            raise pytest.UsageError(
                f"--category {value}: not one of {', '.join(CATEGORIES)}"
            )
    for value in aspects:
        if value not in OBJECTIVES_BY_ASPECT:
            raise pytest.UsageError(
                f"--aspect {value}: not one of {', '.join(OBJECTIVES_BY_ASPECT)}"
            )
    for value in objectives:
        if value not in OBJECTIVES:
            raise pytest.UsageError(
                f"--objective {value}: not one of {', '.join(OBJECTIVES)}"
            )
    # Which group each id came from, so an id a group lists wrongly is blamed on the
    # group rather than on the person, who never typed it.
    group_of: dict[str, str] = {}
    if names:
        defined = groups(config)
        for name in names:
            if name not in defined:
                raise pytest.UsageError(
                    f"--group {name}: no such group in {GROUPS_RELATIVE.as_posix()}; "
                    f"the groups are {', '.join(defined)}"
                )
            for member in defined[name].get("ids") or []:
                ids.append(str(member))
                group_of.setdefault(str(member), name)
    collected = {code_of(item) for item in items}
    missing = sorted(set(ids) - collected)
    if missing:
        known = inventory_ids(config)
        raise pytest.UsageError(
            " ".join(missing_id_message(value, known, group_of) for value in missing)
        )

    # The filters, one per option that narrows the run, each holding the option's
    # name, the values it was given and the function that reads that value off a
    # check. A new selection option is one more entry here, and the filtering and
    # the refusal below need no change for it.
    filters = (
        ("--category", categories, category_of),
        ("--aspect", aspects, aspect_of),
        ("--objective", objectives, objective_of),
        (id_label, ids, code_of),
    )
    # Which checks each option matched on its own. When the combination matches
    # nothing, these are what name the option that is the odd one out. They hold
    # ids rather than runs, so a check that runs once per value counts once and the
    # numbers read against validation/validation_inventory.csv.
    alone: dict[str, set[str]] = {
        label: set() for label, values, _ in filters if values
    }

    kept: list[pytest.Item] = []
    dropped: list[pytest.Item] = []
    for item in items:
        hits = [
            (label, not values or reader(item) in values)
            for label, values, reader in filters
        ]
        for label, hit in hits:
            if hit and label in alone:
                alone[label].add(check_key(item))
        (kept if all(hit for _, hit in hits) else dropped).append(item)

    # Every value named something real, yet nothing survived the combination. That
    # is the same empty run the refusals above exist to prevent, reached by another
    # route, so it is refused the same way rather than reported as a clean result.
    if not kept:
        raise pytest.UsageError(
            empty_selection_message(config, items, filters, alone, objectives)
        )

    if dropped:
        config.hook.pytest_deselected(items=dropped)
        items[:] = kept


#######################################################################################
### Saying why a selection is refused ###


def missing_id_message(value: str, known: set[str], group_of: dict[str, str]) -> str:
    """Say why an id asked for is not among the checks the run collected.

    Args:
        value: The id.
        known: Every id the inventory lists.
        group_of: The group each id came from, for the ids a group supplied.

    Returns:
        The sentences for whichever of three causes it is: the id is real but
        outside the files the run was given, a group lists an id no check has, or
        the id typed belongs to no check.
    """
    if value in known:
        return f"{value} is not in the files or folders given to this run."
    if value in group_of:
        return (
            f"The group {group_of[value]} lists {value}, but no check has that id. "
            f"Correct the group in {GROUPS_RELATIVE.as_posix()}."
        )
    return (
        f"No check has the id {value}. Every check's id is listed in "
        f"{INVENTORY_RELATIVE.as_posix()}."
    )


def empty_selection_message(
    config: pytest.Config,
    items: list[pytest.Item],
    filters: tuple,
    alone: dict[str, set[str]],
    objectives: list[str],
) -> str:
    """Say why the options together leave no check to run.

    Under an aspect's command, the --aspect the command added is not the person's
    option, so it is never named. When the person's own options match checks that
    are all of another aspect, the message says so, and when an objective belongs to
    another aspect, it names that aspect and lists the command's own objectives.
    Otherwise each option's own count is given, so the reader can see which option
    is the odd one out.

    Args:
        config: pytest's configuration for the run.
        items: Every collected check.
        filters: Each option's label, values and the function reading its value.
        alone: The checks each option matched on its own.
        objectives: The objectives the person asked for.

    Returns:
        The message.
    """
    run_aspect = config.stash.get(RUN_ASPECT, None)
    if run_aspect is None or wanted(config, "aspect") != [run_aspect]:
        return per_option_message(alone)
    # The person's own options, without the aspect the command added.
    own = [f for f in filters if f[0] != "--aspect"]
    together = {
        check_key(item)
        for item in items
        if all(not values or reader(item) in values for _, values, reader in own)
    }
    if not together:
        return per_option_message(
            {label: found for label, found in alone.items() if label != "--aspect"}
        )
    foreign = [o for o in objectives if ASPECT_OF.get(o) != run_aspect]
    own_list = ", ".join(OBJECTIVES_BY_ASPECT[run_aspect])
    if foreign and len(foreign) == len(objectives):
        if len(foreign) == 1:
            owner = ASPECT_OF[foreign[0]]
            article = "an" if owner[0] in "aeiou" else "a"
            return (
                f"{foreign[0]} is {article} {owner} objective, so "
                f"validate_{run_aspect} has none of its checks. The {run_aspect} "
                f"objectives are {own_list}."
            )
        return (
            f"{', '.join(foreign)} are not {run_aspect} objectives, so "
            f"validate_{run_aspect} has none of their checks. The {run_aspect} "
            f"objectives are {own_list}."
        )
    noun = "check" if len(together) == 1 else "checks"
    return (
        f"No {run_aspect} checks match the options given. The options match "
        f"{len(together)} {noun} together, but none of them are {run_aspect}. "
        "Widen or drop an option."
    )


def per_option_message(alone: dict[str, set[str]]) -> str:
    """Give each option's own count, for options that match nothing together.

    Args:
        alone: The checks each option matched on its own.

    Returns:
        The message.
    """
    counts = ", ".join(
        f"{label} matched {len(found)}" for label, found in alone.items()
    )
    return (
        f"no check matches every option given: {counts}, in combination 0. "
        "Drop or widen the option that matched fewest."
    )
