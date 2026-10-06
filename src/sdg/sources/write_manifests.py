"""
Script:      write_manifests.py
Description: Writes one file's entry into a manifest, so the file is recorded as
             pinned.

             When the manifest does not exist yet, it is created from the set details
             the caller gives, such as its description and its folder. When it does
             exist, the entry is added to its list of files.

             An entry already in the manifest is never replaced unless the caller asks
             for that, because an entry is the record of what was pinned. Entries are
             matched by their local path, because two studies can post files with the
             same name.

             The manifest is written to a temporary file first, then renamed over the
             real one, so a write that fails part way never leaves a damaged manifest.
             The layout matches the hand-written manifests, with two spaces per
             indent. Rewriting any existing manifest in this layout leaves it
             unchanged, so a diff shows only the entry that changed.

Inputs:      one manifest file, when it already exists (read, then rewritten)
             one entry's fields, and the set details for a new manifest

Outputs:     The manifest file with the entry added or replaced, and its folder if it
             did not exist.
             Hands back the path of the manifest written.

Usage:       This file is not run directly; other code imports it.
             from sdg.sources.write_manifests import write_manifests
                write_manifests(path, set_details, entry)                -> path written
                write_manifests(path, set_details, entry, replace=True)  -> path written

Exit codes:  There are none, because this file is not run on its own. On a problem it stops
             and hands an error to the program using it, which decides what to
             do. Every error is a kind of ManifestError, which read_manifests.py
             defines, and carries the exit number and sub-code a command reports it
             with, from docs/exit_codes.csv. The last two below are defined in this
             file. The errors it can hand back:
             ManifestError             the entry lacks a field every entry needs,
                                       or the existing manifest is not a manifest
                                       object with a list of files
             ManifestUnreadableError   the existing manifest cannot be opened
             ManifestUnparseableError  the existing manifest is not valid JSON
             ManifestEntryExistsError  the manifest already records the file, and
                                       replacing it was not asked for
             ManifestNotWrittenError   the manifest, or its folder, could not be
                                       written to disk

Date:        2026-09-09
Owner:       Jason Delosh
"""

import json
from pathlib import Path
from typing import Any

from .read_manifests import (
    REQUIRED_FIELDS,
    ManifestError,
    ManifestUnparseableError,
    ManifestUnreadableError,
)

#######################################################################################
### Failures ###

# Each failure has an exit number and a sub-code, both listed in docs/exit_codes.csv.
# The other failures this file can raise are defined in read_manifests.py, because
# reading a manifest fails the same way wherever it is read.


class ManifestEntryExistsError(ManifestError):
    """Raised when the manifest already records the file, and replacing it was not
    asked for."""

    exit_code = 19
    sub_code = "MANIFEST-ENTRY-EXISTS"


class ManifestNotWrittenError(ManifestError):
    """Raised when the manifest, or its folder, could not be written to disk."""

    exit_code = 20
    sub_code = "MANIFEST-NOT-WRITTEN"


#######################################################################################
### Writing an entry ###


def write_manifests(
    path: Path,
    set_details: dict[str, Any],
    entry: dict[str, Any],
    replace: bool = False,
) -> Path:
    """Record one file in a manifest, creating the manifest when it does not exist.

    Args:
        path: The manifest file, such as manifests/study_documents/NCT05259917.json.
        set_details: The fields that describe the whole set rather than one file,
            such as set, description and local_dir, which come before the list of
            files. They are used only when the manifest is created,
            and an existing manifest keeps its own.
        entry: The file's entry. It must hold every field in REQUIRED_FIELDS in
            read_manifests.py.
        replace: True to replace an entry already recorded for the same local path.

    Returns:
        The path of the manifest written.

    Raises:
        ManifestError: The entry lacks a required field, or the existing manifest is
            not a manifest object with a list of files.
        ManifestUnreadableError: The existing manifest cannot be opened.
        ManifestUnparseableError: The existing manifest is not valid JSON.
        ManifestEntryExistsError: The manifest already records the file, and replace
            is False.
        ManifestNotWrittenError: The manifest, or its folder, could not be written.
    """
    missing = [field for field in REQUIRED_FIELDS if entry.get(field) in (None, "")]
    if missing:
        raise ManifestError(
            f"{path.name}: the entry for {entry.get('name', '?')} lacks {', '.join(missing)}."
        )

    manifest = _read_or_start(path, set_details)

    # An entry is matched by its local path. A matching entry is replaced where it
    # stands, so the order of the files in the manifest does not change.
    files = manifest["files"]
    for position, existing in enumerate(files):
        if existing.get("local") == entry["local"]:
            if not replace:
                raise ManifestEntryExistsError(
                    f"{path.name} already records {entry['local']}."
                )
            files[position] = entry
            break
    else:
        files.append(entry)

    # The manifest is written beside itself under a .part name, then renamed over the
    # real file. A write that fails part way fails on the .part file, so the real
    # manifest is left as it was.
    partial = path.with_name(path.name + ".part")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        partial.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        partial.replace(path)
    except OSError as exc:
        raise ManifestNotWrittenError(f"{path} could not be written ({exc}).") from exc
    return path


def _read_or_start(path: Path, set_details: dict[str, Any]) -> dict[str, Any]:
    """Read an existing manifest, or start a new one from the set details.

    Args:
        path: The manifest file.
        set_details: The fields that describe the whole set rather than one file,
            from write_manifests.

    Returns:
        The manifest as a dictionary, holding a list under files.

    Raises:
        ManifestUnreadableError: The existing manifest cannot be opened.
        ManifestUnparseableError: The existing manifest is not valid JSON.
        ManifestError: The existing manifest is not a manifest object with a list of
            files.
    """
    if not path.exists():
        return {**set_details, "files": []}

    # An existing manifest that cannot be opened, or is damaged, is refused rather
    # than overwritten, because writing over it would lose the files it records.
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ManifestUnreadableError(f"{path.name} cannot be opened ({exc}).") from exc
    try:
        manifest = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ManifestUnparseableError(
            f"{path.name} is not valid JSON ({exc})."
        ) from exc
    if not isinstance(manifest, dict) or not isinstance(manifest.get("files"), list):
        raise ManifestError(
            f"{path.name} is not a manifest object with a list of files."
        )
    return manifest
