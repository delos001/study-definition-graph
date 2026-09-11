# .githooks/

This folder holds the git hooks for this repo. A git hook runs when git does something, here a commit, and it runs for anyone who commits from any tool. It is enabled once per clone with `git config core.hooksPath .githooks`, which the README's setup section includes. Claude Code hooks, which run around Claude's own tool calls, are a different thing and live in `.claude/`.

The header, index and inventory checks use only the standard library, so they run from any terminal. The ruff and mypy check needs the `sdg` environment; its script finds the tools on the path when that environment is active and runs them through `conda run` when it is not, which is slower but needs no set-up.

## Hooks in use

| Runs | What it does |
| --- | --- |
| `pre-commit` | Refuses the commit if any check below fails. |

| Check inside `pre-commit` | What it does |
| --- | --- |
| `python scripts/build_index.py --check` | Refuses the commit if `scripts/README.md` is out of date with the header blocks it is generated from. |
| `python scripts/verify_headers.py` | Refuses the commit if any Python file under `src/sdg/` or `scripts/` lacks the full header block, has its fields out of order, or has a Date that is not a plain calendar date. |
| `python scripts/build_inventory.py --check` | Refuses the commit if `tests/validation_inventory.csv` is out of date with the checks it is generated from. |
| `python scripts/check_python_files.py --quiet` | Refuses the commit if any Python file fails `ruff format --check`, `ruff check` or `mypy`, all configured in `pyproject.toml`. Each tool prints its own report, so the refusal names the file and the line. |

To add a check, put its script in `scripts/` with a header block, call it from `pre-commit`, and add a row here.
