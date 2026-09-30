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
             This module never downloads, hashes or compares a file on disk.

Inputs:      manifests/*.json, manifests/study_documents/*.json   (read-only)

Outputs:     Nothing on disk.
             Hands back, in memory: the manifests found, one entry, or an entry's fields.

Usage:       This file is not run directly; other code imports it.
             from sdg.sources import manifests, entry_for, entry_named
                manifests()                  -> every manifest
                manifests("cdisc_usdm_v4")   -> one manifest, by name
                entry_for("inputs/standards/cdisc/usdm_v4/dataStructure.yml") -> that file's
                  entry, or None
                entry_named("USDM-IG.pdf")   -> the entry recorded under that file name,
                  or None, and a refusal when two entries share the name

Exit codes:  There are none, because this file is not run on its own. On a problem it stops
             and hands an error to the program using it. Each error carries the
             exit number and sub-code a command reports it with, from
             docs/exit_codes.csv. The errors it can hand back:
             NotInRepoError            the sdg package is not running from inside
                                       its repo
             ManifestMissingError      the manifests folder is missing or empty
             ManifestNameError         no manifest has the name asked for
             ManifestUnreadableError   a manifest cannot be opened
             ManifestUnparseableError  a manifest is not valid JSON
             ManifestError             a manifest is JSON of the wrong shape, an
                                       entry lacks a required field, or a field
                                       holds a value that can never be right: a
                                       size that is not a whole number, or a
                                       sha256 that is not 64 lowercase hex
                                       characters
             OutsideInputsError        an entry's local location does not stay
                                       under inputs/ once resolved, as a full path
                                       or one that steps back up with .. does not
             AmbiguousNameError        a file name asked for is recorded by more
                                       than one entry
             Every error but the first is a kind of ManifestError, so a program
             that does not tell them apart still stops on them.

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

# Study manifests are in manifests/study_documents/. The pipeline stage that downloads a study writes one per study.
# All manifests need to be read to identify documents that have been pinned.
STUDY_MANIFEST_DIR = MANIFEST_DIR / "study_documents"

# Every entry must have the five fields shown below. If one is missing, the file cannot
# be fetched, confirmed or placed. A missing field is reported as a mistake in
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
    """Raised when the sdg package is not running from inside its repo, so it cannot find
    manifests/.

    This happens when the sdg package was installed without -e, which copies the code into
    Python's own library folder instead of pointing at the repo.
    """

    exit_code = 3
    sub_code = "NOT-IN-REPO"


class ManifestError(Exception):
    """Raised when a manifest's content breaks a requirement, and the base of every
    manifest error.

    Raised as itself, it covers a manifest that is valid JSON of the wrong shape, an
    entry that lacks a required field, and a field holding a value that can never be
    right: a size that is not a whole number, or a sha256 that is not 64 lowercase hex
    characters. The message names the file and the cause, quoting a bad value as
    written.

    Each kind of manifest error carries the exit number and sub-code a command reports
    it with, from docs/exit_codes.csv, so every command reports the same problem the
    same way.
    """

    exit_code = 15
    sub_code = "MANIFEST-INVALID"


class ManifestMissingError(ManifestError):
    """Raised when the manifests folder is missing, or holds no manifest."""

    exit_code = 12
    sub_code = "MANIFEST-MISSING"


class ManifestNameError(ManifestError):
    """Raised when no manifest has the name a person asked for."""

    exit_code = 17
    sub_code = "MANIFEST-NAME-NOT-FOUND"


class ManifestUnreadableError(ManifestError):
    """Raised when a manifest is on disk but cannot be opened."""

    exit_code = 13
    sub_code = "MANIFEST-UNREADABLE"


class ManifestUnparseableError(ManifestError):
    """Raised when a manifest is not valid JSON."""

    exit_code = 14
    sub_code = "MANIFEST-UNPARSEABLE"


class OutsideInputsError(ManifestError):
    """Raised when an entry's local location does not stay under inputs/ once resolved.

    Every pinned file lives under inputs/, and the location is where acquire_sources
    writes a download. A full path, or one that steps back up with .., would send a
    download anywhere on the machine, so the entry is refused before anything uses it.
    """

    exit_code = 15
    sub_code = "MANIFEST-LOCATION-OUTSIDE-INPUTS"


class AmbiguousNameError(ManifestError):
    """Raised when a file name asked for is recorded by more than one entry.

    Pinned files keep their publisher's names, so two pinned versions of one document
    share a name. Picking either one would be a guess, so the lookup refuses and names
    the location of each. A name is answered again once one entry records it.
    """

    exit_code = 15
    sub_code = "MANIFEST-NAME-SHARED"


#######################################################################################
### Verify Repo Install ###


def require_repo() -> Path:
    """Confirm that this module is running from inside the repo.

    The check is that pyproject.toml exists at the expected root and names the sdg package.
    A missing manifests folder is a different problem, reported by manifests().

    Returns:
        The repo root.

    Raises:
        NotInRepoError: The sdg package is not running from inside its repo.
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

    # The @property marker lets path be read like a field, as entry.path, instead of
    # being called as entry.path(). It is worked out from local when asked for, not stored.
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
    """Turn one entry, as read from JSON, into an Entry.

    Args:
        raw: The entry as the JSON reader handed it back.
        manifest_name: The name of the manifest file it came from, for messages.

    Returns:
        The same entry as an Entry, with its fields named.

    Raises:
        ManifestError: A required field is missing, or a field holds a value that can
            never match a file. The message names the manifest, the entry and the field.
        OutsideInputsError: The local location does not stay under inputs/ once
            resolved. The message names the manifest, the entry and the location.
    """

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

    # The location is resolved against the repo root, which folds away any .. and
    # lets a full path replace the root entirely, and the result has to sit inside
    # inputs/. Both sides are resolved, so a repo reached through a shortened or
    # linked folder name is compared on the same footing.
    local = str(raw["local"])
    inputs = (REPO_ROOT / "inputs").resolve()
    resolved = (REPO_ROOT / local).resolve()
    if resolved == inputs or not resolved.is_relative_to(inputs):
        raise OutsideInputsError(
            f'{manifest_name}: entry {label} has local "{local}", '
            "which does not stay under inputs/ once resolved\n"
            f"  fix -> write that entry's local in manifests/{manifest_name} as a path "
            "under inputs/, with no .., drive or leading slash, then re-run"
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
    """Read one manifest file from disk.

    Args:
        path: The manifest file.

    Returns:
        A Manifest holding the file's entries.

    Raises:
        ManifestUnreadableError: The file cannot be opened.
        ManifestUnparseableError: The file is not valid JSON.
        ManifestError: The file is JSON of the wrong shape, or one of its entries is
            malformed.
    """

    # A manifest that cannot be opened and one that is not valid JSON are told
    # apart, because the first is often a program holding the file and the second
    # is a damaged file. The message names the file, because the usual fix for a
    # damaged one is to restore it with git.
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ManifestUnreadableError(
            f"{path.name}: cannot be opened ({exc})\n"
            "  fix -> close any program holding the file, or restore manifests/ "
            "(git checkout), then re-run"
        ) from exc
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ManifestUnparseableError(
            f"{path.name}: is not valid JSON ({exc})\n"
            "  fix -> restore manifests/ (git checkout), then re-run"
        ) from exc

    # Valid JSON can still be the wrong shape: a list where the manifest object
    # should be, or an entry that is a bare value rather than an object. Either
    # is refused here with the file named, rather than surfacing later as an
    # attribute error from deep inside the entry reader.
    if not isinstance(raw, dict):
        raise ManifestError(
            f"{path.name}: cannot read (the file holds a {type(raw).__name__}, not a manifest object)\n"
            "  fix -> restore manifests/ (git checkout), then re-run"
        )
    items = raw.get("files", [])
    if not isinstance(items, list) or not all(isinstance(i, dict) for i in items):
        raise ManifestError(
            f"{path.name}: cannot read (files must be a list of entry objects)\n"
            "  fix -> restore manifests/ (git checkout), then re-run"
        )

    entries = tuple(_entry_from(item, path.name) for item in items)
    return Manifest(
        name=path.stem, path=path, local_dir=raw.get("local_dir", ""), entries=entries
    )


#######################################################################################
### Return Manifest Information ###


def manifests(only: str | None = None) -> list[Manifest]:
    """Read every manifest, or only the one named.

    The hand-written manifests in manifests/ come first, sorted by path, and the study
    manifests under manifests/study_documents/ follow them, sorted by path, so every
    run lists them in the same order.

    Args:
        only: The name of one manifest, with or without its .json suffix, or None for
            all of them.

    Returns:
        The hand-written manifests in path order, then the study manifests in path
        order.

    Raises:
        NotInRepoError: The sdg package is not running from inside its repo.
        ManifestMissingError: The manifests folder is missing or empty.
        ManifestNameError: No manifest has the name asked for.
        ManifestError: A manifest cannot be opened, is not valid JSON, or breaks a
            requirement. Each has its own kind of ManifestError.
    """
    require_repo()

    if not MANIFEST_DIR.is_dir():
        raise ManifestMissingError(
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
            raise ManifestNameError(f"no manifest named {wanted} in manifests/")
        raise ManifestMissingError(
            f"no manifests found in {MANIFEST_DIR}\n"
            "  fix -> restore manifests/ (git checkout), then re-run"
        )

    return [_read_one(path) for path in paths]


def as_local(target: str | Path) -> str:
    """Turn a path into the form a manifest uses: relative to the repo root, with forward
    slashes.

    A string is taken to be repo-relative already, and so is a relative Path: both are
    read from the repo root, never from the folder the program was started in, so the
    answer is the same wherever a command is run from. A path outside the repo is given
    back unchanged, so a message about it can show it in full.

    Args:
        target: A repo-relative string, a repo-relative Path, or an absolute path on
            this machine.

    Returns:
        The repo-relative path with forward slashes, or an outside path unchanged.
    """
    if isinstance(target, str):
        return target.replace("\\", "/")
    if not target.is_absolute():
        target = REPO_ROOT / target
    resolved = target.resolve()
    if resolved.is_relative_to(REPO_ROOT):
        return resolved.relative_to(REPO_ROOT).as_posix()
    return str(resolved)


def entry_named(name: str) -> Entry | None:
    """Find the manifest entry with a given file name.

    A caller that holds a file's name rather than its location uses this, so the
    location is written only in the manifest. Pinned files keep their publisher's
    names, so once a second version of a document is pinned the name matches two
    entries. The lookup then refuses rather than pick one.

    Args:
        name: The file name a manifest records, for example USDM-IG.pdf.

    Returns:
        The entry with that name, or None when no manifest has one.

    Raises:
        NotInRepoError: The sdg package is not running from inside its repo.
        ManifestError: A manifest cannot be read.
        AmbiguousNameError: More than one entry records the name. The message names
            the location of each.
    """
    found = [
        entry
        for manifest in manifests()
        for entry in manifest.entries
        if entry.name == name
    ]
    if len(found) > 1:
        places = "\n".join(
            f"  {entry.local} (manifests/{entry.manifest})" for entry in found
        )
        raise AmbiguousNameError(
            f"{len(found)} entries record the file name {name}:\n{places}\n"
            "  cause -> two pinned files share this name, so the name alone cannot "
            "say which version to read\n"
            "  fix -> the code asking for this name has to choose one version of "
            "the file"
        )
    return found[0] if found else None


def entry_for(target: str | Path) -> Entry | None:
    """Find the manifest entry that records a file.

    Every manifest is searched each time. A search is cheap, so no index is kept.

    Args:
        target: The file, as a repo-relative string or a path on this machine.

    Returns:
        The entry that records the file, or None when no manifest does.

    Raises:
        NotInRepoError: The sdg package is not running from inside its repo.
        ManifestError: A manifest cannot be read.
    """
    local = as_local(target)
    for manifest in manifests():
        for entry in manifest.entries:
            if entry.local == local:
                return entry
    return None
