"""
Script:      finalize_file.py
Description: Brings a completed download to its final state with its final
             name, or discards the download that does not match fingerprinting.

             place(partial) strips the .part suffix and renames the file into
             the expected location. It refuses if a file already exists at the final
             name and raises an error.  Pinned files are never overwritten.  A person
             must look at the existing file and decide whether to delete or move it by
             hand, then run acquire_sources again, which redoes only that file.

             discard(partial) deletes the temporary file. Called when the
             fingerprint did not match, so a wrong download never sits on
             disk under any name.

             This module moves or deletes the one file it is given. It does not
             fingerprint, does not open manifests and does not download; the
             program using it, acquire_sources, has already decided which of the
             two to do.

Inputs:      one .part file

Outputs:     place: the file under its final name; the .part name is gone.
             discard: nothing; the .part file is gone.
             Hands back the final path (place) or nothing (discard).

Usage:       Not run directly; imported.
             from sdg.sources import place, discard
                place(partial)     -> final path
                discard(partial)   -> nothing

Exit codes:  None. Not run on its own, so no exit code. On a problem it stops
             and hands an error to the program using it, which decides what to
             do. The errors it can hand back:
             FileExistsError     a file is already at the final name; nothing moved
             FileNotFoundError   the .part file does not exist
             ValueError          the path given does not end in .part

Date:        2026-09-08
Owner:       Jason Delosh
"""

from __future__ import annotations

from pathlib import Path

from .fetch_file import PARTIAL_SUFFIX

#######################################################################################
### Finalize the File ###


def _final_path(partial: Path) -> Path:
    """Work out the final name of a .part file by removing the suffix.

    Args:
        partial: The .part file.

    Returns:
        The same path without the .part suffix.

    Raises:
        ValueError: The path does not end in .part, so it is not a download this module
            should touch.
    """
    if partial.name.endswith(PARTIAL_SUFFIX):
        return partial.with_name(partial.name[: -len(PARTIAL_SUFFIX)])
    raise ValueError(f"not a {PARTIAL_SUFFIX} file: {partial}")


def place(partial: Path) -> Path:
    """Rename a .part file to its final name.

    The check for a file already at the final name comes before the rename, because a
    rename would replace it without asking, and a pinned file is never replaced by code.

    Args:
        partial: The .part file to place.

    Returns:
        The final path the file now sits at.

    Raises:
        ValueError: The path does not end in .part.
        FileNotFoundError: There is no .part file at the path.
        FileExistsError: A file is already at the final name. Nothing is moved, and the
            .part file stays where it is.
    """
    partial = Path(partial)
    final = _final_path(partial)

    if not partial.is_file():
        raise FileNotFoundError(partial)

    # The check comes before the rename because rename would replace an
    # existing file without asking. A pinned file is never replaced by code.
    if final.exists():
        raise FileExistsError(
            f"{final} already exists; {partial.name} left in place\n"
            "  fix -> look at the existing file, delete or move it by hand, then run acquire_sources again"
        )

    partial.replace(final)
    return final


def discard(partial: Path) -> None:
    """Delete a .part file.

    Args:
        partial: The .part file to delete.

    Raises:
        ValueError: The path does not end in .part.
        FileNotFoundError: There is no .part file at the path.
    """
    partial = Path(partial)
    _final_path(partial)  # refuses anything that is not a .part file

    if not partial.is_file():
        raise FileNotFoundError(partial)

    partial.unlink()
