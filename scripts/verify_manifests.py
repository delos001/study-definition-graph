"""
Script:      verify_manifests.py
Description: Checks every pinned file against the checksum recorded for it in
             data/manifests/, and reports anything that has drifted.

             This exists because CLAUDE.md requires the recorded sha256 to be
             verified before a pinned file is parsed, and until now that check
             was only ever run by hand. A rule nobody can run is a rule nobody
             keeps.

             It also reports the reverse case: files sitting under data/raw/
             that no manifest records. Those are the dangerous ones. A file with
             a bad checksum announces itself; a file nobody wrote down looks
             exactly like a file that was properly pinned, and will not survive
             a fresh clone because data/ is gitignored.

Inputs:      data/manifests/*.json   (read-only)
             data/raw/**             (read-only, opened only to hash)

Outputs:     A report on stdout. Writes nothing to disk.

Usage:       python scripts/verify_manifests.py
                 check everything, print one line per set plus any problems
             python scripts/verify_manifests.py --verbose
                 also list every file that passed
             python scripts/verify_manifests.py --quiet
                 print nothing; use the exit code. For hooks and scripts.
             python scripts/verify_manifests.py --set raw_ich_m11
                 check one manifest only

Exit codes:  0  every recorded file is present and matches, no unrecorded files
             1  a recorded file is missing, or its checksum does not match
             2  a file under data/raw/ is not recorded in any manifest
             3  no manifests found, or one could not be parsed

             1 outranks 2 when both occur, because a corrupted pin is worse
             than an undocumented one.

Date:        2026-08-18
Author:      Jason Delosh
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


### Constants ##################################################################

# Paths are resolved from this file's own location rather than the working
# directory, so the script behaves the same whether it is run from the repo root
# or from inside scripts/.
REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_DIR = REPO_ROOT / "data" / "manifests"
RAW_DIR = REPO_ROOT / "data" / "raw"

# Files hashed in 1 MB chunks rather than read whole. The corpus includes a
# 5.9 MB PDF and a 3.8 MB one, and reading those into memory to hash them is
# needless when hashlib accepts a stream.
CHUNK_BYTES = 1024 * 1024

# Placeholder files that exist only to keep an empty directory in git. They are
# not data and are never recorded in a manifest, so they must not be reported
# as unrecorded.
IGNORED_NAMES = {".gitkeep"}

# Excel writes a "~$name.xlsx" lock file beside any workbook that is currently
# open, inside data/raw/ despite that tree being immutable. It is an editor
# artifact rather than data, it disappears when the workbook is closed, and
# read_xlsx.py already filters it for the same reason. Skipped here so a merely
# open spreadsheet does not fail the check.
IGNORED_PREFIXES = ("~$",)


### Hashing ####################################################################


def sha256_of(path: Path) -> str:
    """
    Return the hex sha256 of a file, read in chunks.

    Chunked rather than path.read_bytes() so that memory use stays flat
    regardless of file size. The corpus is already multi-megabyte and the ICH
    technical specification alone is 3.8 MB.
    """
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK_BYTES), b""):
            digest.update(chunk)

    return digest.hexdigest()


### Manifest loading ###########################################################


def load_manifests(only: str | None) -> tuple[list[tuple[Path, dict]], list[str]]:
    """
    Read every manifest, or just the one named by --set.

    Returns the loaded manifests and a list of load errors. Errors are collected
    and returned rather than raised, so that one malformed manifest does not
    hide the state of every other set. The caller decides what to do with them.

    The --set argument is matched against the filename stem, so both
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


### Checking ###################################################################


def check_entry(entry: dict) -> tuple[str, str]:
    """
    Check one manifest entry against the file on disk.

    Returns (status, detail) where status is one of "ok", "missing",
    "mismatch" or "malformed".

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
    # hole in the guarantee this script exists to provide.
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


def find_unrecorded(recorded: set[str]) -> list[str]:
    """
    List files under data/raw/ that no manifest accounts for.

    Comparison is on posix-style relative paths because manifests are written
    with forward slashes and this repo runs on Windows, where Path renders
    backslashes. Normalising both sides to posix avoids every path in the
    corpus reporting as unrecorded.

    Returns paths sorted, so output is stable between runs and diffable.
    """
    if not RAW_DIR.exists():
        return []

    found = []
    for path in RAW_DIR.rglob("*"):
        if not path.is_file() or path.name in IGNORED_NAMES:
            continue
        if path.name.startswith(IGNORED_PREFIXES):
            continue

        relative = path.relative_to(REPO_ROOT).as_posix()
        if relative not in recorded:
            found.append(relative)

    return sorted(found)


### Entry point ################################################################


def main() -> int:
    """
    Check every manifest, print a report, and return a shell exit code.

    Output is organised by manifest so a failure can be traced to the set it
    belongs to, and therefore to the url it should be re-downloaded from.
    """
    # Manifest role names and file paths are plain ASCII, but the report is
    # printed alongside output from the other scripts, which force UTF-8 for the
    # same reason: a Windows console defaults to a legacy code page.
    sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        description="Verify pinned files against the checksums in data/manifests/."
    )
    parser.add_argument("--set", help="check one manifest only, e.g. raw_ich_m11")
    parser.add_argument("--verbose", action="store_true", help="list files that passed")
    parser.add_argument("--quiet", action="store_true", help="print nothing; use the exit code")
    args = parser.parse_args()

    def say(line: str = "") -> None:
        """Print unless --quiet. Wrapped so no check has to test the flag."""
        if not args.quiet:
            print(line)

    manifests, load_errors = load_manifests(args.set)

    if load_errors:
        for error in load_errors:
            say(f"MANIFEST UNREADABLE  {error}")

    if not manifests:
        say(f"No manifests found in {MANIFEST_DIR}.")
        return 3

    recorded_paths: set[str] = set()
    problems: list[str] = []
    total_ok = 0

    for manifest_path, manifest in manifests:
        entries = manifest.get("files", [])
        set_ok = 0
        set_problems: list[str] = []

        for entry in entries:
            status, detail = check_entry(entry)

            if entry.get("local"):
                recorded_paths.add(entry["local"])

            if status == "ok":
                set_ok += 1
                if args.verbose:
                    say(f"    ok        {detail}")
            else:
                set_problems.append(f"    {status.upper():9} {detail}")

        total_ok += set_ok
        marker = "OK  " if not set_problems else "FAIL"
        say(f"{marker}  {manifest_path.name:28} {set_ok}/{len(entries)} verified")

        for line in set_problems:
            say(line)
        problems.extend(set_problems)

    # Only meaningful across the whole corpus, so it is skipped when --set has
    # narrowed the run to one manifest; every other set's files would otherwise
    # be reported as unrecorded.
    unrecorded = [] if args.set else find_unrecorded(recorded_paths)

    say()
    say(f"{total_ok} file(s) verified, {len(problems)} problem(s), {len(unrecorded)} unrecorded.")

    if unrecorded:
        say()
        say("Present under data/raw/ but not in any manifest:")
        for path in unrecorded:
            say(f"    {path}")
        say()
        say("data/ is gitignored, so an unrecorded file cannot be restored from a")
        say("clean clone. Add it to a manifest or delete it.")

    if load_errors:
        return 3
    if problems:
        return 1
    if unrecorded:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
