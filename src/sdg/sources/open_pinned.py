"""
Script:      open_pinned.py
Description: Provides a pipeline with a path of a pinned file after proving it is the
             recorded one. A pinned file is a downloaded standard or worked
             example whose version never moves.

             open_pinned(path)
             - finds the file's manifest entry,
             - fingerprints the file and compares it to the entry, and
             - hands off the path for the verified file with its identity: its sha256
             and the url it was fetched from, which carries the source's version.
             A stage stamps that identity on whatever it produces from the file.
             A file that cannot be proven is refused, with a message naming the cause
             and the remedy.

             This is the only way pipeline code obtains a pinned file. The
             manifest is how the proof is made today; if a source is one day
             served by an API, the inside of this module changes and the
             stages calling it do not.

             Each step is a function in the sdg package. This module runs them
             in order:
             - read manifests: find the entry for the path
             - fingerprint: compare the file to its entry

             The package must be installed from inside the repo (pip install
             -e .), or nothing under manifests/ can be found. That is checked
             before any path is used.

Inputs:      manifests/*.json, manifests/data_raw/*.json   (read-only)
             the pinned file named                          (read-only, opened only to hash)

Outputs:     Nothing on disk. Hands back the file with its identity: local
             path, path on this machine, sha256, url, and the manifest that
             records it.

Usage:       Not run directly; imported.
             from sdg.sources.open_pinned import open_pinned
                spec = open_pinned("standards/cdisc/usdm_v4/dataStructure.yml")
                spec.read_text()   -> the content
                spec.sha256        -> its fingerprint, for provenance
                spec.url           -> where it came from, carrying the version

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

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

#######################################################################################
### Where things are ###
#
# Paths are resolved from this file's own location rather than the working
# directory, so behaviour is the same wherever a process is launched from. This
# file lives at src/sdg/pinned.py, so the repo root is three parents up.

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_DIR = REPO_ROOT / "data" / "manifests"
RAW_DIR = REPO_ROOT / "data" / "raw"

# Files hashed in 1 MB chunks rather than read whole. The corpus includes a
# 5.9 MB PDF and a 3.8 MB one, and reading those into memory to hash them is
# needless when hashlib accepts a stream.
CHUNK_BYTES = 1024 * 1024


class NotInRepoError(Exception):
    """The package is not running from inside its repo, so nothing under data/
    or scripts/ can be found. Happens when it was installed without -e, which
    copies the code into Python's own library folder."""


def require_repo() -> Path:
    """Confirms the folder this module takes to be the repo really is one (it
    holds pyproject.toml and data/manifests/) and produces that path. Raises
    NotInRepoError naming where the package was found and the install command
    that fixes it."""
    if (REPO_ROOT / "pyproject.toml").exists() and MANIFEST_DIR.is_dir():
        return REPO_ROOT
    raise NotInRepoError(
        f"sdg is not running from inside its repo (found at {Path(__file__).resolve().parent}).\n"
        "  fix -> install it from the repo checkout with: pip install -e ."
    )


#######################################################################################
### Reading manifests and hashing files ###
#
# Shared with scripts/verify_manifests.py and scripts/fetch_sources.py. Function
# names are unchanged from when they lived in verify_manifests.py.


def sha256_of(path: Path) -> str:
    """Takes a file path and produces its hex sha256, read in chunks so memory
    use stays flat regardless of file size."""
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK_BYTES), b""):
            digest.update(chunk)

    return digest.hexdigest()


def load_manifests(only: str | None) -> tuple[list[tuple[Path, dict]], list[str]]:
    """Reads every manifest under data/manifests/, or just the one named, and
    produces the loaded (path, manifest) pairs plus a list of load errors.

    Errors are collected and returned rather than raised, so that one malformed
    manifest does not hide the state of every other set. The caller decides what
    to do with them. `only` is matched against the filename stem, so both
    "raw_ich_m11" and "raw_ich_m11.json" work.
    """
    errors: list[str] = []
    loaded: list[tuple[Path, dict]] = []

    wanted = only.removesuffix(".json") if only else None

    for path in sorted(MANIFEST_DIR.glob("*.json")):
        if wanted and path.stem != wanted:
            continue

        # A manifest that will not parse is a hard problem worth naming
        # precisely, since every downstream check depends on it. Absorbed here
        # so the remaining manifests are still checked.
        try:
            loaded.append((path, json.loads(path.read_text(encoding="utf-8"))))
        except (json.JSONDecodeError, OSError) as exc:
            errors.append(f"{path.name}: cannot read ({exc})")

    return loaded, errors


def check_entry(entry: dict) -> tuple[str, str]:
    """Takes one manifest entry and checks the file it names against it,
    producing (status, detail) where status is "ok", "missing", "mismatch" or
    "malformed".

    Size is checked before the hash, and reported separately, because the two
    failures mean different things. A size difference is usually a truncated or
    replaced download; a size match with a hash difference means the content
    changed while staying the same length, which is the case worth looking at
    closely.
    """
    local = entry.get("local")
    recorded_hash = entry.get("sha256")

    # An entry missing either field cannot be checked at all. Reported rather
    # than skipped, because a manifest row that verifies nothing is a silent
    # hole in the guarantee this module exists to provide.
    if not local or not recorded_hash:
        return "malformed", f"{entry.get('name', '?')}: entry has no local path or no sha256"

    path = REPO_ROOT / local

    if not path.exists():
        return "missing", local

    recorded_size = entry.get("bytes")
    actual_size = path.stat().st_size
    if recorded_size is not None and actual_size != recorded_size:
        return "mismatch", f"{local}: size {actual_size} bytes, manifest says {recorded_size}"

    actual_hash = sha256_of(path)
    if actual_hash != recorded_hash:
        return "mismatch", f"{local}: sha256 {actual_hash[:16]}..., manifest says {recorded_hash[:16]}..."

    return "ok", local


#######################################################################################
### The contract: pinned() ###


class IntegrityError(Exception):
    """A pinned file could not be verified against its manifest, or does not
    match it. One cause, one message: a size or fingerprint mismatch, an
    unreadable or absent manifest, a malformed entry, and a file no entry
    records each say what happened and how to recover."""


# Recovery paths shown when the file's fingerprint or size does not match. Only
# this cause has three ways back; the others carry a one-line remedy.
_MISMATCH_RECOVERY = (
    "  changed by accident   -> remove the file, then use python scripts/fetch_sources.py\n"
    "  read it anyway (once) -> use the caller's unverified mode, e.g. --allow-unpinned\n"
    "  a real new version    -> deliberate re-pin (new url, re-fetch, recompute); not a quick edit"
)


@dataclass(frozen=True)
class PinnedFile:
    """One verified pinned file and its identity. `local` is the repo-relative
    path as the manifest writes it; `path` is where it is on this machine;
    `sha256` and `url` are the fingerprint and origin recorded for it (the url
    carries the source's version, e.g. a git commit); `manifest` names the set
    that records it."""

    local: str
    path: Path
    sha256: str
    url: str
    manifest: str

    def read_text(self, encoding: str = "utf-8") -> str:
        """Produces the file's content as text. A caller that needs the raw
        bytes (a PDF, a workbook) opens `path` itself."""
        return self.path.read_text(encoding=encoding)


def _as_local(target: str | Path) -> str:
    """Takes a repo-relative string or any Path and produces the repo-relative,
    forward-slash form manifests use. A path outside the repo stays as given,
    so the not-recorded message can show it in full."""
    if isinstance(target, str):
        return target.replace("\\", "/")
    resolved = target.resolve()
    if resolved.is_relative_to(REPO_ROOT):
        return resolved.relative_to(REPO_ROOT).as_posix()
    return str(resolved)


def pinned(target: str | Path) -> PinnedFile:
    """Takes a pinned file's path (repo-relative, as manifests write it, or any
    Path) and produces it as a PinnedFile after checking it against its manifest
    entry.

    Raises NotInRepoError if the package is not running from its repo,
    FileNotFoundError if the file has not been downloaded, and IntegrityError
    for every other way the check can fail, each with its own message.
    """
    require_repo()
    local = _as_local(target)
    manifests, errors = load_manifests(None)

    # An unreadable or absent manifest is a manifest problem, not a data
    # problem. Named as such, or the remedy would send the user to re-download
    # a file that is fine.
    if errors:
        raise IntegrityError(
            f"cannot verify {local}: a manifest is unreadable\n"
            + "".join(f"  {error}\n" for error in errors)
            + "  fix -> restore data/manifests/ (git checkout), then re-run"
        )
    if not manifests:
        raise IntegrityError(
            f"cannot verify {local}: no manifests found in data/manifests/\n"
            "  fix -> restore data/manifests/ (git checkout), then re-run"
        )

    for manifest_path, manifest in manifests:
        for entry in manifest.get("files", []):
            if entry.get("local") != local:
                continue

            status, detail = check_entry(entry)
            if status == "ok":
                return PinnedFile(
                    local=local,
                    path=REPO_ROOT / local,
                    sha256=entry["sha256"],
                    url=entry.get("url", ""),
                    manifest=manifest_path.name,
                )
            if status == "missing":
                raise FileNotFoundError(REPO_ROOT / local)
            # check_entry's detail already says whether size or sha256 differs,
            # so it is passed through rather than summarised.
            if status == "mismatch":
                raise IntegrityError(
                    f"{detail}\n  (recorded in {manifest_path.name})\n{_MISMATCH_RECOVERY}"
                )
            # "malformed": the entry has no sha256, so nothing can be checked.
            raise IntegrityError(
                f"cannot verify {local}: its manifest entry is malformed ({detail})\n"
                f"  fix -> repair that entry in {manifest_path.name}, then re-run"
            )

    # The manifests never recorded it: a test fixture, or a pinned file whose
    # manifest row was never written.
    raise IntegrityError(
        f"cannot verify {local}: no manifest entry records it\n"
        "  a pinned file   -> add its manifest entry (url, sha256, bytes)\n"
        "  a test fixture  -> read it directly; pinned() is only for recorded files"
    )
