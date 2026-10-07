"""
Script:      write_manifests.py
Description: Writes a file's entry into an existing manifest or creates a new manifest
             for the file, or set of files, if one does not exist.

             When the manifest does not exist yet, it is created from the set details
             obtained by the script that calls this script. Details such as its
             description and its folder are used.
             When it does exist, the entry is added to its list of file entries.

             To tell whether a file is already recorded, its local path, such as
             inputs/study_documents/NCT05259917/Prot_000.pdf, is compared with each
             entry's local path.

             If a manifest already exists, its contents are read into memory and the
             new entry is then added to those contents. A new manifest starts from the
             set details. In either case, a temporary file is created
             (manifestname + .part), so an existing manifest isn't damaged during the
             update.

             When a manifest already exists, the .part file is renamed to the
             previous manifest's name, replacing the previous manifest.
             When no previous manifest exists, the .part is dropped from the file name
             to create the new manifest.

             An entry already in the manifest is never replaced unless the script that
             calls this script asks for that, because an entry is the record of what was
             pinned.

             A manifest is written in the same layout as hand-written manifests.
             Rewriting any existing manifest in this layout leaves it unchanged,
             so a diff shows only the entry that changed.

Inputs:      one manifest file, when it already exists (read, then rewritten)
             one entry's fields, and the set details for a new manifest

Outputs:     The manifest file with the entry added or replaced, and its folder if it
             did not exist.
             Hands back the path of the manifest written.

Usage:       This file is not run directly; other code imports it.
             from sdg.sources.write_manifests import write_entry
                write_entry(path, set_details, entry)                -> path written
                write_entry(path, set_details, entry, replace=True)  -> path written

Exit codes:  There are none, because this file is not run on its own. On a problem it
             stops and hands an error to the program using it, which decides what to
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


def write_entry(
    path: Path,
    set_details: dict[str, Any],
    entry: dict[str, Any],
    replace: bool = False,
) -> Path:
    """Record one file's details in a manifest. Create the manifest when it does not
    exist.

    Args:
        path: The manifest file, such as manifests/study_documents/NCT05259917.json.
        set_details: The fields that describe the whole set rather than one file,
            such as set, description and local_dir, which come before the list of
            files. They are used only when the manifest is created. An existing manifest
            keeps its own set details.
        entry: The details of one file being recorded, such as name, url, local path,
            size and sha256. It must hold every field in REQUIRED_FIELDS in read_manifests.py.
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

    # A new entry's local path is compared with each existing entry's local path. When
    # one matches and replace is True, the existing entry is replaced where it stands,
    # so the order of the files does not change. When replace is False, the write is
    # refused.
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

    # The updated manifest is first written to a temporary file (manifestname + .part)
    # in the same folder. When that write is complete, the .part file is renamed to the
    # manifest's name, replacing the previous manifest if there was one. A write that
    # fails part way damages only the .part file.
    partial = path.with_name(path.name + ".part")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        partial.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        partial.replace(path)
    except OSError as exc:
        # The .part file is removed so it is not left beside the manifest. When it
        # cannot be removed either, it stays, because the error raised below already
        # says what went wrong.
        try:
            partial.unlink(missing_ok=True)
        except OSError:
            pass
        raise ManifestNotWrittenError(f"{path} could not be written ({exc}).") from exc
    return path


#######################################################################################
### Getting manifest contents into memory ###


def _read_or_start(path: Path, set_details: dict[str, Any]) -> dict[str, Any]:
    """Read an existing manifest associated with the given file or set of files, or
    create a new manifest from the set details, and place the information into memory.

    Args:
        path: The manifest file.
        set_details: The fields that describe the whole set rather than one file,
            from write_entry.

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
