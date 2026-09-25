# Validation report dictionary

Defines every column of a validation report and of the run's own file beside it, and every value a coded column may hold.

A report is written by an aspect's command when it is given `--validation-report`, as in `validate_technical --validation-report`. It lands in the folder for its aspect inside this one, as `technical/` holds the technical reports. Each run writes two CSV files. The report, named `<aspect>_<date>_<commit>.csv`, holds one row per check that ran. The run's own file, named the same with `_run` added, as in `<aspect>_<date>_<commit>_run.csv`, holds one row with the details that are the same for every check in the run. The two join on `run_id`. Every column is written by `src/sdgval/report.py`. Nothing in either file is typed by hand.

The check columns carry the same names as `validation/validation_inventory.csv`, so a row joins to the inventory by `id`. Their definitions are in `validation/validation_inventory_dictionary.md` and are not repeated here.

## Report columns

### `run_id`
- Identifies the run, and joins each row to the run's own file.
- Read by the writer from the report's own file name.
- Holds the file name without `.csv`, such as `technical_2026-09-25_1286c8b`, with the numbered suffix a second run on the same day and commit gets, so the id in the rows and the file that holds them can never disagree.

### `run_started`
- Records when the run began, on every row, so results can be plotted over time without joining to the run's own file.
- Read by the writer from the clock at the start of the run.
- Holds a local timestamp with its zone, as `YYYY-MM-DD HH:MM:SS +HHMM`.

### `selection`
- Records which checks the command line selected, kept on every row so a reader has it at hand.
- Read by the writer from pytest's parsed arguments.
- Holds a JSON object with one key for each way the run was narrowed, using the keys listed under the run's own file's `selection_` columns. A key is present only when that way was used, and an empty object, `{}`, means nothing narrowed the run. The same selection, one column per key, is in the run's own file.

### `category`, `quality_aspect`, `objective`, `staged_case`, `folder_path`, `file_name`, `name`, `id`, `target_folder_path`, `target_file_name`, `expected_result`
- Same as in the inventory, in the inventory's order, defined in `validation/validation_inventory_dictionary.md`. `parameter` sits between `name` and `id`.
- Read by the writer from the check's markers, docstring and file path at run time, not from the inventory. `quality_aspect` is looked up from the objective, the way the inventory fills it.
- `expected_result` holds `(no docstring)` when the check has none, and `target_file_name` carries the words `(not found at run time)` after the name when the covered file was missing.

### `parameter`
- Says which value a parametrized check ran with, since pytest runs such a check once per value and the report has one row per run.
- Read by the writer from pytest's name for the run: the name the check gives it with `ids=`, or the value itself when it is a plain word, number or path. The full list of a check's values is the `@pytest.mark.parametrize` line above its function in the test file, or, when that line calls a function, whatever the function lists at run time.
- Holds the run's name, such as `unlisted code first`, or nothing when the check has no parameters.

### `outcome`
- Says how the check ended.
- Read by the writer from pytest's result for the check's set-up, run and clean-up.
- Holds one of the outcomes below.

### `outcome_reason`
- Says why the outcome is not passed.
- Read by the writer from pytest's result: the first line of the failure message, the skip reason, or which step broke.
- Holds one line, or nothing when the check passed. A check that goes wrong twice holds both reasons, separated by a semicolon, in the order the steps ran. On the row written when no check ran it holds that sentence alone, because the exit status is all the writer knows about the cause, and `pytest_exit_cause` in the run's own file already carries it.

### `target_last_changed`, `target_change_id`
- Record which version of the script the check covers ran, the one `target_folder_path` and `target_file_name` name. A report run starts only on a working folder that matches its commit, so the script's last change is the version that ran.
- Read by the writer from git's history of the file.
- Hold the date of the last change, as `YYYY-MM-DD`, and its short id. Comparing the id across two reports shows whether the script changed between them. Both are empty when the script was not found at run time, `(not committed)` when git has no change for it, and `(unknown)` when git did not answer.

### `check_file_last_changed`, `check_file_change_id`
- Record which version of the test file the check sits in ran, the one `folder_path` and `file_name` name. A check edited to test less can pass where the earlier one failed, and these show that the test file changed.
- Read by the writer from git's history of the file.
- Hold the same values as the two target columns.

### `fixtures`
- Records which version of each fixture the check read. A fixture is a small stand-in file in `validation/fixtures/`, and a check names the ones it reads with the `@needs_fixture` label.
- Read by the writer from the check's label and git's history of each file.
- Holds a JSON list with one entry per fixture, each with its `name` inside `validation/fixtures/`, its `last_changed` date and its `change_id`, or nothing when the check names no fixture.

## Run file columns

### `run_id`, `run_started`
- Same as in the report.

### `run_by`
- Records who ran the checks.
- Read by the writer from git's configured user name.
- Holds the name, or `(unknown)` when git did not answer.

### `run_verdict`
- Says whether the run as a whole passed.
- Read by the writer from pytest's exit code.
- Holds one of the verdicts below.

### `pytest_exit_code`
- Records pytest's exit code for the run.
- Read by the writer from pytest.
- Holds a whole number from 0 to 5.

### `pytest_exit_cause`
- Says what the exit code means.
- Read by the writer from the table of exit causes below.
- Holds one of the exit causes below.

### `checks_collected`
- Says how many checks the run set out to cover.
- Read by the writer from the checks pytest was left holding, plus every check dropped before the run, which pytest reports through a hook it fires for each one.
- Holds a whole number. It is counted from what happened rather than from the options that were typed, because an option the writer knows nothing about narrows a run just the same. A file kept out of collection altogether, as `--ignore` does, is never seen by the run, so it cannot be counted here.

### `checks_reported`
- Says how many checks the report holds a row for.
- Read by the writer from the outcomes it collected.
- Holds a whole number. It is lower than `checks_collected` when checks were dropped from the run or the run stopped before reaching them, so a run that covered part of the suite cannot read as one that covered all of it. It is 0 when no check ran.

### `commit`
- Records the commit the checks ran against. The working folder matched it exactly, because a run with uncommitted changes is refused before any check runs. It is the one way to get back the exact code that ran, test files included, with `git show <commit>:<path>`.
- Read by the writer from git.
- Holds the short hash, or `(unknown)` when git did not answer.

### `python_version`, `pytest_version`, `platform`
- Record the Python version, the pytest version and the operating system the run used.
- Read by the writer from the running interpreter.
- Hold the versions and the platform string as the tools report them.

### `installed_packages`
- Records every package installed where the run ran, with its version. `environment.yml` fixes no package's version, so a package can change between two runs without anything in the repository changing, and a package the project never imports can still break it through one that does.
- Read by the writer from each installed package's own record of its version.
- Holds a JSON object of package name to version, in name order.

### `selection_aspect`, `selection_category`, `selection_objective`, `selection_id`, `selection_group`
- Record the values given to `--aspect`, `--category`, `--objective`, `--id` and `--group`, the options of `src/sdgval/select_checks.py`.
- Read by the writer from pytest's parsed arguments.
- Each holds a JSON list of the values given, such as `["technical"]`, or nothing when the option was not used. An aspect's command always gives its own aspect.

### `selection_keyword`, `selection_marker`
- Record the expression given to pytest's `-k` filter, which selects checks by words in their names, and to its `-m` filter, which selects them by their labels.
- Read by the writer from pytest's parsed arguments.
- Each holds the expression as typed, or nothing when the filter was not used.

### `selection_paths`
- Records the files, folders or single checks the person typed.
- Read by the writer from pytest's parsed arguments. A path pytest filled in from its own configuration is not recorded, because the person did not narrow the run with it.
- Holds a JSON list of the paths, or nothing when none was typed.

The selection columns come last, so a new way of narrowing a run adds a column at the right and every other column keeps its place.

## Verdicts

- `PASS`: pytest exited 0.
- `FAIL`: pytest exited with any other number.

## Outcomes

- `passed`: the check ran and every assertion held.
- `failed`: the check ran and an assertion did not hold.
- `skipped`: the check did not run, by its own skip marker or because a pinned file it names was not downloaded or no longer matches its manifest entry.
- `error`: the check's set-up or clean-up broke, whatever the check itself did.
- `none`: no check ran at all. The report then has this one row, and `pytest_exit_cause` in the run's own file says why nothing ran.

A later step never makes a row better. A check whose assertions held but whose clean-up broke is `error`. A check that failed and then broke in its clean-up is `error` too, and `outcome_reason` keeps the failure alongside the clean-up, so the later step cannot hide the earlier one.

## Exit causes

- `0`: all tests passed.
- `1`: one or more tests failed or errored.
- `2`: the run was interrupted.
- `3`: pytest hit an internal error.
- `4`: pytest was given a bad command line.
- `5`: no tests were collected.
