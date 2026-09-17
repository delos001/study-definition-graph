# .claude/

This folder holds the Claude Code configuration for this repo.


| File | What it is |
| --- | --- |
| `settings.json` | The project settings, committed. It names every hook below and when it runs. |
| `settings.local.json` | Personal settings for this machine, not committed. It holds nothing about hooks. |
| `hooks/` | The scripts the hooks run. Each follows `.claude/rules/writing_python_files.md` like every other Python file, `repo_tools/verify_headers.py`, run by the pre-commit hook `.githooks/pre-commit`, holds them to it, and their checks live under `validation/claude_hooks/`. |
| `rules/` | The rules Claude Code loads when a matching file is opened. `writing_python_files.md` is the one rule and covers every Python file the project writes. |

## Hooks in use

Claude Code hooks run around Claude's own tool calls in a session; they are different from git hooks, which run around git commands for anyone and live in `.githooks/`.

| Runs | Script | What it does |
| --- | --- | --- |
| Before every Write or Edit | `hooks/deny_pinned_edits.py` | Refuses the call if the path is under `inputs/`, except a `README.md` or `.gitkeep`, or is one of the hand-written manifests at the top of `manifests/`. One rule, no list: everything under `inputs/` is pinned. The repo root comes from `CLAUDE_PROJECT_DIR`, so the check holds whatever folder the session has moved to. This makes the CLAUDE.md rule that pinned files are never edited something Claude cannot break by mistake. It does not see edits made through a shell command. |

To add a hook, write its script in `hooks/` with a header block, name it in `settings.json`, and add a row to the table above.
