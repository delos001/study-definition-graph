"""
Script:      deny_pinned_edits.py
Description: A Claude Code hook that refuses any Write or Edit to a pinned file
             or a hand-written manifest. It runs before the tool call, reads the
             call's details from stdin, and answers deny or allow.

             One rule decides what is pinned: everything under inputs/. That
             folder holds only downloads recorded in a manifest, so nothing
             there is ever edited by hand. The two files the project writes
             into it itself, README.md and .gitkeep, are allowed. The six
             hand-written manifests at the top of manifests/ are refused too;
             the machine-written ones under manifests/study_documents/ are
             not, since the fetch script is meant to write them.

             The repo root is taken from CLAUDE_PROJECT_DIR, which Claude Code
             sets to the folder the session was opened in. The call's cwd is
             used only when that variable is absent, because cwd follows any
             cd run in the session and would make the hook look in the wrong
             place and allow everything.

             This turns the rule in CLAUDE.md, pinned files are never edited,
             into something Claude cannot break by mistake. It does not cover
             edits made through a shell command; those are still on the person
             reviewing the session. It uses only the standard library and
             reads no file, so it works before the package is installed.

Inputs:      stdin  (JSON from Claude Code: tool_name, tool_input.file_path, cwd)
             CLAUDE_PROJECT_DIR  (environment, the repo root)

Outputs:     Nothing on disk. Prints a JSON decision to stdout when the call is
             refused; prints nothing when it is allowed.

Usage:       Not run by hand. Named in .claude/settings.json as a PreToolUse
             hook for Write and Edit.
                 echo '{"tool_input":{"file_path":"inputs/x.pdf"}}' | python .claude/hooks/deny_pinned_edits.py

Exit codes:  0  always; the decision is in the printed JSON, not the exit code

Date:        2026-09-09
Owner:       Jason Delosh
"""

import json
import os
import sys
from pathlib import Path

# The one folder that holds pinned files. scripts/find_unrecorded_files.py
# walks the same folder; the two agree because there is only one name.
PINNED_FOLDER = "inputs"

# Files the project writes into the pinned folder itself.
OWN_FILES = ("README.md", ".gitkeep")

MANIFEST_FOLDER = "manifests"


def repo_root(call: dict) -> Path:
    """Gives back the repo root: CLAUDE_PROJECT_DIR when Claude Code sets it,
    otherwise the call's cwd, otherwise the process's own working directory."""
    root = os.environ.get("CLAUDE_PROJECT_DIR") or call.get("cwd") or str(Path.cwd())
    return Path(root).resolve()


def repo_relative(file_path: str, root: Path) -> Path | None:
    """Turns the path Claude is about to write into a path relative to the
    repo root, or None if the file is outside the repo."""
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
    local = relative.as_posix()

    if parts[0] == PINNED_FOLDER and relative.name not in OWN_FILES:
        return (
            f"{local} is under {PINNED_FOLDER}/, which holds only pinned downloads. "
            "Pinned files are never edited (CLAUDE.md). Only README.md and .gitkeep are "
            "written there by hand; everything else arrives through acquire_sources and "
            "a manifest entry."
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
    is pinned. Anything unexpected in the input is treated as allow, so a
    malformed message can never block ordinary work."""
    try:
        call = json.load(sys.stdin)
        file_path = call["tool_input"]["file_path"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return 0

    relative = repo_relative(file_path, repo_root(call))
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
