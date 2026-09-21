# validation/

This folder holds the repo's validation suite and the files that support it.

Guidance for writing a validation check is in `.claude/rules/writing_python_files.md`.

Instructions for running the validation checks are under How to run validation, at the end of this file.


## In this folder

### Top level support files

Support files are the machinery and records the validation checks rely on.
- `validation_inventory.csv`
  - Lists every check, one row per check, with its validation details.
  - Written by `python repo_tools/build_inventory.py`.
  - Its columns, their values and how each is changed are defined in `validation_inventory_dictionary.md`.
- `validation_inventory_dictionary.md`: Defines every column of the inventory and every value a coded column may hold.
- `validation_report_dictionary.md`: Defines every column of a validation report and every value a coded column may hold.
- `select_checks.py`: Adds the `--category`, `--objective`, `--id` and `--group` options to pytest. `pyproject.toml` loads it at startup.
- `validation_groups.yml`: Names the groups of checks that `pytest --group` can run, each with its purpose and its ids.
- `exit_codes.csv`: Holds the repo-wide table of exit codes, one row per code.
- `conftest.py`
  - Holds pytest's shared fixtures and configuration for this folder. pytest looks for a file with exactly this name.
  - Registers the markers the checks carry, `@code`, `@category`, `@objective`, `@positive`, `@negative` and `@needs_pinned`, and skips a check whose pinned file is not downloaded or no longer matches its manifest entry.
  - Writes the validation report when pytest is run with `--validation-report`.

### Top level validation files

These are validation files that sit at the top level because the files they validate sit at the top of their own folders.
- `test_console_output.py`: Validates `src/sdg/console_output.py`.
- `test_conftest.py`: Validates `conftest.py`.
- `test_select_checks.py`: Validates `select_checks.py`.

### Folders

Each folder of validation checks mirrors a folder of code it validates. The validation file carries its target name with `test_` in front, so `validation/sources/test_fetch_file.py` validates `src/sdg/sources/fetch_file.py`.

- `claude_hooks/`
  - Holds the validation checks for the Claude Code hooks in `.claude/hooks/`.

- `fixtures/`
  - Holds small stand-ins for the pinned files under `inputs/` that are read by staged checks. Real pinned files are not touched.
  - Holds `usdm_three_classes.yml`, three classes copied verbatim from the pinned `dataStructure.yml`, and no checks.

- `repo_tools/`
  - Holds the validation checks for the repo maintenance tools in `repo_tools/`.

- `reports/`
  - Holds the validation reports, one CSV file per run.
  - Its columns and their values are defined in `validation_report_dictionary.md`.
  - See Generating a validation report section below.

- `sources/`
  - Holds the validation checks for `src/sdg/sources/`.

- `usdm/`
  - Holds the validation checks for `src/sdg/usdm/`.

- `view/`
  - Holds the validation checks for `src/sdg/view/`.

## How to run validation

Run every command from the repo root, in the `sdg` environment.

### Running every check

```powershell
pytest
pytest -v
```

- During development, run every check whenever you change code or a check. The pre-commit hook does not run them, so this is up to you.
- `pytest` runs every check in every test file under `validation/` and prints the results. It writes nothing.
- `pytest -v` does the same, with one line per check naming it.

### Running a sub-set of checks

```powershell
pytest validation/sources/<file_name>.py
pytest -k manifest
pytest --category sources
pytest --objective stability --category sources
pytest --id SRC0128,HRS0018
pytest --group pinned
pytest --collect-only -q --id SRC0128
```

- Name a test file, such as `validation/sources/test_fetch_file.py`, to run only its checks.
- Use `-k`, pytest's own filter, followed by a word to run only the checks whose name or file name contains it.
- Use `--category`, `--objective` or `--id`, spelled as the inventory's columns are, to run only the checks whose value matches. Two different options narrow each other. A comma-separated list means any of the values.
- Use `--group` to run the checks a named group in `validation_groups.yml` lists. A group is for a set that no folder, category or objective can name on its own.
- A value that names no category, objective, group or collected check stops the run, so a typo cannot pass for a clean run of nothing.
- Add `--collect-only -q` to any selection to list the checks it would run, one line each, without running them.
- A few checks are written to run once for each value in a list, such as the fixity check, which runs once per pinned file. Nothing is typed for this. pytest runs every value on its own, and the report gets one row per value with the value in its `parameter` column. Most checks have no such list, run once, and leave that column empty.
- To run one value only, copy its line from the `--collect-only` listing, which shows the value in brackets, and give it as the path argument.


### Generating a validation report

```powershell
pytest --validation-report
pytest --group hook --validation-report
pytest --category sources --objective stability --validation-report
pytest validation/sources --id SRC0128 --validation-report
```

- Add `--validation-report` to any run above, whole or narrowed, and the report covers exactly the checks that run. Nothing else about the run changes.
- Run it only when the code is declared ready. The report is the formal record that the code was validated.
- The run refuses to start when the working folder has changes that are not committed, and names them. A report names the commit it validated, so commit or stash first.
- The run writes one CSV file into `reports/`, named for the date and the commit. Commit that file.
- The report's `selection` column records what was selected, so a partial run cannot pass for a full one.
- What a report holds is defined in `validation_report_dictionary.md`.
