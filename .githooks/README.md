# .githooks/

This folder holds the git hooks for this repo.

A git hook runs when git does something and it runs for anyone who commits from any tool.

It is enabled once per clone with `git config core.hooksPath .githooks`, which the README's setup section includes. Claude Code hooks, which run around Claude's own tool calls, are a different thing and live in `.claude/`.

- The header, index and inventory checks, `repo_tools/verify_headers.py`,
  `repo_tools/build_index.py` and `repo_tools/build_inventory.py`, use only the standard library, so they run from any terminal.

- The ruff and mypy check, `repo_tools/check_python_files.py`, needs the `sdg`
  environment. It finds the tools on the path when that environment is active and runs them through `conda run` when it is not, which is slower but needs no set-up.

## Hooks in use

| Runs | What it does |
| --- | --- |
| `pre-commit` | Refuses the commit if any check below fails. |

| Check inside `pre-commit` | What it does |
| --- | --- |
| `python repo_tools/build_index.py --check` | Refuses the commit if `repo_tools/README.md` is out of date with the header blocks it is generated from. |
| `python repo_tools/verify_headers.py` | Refuses the commit if any Python file under `src/sdg/`, `repo_tools/`, `validation/` or `.claude/hooks/` lacks the full header block, has its fields out of order, has a Date that is not a plain calendar date, or lists exit codes that disagree with `validation/exit_codes.csv` or with its own `main()`. |
| `python repo_tools/build_inventory.py --check` | Refuses the commit if `validation/validation_inventory.csv` is out of date with the check files under `validation/` it is generated from. |
| `python repo_tools/check_python_files.py --quiet` | Refuses the commit if any Python file fails `ruff format --check`, `ruff check` or `mypy`, all configured in `pyproject.toml`. Each tool prints its own report, so the refusal names the file and the line. |

To add a check, put it in `repo_tools/` with a header block, call it from `pre-commit`, and add a row here.
