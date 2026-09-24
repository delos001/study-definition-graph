"""
Script:      staged_manifests.py
Description: Builds the made-up pinned files and manifest entries that checks stage
             in place of the real ones: the bytes a staged file holds, and a
             manifest entry that matches them, or differs in one chosen way.

             It is shared by the checks of more than one script, so it lives in
             validation/shared/ rather than in any one test file. The fixtures
             that write these files to disk are in validation/conftest.py, because
             pytest finds a shared fixture only there.

Inputs:      Nothing on disk.

Outputs:     Nothing on disk. Hands back bytes and manifest entries.

Usage:       from validation.shared.staged_manifests import CONTENT, LOCAL
                 use in a check, or in a fixture in validation/conftest.py

Exit codes:  None of its own. It is imported by the checks.

Date:        2026-09-24
Owner:       Jason Delosh
"""

from __future__ import annotations

import hashlib
from typing import Any

from sdg.sources.read_manifests import Entry

#######################################################################################
### Staged pinned files ###

# The bytes a staged pinned file holds. Short, so a check that changes them can show
# the change in one line.
CONTENT = b"pinned bytes\n"

# Where a staged pinned file sits, as a manifest writes it, and the sha256 of its
# bytes.
LOCAL = "inputs/set_a/file.txt"
SHA256 = hashlib.sha256(CONTENT).hexdigest()


def entry_for_bytes(content: bytes, **overrides: Any) -> Entry:
    """Build a manifest entry whose size and sha256 match the given bytes.

    Args:
        content: The bytes the entry describes.
        **overrides: Any field to change, so a check can stage exactly one difference.

    Returns:
        The entry.
    """
    # Typed as Any so the fields can be handed to Entry by name, which takes one text
    # and one number.
    fields: dict[str, Any] = dict(
        name="file.txt",
        url="https://example.invalid/file.txt",
        local="inputs/file.txt",
        bytes=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
        manifest="set_a.json",
    )
    fields.update(overrides)
    return Entry(**fields)
