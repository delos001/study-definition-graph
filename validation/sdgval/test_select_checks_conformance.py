"""
Script:      test_select_checks_conformance.py
Description: The conformance checks for src/sdgval/select_checks.py. They confirm
             that the real groups file it reads, validation/validation_groups.yml,
             follows its rules. The technical checks are in
             test_select_checks_technical.py, beside this file.

Inputs:      validation/validation_groups.yml     (read-only)
             validation/validation_inventory.csv (read-only)
             validation/**/test_*.py             (read-only; collected by pytest in
                 a separate process, never run)

Outputs:     Writes nothing to disk.

Usage:       pytest validation/sdgval/test_select_checks_conformance.py
                 run these checks
             pytest validation/sdgval/test_select_checks_conformance.py -v
                 one line per check with its result

Exit codes:  pytest's own: 0 all passed, 1 some failed

Date:        2026-09-26
Owner:       Jason Delosh
"""

from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

import yaml

from sdgval.build_inventory import INVENTORY_PATH, REPO_ROOT
from sdgval.labels import category, code, objective

# The stability check reads every pinned file but carries no needs_pinned label, on
# purpose. The label would skip it when a file changed, which is the one time it must
# fail. It belongs in the pinned group all the same.
STABILITY_CHECK = "SA00106"


def groups() -> dict[str, dict]:
    """Read the real groups file.

    Returns:
        The groups by name, as the file writes them.
    """
    path = REPO_ROOT / "validation" / "validation_groups.yml"
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def needs_pinned_ids() -> set[str]:
    """List the ids of every check that carries the needs_pinned label.

    pytest itself is asked, in a separate process that only collects, because a
    check may carry the label through a shared name such as needs_pinned_file, which
    reading the test files as text would miss. The runs it lists are matched to
    their ids through the inventory.

    Returns:
        The ids.
    """
    listing = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-m", "needs_pinned"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    runs = {
        line.split("[")[0]
        for line in listing.splitlines()
        if line.startswith("validation/") and "::" in line
    }
    with Path(INVENTORY_PATH).open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    return {
        row["id"]
        for row in rows
        if f"{row['folder_path']}/{row['file_name']}::{row['name']}" in runs
    }


#######################################################################################
### The conformance checks ###


@code("SA00511")
@category("repository")
@objective("conformance")
def test_every_group_lists_only_ids_the_inventory_holds():
    """Every id each group in validation/validation_groups.yml lists is a check in
    validation/validation_inventory.csv, so no group names a check that does not
    exist."""
    with Path(INVENTORY_PATH).open(encoding="utf-8", newline="") as fh:
        known = {row["id"] for row in csv.DictReader(fh)}
    unknown = {
        name: sorted(set(map(str, group.get("ids") or [])) - known)
        for name, group in groups().items()
    }
    assert not {name: ids for name, ids in unknown.items() if ids}


@code("SA00512")
@category("repository")
@objective("conformance")
def test_the_pinned_group_lists_every_check_that_reads_a_pinned_file():
    """The pinned group lists every check that carries the needs_pinned label, and the
    stability check, and nothing else, so a new check that reads a pinned file cannot
    be left out of it."""
    listed = set(map(str, groups()["pinned"]["ids"]))
    assert listed == needs_pinned_ids() | {STABILITY_CHECK}
