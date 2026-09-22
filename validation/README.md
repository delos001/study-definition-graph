# validation/

This folder holds the repo's validation suite and the files that support it.

Guidance for writing a validation check is in `.claude/rules/writing_python_files.md`.

Instructions for running the validation checks are in [running_validation.md](running_validation.md).


## In this folder

### Top level support files

Support files are the machinery and records the validation checks rely on.
- `validation_inventory.csv`
  - Lists every check, one row per check, with its validation details.
  - Written by `python repo_tools/build_inventory.py`.
  - Its columns, their values and how each is changed are defined in `validation_inventory_dictionary.md`.
- `validation_inventory_dictionary.md`: Defines every column of the inventory and every value a coded column may hold.
- `validation_report_dictionary.md`: Defines every column of a validation report and every value a coded column may hold.
- `running_validation.md`: Says how to choose which checks run and how to file a validation report.
- `select_checks.py`: Adds the `--category`, `--aspect`, `--objective`, `--id` and `--group` options to pytest. `pyproject.toml` loads it at startup.
- `validation_groups.yml`: Names the groups of checks that `pytest --group` can run, each with its purpose and its ids.
- `exit_codes.csv`: Holds the repo-wide table of exit codes, one row per code.
- `conftest.py`
  - Holds pytest's shared fixtures and configuration for this folder. pytest looks for a file with exactly this name.
  - Registers the markers the checks carry, `@code`, `@category`, `@objective`, `@positive`, `@negative` and `@needs_pinned`, and skips a check whose pinned file is not downloaded or no longer matches its manifest entry. A check carries no aspect marker; the aspect is looked up from the objective.
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
  - How one is filed is in [running_validation.md](running_validation.md).

- `sources/`
  - Holds the validation checks for `src/sdg/sources/`.

- `usdm/`
  - Holds the validation checks for `src/sdg/usdm/`.

- `view/`
  - Holds the validation checks for `src/sdg/view/`.
