"""
Script:      deny_pinned_edits.py
Description: A Claude Code hook that refuses any Write or Edit to a pinned file
             or a hand-written manifest. It runs before the tool call, reads the
             call's details from stdin, and answers deny or allow.

             Pinned files are everything under standards/ and data/, except the
             READMEs and .gitkeep placeholders written by this project. The six
             hand-written manifests at the top of manifests/ are covered too;
             the machine-written ones under manifests/data_raw/ are not, since
             the fetch script is meant to write them.

             This turns the rule in CLAUDE.md, pinned files are never edited,
             into something Claude cannot break by mistake. It does not cover
             edits made through a shell command; those are still on the person
             reviewing the session.

Inputs:      stdin  (JSON from Claude Code: tool_name, tool_input.file_path, cwd)

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

# Everything under these folders is a pinned download, except the files named
# in ALLOWED_NAMES, which the project writes itself.
PINNED_FOLDERS = ("standards", "data")
ALLOWED_NAMES = ("README.md", ".gitkeep")

# The hand-written manifests sit directly in this folder. Manifests one level
# down, in manifests/data_raw/, are written by the fetch script and are allowed.
MANIFEST_FOLDER = "manifests"


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


def reason_to_deny(relative: Path) -> str | None:
    """Gives back the sentence explaining why this path must not be written,
    or None if writing it is fine."""
    parts = relative.parts
    if not parts:
        return None

    if parts[0] in PINNED_FOLDERS and relative.name not in ALLOWED_NAMES:
        return (
            f"{relative.as_posix()} is a pinned file under {parts[0]}/. Pinned files are "
            "never edited (CLAUDE.md). To replace one, change its manifest entry and run "
            "acquire_sources."
        )

    if parts[0] == MANIFEST_FOLDER and len(parts) == 2 and relative.suffix == ".json":
        return (
            f"{relative.as_posix()} is a hand-written manifest. A version never moves; "
            "a deliberate re-pin is recorded in DECISIONS.md and made by a person, not by "
            "an edit in a session."
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

    reason = reason_to_deny(relative)
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
