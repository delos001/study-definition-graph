"""
Script:      verify_pinned.py
Description: Verifies a pinned file is the file of record then hands a pipeline stage
             the path and identity of the pinned file.

             Each step is a function in sdg package:
             verify_pinned(path)
             - finds the file's manifest entry,
             - fingerprints the file and compares it to the entry, and
             - hands the file back with its source version's identity: its sha256 and
               the url it was fetched from.
             A stage stamps that identity on whatever it produces from the file.
             A file that cannot be proven is refused, with a message naming the cause
             and the remedy.

             This is the only way code obtains a pinned file. The
             manifest is how the proof is made today; if a source is one day
             served by an API, the inside of this module changes and the
             stages calling it do not.

             The package must be installed from inside the repo (pip install
             -e .), or nothing under manifests/ can be found. The manifest
             reader checks that before it looks for anything.

Inputs:      manifests/*.json, manifests/study_documents/*.json   (read-only)
             the pinned file named                  (read-only, opened only to hash)

Outputs:     Nothing on disk. Hands back the file with its identity: local
             path, path on this machine, sha256, url, and the manifest that
             records it.

Usage:       Not run directly; imported.
             from sdg.sources import verify_pinned
                spec = verify_pinned("inputs/standards/cdisc/usdm_v4/dataStructure.yml")
                spec.read_text()   -> the content
                spec.sha256        -> its fingerprint, for provenance
                spec.url           -> where it came from, carrying the version
             A string is read as a path from the repo root; a Path may be absolute.

Exit codes:  None. Not run on its own, so no exit code. On a problem it stops
             and hands an error to the program using it, which decides what to
             do. The errors it can hand back:
             NotInRepoError      the package is not running from inside its repo
             FileNotFoundError   the file has not been downloaded
             IntegrityError      no entry records the file, a manifest cannot be
                                 read, or the file does not match its entry

Date:        2026-09-04
Owner:       Jason Delosh
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .fingerprint_file import compare
from .read_manifests import ManifestError, as_local, entry_for

#######################################################################################
### Error Class ###


class IntegrityError(Exception):
    """Class that informs that a pinned file could not be proven to be the recorded one.
    One cause, one message:
    - no manifest entry records the file,
    - a manifest cannot be read, or
    - the file's size or sha256 differs from its entry.
    Each message says what happened and how to recover."""


# These three lines are shown when the file's size or sha256 differs from its
# entry. That cause has three ways back; the other causes have one remedy each.
_MISMATCH_RECOVERY = (
    "  changed by accident   -> remove the file, then run python -m sdg.sources.acquire_sources\n"
    "  read it anyway (once) -> use the caller's unverified mode, e.g. --allow-unpinned\n"
    "  a real new version    -> deliberate re-pin (new url, re-fetch, recompute); not a quick edit"
)


#######################################################################################
### Define Pinned File ###


# @dataclass decorator writes the setup, printing and comparison code for this class
# from the field list below. frozen=True makes a PinnedFile unchangeable once made,
# because it is the proof that was given to the stage and nothing should alter it.
@dataclass(frozen=True)
class PinnedFile:
    """One pinned file that has been proven, with its identity."""

    local: str  # the path from the repo root, as the manifest writes it
    path: Path  # where the file is on this machine
    sha256: str  # its fingerprint, for provenance
    url: str  # where it was fetched from; the url carries the source's version
    manifest: str  # the manifest file that records it, for messages

    def read_text(self, encoding: str = "utf-8") -> str:
        """Returns the file's content as text. A stage that needs the raw
        bytes, for a PDF or a workbook, opens `path` itself."""
        return self.path.read_text(encoding=encoding)


#######################################################################################
### Verify Target Matches Manifest ###


def verify_pinned(target: str | Path) -> PinnedFile:
    """Confirms that the file at `target` is the file its manifest entry records,
    and returns it as a PinnedFile (see class PinnedFile): the file's path and
    identity, which the stage uses to read the file.

    Raises NotInRepoError if the package is not running from its repo.
    Raises FileNotFoundError if the file has not been downloaded.
    Raises IntegrityError for any other failure, each with its own message.
    """
    local = as_local(target)

    # A manifest that cannot be read is a manifest problem, not a file problem.
    # It is reported as one, or the remedy would send a person to re-download a
    # file that is fine.
    try:
        entry = entry_for(local)
    except ManifestError as exc:
        raise IntegrityError(f"cannot verify {local}: {exc}") from exc

    if entry is None:
        raise IntegrityError(
            f"cannot verify {local}: no manifest entry records it\n"
            "  a pinned file   -> add its manifest entry (url, sha256, bytes)\n"
            "  a test fixture  -> read it directly; verify_pinned() is only for recorded files"
        )

    if not entry.path.is_file():
        raise FileNotFoundError(entry.path)

    result = compare(entry.path, entry)
    if not result.matched:
        raise IntegrityError(
            f"{local}: {result.detail}\n  (recorded in {entry.manifest})\n{_MISMATCH_RECOVERY}"
        )

    return PinnedFile(
        local=local,
        path=entry.path,
        sha256=entry.sha256,
        url=entry.url,
        manifest=entry.manifest,
    )
