"""
Script:      test_skip_rules_technical.py
Description: Checks for src/sdgval/skip_rules.py, the plugin that skips a check
             whose pinned files are not downloaded or have changed, and fails the
             set-up of a check whose label names a file no manifest records, or a
             fixture file that is not there.

             Each check stages a throwaway suite with the staged_suite fixture in
             validation/conftest.py. The suite stages a small repo of its own and
             points the manifest reader at it, then runs as a separate pytest
             process with a report asked for, and the report shows what the rule
             did with each check. The check of two runs in one process runs a
             short script instead, which starts pytest twice and changes a pinned
             file between the runs, and reads what pytest printed.

Inputs:      Nothing real. Each staged suite and its small repo are written to
             pytest's own temporary folder.

Outputs:     Writes nothing to disk outside pytest's temporary folder.

Usage:       pytest validation/sdgval/test_skip_rules_technical.py
                 run these checks
             pytest validation/sdgval/test_skip_rules_technical.py -v
                 one line per check with its result

Exit codes:  None of its own. It runs inside pytest.

Date:        2026-09-24
Owner:       Jason Delosh
"""

from __future__ import annotations

import sys

import pytest

from sdgval.labels import category, code, negative, objective, positive

#######################################################################################
### The pinned-file gate ###
#
# A throwaway suite stages a small repo with one pinned file that matches its entry,
# one that has changed, one that was never downloaded, and a pattern no manifest
# records. Each of its checks names one of them with @needs_pinned, or several at
# once, and the report shows what the gate did with each.


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


    @pytest.mark.needs_pinned("inputs/set/good.txt", "inputs/set/missing.txt")
    def test_reads_good_then_missing():
        """Reads two files named one by one, where the second was never downloaded."""


    @pytest.mark.needs_pinned("inputs/set/*.txt")
    def test_reads_the_whole_set():
        """Reads every file in the set, where the first file matches its entry and the
        second has changed."""
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


@code("SA00620")
@category("repository")
@objective("functionality")
@negative
def test_a_second_file_the_label_names_is_looked_at_too(gated, staged_suite):
    """A check whose label names two pinned files, the first in order and the second
    not downloaded, is skipped, and the reason names the second file."""
    _, rows = gated
    row = staged_suite.row(rows, "test_reads_good_then_missing")
    assert row["outcome"] == "skipped"
    assert row["outcome_reason"] == (
        "not downloaded: inputs/set/missing.txt; run acquire_sources"
    )


@code("SA00621")
@category("repository")
@objective("functionality")
@negative
def test_every_file_a_pattern_matches_is_looked_at(gated, staged_suite):
    """A check whose label is a pattern matching several pinned files, the first in
    order and a later one changed, is skipped as blocked, naming the changed file."""
    _, rows = gated
    row = staged_suite.row(rows, "test_reads_the_whole_set")
    assert row["outcome"] == "skipped"
    assert row["outcome_reason"].startswith(
        "blocked: inputs/set/changed.txt does not match its manifest entry"
    )


# The manifest reader is pointed at a small staged repo with one manifest, so the
# suite never reads the real manifests.
UNMATCHED_SUITE = '''
    import json
    from pathlib import Path

    import pytest

    from sdg.sources import read_manifests

    ROOT = Path(__file__).parent / "staged_repo"
    (ROOT / "manifests" / "study_documents").mkdir(parents=True, exist_ok=True)
    (ROOT / "pyproject.toml").write_text('name = "sdg"', encoding="utf-8")
    (ROOT / "manifests/set.json").write_text(json.dumps({"files": []}), encoding="utf-8")
    read_manifests.REPO_ROOT = ROOT
    read_manifests.MANIFEST_DIR = ROOT / "manifests"
    read_manifests.STUDY_MANIFEST_DIR = ROOT / "manifests" / "study_documents"


    @pytest.mark.needs_pinned("inputs/no_such_folder/*.txt")
    def test_reads_unrecorded():
        """Reads files no manifest records."""
    '''


@code("SA00457")
@category("repository")
@objective("functionality")
@negative
def test_a_check_naming_a_file_no_manifest_records_errors(staged_suite):
    """A check whose pinned-file label names files no manifest records fails at set-up,
    because the label is a mistake. The run fails, the row says error, and the terminal
    says to correct the label."""
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


#######################################################################################
### Checks the inventory has switched off ###

# Two checks, one of which the staged inventory marks as switched off.
SWITCHED_OFF_SUITE = """
    import pytest

    @pytest.mark.code("XYZ0601")
    @pytest.mark.objective("functionality")
    def test_switched_off():
        \"\"\"A check the inventory marks as not active.\"\"\"

    @pytest.mark.code("XYZ0602")
    @pytest.mark.objective("functionality")
    def test_runs():
        \"\"\"A check the inventory marks as active.\"\"\"
    """


def stage_inventory(staged_suite, status: str, reason: str) -> None:
    """Write an inventory under the staged suite marking XYZ0601 with a status.

    Args:
        staged_suite: The throwaway suite, from validation/conftest.py.
        status: The status XYZ0601 is given.
        reason: The reason recorded for it.
    """
    staged_suite.validation.mkdir(exist_ok=True)
    (staged_suite.validation / "validation_inventory.csv").write_text(
        f"id,status,status_reason\nXYZ0601,{status},{reason}\nXYZ0602,active,\n",
        encoding="utf-8",
    )


@code("SA00534")
@category("repository")
@objective("functionality")
@positive
def test_an_inactive_check_is_skipped_with_its_reason(staged_suite):
    """A check the inventory marks inactive is skipped, and its row gives the status
    and the reason the inventory records, while an active check still runs."""
    stage_inventory(staged_suite, "inactive", "Waiting on a new fixture.")
    result, out = staged_suite.run(SWITCHED_OFF_SUITE)
    rows = staged_suite.report(out)
    row = staged_suite.row(rows, "test_switched_off")
    assert row["outcome"] == "skipped"
    assert row["outcome_reason"] == (
        "the inventory marks this check inactive. Waiting on a new fixture."
    )
    assert staged_suite.row(rows, "test_runs")["outcome"] == "passed"


@code("SA00535")
@category("repository")
@objective("functionality")
@positive
def test_a_pending_check_is_skipped(staged_suite):
    """A check the inventory marks pending is skipped, and its row gives the status
    and the reason the inventory records."""
    stage_inventory(staged_suite, "pending", "Waiting to be switched on.")
    result, out = staged_suite.run(SWITCHED_OFF_SUITE)
    row = staged_suite.row(staged_suite.report(out), "test_switched_off")
    assert row["outcome"] == "skipped"
    assert row["outcome_reason"] == (
        "the inventory marks this check pending. Waiting to be switched on."
    )


#######################################################################################
### A fixture file a check names that is not there ###

# A check that names a fixture file validation/fixtures/ does not hold.
MISSING_FIXTURE_SUITE = """
    import pytest

    @pytest.mark.needs_fixture("no_such_file.yml")
    def test_reads_a_missing_fixture():
        \"\"\"Reads a fixture file that is not there.\"\"\"
    """


@code("SA00577")
@category("repository")
@objective("functionality")
@negative
def test_a_check_naming_a_fixture_that_is_not_there_errors(staged_suite):
    """A check whose fixture label names a file that is not in validation/fixtures/
    fails at set-up, because the label is a mistake. The run fails, the row says
    error, and the terminal names the file and says to correct the label."""
    result, out = staged_suite.run(MISSING_FIXTURE_SUITE)
    assert result.ret == 1
    row = staged_suite.row(staged_suite.report(out), "test_reads_a_missing_fixture")
    assert row["outcome"] == "error"
    assert row["outcome_reason"] == "set-up failed"
    result.stdout.fnmatch_lines(
        [
            "*validation/fixtures/no_such_file.yml is not there; correct the "
            "@needs_fixture marker*"
        ]
    )


#######################################################################################
### Two runs in one process ###
#
# A pinned file is measured once per run. Two runs in one process are staged with the
# file changed between them, and the second run must see the change.

# One check that reads a pinned file. The small repo is staged when the file is first
# collected, and the pinned file is written only when it is not there yet, so a second
# run in the same process keeps the change made between the runs.
ONE_PINNED_CHECK_SUITE = '''
    import hashlib
    import json
    from pathlib import Path

    import pytest

    from sdg.sources import read_manifests

    ROOT = Path(__file__).parent / "staged_repo"
    for folder in ("manifests/study_documents", "inputs/set"):
        (ROOT / folder).mkdir(parents=True, exist_ok=True)
    (ROOT / "pyproject.toml").write_text('name = "sdg"', encoding="utf-8")
    if not (ROOT / "inputs/set/good.txt").exists():
        (ROOT / "inputs/set/good.txt").write_bytes(b"good")
    recorded = {
        "name": "good.txt",
        "url": "https://example.invalid/good.txt",
        "local": "inputs/set/good.txt",
        "bytes": 4,
        "sha256": hashlib.sha256(b"good").hexdigest(),
    }
    (ROOT / "manifests/set.json").write_text(
        json.dumps({"files": [recorded]}), encoding="utf-8"
    )
    read_manifests.REPO_ROOT = ROOT
    read_manifests.MANIFEST_DIR = ROOT / "manifests"
    read_manifests.STUDY_MANIFEST_DIR = ROOT / "manifests" / "study_documents"


    @pytest.mark.needs_pinned("inputs/set/good.txt")
    def test_reads_good():
        """Reads a file that matches its entry."""
    '''

# Two pytest runs in one process, with the pinned file changed between them.
TWO_RUNS_WITH_A_CHANGE_BETWEEN = (
    "import sys\n"
    "from pathlib import Path\n"
    "import pytest\n"
    "first = pytest.main(['-rs', '-p', 'no:cacheprovider'])\n"
    "Path('validation/staged_repo/inputs/set/good.txt').write_bytes(b'edited')\n"
    "second = pytest.main(['-rs', '-p', 'no:cacheprovider'])\n"
    "sys.exit(first or second)\n"
)


@code("SA00578")
@category("repository")
@objective("functionality")
@positive
def test_a_second_run_in_one_process_sees_a_pinned_file_that_changed(
    staged_suite, pytester
):
    """Of two runs in one process, with a pinned file changed between them, the first
    runs the check that reads the file and the second skips it as blocked, because
    each run measures the pinned files for itself."""
    staged_suite.write(ONE_PINNED_CHECK_SUITE)
    result = pytester.run(sys.executable, "-c", TWO_RUNS_WITH_A_CHANGE_BETWEEN)
    result.stdout.fnmatch_lines(
        [
            "*1 passed*",
            "*blocked: inputs/set/good.txt does not match its manifest entry*",
            "*1 skipped*",
        ]
    )
