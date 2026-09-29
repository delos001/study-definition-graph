"""
Script:      aspect_order.py
Description: A pytest plugin that runs a run holding checks of more than one
             aspect of quality in stages, and holds back a later stage when an
             earlier one did not come through clean.

             The stages are technical, then conformance, then integrity. A
             finding about the shape or the content of what the code produced
             cannot be trusted while the code itself is failing, and a finding
             about content cannot be trusted while its shape is wrong. So each
             stage runs in full, and a later stage runs only when every active
             check in the earlier stages came through. The reasoning is in
             DECISIONS.md, "A validation report covers one aspect of quality, and
             a run that holds several runs them in order".

             An earlier stage holds the later ones back when one of its checks
             fails, when a check's set-up or clean-up breaks, or when an active
             check is skipped, as it is when a pinned file it reads is not
             downloaded or no longer matches its manifest entry, since that check
             was meant to confirm something and could not. A check the inventory marks pending or
             inactive never holds a stage back, because it is switched off and
             was not meant to confirm anything. Every check in a held-back stage
             is skipped with a reason naming the stage that did not pass and the
             first check that stopped it.

             A run of one aspect, as an aspect's command makes, is left as it is.
             A check that carries no objective, which only a staged suite inside
             a check can hold, runs before the stages and takes no part in them.

Inputs:      Nothing of its own. It reads each check's objective through
             src/sdgval/labels.py, and whether a skipped check was switched off
             through src/sdgval/skip_rules.py.

Outputs:     Nothing on disk. It reorders the checks of a run that holds more than
             one aspect, and skips the checks of a stage that is held back.

Usage:       pytest
                 loaded on its own through the pytest11 entry point in
                 pyproject.toml; nothing to type

Exit codes:  None of its own. It runs inside pytest.

Date:        2026-09-29
Owner:       Jason Delosh
"""

from __future__ import annotations

from collections.abc import Generator
from dataclasses import dataclass, field

import pytest

from sdgval.labels import aspect_of
from sdgval.skip_rules import status_skip_reason

#######################################################################################
### Settings ###

# The stages, in the order they run. An aspect missing here would never run in a
# mixed run, so a check of this file confirms every aspect is listed.
STAGES = ("technical", "conformance", "integrity")


@dataclass
class RunStages:
    """What one run knows about its stages."""

    # Whether the run holds checks of more than one aspect. Only then are the stages
    # ordered and gated.
    mixed: bool = False
    # The stage of each check, keyed by its node id.
    stage_of: dict[str, int] = field(default_factory=dict)
    # The first check that held each stage back, with what happened to it, keyed by
    # the stage's position in STAGES.
    blocked_by: dict[int, str] = field(default_factory=dict)


# Where each run keeps its stages, in pytest's stash, so two runs in one process never
# share them.
RUN_STAGES = pytest.StashKey[RunStages]()


def stage_index(item: pytest.Item) -> int:
    """Say which stage a check belongs to.

    Args:
        item: The check.

    Returns:
        The position of its aspect in STAGES, or -1 for a check that carries no
        objective, which runs before every stage.
    """
    aspect = aspect_of(item)
    return STAGES.index(aspect) if aspect in STAGES else -1


#######################################################################################
### Putting the checks in stage order ###


def pytest_configure(config: pytest.Config) -> None:
    """Start the run's record of its stages.

    Args:
        config: pytest's configuration for the run.
    """
    config.stash[RUN_STAGES] = RunStages()


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Sort a run that holds more than one aspect into its stages.

    It runs after the selection options have removed what they remove, so it orders
    only the checks that will run. The order within a stage is kept as it was.

    Args:
        config: pytest's configuration for the run.
        items: The checks the run holds, sorted in place.
    """
    stages = config.stash[RUN_STAGES]
    stages.stage_of = {item.nodeid: stage_index(item) for item in items}
    stages.mixed = len({index for index in stages.stage_of.values() if index >= 0}) > 1
    if stages.mixed:
        items.sort(key=stage_index)


#######################################################################################
### Holding a stage back ###


def held_back_reason(stages: RunStages, index: int) -> str | None:
    """Say why a check's stage is held back, when an earlier stage did not pass.

    Args:
        stages: The run's record of its stages.
        index: The check's stage, its position in STAGES.

    Returns:
        None when every earlier stage came through. Otherwise the reason, naming
        the earliest stage that did not pass and the first check that stopped it.
    """
    for earlier in range(index):
        if earlier in stages.blocked_by:
            return (
                f"held back: the {STAGES[earlier]} stage did not pass, because "
                f"{stages.blocked_by[earlier]}. Fix that, then run again."
            )
    return None


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item: pytest.Item) -> None:
    """Skip a check whose stage is held back by an earlier stage.

    It runs before the other set-up rules, so a held-back check is not measured or
    set up at all.

    Args:
        item: The check about to run.
    """
    stages = item.config.stash[RUN_STAGES]
    if not stages.mixed:
        return
    reason = held_back_reason(stages, stages.stage_of.get(item.nodeid, -1))
    if reason:
        pytest.skip(reason)


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(
    item: pytest.Item, call: pytest.CallInfo[None]
) -> Generator[None, pytest.TestReport, pytest.TestReport]:
    """Record a check that holds its stage's later stages back.

    A failed check, and a set-up or clean-up that broke, hold them back. So does a
    skip, other than one because the inventory switched the check off, or one this
    plugin made because an earlier stage was already held back.

    Args:
        item: The check.
        call: What happened in one phase of the check: set-up, the check itself, or
            clean-up.

    Returns:
        pytest's own report for the phase, unchanged.
    """
    report = yield
    stages = item.config.stash[RUN_STAGES]
    index = stages.stage_of.get(item.nodeid, -1)
    if not stages.mixed or index < 0 or index in stages.blocked_by:
        return report
    if report.failed:
        what = "failed" if report.when == "call" else f"broke in its {report.when}"
        stages.blocked_by[index] = f"{item.nodeid} {what}"
    elif report.skipped:
        switched_off = status_skip_reason(item) is not None
        already_held = held_back_reason(stages, index) is not None
        if not switched_off and not already_held:
            # pytest keeps a skip's reason as the last part of its long report,
            # written as "Skipped: " and the reason.
            said = report.longrepr[2] if isinstance(report.longrepr, tuple) else ""
            said = said.removeprefix("Skipped: ")
            stages.blocked_by[index] = f"{item.nodeid} was skipped ({said})"
    return report
