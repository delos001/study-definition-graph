"""
Script:      test_select_checks_integrity.py
Description: The integrity checks for src/sdgval/select_checks.py. They confirm that
             the real groups file it reads, validation/validation_groups.yml, leaves
             nothing out. The pinned groups have to list every check that reads a
             pinned file, and the hook groups have to hold a check for every command
             the pre-commit hook runs. The technical checks are in
             test_select_checks_technical.py, and the conformance checks in
             test_select_checks_conformance.py, beside this file.

Inputs:      validation/validation_groups.yml     (read-only)
             validation/validation_inventory.csv (read-only)
             .pre-commit-config.yaml             (read-only)
             pyproject.toml                      (read-only)
             validation/**/test_*.py             (read-only; collected by pytest in
                 a separate process, never run)

Outputs:     Writes nothing to disk.

Usage:       pytest validation/sdgval/test_select_checks_integrity.py
                 run these checks
             pytest validation/sdgval/test_select_checks_integrity.py -v
                 one line per check with its result

Exit codes:  None of its own. It runs inside pytest.

Date:        2026-09-29
Owner:       Jason Delosh
"""

from __future__ import annotations

import csv
import subprocess
import sys
import tomllib
from pathlib import Path

import yaml

from sdgval.build_inventory import INVENTORY_PATH, REPO_ROOT
from sdgval.labels import category, code, objective
from validation.shared.validation_groups import read_groups

# The stability check reads every pinned file but carries no needs_pinned label, on
# purpose. The label would skip it when a file changed, which is the one time it must
# fail. It belongs in the pinned groups all the same.
STABILITY_CHECK = "SA00106"

# The groups that together hold every check reading a pinned file, one per aspect of
# quality, because no group mixes aspects.
PINNED_GROUPS = ("pinned_integrity", "pinned_conformance")

# The groups that together reproduce the pre-commit hook on the real repo, one per
# aspect of quality.
HOOK_GROUPS = ("hook_integrity", "hook_conformance")


def inventory_rows() -> list[dict[str, str]]:
    """Read the rows of the real inventory.

    Returns:
        One dict per row, keyed by column name.
    """
    with Path(INVENTORY_PATH).open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def needs_pinned_ids() -> set[str]:
    """List the ids of every check that carries the needs_pinned label.

    pytest itself is asked, in a separate process that only collects, because a
    check may carry the label through a shared name such as needs_pinned_file, which
    reading the check files as text would miss. The runs it lists are matched to
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
    return {
        row["id"]
        for row in inventory_rows()
        if f"{row['folder_path']}/{row['file_name']}::{row['name']}" in runs
    }


def hook_command_files() -> dict[str, str]:
    """Name the file behind each command a step of the real pre-commit hook runs.

    A step's entry runs its command through conda, so the command is the one word of
    the entry that pyproject.toml installs as a command. The file is the module
    pyproject.toml points that command at. A step whose entry names no installed
    command is kept with its whole entry, so the check fails naming it rather than
    passing over it.

    Returns:
        The file behind each command, as its path from the repo root, keyed by the
        command.
    """
    pyproject = tomllib.loads(
        (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    scripts = pyproject["project"]["scripts"]
    config = yaml.safe_load(
        (REPO_ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    )
    files = {}
    for repo in config["repos"]:
        for hook in repo["hooks"]:
            words = hook["entry"].split()
            command = next((word for word in words if word in scripts), None)
            if command is None:
                files[hook["entry"]] = "(no installed command)"
                continue
            module = scripts[command].split(":")[0]
            files[command] = "src/" + module.replace(".", "/") + ".py"
    return files


#######################################################################################
### The integrity checks ###


@code("SA00512")
@category("repository")
@objective("completeness")
def test_the_pinned_groups_list_every_check_that_reads_a_pinned_file():
    """The pinned_integrity and pinned_conformance groups together list every check
    that carries the pinned-file label, and the stability check, and nothing else. A
    new check that reads a pinned file cannot be left out of them."""
    defined = read_groups()
    listed = {str(i) for name in PINNED_GROUPS for i in defined[name]["ids"]}
    assert listed == needs_pinned_ids() | {STABILITY_CHECK}


@code("SA00618")
@category("repository")
@objective("completeness")
def test_the_hook_groups_hold_a_check_for_every_hook_command():
    """Every command a step of the real pre-commit hook in .pre-commit-config.yaml runs
    has at least one check in the hook_integrity or hook_conformance group, so running
    those groups reproduces every step of the hook."""
    defined = read_groups()
    listed = {str(i) for name in HOOK_GROUPS for i in defined[name]["ids"]}
    covered = {
        f"{row['target_folder_path']}/{row['target_file_name']}"
        for row in inventory_rows()
        if row["id"] in listed
    }
    uncovered = {
        command: file
        for command, file in hook_command_files().items()
        if file not in covered
    }
    assert uncovered == {}
