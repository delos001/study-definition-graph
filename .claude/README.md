# .claude/

This folder holds the Claude Code configuration for this repo.

| File | What it is |
| --- | --- |
| `settings.json` | The project settings, committed. It names every hook below and when it runs. |
| `settings.local.json` | Personal settings for this machine, not committed. It holds nothing about hooks. |
| `hooks/` | The scripts the hooks run. Each follows `.claude/rules/writing_python_files.md` like every other Python file. `verify_headers`, a step of the pre-commit hook in `.pre-commit-config.yaml`, holds them to it. Their checks live under `validation/claude_hooks/`. |
| `rules/` | The rules Claude Code loads, described under Rules below. |

## Hooks in use

Claude Code hooks run around Claude's own tool calls in a session; they are different from git hooks, which run around git commands for anyone and are listed in `.pre-commit-config.yaml`.

| Runs | Script | What it does |
| --- | --- | --- |
| Before every Write or Edit | `hooks/deny_pinned_edits.py` | Refuses the call when its path is a pinned file, so the CLAUDE.md rule that pinned files are never edited is one Claude cannot break by mistake. |

`hooks/deny_pinned_edits.py` works by these rules.

- It refuses any path under `inputs/`, except a `README.md` or `.gitkeep`, and any of the hand-written manifests at the top of `manifests/`. It keeps no list of files, because everything under `inputs/` is pinned.
- It reads the repo root from `CLAUDE_PROJECT_DIR`, so the guard holds whatever folder the session has moved to.
- It watches Claude's Write and Edit tools only.
- It does not see an edit made through a shell command. Matching command text for a pinned path would miss some cases and block harmless commands. Against such an edit, the guard is `acquire_sources`, which reports any pinned file that changed.
- It does not watch Claude's notebook editor, because no pinned file is a notebook.

To add a hook, write its script in `hooks/` with a header block, name it in `settings.json`, and add a row to the table above.

Give the script a file name that no built-in, standard library or installed Python module uses. pytest and mypy import a hook by its bare file name, so a hook called `yaml.py` would hide the real `yaml` module from every check. `validation/claude_hooks/test_deny_pinned_edits_conformance.py` holds the check that confirms each hook's name is free.


## Rules

- `rules/writing_python_files.md` says how every Python file in the repo is written and described, the checks included.
  - Claude Code loads it when a file matching one of the paths listed at its top is opened.
  - It is not loaded for a new file, because a new file matches no path until it exists.
