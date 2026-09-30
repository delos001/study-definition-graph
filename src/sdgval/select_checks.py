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

             Each option is defined once, in SELECTION_OPTIONS below, with its
             name, its help text, the label it reads off a check and the values it
             accepts. The command line, the filtering and the report's selection
             columns in src/sdgval/report.py are all built from that one table, so
             a new option is one more entry there.

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
             run was given, or a group lists it wrongly. A run that collected no
             check at all had nothing to select from, so it is left to pytest,
             which ends it with its own exit status for that.

             A group is refused too when it cannot be run as written. That is a
             group whose ids are empty, missing or not a list, and a group whose
             checks belong to more than one aspect of quality, because a report
             covers one aspect.

             Each refusal leaves its cause in pytest's stash before it stops the
             run. A plain pytest run ignores the cause and exits 4. An aspect's
             command reads it, through src/sdgval/aspect_run.py, and ends with the
             repo's own number for that cause.

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
             pytest --group pinned_integrity
                 run the checks the named group lists

Exit codes:  None of its own. It runs inside pytest, which exits 4, its own usage
             error, for every refusal above. An aspect's command turns the cause
             each refusal leaves into the repo's number for it, and that
             command's header lists the numbers.

Date:        2026-09-21
Owner:       Jason Delosh
"""

from __future__ import annotations

import csv
import enum
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn

import pytest
import yaml

from sdg.exit_codes import problem_line
from sdgval.build_inventory import OUT_OF_USE
from sdgval.labels import aspect_of, category_of, code_of, objective_of
from sdgval.vocabulary import (
    ASPECT_OF,
    CATEGORIES,
    OBJECTIVES,
    OBJECTIVES_BY_ASPECT,
)

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


#######################################################################################
### The selection options ###


@dataclass(frozen=True)
class SelectionOption:
    """One way of selecting checks that this file adds to the pytest command line.

    An option either reads a label off each check and keeps the checks whose label
    it names, or it names something that stands for a list of ids, as a group does,
    and adds those ids to another option's values.
    """

    # The option's name without its dashes. A report records its values under the
    # same name.
    name: str
    # What the option does, as pytest's help prints it.
    meaning: str
    # The function that reads the option's value off a check, or None for an option
    # that adds to another option's values instead.
    reader: Callable[[pytest.Item], str] | None = None
    # The values the option accepts, or None when a value is looked up among the
    # checks themselves.
    allowed: tuple[str, ...] | None = None
    # The option whose values this one adds to, or None for an option that narrows
    # against every other.
    adds_to: str | None = None


# Every selection option, in the order a report writes their columns. Options with a
# reader narrow each other. An option that adds to another adds up with it, so --id
# and --group together keep the checks either one names.
SELECTION_OPTIONS = (
    SelectionOption(
        "aspect",
        "run only the checks with this aspect of quality",
        reader=aspect_of,
        allowed=tuple(OBJECTIVES_BY_ASPECT),
    ),
    SelectionOption(
        "category",
        "run only the checks with this category",
        reader=category_of,
        allowed=CATEGORIES,
    ),
    SelectionOption(
        "objective",
        "run only the checks with this objective",
        reader=objective_of,
        allowed=OBJECTIVES,
    ),
    SelectionOption("id", "run only the check with this id", reader=code_of),
    SelectionOption("group", "run only the checks the named group lists", adds_to="id"),
)

# The options' names, which the report writer records the values of.
SELECTORS = tuple(option.name for option in SELECTION_OPTIONS)


#######################################################################################
### Refusing a run ###


class Refusal(enum.Enum):
    """The causes this package refuses a run for, before any check runs.

    Each refusal stops the run with pytest's usage error, which a plain pytest run
    reports as 4 whatever the cause. src/sdgval/aspect_run.py turns each cause into
    the exit number and sub-code in REFUSAL_EXITS, so an aspect's command says which
    cause it was.
    """

    ASPECT_GIVEN = enum.auto()
    NOTHING_SELECTED = enum.auto()
    NO_CHECK_COLLECTED = enum.auto()
    GROUPS_FILE_MISSING = enum.auto()
    GROUP_WITHOUT_IDS = enum.auto()
    GROUP_OF_MIXED_ASPECTS = enum.auto()
    GROUP_WITH_UNKNOWN_ID = enum.auto()
    UNCOMMITTED_CHANGES = enum.auto()
    GIT_NOT_FOUND = enum.auto()
    GIT_SILENT = enum.auto()


# The exit number and sub-code each refusal is reported with, from docs/exit_codes.csv.
# The sub-code opens the refusal's message, and src/sdgval/aspect_run.py ends the run
# on the number.
REFUSAL_EXITS: dict[Refusal, tuple[int, str]] = {
    Refusal.ASPECT_GIVEN: (2, "ASPECT-OPTION-GIVEN"),
    Refusal.UNCOMMITTED_CHANGES: (3, "UNCOMMITTED-CHANGES"),
    Refusal.GIT_NOT_FOUND: (6, "GIT-NOT-FOUND"),
    Refusal.GIT_SILENT: (7, "GIT-FAILED"),
    Refusal.GROUPS_FILE_MISSING: (12, "GROUPS-FILE-MISSING"),
    Refusal.GROUP_OF_MIXED_ASPECTS: (15, "GROUP-MIXES-ASPECTS"),
    Refusal.GROUP_WITHOUT_IDS: (15, "GROUP-HAS-NO-IDS"),
    Refusal.GROUP_WITH_UNKNOWN_ID: (16, "GROUP-ID-UNKNOWN"),
    Refusal.NOTHING_SELECTED: (17, "SELECTION-MATCHES-NOTHING"),
    Refusal.NO_CHECK_COLLECTED: (18, "NO-CHECKS-COLLECTED"),
}


# Where a refusal leaves its cause, in pytest's stash, for an aspect's command to read
# once pytest has stopped.
REFUSAL = pytest.StashKey[Refusal]()


def refuse(config: pytest.Config, cause: Refusal, message: str) -> NoReturn:
    """Stop the run with pytest's usage error, leaving the cause behind.

    Args:
        config: pytest's configuration for the run.
        cause: Why the run is refused.
        message: What the person reads, saying what is wrong and what to do.

    Raises:
        pytest.UsageError: Always, carrying the message with the cause's sub-code in
            front of it.
    """
    config.stash[REFUSAL] = cause
    raise pytest.UsageError(problem_line(REFUSAL_EXITS[cause][1], message))


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
### The options on the command line ###


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add each selection option to the pytest command line.

    Each takes a value. Repeating an option, or giving a comma-separated list, means
    any of the values.

    Args:
        parser: pytest's command-line parser.
    """
    for option in SELECTION_OPTIONS:
        parser.addoption(
            f"--{option.name}",
            action="append",
            default=None,
            metavar="VALUE",
            help=f"{option.meaning}; repeat, or give a comma-separated list, for several",
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
        refuse(
            config,
            Refusal.GROUPS_FILE_MISSING,
            f"--group needs {GROUPS_RELATIVE.as_posix()} under {config.rootpath}, "
            "and it is missing",
        )
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def group_members(config: pytest.Config, name: str, defined: dict) -> list[str]:
    """Read the ids one named group lists, refusing a group that cannot run.

    Args:
        config: pytest's configuration for the run.
        name: The group's name, as the person typed it.
        defined: Every group the groups file defines.

    Returns:
        The ids the group lists, in the file's order.

    Raises:
        pytest.UsageError: The file defines no such group, or the group has no list
            of ids with at least one id in it.
    """
    if name not in defined:
        refuse(
            config,
            Refusal.NOTHING_SELECTED,
            f"--group {name}: no such group in {GROUPS_RELATIVE.as_posix()}; "
            f"the groups are {', '.join(defined)}",
        )
    group = defined[name]
    members = group.get("ids") if isinstance(group, dict) else None
    if not isinstance(members, list) or not members:
        refuse(
            config,
            Refusal.GROUP_WITHOUT_IDS,
            f"The group {name} in {GROUPS_RELATIVE.as_posix()} has no list of ids, so "
            "it names no check to run. Give it an ids list naming at least one check.",
        )
    return [str(member) for member in members]


def inventory_ids(config: pytest.Config) -> set[str]:
    """Read the id of every check validation/validation_inventory.csv lists as in use.

    It tells an id that exists, but lies outside the files a run was given, apart
    from an id that no check has at all. A superseded or retired row is left out,
    because its row is kept after its check is removed, so no check has its id.

    Args:
        config: pytest's configuration for the run, which knows the root folder.

    Returns:
        The ids, or an empty set when there is no inventory under the root folder.
    """
    path = config.rootpath / INVENTORY_RELATIVE
    if not path.is_file():
        return set()
    with path.open(encoding="utf-8", newline="") as fh:
        return {
            row["id"]
            for row in csv.DictReader(fh)
            if row.get("status") not in OUT_OF_USE
        }


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
            check, a group cannot run as written, or the options together leave no
            check to run.
    """
    given = {option.name: wanted(config, option.name) for option in SELECTION_OPTIONS}
    if not any(given.values()):
        return
    # With no check collected there is nothing to select from. That is pytest's own
    # "no tests collected", or a check file that failed to load, and pytest reports
    # either one with its own exit status, so it is left to pytest rather than refused
    # as a selection that matches nothing.
    if not items:
        return

    for option in SELECTION_OPTIONS:
        for value in given[option.name]:
            if option.allowed is not None and value not in option.allowed:
                refuse(
                    config,
                    Refusal.NOTHING_SELECTED,
                    f"--{option.name} {value}: not one of {', '.join(option.allowed)}",
                )

    # Each group becomes the ids it lists, added to the values of the option it adds
    # to. Which group each id came from is kept, so an id a group lists wrongly is
    # blamed on the group rather than on the person, who never typed it.
    added: dict[str, list[str]] = {option.name: [] for option in SELECTION_OPTIONS}
    group_of: dict[str, str] = {}
    members_of: dict[str, list[str]] = {}
    if given["group"]:
        defined = groups(config)
        for name in given["group"]:
            members_of[name] = group_members(config, name, defined)
            added["id"].extend(members_of[name])
            for member in members_of[name]:
                group_of.setdefault(member, name)

    ids = given["id"] + added["id"]
    collected = {code_of(item) for item in items}
    missing = sorted(set(ids) - collected)
    if missing:
        known = inventory_ids(config)
        cause = (
            Refusal.GROUP_WITH_UNKNOWN_ID
            if any(value in group_of and value not in known for value in missing)
            else Refusal.NOTHING_SELECTED
        )
        refuse(
            config,
            cause,
            " ".join(missing_id_message(value, known, group_of) for value in missing),
        )
    for name, members in members_of.items():
        refuse_mixed_group(config, name, members, items)

    # The filters, one per option that reads a label, each holding the label the
    # refusals name it by, the values it was given, with those of any option that
    # adds to it, and the function that reads that value off a check. They are built
    # from SELECTION_OPTIONS, so the filtering and the refusals below need no change
    # for a new option.
    filters = tuple(
        (
            " and ".join(
                f"--{other.name}"
                for other in SELECTION_OPTIONS
                if (other.name == option.name or other.adds_to == option.name)
                and given[other.name]
            ),
            given[option.name] + added[option.name],
            option.reader,
        )
        for option in SELECTION_OPTIONS
        if option.reader is not None
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
        refuse(
            config,
            Refusal.NOTHING_SELECTED,
            empty_selection_message(config, items, filters, alone, given["objective"]),
        )

    if dropped:
        config.hook.pytest_deselected(items=dropped)
        items[:] = kept


def refuse_mixed_group(
    config: pytest.Config, name: str, members: list[str], items: list[pytest.Item]
) -> None:
    """Refuse a group whose checks belong to more than one aspect of quality.

    A report covers one aspect, so a group that mixes aspects cannot be run whole by
    any aspect's command.

    Args:
        config: pytest's configuration for the run.
        name: The group's name.
        members: The ids the group lists, each a collected check.
        items: Every collected check.

    Raises:
        pytest.UsageError: The group's checks belong to more than one aspect.
    """
    aspects = sorted(
        {aspect_of(item) for item in items if code_of(item) in members} - {""}
    )
    if len(aspects) > 1:
        refuse(
            config,
            Refusal.GROUP_OF_MIXED_ASPECTS,
            f"The group {name} in {GROUPS_RELATIVE.as_posix()} lists checks of more "
            f"than one aspect of quality, {', '.join(aspects)}. A group holds the "
            "checks of one aspect, so split it into one group per aspect.",
        )


#######################################################################################
### Saying why a selection is refused ###


def missing_id_message(value: str, known: set[str], group_of: dict[str, str]) -> str:
    """Say why an id asked for is not among the checks the run collected.

    Args:
        value: The id.
        known: Every id the inventory lists as in use.
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
    option, so it is never named. The command refuses any --aspect the person gives
    before collection starts, so the aspect in the run is always the command's own.
    When the person's own options match checks that are all of another aspect, the
    message says so, and when an objective belongs to another aspect, it names that
    aspect and lists the command's own objectives. Otherwise each option's own count
    is given, so the reader can see which option is the odd one out.

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
    if run_aspect is None:
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
