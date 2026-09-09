"""
Script:      deny_pinned_edits.py
Description: A Claude Code hook that refuses any Write or Edit to a pinned file
             or a hand-written manifest. It runs before the tool call, reads the
             call's details from stdin, and answers deny or allow.

             What counts as pinned is read from the manifests, not kept as a
             list here. A file is pinned if a manifest entry records it, and a
             folder is pinned if some manifest's local_dir points into it,
             today standards/ and data/. Inside a pinned folder, only the files
             the project writes itself are allowed: README.md and .gitkeep. The
             six hand-written manifests at the top of manifests/ are refused
             too; the machine-written ones under manifests/data_raw/ are not,
             since the fetch script is meant to write them.

             This turns the rule in CLAUDE.md, pinned files are never edited,
             into something Claude cannot break by mistake. It does not cover
             edits made through a shell command; those are still on the person
             reviewing the session. It uses only the standard library, because
             it must work before the package is installed. If the manifests
             cannot be read it allows the call, so a broken manifest never
             blocks the work of fixing it.

Inputs:      stdin  (JSON from Claude Code: tool_name, tool_input.file_path, cwd)
             manifests/*.json, manifests/data_raw/*.json   (read-only)

Outputs:     Nothing on disk. Prints a JSON decision to stdout when the call is
             refused; prints nothing when it is allowed.

Usage:       Not run by hand. Named in .claude/settings.json as a PreToolUse
             hook for Write and Edit.
                 echo '{"tool_input":{"file_path":"standards/x.pdf"}}' | python .claude/hooks/deny_pinned_edits.py

Exit codes:  0  always; the decision is in the printed JSON, not the exit code

Date:        2026-09-09
Owner:       Jason Delosh
"""

import json
import sys
from pathlib import Path

# Files the project writes into the pinned folders itself. The same short list
# is in scripts/find_unrecorded_files.py; this hook cannot import it because
# it runs before the package is installed.
OWN_FILES = ("README.md", ".gitkeep")

MANIFEST_FOLDER = "manifests"


def read_manifests(root: Path) -> tuple[set[str], set[str]]:
    """Reads every manifest under manifests/ and manifests/data_raw/ and gives
    back two sets: the local paths every entry records, and the top-level
    folders the manifests point into. Any manifest that cannot be read is
    skipped, so this hook never blocks work on a broken manifest."""
    recorded: set[str] = set()
    roots: set[str] = set()
    folder = root / MANIFEST_FOLDER
    for path in list(folder.glob("*.json")) + list((folder / "data_raw").glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        local_dir = data.get("local_dir") or ""
        if local_dir:
            roots.add(Path(local_dir).parts[0])
        for entry in data.get("files", []):
            local = entry.get("local")
            if local:
                recorded.add(local)
    return recorded, roots


def repo_relative(file_path: str, cwd: str) -> Path | None:
    """Turns the path Claude is about to write into a path relative to the
    repo root, or None if the file is outside the repo. The repo root is the
    folder Claude Code is running in, which the hook receives as cwd."""
    root = Path(cwd).resolve()
    target = Path(file_path)
    if not target.is_absolute():
        target = root / target
    target = target.resolve()
    try:
        return target.relative_to(root)
    except ValueError:
        return None


def reason_to_deny(relative: Path, recorded: set[str], roots: set[str]) -> str | None:
    """Gives back the sentence explaining why this path must not be written,
    or None if writing it is fine."""
    parts = relative.parts
    if not parts:
        return None
    local = relative.as_posix()

    if local in recorded:
        return (
            f"{local} is a pinned file recorded in a manifest. Pinned files are never "
            "edited (CLAUDE.md). To replace one, change its manifest entry and run "
            "acquire_sources."
        )

    if parts[0] in roots and relative.name not in OWN_FILES:
        return (
            f"{local} is inside {parts[0]}/, a pinned folder. Only README.md and .gitkeep "
            "are written there by hand; everything else arrives through acquire_sources "
            "and a manifest entry."
        )

    if parts[0] == MANIFEST_FOLDER and len(parts) == 2 and relative.suffix == ".json":
        return (
            f"{local} is a hand-written manifest. A version never moves; a deliberate "
            "re-pin is recorded in DECISIONS.md and made by a person, not by an edit in "
            "a session."
        )

    return None


def main() -> int:
    """Reads the tool call from stdin and prints a deny decision if the path
    is protected. Anything unexpected in the input is treated as allow, so a
    malformed message can never block ordinary work."""
    try:
        call = json.load(sys.stdin)
        file_path = call["tool_input"]["file_path"]
        cwd = call.get("cwd") or str(Path.cwd())
    except (json.JSONDecodeError, KeyError, TypeError):
        return 0

    relative = repo_relative(file_path, cwd)
    if relative is None:
        return 0

    recorded, roots = read_manifests(Path(cwd).resolve())
    reason = reason_to_deny(relative, recorded, roots)
    if reason is None:
        return 0

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
