"""
Script:      labels.py
Description: A pytest plugin that declares the labels a check may carry and reads
             them off a check. A label is what pytest calls a marker: @code,
             @category, @objective, @positive, @negative, @needs_pinned and
             @needs_fixture.

             pytest warns about a label it has not been told about, so each is
             declared here with a sentence saying what it means. The readers are
             here too, because the selection options in select_checks.py and the
             report in report.py both read the same labels, and one place for them
             means the two can never read a label differently.

             The aspect of quality is not a label. It is looked up from the
             objective, the same way the inventory's quality_aspect column is
             filled, so a check can never carry an aspect its objective does not
             belong to.

Inputs:      Nothing on disk.

Outputs:     Nothing on disk. Hands back the value of a label on a check.

Usage:       pytest
                 loaded on its own through the pytest11 entry point in
                 pyproject.toml; nothing to type
             from sdgval.labels import code_of, objective_of
                 read a check's labels in another plugin

Exit codes:  None of its own. It runs inside pytest.

Date:        2026-09-24
Owner:       Jason Delosh
"""

from __future__ import annotations

import pytest

from sdgval.build_inventory import ASPECT_OF

#######################################################################################
### Declaring the labels ###


def pytest_configure(config: pytest.Config) -> None:
    """Tell pytest about the labels the checks use.

    Args:
        config: pytest's configuration.
    """
    config.addinivalue_line(
        "markers",
        "category(name): what kind of thing the check confirms, one of the categories "
        "in validation/validation_inventory_dictionary.md",
    )
    config.addinivalue_line(
        "markers",
        "objective(name): what the check confirms about its category, one of the "
        "objectives in validation/validation_inventory_dictionary.md",
    )
    config.addinivalue_line(
        "markers",
        "positive: a check of a staged working situation, expected to succeed",
    )
    config.addinivalue_line(
        "markers",
        "negative: a check of a staged broken situation, expected to refuse for "
        "the right reason",
    )
    # The code is the check's short, permanent id in validation/validation_inventory.csv:
    # S, a suite letter and five digits, such as SA00042, assigned once and never
    # reused.
    config.addinivalue_line(
        "markers", "code(id): the check's id in validation/validation_inventory.csv"
    )
    config.addinivalue_line(
        "markers",
        "needs_pinned(*paths): the real pinned files the check reads, each written as "
        "a manifest writes it, where * stands for any run of characters",
    )
    config.addinivalue_line(
        "markers",
        "needs_fixture(*names): the files in validation/fixtures/ the check reads, "
        "each written as its name inside that folder",
    )


#######################################################################################
### Reading the labels off a check ###


def _marker_value(item: pytest.Item, name: str) -> str:
    """Read the text a label such as @code("SA00001") was given.

    Args:
        item: The check.
        name: The label's name.

    Returns:
        The text, or an empty string when the check carries no such label.
    """
    marker = item.get_closest_marker(name)
    return str(marker.args[0]) if marker and marker.args else ""


def code_of(item: pytest.Item) -> str:
    """Read a check's permanent id off its code label.

    Args:
        item: The check.

    Returns:
        The id, or an empty string when the check carries no code label.
    """
    return _marker_value(item, "code")


def category_of(item: pytest.Item) -> str:
    """Read a check's category off its category label.

    Args:
        item: The check.

    Returns:
        The category, or an empty string when the check carries no category label.
    """
    return _marker_value(item, "category")


def objective_of(item: pytest.Item) -> str:
    """Read a check's objective off its objective label.

    Args:
        item: The check.

    Returns:
        The objective, or an empty string when the check carries no objective label.
    """
    return _marker_value(item, "objective")


def aspect_of(item: pytest.Item) -> str:
    """Say which aspect of quality a check's objective belongs to.

    Args:
        item: The check.

    Returns:
        The aspect, or an empty string when the check carries no objective the table
        knows.
    """
    return ASPECT_OF.get(objective_of(item), "")


def fixtures_of(item: pytest.Item) -> list[str]:
    """Read the fixture files a check names with its needs_fixture label.

    Args:
        item: The check.

    Returns:
        Each name as written, relative to validation/fixtures/, or an empty list when
        the check carries no such label.
    """
    marker = item.get_closest_marker("needs_fixture")
    return [str(name) for name in marker.args] if marker else []


def case_of(item: pytest.Item) -> str:
    """Read a check's case off its positive or negative label.

    Args:
        item: The check.

    Returns:
        positive, negative, or an empty string when it carries neither, as a check
        that looked at something real rather than staging a situation does.
    """
    if item.get_closest_marker("positive"):
        return "positive"
    if item.get_closest_marker("negative"):
        return "negative"
    return ""
