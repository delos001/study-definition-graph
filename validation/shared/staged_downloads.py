"""
Script:      staged_downloads.py
Description: Describes a staged download: a file written under its .part name, as a
             download leaves it, with nothing yet at its final name. Checks of the
             step that moves a finished download into place stage one of these in
             place of a real download.

             The fixtures that write one to disk are in validation/conftest.py,
             because pytest finds a shared fixture only there.

Inputs:      Nothing on disk.

Outputs:     Nothing on disk.

Usage:       from validation.shared.staged_downloads import CONTENT, Staged
                 use in a check, or in a fixture in validation/conftest.py

Exit codes:  None of its own. It is imported by the checks.

Date:        2026-09-24
Owner:       Jason Delosh
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

#######################################################################################
### A staged download ###

# The bytes a staged download holds.
CONTENT = b"downloaded bytes\n"


@dataclass(frozen=True)
class Staged:
    """One download staged under its .part name, and the final name it is for."""

    partial: Path
    final: Path
