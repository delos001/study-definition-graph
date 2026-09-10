# .claude/

This folder holds the Claude Code configuration for this repo. Claude Code hooks run around Claude's own tool calls in a session; they are different from git hooks, which run around git commands for anyone and live in `.githooks/`.

| File | What it is |
| --- | --- |
| `settings.json` | The project settings, committed. It names every hook below and when it runs. |
| `settings.local.json` | Personal settings for this machine, not committed. It holds nothing about hooks. |
| `hooks/` | The scripts the hooks run. Each has the same header block as every script in the repo. |

## Hooks in use

| Runs | Script | What it does |
| --- | --- | --- |
| Before every Write or Edit | `hooks/deny_pinned_edits.py` | Refuses the call if the path is under `inputs/`, except a `README.md` or `.gitkeep`, or is one of the hand-written manifests at the top of `manifests/`. One rule, no list: everything under `inputs/` is pinned. The repo root comes from `CLAUDE_PROJECT_DIR`, so the check holds whatever folder the session has moved to. This makes the CLAUDE.md rule that pinned files are never edited something Claude cannot break by mistake. It does not see edits made through a shell command. |

To add a hook, write its script in `hooks/` with a header block, name it in `settings.json`, and add a row here.

## Git hooks, for reference

These live in `.githooks/`, not here, and run for anyone who commits. They are listed so this file names every hook the repo uses.

| Runs | Check | What it does |
| --- | --- | --- |
| Before every commit | `python scripts/build_index.py --check` | Refuses the commit if `scripts/README.md` is out of date with the header blocks it is generated from. |
| Before every commit | `python scripts/verify_headers.py` | Refuses the commit if any Python file under `src/sdg/` or `scripts/` lacks the full header block or has its fields out of order. |
