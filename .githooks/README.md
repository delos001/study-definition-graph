# .githooks/

This folder holds the git hooks for this repo.

A git hook runs when git does something and it runs for anyone who commits from any tool.

It is enabled once per clone with `git config core.hooksPath .githooks`, which the setup section of the root `README.md` includes. Claude Code hooks, which run around Claude's own tool calls, are a different thing and live in `.claude/`.

Each check is a repo tool, an installed command of the `sdg` environment. When that environment is active, the command is on the path and runs directly. When it is not, the hook runs it through `conda run -n sdg`, which is slower but needs no set-up, so a commit works from any terminal.

## Hooks in use

| Runs | What it does |
| --- | --- |
| `pre-commit` | Refuses the commit if any check below fails. |

| Check inside `pre-commit` | What it does |
| --- | --- |
| `build_index --check` | Refuses the commit if `src/sdgtools/README.md` is out of date with the header blocks it is generated from. |
| `verify_headers` | Refuses the commit if any Python file under `src/`, `validation/` or `.claude/hooks/` <br> - lacks the full header block, <br> - has its fields out of order, <br> - has a Date that is not a plain calendar date, or <br> - lists exit codes that disagree with `validation/exit_codes.csv` or with its own `main()`. |
| `build_inventory --check` | Refuses the commit if `validation/validation_inventory.csv` is out of date with the check files under `validation/` it is generated from. |
| `check_python_files --quiet` | Refuses the commit if any Python file fails `ruff format --check`, `ruff check` or `mypy`, all configured in `pyproject.toml`. Each tool prints its own report, so the refusal names the file and the line. |

To add a check, put it in `src/sdgtools/` with a header block, install it as a command in `pyproject.toml`, call it from `pre-commit` through `run_tool`, and add a row here.
