"""
Script:      skip_rules.py
Description: A pytest plugin holding the rules that skip a check before it runs.

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

Inputs:      manifests/*.json, manifests/study_documents/*.json   (read-only, through
                 src/sdg/sources/read_manifests.py)
             inputs/**   (read-only; only the files a @needs_pinned check names,
                 which are measured)

Outputs:     Nothing on disk. Skips a check, or fails its set-up, with the reason.

Usage:       pytest
                 loaded on its own through the pytest11 entry point in
                 pyproject.toml; nothing to type

Exit codes:  None of its own. It runs inside pytest.

Date:        2026-09-24
Owner:       Jason Delosh
"""

from __future__ import annotations

import fnmatch
import functools

import pytest

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


# Each pattern is looked at once per run, since a pinned file does not change while
# the checks run and measuring it again for every check would only cost time.
_cached_skip_reason = functools.cache(pinned_skip_reason)


def pytest_runtest_setup(item: pytest.Item) -> None:
    """Skip a check whose pinned files are not downloaded or no longer match.

    pytest calls this before it sets up each check, so the pinned files are looked at
    before any fixture could point the manifest reader somewhere else. A label naming
    a file no manifest records makes the check's set-up fail instead, which pytest
    reports as an error.

    Args:
        item: The check about to run.
    """
    for marker in item.iter_markers("needs_pinned"):
        for pattern in marker.args:
            # A pattern that matches nothing is not a state of the repo to skip on,
            # so it is turned into a set-up failure with the message kept.
            try:
                reason = _cached_skip_reason(pattern)
            except UnmatchedPatternError as exc:
                pytest.fail(str(exc), pytrace=False)
            if reason:
                pytest.skip(reason)
