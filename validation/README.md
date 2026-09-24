# validation/

This folder holds the repo's validation checks and the files that support them. The code that runs the checks, which selects them, skips them and writes their reports, is the validation package in `src/sdgval/`.

Guidance for writing a validation check is in `.claude/rules/writing_python_files.md`.

Instructions for running the validation checks are in [running_validation.md](running_validation.md).


## In this folder

### Top level support files

Support files are the records and settings the validation checks rely on.
- `validation_inventory.csv`
  - Lists every check, one row per check, with its validation details.
  - Written by the `build_inventory` command.
  - Its columns, their values and how each is changed are defined in `validation_inventory_dictionary.md`.
- `validation_inventory_dictionary.md`: Defines every column of the inventory and every value a coded column may hold.
- `validation_report_dictionary.md`: Defines every column of a validation report and every value a coded column may hold.
- `running_validation.md`: Says how to choose which checks run and how to file a validation report.
- `validation_groups.yml`: Names the groups of checks that `pytest --group` can run, each with its purpose and its ids.
- `exit_codes.csv`: Holds the repo-wide table of exit codes, one row per code.
- `conftest.py`
  - Holds the fixtures the checks share, the setups a check asks for by name. pytest looks for a file with exactly this name.
  - Holds nothing else. The labels, the skips and the report are the validation package's plugins in `src/sdgval/`.

### Folders

Each folder of checks mirrors the code it validates, one folder per installed package under `src/`. A test file's name is its target's name with `test_` in front and its aspect of quality at the end, so `validation/sdg/sources/test_fetch_file_operation.py` holds the operation checks for `src/sdg/sources/fetch_file.py`. A test file holds checks of one aspect only.

- `sdg/`
  - Holds the validation checks for the pipeline, `src/sdg/`, one folder per group of work.

- `sdgtools/`
  - Holds the validation checks for the repo tools in `src/sdgtools/`.

- `sdgval/`
  - Holds the validation checks for the validation package in `src/sdgval/`.

- `claude_hooks/`
  - Holds the validation checks for the Claude Code hooks in `.claude/hooks/`. It cannot mirror that folder by name, because pytest does not look inside a folder whose name starts with a dot.

- `shared/`
  - Holds the code that checks of more than one file share, one file per job, such as `fake_server.py` for a fake download server. It holds no checks.
  - The fixtures built on it are in `conftest.py`, because pytest finds a shared fixture only there.

- `fixtures/`
  - Holds small stand-ins for the pinned files under `inputs/` that are read by staged checks. Real pinned files are not touched.
  - Holds `usdm_three_classes.yml`, three classes copied verbatim from the pinned `dataStructure.yml`, and no checks.

- `reports/`
  - Holds the validation reports, one CSV file per run.
  - Its columns and their values are defined in `validation_report_dictionary.md`.
  - How one is filed is in [running_validation.md](running_validation.md).
