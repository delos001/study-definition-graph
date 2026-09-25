"""
Script:      test_skip_rules_technical.py
Description: Checks for src/sdgval/skip_rules.py, the plugin that skips a check
             whose pinned files are not downloaded or have changed, and fails the
             set-up of a check whose label names a file no manifest records.

             Each check stages a throwaway suite with the staged_suite fixture in
             validation/conftest.py. The suite stages a small repo of its own and
             points the manifest reader at it, then runs as a separate pytest
             process with a report asked for, and the report shows what the rule
             did with each check.

Inputs:      Nothing real. Each staged suite and its small repo are written to
             pytest's own temporary folder.

Outputs:     Writes nothing to disk outside pytest's temporary folder.

Usage:       pytest validation/sdgval/test_skip_rules_technical.py
                 run these checks
             pytest validation/sdgval/test_skip_rules_technical.py -v
                 one line per check with its result

Exit codes:  pytest's own: 0 all passed, 1 some failed

Date:        2026-09-24
Owner:       Jason Delosh
"""

from __future__ import annotations

import pytest

positive = pytest.mark.positive
negative = pytest.mark.negative
# Every check carries a @code line: its short, permanent id in
# validation/validation_inventory.csv, assigned once and never reused.
code = pytest.mark.code
# Every check carries an @objective line: what the check confirms about its category,
# one of the objectives validation/validation_inventory_dictionary.md defines.
objective = pytest.mark.objective
# Every check carries a @category line: what kind of thing the check confirms, one
# of the categories validation/validation_inventory_dictionary.md defines.
category = pytest.mark.category


#######################################################################################
### The pinned-file gate ###
#
# A throwaway suite stages a small repo with one pinned file that matches its entry,
# one that has changed, one that was never downloaded, and a pattern no manifest
# records. Each of its checks names one of them with @needs_pinned, and the report
# shows what the gate did with each.


GATED_SUITE = '''
    import hashlib
    import json
    from pathlib import Path

    import pytest

    from sdg.sources import read_manifests

    # The small repo is staged beside this file, and the manifest reader is pointed at
    # it when the file is collected. That is before any check is set up, which is
    # when the pinned-file gate reads the manifests.
    ROOT = Path(__file__).parent / "staged_repo"
    for folder in ("manifests/study_documents", "inputs/set"):
        (ROOT / folder).mkdir(parents=True, exist_ok=True)
    (ROOT / "pyproject.toml").write_text('name = "sdg"', encoding="utf-8")


    def entry(name, recorded):
        return {
            "name": name,
            "url": f"https://example.invalid/{name}",
            "local": f"inputs/set/{name}",
            "bytes": len(recorded),
            "sha256": hashlib.sha256(recorded).hexdigest(),
        }


    (ROOT / "inputs/set/good.txt").write_bytes(b"good")
    (ROOT / "inputs/set/changed.txt").write_bytes(b"edited")
    recorded = [
        entry("good.txt", b"good"),
        entry("changed.txt", b"original"),
        entry("missing.txt", b"never downloaded"),
    ]
    (ROOT / "manifests/set.json").write_text(
        json.dumps({"files": recorded}), encoding="utf-8"
    )
    read_manifests.REPO_ROOT = ROOT
    read_manifests.MANIFEST_DIR = ROOT / "manifests"
    read_manifests.STUDY_MANIFEST_DIR = ROOT / "manifests" / "study_documents"


    @pytest.mark.needs_pinned("inputs/set/good.txt")
    def test_reads_good():
        """Reads a file that matches its entry."""


    @pytest.mark.needs_pinned("inputs/set/changed.txt")
    def test_reads_changed():
        """Reads a file changed since it was pinned."""


    @pytest.mark.needs_pinned("inputs/set/missing.txt")
    def test_reads_missing():
        """Reads a file never downloaded."""
    '''


@pytest.fixture
def gated(staged_suite):
    """Run the suite with the staged pinned files and hand back pytest's result and
    the report's rows."""
    result, out = staged_suite.run(GATED_SUITE)
    return result, staged_suite.report(out)


@code("SA00454")
@category("repository")
@objective("functionality")
@positive
def test_a_check_whose_pinned_file_matches_runs(gated, staged_suite):
    """A check whose pinned file is on disk and matches its manifest entry runs, and
    its row says passed."""
    _, rows = gated
    assert staged_suite.row(rows, "test_reads_good")["outcome"] == "passed"


@code("SA00455")
@category("repository")
@objective("functionality")
@negative
def test_a_check_whose_pinned_file_changed_is_blocked(gated, staged_suite):
    """A check whose pinned file no longer matches its manifest entry is skipped as
    blocked, naming the file, and the run still passes, because only the stability
    check for that file fails for the change."""
    result, rows = gated
    row = staged_suite.row(rows, "test_reads_changed")
    assert row["outcome"] == "skipped"
    assert row["outcome_reason"].startswith(
        "blocked: inputs/set/changed.txt does not match its manifest entry"
    )
    assert result.ret == 0


@code("SA00456")
@category("repository")
@objective("functionality")
@negative
def test_a_check_whose_pinned_file_is_not_downloaded_is_skipped(gated, staged_suite):
    """A check whose pinned file is recorded but not on disk is skipped, and the
    reason names the file and says to run acquire_sources."""
    _, rows = gated
    row = staged_suite.row(rows, "test_reads_missing")
    assert row["outcome"] == "skipped"
    assert row["outcome_reason"] == (
        "not downloaded: inputs/set/missing.txt; run acquire_sources"
    )


UNMATCHED_SUITE = '''
    import pytest


    @pytest.mark.needs_pinned("inputs/no_such_folder/*.txt")
    def test_reads_unrecorded():
        """Reads files no manifest records."""
    '''


@code("SA00457")
@category("repository")
@objective("functionality")
@negative
def test_a_check_naming_a_file_no_manifest_records_errors(staged_suite):
    """A check whose @needs_pinned names files no manifest records is a mistake in the
    check, so its set-up fails: the run fails, the row says error, and the terminal
    names the pattern and says to correct the marker."""
    result, out = staged_suite.run(UNMATCHED_SUITE)
    assert result.ret == 1
    row = staged_suite.row(staged_suite.report(out), "test_reads_unrecorded")
    assert row["outcome"] == "error"
    assert row["outcome_reason"] == "set-up failed"
    result.stdout.fnmatch_lines(
        [
            "*no manifest records a file matching inputs/no_such_folder/*.txt*",
            "*correct the @needs_pinned marker*",
        ]
    )
