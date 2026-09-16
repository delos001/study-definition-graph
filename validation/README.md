# validation/

Automated checks for the code in `src/sdg/`, the repo tools in `repo_tools/` and the Claude Code hooks in `.claude/hooks/`. Every check is listed in `validation_inventory.csv` with its permanent id, its kind, the promise it proves and its status. That file is the inventory; this one only says what is in the folder.

## How to run

From the repo root, in the `sdg` environment:

```powershell
pytest                       # run every check; prints results, writes nothing
pytest -v                    # one line per check
pytest --validation-report   # run every check and write a validation report (see below)
```

## What is here

| Path | What it is |
| --- | --- |
| `conftest.py` | pytest's shared fixtures and configuration for this folder; pytest requires the name. Adds the `--validation-report` flag, the `positive`, `negative` and `code` markers, and the fixtures that stage manifests and files in a temporary folder so no check touches the real `manifests/` or `inputs/`. |
| `sources/`, `usdm/`, `view/`, `repo_tools/` | One subfolder per code folder, mirroring `src/sdg/sources/`, `src/sdg/usdm/`, `src/sdg/view/` and `repo_tools/`. A test file lives at the same relative path as the file it tests and carries its name: `validation/sources/test_fetch_file.py` tests `src/sdg/sources/fetch_file.py`. |
| `claude_hooks/` | The checks for the Claude Code hooks in `.claude/hooks/`. The folder cannot carry the dot-name it mirrors, because pytest does not look inside a folder whose name starts with a dot. |
| `test_validation_report.py` | The checks for the report-writer in `conftest.py`. It stays at the top level because `conftest.py` does. |
| `fixtures/` | Small input files the checks read instead of the pinned data. `usdm_three_classes.yml` holds three classes copied verbatim from the pinned `dataStructure.yml`. |
| `validation_inventory.csv` | One row per check: the code file it targets, the test file, the check name, its permanent id (the `@code` marker), whether it is positive or negative, the one sentence it proves, its status and its version. Generated from the test files by `python repo_tools/build_inventory.py`; status and version are the hand-kept columns and are carried over by id. The pre-commit hook refuses a commit whose inventory is stale. |
| `exit_codes.csv` | The repo-wide exit-code table, one row per code: the number and the one cause it means. Every header's `Exit codes` field uses these numbers and this wording. |
| `reports/` | Validation reports, one CSV file per validation run, one row per check. Written only when asked; committed. |

## Validation reports

Development runs write nothing. When the code is declared ready, run `pytest --validation-report`. `conftest.py` then writes one CSV file into `reports/`, named for the date and the commit, with one row per check. Each row leads with the check: its code, name, kind, what it proves, its outcome and, when that is not passed, the reason. Then come the run's details, meaning the verdict, the commit, who ran it, when and which checks were selected, and at the far right the file hashes, the pinned data version and the tool versions. The check columns carry the inventory's column names, so a row joins to it by check_name_code. Commit that file. A report says PASS only when pytest itself exited 0.
