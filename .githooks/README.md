# .githooks/

This folder holds the git hooks for this repo. A git hook runs when git does something, here a commit, and it runs for anyone who commits from any tool. It is enabled once per clone with `git config core.hooksPath .githooks`, which the README's setup section includes. Claude Code hooks, which run around Claude's own tool calls, are a different thing and live in `.claude/`.

Only checks that need no third-party packages belong here, so the hooks work from any terminal whether or not the `sdg` environment is active.

## Hooks in use

| Runs | What it does |
| --- | --- |
| `pre-commit` | Refuses the commit if either check below fails. |

| Check inside `pre-commit` | What it does |
| --- | --- |
| `python scripts/build_index.py --check` | Refuses the commit if `scripts/README.md` is out of date with the header blocks it is generated from. |
| `python scripts/verify_headers.py` | Refuses the commit if any Python file under `src/sdg/` or `scripts/` lacks the full header block, has its fields out of order, or has a Date that is not a plain calendar date. |

To add a check, put its script in `scripts/` with a header block, call it from `pre-commit`, and add a row here.
