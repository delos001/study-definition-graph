"""
Script:      fingerprint_file.py
Description: This module measures the size and sha256 of a file, and returns whether
             the file matches the manifest entry for that file.

             The file is read in pieces, so a large PDF is never held in its entirety
             in memory.

             fingerprint(path) gives the two values every manifest entry records:
               - the file's size in bytes and
               - its sha256.

             compare(path, entry) checks both values against the entry.

             Size is checked first and reported on its own, because the two failures
             mean different things: a size difference is usually a truncated or
             replaced download, while the same size with a different sha256 means
             the content changed in place, which is the case worth a closer look.

             This module reads the file it is given and nothing else. It does
             not open manifests and does not download.

Inputs:      one file   (read-only, opened only to hash)

Outputs:     Nothing on disk.
             Hands back the fingerprint (size, sha256), or the comparison result listed
             as 'matched' or which value differed and how.

Usage:       Not run directly; imported.
             from sdg.sources import fingerprint, compare
                fingerprint(path)        -> (size, sha256)
                compare(path, entry)     -> matched, or the difference found

Exit codes:  None. Not run on its own, so no exit code. On a problem it stops
             and hands an error to the program using it, which decides what to
             do. The errors it can hand back:
             FileNotFoundError   the path does not exist

Date:        2026-09-08
Owner:       Jason Delosh
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from .read_manifests import Entry

#######################################################################################
### Settings ###

# A file is read in pieces of this size while it is hashed. One megabyte keeps
# memory use flat whatever the file size; the largest pinned file is a 5.9 MB
# PDF.
CHUNK_BYTES = 1024 * 1024


#######################################################################################
### Define Fingerprint and Comparison ###


# @dataclass decorator writes the setup, printing and comparison code for this class
# from the field list below. frozen=True makes a Fingerprint unchangeable once made,
# because it is a measurement and nothing should alter it afterwards.
@dataclass(frozen=True)
class Fingerprint:
    """The two measurements of one file that every manifest entry records."""

    bytes: int
    sha256: str


# The same decorator does the same job here.
@dataclass(frozen=True)
class Comparison:
    """The result of checking one file against its manifest entry."""

    matched: bool
    detail: str  # "matched", or which value differed and how, ready to print


#######################################################################################
### Fingerprint and Compare ###


def fingerprint(path: Path) -> Fingerprint:
    """Measures one file and gives back its size in bytes and its sha256.
    The file is read in pieces (see CHUNK_BYTES).
    Raises FileNotFoundError if the path does not exist."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(path)

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK_BYTES), b""):
            digest.update(chunk)

    return Fingerprint(bytes=path.stat().st_size, sha256=digest.hexdigest())


def compare(path: Path, entry: Entry) -> Comparison:
    """Compares output from fingerprint function against its manifest entry and returns
    whether it matched or not.  If not, it returns the details of the mismatch.
    Size is checked first. When the size differs the sha256 is not computed, because
    a difference in file size automatically means sha256 will not match, and the size
    difference is the more useful thing to report."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(path)

    actual_size = path.stat().st_size
    if actual_size != entry.bytes:
        return Comparison(
            matched=False,
            detail=f"size {actual_size} bytes, manifest says {entry.bytes}",
        )

    actual = fingerprint(path)
    if actual.sha256 != entry.sha256:
        return Comparison(
            matched=False,
            detail=f"sha256 {actual.sha256[:16]}..., manifest says {entry.sha256[:16]}...",
        )

    return Comparison(matched=True, detail="matched")
