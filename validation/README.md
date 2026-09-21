# validation/

This folder holds the repo's validation suite and the files that support it.

Guidance for writing a validation check is in `.claude/rules/writing_python_files.md`.

Instructions for running the validation checks are under How to run, at the end of this file.


## In this folder

### Top level support files

Support files are the machinery and records the validation checks rely on.
- `validation_inventory.csv`
  - Lists every check, one row per check, records what each check looks at, and why it exists.
  - Written by `python repo_tools/build_inventory.py`.
  - Its columns are defined in `validation_inventory_dictionary.csv`, and the terms it uses under Objectives and Terms the inventory uses below.
  - To change a value, edit its source, which the `source` column of the dictionary names, then run `python repo_tools/build_inventory.py`.
  - A value edited directly in the CSV is overwritten the next time the inventory is rebuilt. The hand-kept columns are the exception, and they are edited in the CSV itself.
- `exit_codes.csv`: Holds the repo-wide table of exit codes, one row per code.
- `validation_file_catalog.md`: Describes every validation file in this folder in detail.
- `conftest.py`: Holds pytest's shared fixtures and configuration for this folder, and writes the validation report.

### Top level validation files

These are validation files like the ones in the folders. They sit at the top level because the files they validate sit at the top of their own folders.
- `test_console_output.py`: Validates `src/sdg/console_output.py`.
- `test_validation_report.py`: Validates `conftest.py`.

### Folders

- Each folder of valiadtion checks mirrors a folder of code it validates. A test file sits at the same relative path as the file it validates.

- The validation file carries its target name with `test_` in front, so `validation/sources/test_fetch_file.py` validates `src/sdg/sources/fetch_file.py`.

- `claude_hooks/`
  - Holds the validation checks for the Claude Code hooks in `.claude/hooks/`.
  - Its name differs from the folder it mirrors, because pytest does not look inside a folder whose name starts with a dot.

- `fixtures/`
  - Holds small stand-ins for the pinned files under `inputs/` that are read by staged checks. Real pinned files are not touched.
  - Holds no checks.

- `repo_tools/`
  - Holds the validation checks for the repo maintenance tools in `repo_tools/`.

- `reports/`
  - Holds the validation reports, one CSV file per validation run.
  - Receives a report only from `pytest --validation-report`.
  - See validation reports section below for details.

- `sources/`
  - Holds the validation checks for `src/sdg/sources/`.

- `usdm/`
  - Holds the validation checks for `src/sdg/usdm/`.

- `view/`
  - Holds the validation checks for scripts in `src/sdg/view/`.

## Objectives

An objective is why a check exists.

### Behavior cases (needs new name)

Every behavior check is one of two cases.

- **positive** means the check sets up a working situation and expects the code to succeed.
- **negative** means the check sets up a broken situation and expects the code to refuse it for the right reason, with the right message or exit code.


## Terms the inventory uses

### Statuses

A status answers whether what the check guards is still guarded.

| Status | What it means | What else the row must hold |
| --- | --- | --- |
| `pending` | The check is planned or being built. It is not in use yet. | Nothing else. |
| `active` | The check exists and runs in every run. | Nothing else. |
| `inactive` | The check was in use and is switched off for now. It has not been withdrawn. | `status_reason` says why it is off. |
| `superseded` | Other checks now cover what this check guarded, so nothing is lost. | `superseded_by` names those checks, and each one is active. |
| `retired` | The check was withdrawn, and nothing covers what it guarded. That is a loss of capability. | `status_reason` says why the loss was accepted. |

- A superseded or retired check cannot still be in the test files.
- `python repo_tools/build_inventory.py --check-status` checks these rules on the inventory as it is, and every regeneration checks them too.
- Until the first validation run, a deleted check's row is removed rather than given a status. After that run every row is kept, whatever its status, so a report can always be traced to the checks that existed when it was made.

### Versions

- A check's version is a whole number, starting at 1.
- A check moves to the next number when all three of these have happened:
  1. The changed check passes its validation.
  2. The validation report is filed.
  3. The check is put into production.
- Until the first validation run, every check stays at version 1.

## Validation reports

- Development runs write nothing.
- When the code is declared ready, run `pytest --validation-report`. `conftest.py` then writes one CSV file into `reports/`, named for the date and the commit. Commit that file.
- A report has one row per check that ran. Each row leads with the check, meaning its id, name, objective, behavior case, expected result, outcome, and the reason when the outcome is not passed. Then come the run's details, meaning the verdict, the commit, who ran it, when it ran and which checks were selected. At the far right are the file hashes, the pinned data version and the tool versions.
- The check columns carry the inventory's column names, so a row joins to the inventory by `validation_check_id`.
- A check whose pinned file is not downloaded, or no longer matches its manifest entry, is skipped, and its row gives the reason. Only the stability check for that file fails, so one changed file shows as one failure.
- A report says PASS only when pytest itself exited 0.

## How to run

Run every command from the repo root, in the `sdg` environment.

### During development

```powershell
pytest
pytest -v
```

- Run the checks whenever you change code or a check. The pre-commit hook does not run them, so this is up to you.
- `pytest` runs every check in every test file under `validation/` and prints the results. It writes nothing.
- `pytest -v` does the same, with one line per check naming it.

### Running only some checks

```powershell
pytest validation/sources/test_fetch_file.py
pytest -k manifest
```

- Name a test file to run only its checks.
- Use `-k`, pytest's own filter, followed by a word to run only the checks that match it.
- A check matches when its name or its test file's name contains the word, so `-k manifest` runs every check in `test_read_manifests.py` as well as the checks elsewhere with "manifest" in their names.

### When the code is declared ready

```powershell
pytest --validation-report
```

- This run produces a validation report, the formal record that the code was validated.
- It runs the same checks as `pytest`, then writes one report into `reports/`.
- A run narrowed to some checks can also write a report. The report's `selection` column records what was selected, so a partial run cannot pass for a full one.
- What a report holds is described under Validation reports below.
