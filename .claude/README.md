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
| Before every Write or Edit | `hooks/deny_pinned_edits.py` | Refuses the call if the path is a pinned file, meaning anything under `standards/` or `data/` except a `README.md` or `.gitkeep`, or one of the hand-written manifests at the top of `manifests/`. This makes the CLAUDE.md rule that pinned files are never edited something Claude cannot break by mistake. It does not see edits made through a shell command. |

To add a hook, write its script in `hooks/` with a header block, name it in `settings.json`, and add a row here.
