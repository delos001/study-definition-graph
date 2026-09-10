"""
Script:      read_manifests.py
Description: Reads the manifests and provides three pieces of information:
             1 which manifests exist:
                - all of them, or
                - one, by name
             2 which manifest entry describes a given file, if any,
             3 an entry's details as named fields rather than JSON keys
                - its url,
                - local path,
                - size,
                - fingerprint

             Manifests under manifests/study_documents/ are read alongside the top-level
             manifests.
             This module never downloads, hashes or checks a file against disk.

Inputs:      manifests/*.json, manifests/study_documents/*.json   (read-only)

Outputs:     Nothing on disk.
             Hands back, in memory: the manifests found, one entry, or an entry's fields.

Usage:       Not run directly; imported.
             from sdg.sources import manifests, entry_for
                manifests()                  -> every manifest
                manifests("cdisc_usdm_v4")   -> one manifest, by name
                entry_for("inputs/standards/cdisc/usdm_v4/dataStructure.yml") -> that file's
                  entry, or None

Exit codes:  None. Not run on its own, so no exit code. On a problem it stops
             and hands an error to the program using it, which decides what to
             do. The errors it can hand back:
             NotInRepoError   the package is not running from inside its repo
             ManifestError    a manifest cannot be read, an entry lacks a required
                              field, or a field holds a value that can never be
                              right: a size that is not a whole number, or a
                              sha256 that is not 64 lowercase hex characters

Date:        2026-09-08
Owner:       Jason Delosh
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

#######################################################################################
### Repo Navigation ###
#
# The repo root is found from this file's own location. This file sits at
# src/sdg/sources/read_manifests.py, so the root is four folders up. Finding it
# this way, rather than from the working directory, means the answer is the
# same no matter where a program was started from.

REPO_ROOT = Path(__file__).resolve().parents[3]
MANIFEST_DIR = REPO_ROOT / "manifests"

# Study manifests are in manifests/study_documents/. The fetch script writes one per study.
# All manifests need to be read to identify documents that have been pinned.
STUDY_MANIFEST_DIR = MANIFEST_DIR / "study_documents"

# Every entry must have the five fields shown below. If one is missing, the file cannot
# be fetched, checked or placed. A missing field is reported as a mistake in
# the manifest; the entry is not skipped.
REQUIRED_FIELDS = ("name", "url", "local", "bytes", "sha256")

# Two of the fields are typed by hand and have one valid shape each. A size
# with a comma or a space in it, or a sha256 with the wrong length or in
# uppercase, can never match any file, so it is reported here with the value
# as written rather than later as a mismatch that sends a person to
# re-download a file that is fine.
SIZE_RE = re.compile(r"[0-9]+")
SHA256_RE = re.compile(r"[0-9a-f]{64}")


#######################################################################################
### Error Classes ###


class NotInRepoError(Exception):
    """Informs that the package is not running from inside its repo, so it cannot find
    manifests/. This happens when it was installed without -e, which copies the
    code into Python's own library folder."""


class ManifestError(Exception):
    """Informs that a manifest cannot be read, none exist, or an entry lacks a required
    field. The message names the file and the cause."""


#######################################################################################
### Verify Repo Install ###


def require_repo() -> Path:
    """Checks that this module is running from inside the repo, and gives back
    the repo root: verifies the pyproject.toml exists and names this package.
    Note: a missing manifests folder is a different problem reported by manifests()
    """
    pyproject = REPO_ROOT / "pyproject.toml"
    if pyproject.exists() and 'name = "sdg"' in pyproject.read_text(encoding="utf-8"):
        return REPO_ROOT
    raise NotInRepoError(
        f"sdg is not running from inside its repo (found at {Path(__file__).resolve().parent}).\n"
        "  fix -> install it from the repo checkout with: pip install -e ."
    )


#######################################################################################
### Define Manifest and Entry ###


# @dataclass decorator for the class that holds these fields.  Without it you
# need a separate setup method assigning each one plus code to print readably and
# compare two of them. The decorator (frozen=True) makes the fields immutable, so they
# cannot be changed after creation.
@dataclass(frozen=True)
class Entry:
    """One manifest entry, describing one pinned file."""

    name: str
    url: str
    local: str  # the path from the repo root, written with forward slashes to match the manifest
    bytes: int
    sha256: str
    manifest: (
        str  # the name of the manifest file the entry came from, used in messages.
    )

    # create decorator (@property) lets path be read like a field, entry.path, instead of
    # called as entry.path().  It is worked out from local when asked for, not stored.
    @property
    def path(self) -> Path:
        """The file's location on this machine."""
        return REPO_ROOT / self.local


# @dataclass writes the setup, printing and comparison code for this class from
# the field list below. frozen=True makes a Manifest unchangeable once read.
# entries is a tuple rather than a list for the same reason: a tuple cannot be
# added to or altered, so the entries read from the file stay as they were read.
@dataclass(frozen=True)
class Manifest:
    """One manifest file."""

    name: str  # the file name without .json, which is also the set name.
    path: Path
    local_dir: str  # the folder its files land in.
    entries: tuple[Entry, ...]


#######################################################################################
### Read Manifest ###


def _entry_from(raw: dict, manifest_name: str) -> Entry:
    """Turns one entry, as read from JSON, into an Entry (see class Entry).
    If a required field is missing it raises ManifestError naming the manifest, the
    entry and the field."""

    label = raw.get("name") or raw.get("local") or "?"
    fix = f"  fix -> repair that entry in manifests/{manifest_name}, then re-run"

    missing = [field for field in REQUIRED_FIELDS if raw.get(field) in (None, "")]
    if missing:
        raise ManifestError(
            f"{manifest_name}: entry {label} lacks {', '.join(missing)}\n{fix}"
        )

    # The value is shown as written, in quotes, so a person sees their own
    # typo and not a claim that the field is missing.
    size = str(raw["bytes"])
    if not SIZE_RE.fullmatch(size):
        raise ManifestError(
            f'{manifest_name}: entry {label} has bytes "{size}", which is not a whole number\n{fix}'
        )
    sha256 = str(raw["sha256"])
    if not SHA256_RE.fullmatch(sha256):
        raise ManifestError(
            f'{manifest_name}: entry {label} has sha256 "{sha256}", '
            f"which is not 64 lowercase hex characters\n{fix}"
        )

    return Entry(
        name=raw["name"],
        url=raw["url"],
        local=raw["local"],
        bytes=int(raw["bytes"]),
        sha256=raw["sha256"],
        manifest=manifest_name,
    )


def _read_one(path: Path) -> Manifest:
    """Reads one manifest file from disk and gives back a Manifest object holding its
    entries (see class Manifest).
    Raises ManifestError if the file is not valid JSON or an entry is malformed."""

    # A manifest that is not valid JSON and one that cannot be opened are the
    # same problem: nothing in it can be trusted. The message names the file,
    # because the usual fix is to restore that file with git.
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise ManifestError(
            f"{path.name}: cannot read ({exc})\n"
            "  fix -> restore manifests/ (git checkout), then re-run"
        ) from exc

    entries = tuple(_entry_from(item, path.name) for item in raw.get("files", []))
    return Manifest(
        name=path.stem, path=path, local_dir=raw.get("local_dir", ""), entries=entries
    )


#######################################################################################
### Return Manifest Information ###


def manifests(only: str | None = None) -> list[Manifest]:
    """Gives back every manifest, or only the one named. The hand-written
    manifests in manifests/ and the study manifests under study_documents/ are read together.
    They are sorted by path so every run lists them in the same order.
    Raises ManifestError when the folder is missing or empty, when the named set does
    not exist, or when any manifest cannot be read.
    """
    require_repo()

    if not MANIFEST_DIR.is_dir():
        raise ManifestError(
            f"no manifests folder at {MANIFEST_DIR}\n"
            "  fix -> restore manifests/ (git checkout), then re-run"
        )

    # `only` is matched against the file name without .json, so both "cdisc_usdm_v4"
    # and "cdisc_usdm_v4.json" work.
    wanted = only.removesuffix(".json") if only else None
    paths = sorted(MANIFEST_DIR.glob("*.json")) + sorted(
        STUDY_MANIFEST_DIR.glob("*.json")
    )
    if wanted:
        paths = [path for path in paths if path.stem == wanted]

    if not paths:
        if wanted:
            raise ManifestError(f"no manifest named {wanted} in manifests/")
        raise ManifestError(
            f"no manifests found in {MANIFEST_DIR}\n"
            "  fix -> restore manifests/ (git checkout), then re-run"
        )

    return [_read_one(path) for path in paths]


def as_local(target: str | Path) -> str:
    """Turns a path into the form that can be used by manifests: relative to the repo
    root, with forward slashes. A string is taken to be repo-relative already. A
    path outside the repo is given back unchanged, so a message about it can
    show it in full."""
    if isinstance(target, str):
        return target.replace("\\", "/")
    resolved = target.resolve()
    if resolved.is_relative_to(REPO_ROOT):
        return resolved.relative_to(REPO_ROOT).as_posix()
    return str(resolved)


def entry_for(target: str | Path) -> Entry | None:
    """Gives back the manifest entry that records a file, or None if no manifest does.
    Every manifest is searched each time. A search is computationally cheap so no index
    is kept."""
    local = as_local(target)
    for manifest in manifests():
        for entry in manifest.entries:
            if entry.local == local:
                return entry
    return None
