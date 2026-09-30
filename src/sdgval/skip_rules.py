"""
Script:      skip_rules.py
Description: A pytest plugin holding the rules that skip a check before it runs,
             or fail its set-up when one of its labels is a mistake.

             A check that reads real pinned files names them with @needs_pinned.
             Before the check runs, every file that matches is looked at, and the
             check is skipped with the reason when one is not downloaded or no
             longer matches its manifest entry. The second case is called blocked.
             A skipped check is recorded as skipped in a report, with that
             reason. The stability check for each pinned file is the only check
             that fails for a changed file, so the change is reported once, not as
             a failure of every check that reads it.

             A label that names a file no manifest records is a mistake in the
             check, so that check errors rather than skips, and the run fails.
             Each pattern is looked at once per run, and the answer is kept with
             that run, so a second run in the same process looks again.

             A check that reads a file in validation/fixtures/ names it with
             @needs_fixture. A name that is not a file in that folder is a mistake
             in the check too, so the check errors with a message naming the file,
             the same way a @needs_pinned label that matches nothing does.

             A check that validation/validation_inventory.csv marks as anything
             but active, such as inactive or pending, is skipped too, and the
             reason gives its status and the reason the inventory records. A report
             then shows it as skipped with that reason, rather than it running as
             though nothing had switched it off.

Inputs:      validation/validation_inventory.csv   (read-only; each check's status)
             every manifest, read through src/sdg/sources/read_manifests.py
                 (read-only)
             inputs/**   (read-only; only the files a @needs_pinned check names,
                 which are measured)
             validation/fixtures/   (read-only; only whether each file a
                 @needs_fixture check names is there)

Outputs:     Nothing on disk. Skips a check, or fails its set-up, with the reason.

Usage:       pytest
                 loaded on its own through the pytest11 entry point in
                 pyproject.toml; nothing to type

Exit codes:  None of its own. It runs inside pytest.

Date:        2026-09-24
Owner:       Jason Delosh
"""

from __future__ import annotations

import csv
import fnmatch
from pathlib import Path

import pytest

from sdgval.labels import code_of, fixtures_of
from sdgval.select_checks import INVENTORY_RELATIVE

#######################################################################################
### Settings ###

# Where the files a check names with @needs_fixture live, under pytest's root folder.
FIXTURES_RELATIVE = Path("validation") / "fixtures"

#######################################################################################
### A check the inventory has switched off ###

# Where each run keeps the statuses it read from the inventory, in pytest's stash, so
# the file is read once per run and two runs in one process never share them.
STATUSES = pytest.StashKey[dict[str, tuple[str, str]]]()


def inventory_statuses(config: pytest.Config) -> dict[str, tuple[str, str]]:
    """Read each check's status and reason from validation/validation_inventory.csv.

    Args:
        config: pytest's configuration for the run, which knows the root folder.

    Returns:
        Each check's status and status reason, keyed by its id. It is empty when
        there is no inventory under the root folder, as for a staged suite.
    """
    path = config.rootpath / INVENTORY_RELATIVE
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8", newline="") as fh:
        return {
            row["id"]: (row.get("status", "active"), row.get("status_reason", ""))
            for row in csv.DictReader(fh)
        }


def pytest_configure(config: pytest.Config) -> None:
    """Read the statuses once, and start the run's own store of pinned-file answers.

    Args:
        config: pytest's configuration for the run.
    """
    config.stash[STATUSES] = inventory_statuses(config)
    config.stash[PINNED_ANSWERS] = {}


def status_skip_reason(item: pytest.Item) -> str | None:
    """Say why a check the inventory has switched off does not run.

    Args:
        item: The check about to run.

    Returns:
        None for an active check, or one not in the inventory. Otherwise the
        reason, naming the status and the reason the inventory records.
    """
    status, why = item.config.stash[STATUSES].get(code_of(item), ("active", ""))
    if status == "active":
        return None
    return f"the inventory marks this check {status}. {why}".strip()


#######################################################################################
### Pinned files a check depends on ###


class UnmatchedPatternError(Exception):
    """A @needs_pinned label names a file that no manifest records."""


def pinned_skip_reason(pattern: str) -> str | None:
    """Say why a check that reads the pinned files matching a pattern cannot run.

    The pattern is a path as a manifest writes it, where * stands for any run of
    characters. Each manifest entry whose path matches is looked at in turn, and the
    first problem found is the answer.

    Args:
        pattern: The pinned file or files the check reads.

    Returns:
        None when every matching file is on disk and matches its entry. Otherwise the
        reason: a file is not downloaded, or a file no longer matches its entry,
        which is reported as blocked.

    Raises:
        UnmatchedPatternError: No manifest records a file matching the pattern.
        NotInRepoError: The sdg package is not running from inside its repo.
        ManifestError: A manifest is missing or cannot be read.
    """
    # Imported here rather than at the top, so the report can still be written when
    # the sdg package itself is broken.
    from sdg.sources.fingerprint_file import compare
    from sdg.sources.read_manifests import manifests

    matched = [
        entry
        for manifest in manifests()
        for entry in manifest.entries
        if fnmatch.fnmatchcase(entry.local, pattern)
    ]
    if not matched:
        raise UnmatchedPatternError(
            f"no manifest records a file matching {pattern}; "
            "correct the @needs_pinned marker"
        )
    for entry in matched:
        if not entry.path.is_file():
            return f"not downloaded: {entry.local}; run acquire_sources"
        if not compare(entry.path, entry).matched:
            return (
                f"blocked: {entry.local} does not match its manifest entry; "
                "see the stability check for that file"
            )
    return None


# Where each run keeps the answer for each pattern it has looked at, in pytest's
# stash. A pinned file does not change while the checks run, so measuring it again
# for every check would only cost time. The answers are kept with the run rather
# than for the whole process, so a second run in the same process measures the
# files again and sees a file that changed between the two.
PINNED_ANSWERS = pytest.StashKey[dict[str, str | None]]()


def pinned_answer(config: pytest.Config, pattern: str) -> str | None:
    """Give the run's answer for one pattern, measuring the files the first time.

    Args:
        config: pytest's configuration for the run.
        pattern: The pinned file or files the check reads.

    Returns:
        The answer pinned_skip_reason() gives for the pattern.

    Raises:
        UnmatchedPatternError: No manifest records a file matching the pattern.
    """
    answers = config.stash[PINNED_ANSWERS]
    if pattern not in answers:
        answers[pattern] = pinned_skip_reason(pattern)
    return answers[pattern]


#######################################################################################
### Fixture files a check depends on ###


def missing_fixture(item: pytest.Item) -> str | None:
    """Name the first file a check's @needs_fixture label names that is not there.

    Args:
        item: The check about to run.

    Returns:
        The message for the missing file, or None when every named file is in
        validation/fixtures/.
    """
    folder = item.config.rootpath / FIXTURES_RELATIVE
    for name in fixtures_of(item):
        if not (folder / name).is_file():
            return (
                f"{FIXTURES_RELATIVE.as_posix()}/{name} is not there; "
                "correct the @needs_fixture marker"
            )
    return None


def pytest_runtest_setup(item: pytest.Item) -> None:
    """Skip a check that is switched off, or whose pinned files are not in order.

    pytest calls this before it sets up each check, so the pinned files are looked at
    before any fixture could point the manifest reader somewhere else. A label naming
    a file no manifest records, or a fixture file that is not there, makes the
    check's set-up fail instead, which pytest reports as an error.

    A check the inventory has switched off is skipped first, since whether its
    pinned files are in order does not matter when it is not meant to run.

    Args:
        item: The check about to run.
    """
    status_reason = status_skip_reason(item)
    if status_reason:
        pytest.skip(status_reason)
    fixture_problem = missing_fixture(item)
    if fixture_problem:
        pytest.fail(fixture_problem, pytrace=False)
    for marker in item.iter_markers("needs_pinned"):
        for pattern in marker.args:
            # A pattern that matches nothing is not a state of the repo to skip on,
            # so it is turned into a set-up failure with the message kept.
            try:
                reason = pinned_answer(item.config, pattern)
            except UnmatchedPatternError as exc:
                pytest.fail(str(exc), pytrace=False)
            if reason:
                pytest.skip(reason)
