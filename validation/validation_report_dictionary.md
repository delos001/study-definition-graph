# Validation report dictionary

Defines every column of a validation report and every value a coded column may hold.

A report is written by `pytest --validation-report` into `reports/`, one CSV file per run named `run_<date>_<commit>.csv`, with one row per check that ran. The run's own details are repeated on every row, so a report is complete on its own. Every column is written by `conftest.py`; nothing in a report is typed by hand.

The check columns carry the same names as `validation_inventory.csv`, so a row joins to the inventory by `id`. Their definitions are in `validation_inventory_dictionary.md` and are not repeated here.

## Columns

### `run_id`
- Identifies the run.
- Read by the writer from the report's own file name.
- Holds the file name without `.csv`, such as `run_2026-09-21_1286c8b`, with the numbered suffix a second run on the same day and commit gets, so the id in the rows and the file that holds them can never disagree.

### `selection`
- Records which checks the command line selected.
- Read by the writer from pytest's parsed arguments.
- Holds `all` for the whole suite, or the paths, node ids, `-k` and `-m` filters and the `--category`, `--objective`, `--id` and `--group` options that were given. It records what was asked for, which is what a reader needs to run the same thing again. Whether the run then covered everything it set out to is `checks_collected` against `checks_reported`.

### `checks_collected`
- Says how many checks the run set out to cover.
- Read by the writer from the checks pytest was left holding, plus every check dropped before the run, which pytest reports through a hook it fires for each one.
- Holds a whole number. It is counted from what happened rather than from the options that were typed, because an option the writer knows nothing about narrows a run just the same. A file kept out of collection altogether, as `--ignore` does, is never seen by the run, so it cannot be counted here and `selection` is what records it.

### `checks_reported`
- Says how many checks the report holds a row for.
- Read by the writer from the outcomes it collected.
- Holds a whole number. It is lower than `checks_collected` when checks were dropped from the run or the run stopped before reaching them, so a run that covered part of the suite cannot read as one that covered all of it. It is 0 on the row written when no check ran.

### `run_verdict`
- Says whether the run as a whole passed.
- Read by the writer from pytest's exit status.
- Holds one of the verdicts below.

### `pytest_exit_status`
- Records pytest's exit number for the run.
- Read by the writer from pytest.
- Holds a whole number from 0 to 5.

### `exit_meaning`
- Says what the exit number means.
- Read by the writer from the table of exit meanings below.
- Holds one of the exit meanings below.

### `category`, `objective`, `staged_case`, `folder_path`, `file_name`, `name`, `id`, `target_folder_path`, `target_file_name`, `expected_result`
- Same as in the inventory, in the inventory's order, defined in `validation_inventory_dictionary.md`. `parameter` sits between `name` and `id`.
- Read by the writer from the check's markers, docstring and file path at run time, not from the inventory.
- `expected_result` holds `(no docstring)` when the check has none, and `target_file_name` carries the words `(not found at run time)` after the name when the covered file was missing.

### `parameter`
- Says which value a parametrized check ran with, since pytest runs such a check once per value and the report has one row per run.
- Read by the writer from pytest's id for the value. The full list of a check's values is the `@pytest.mark.parametrize` line above its function in the test file, or, when that line calls a function, whatever the function lists at run time, as the fixity check lists every pinned file.
- Holds the id, such as a pinned file's path for the fixity check, or nothing when the check has no parameters.

### `outcome`
- Says how the check ended.
- Read by the writer from pytest's result for the check's set-up, run and clean-up.
- Holds one of the outcomes below.

### `outcome_reason`
- Says why the outcome is not passed.
- Read by the writer from pytest's result: the first line of the failure message, the skip reason, or which step broke.
- Holds one line, or nothing when the check passed. A check that goes wrong twice holds both reasons, separated by a semicolon, in the order the steps ran. On the row written when no check ran it holds that sentence alone, because the exit status is all the writer knows about the cause, and `exit_meaning` already carries it.

### `started`
- Records when the run began.
- Read by the writer from the clock at the start of the run.
- Holds a local timestamp with its zone, as `YYYY-MM-DD HH:MM:SS +HHMM`.

### `commit`
- Records the commit the checks ran against. The working folder matched it exactly, because a run with uncommitted changes is refused before any check runs. It is the one way to get back the exact code that ran, test files included, with `git show <commit>:<path>`.
- Read by the writer from git.
- Holds the short hash, or `(unknown)` when git did not answer.

### `run_by`
- Records who ran the checks.
- Read by the writer from git's configured user name.
- Holds the name, or `(unknown)` when git did not answer.

### `check_file_sha256`
- Fingerprints the test file the check came from, the one `folder_path` and `file_name` name, as it was when the run read it.
- Read by the writer by hashing the file's bytes.
- Holds the sha256 as hex. It recognises a version but cannot produce one. Hash the file you hold and compare: a match means you are reading the check that ran, and a difference means the file was edited since the report. To get the version that ran, use `commit`.

### `fixture_sha256s`
- Fingerprints every file under `fixtures/`, the small stand-ins the staged checks read, as they were when the run read them.
- Read by the writer by hashing each file's bytes.
- Holds `validation/fixtures/<name>=<sha256>` for each file, separated by semicolons. Each is used the same way as `check_file_sha256`.

### `pinned_usdm_sha256`
- Records which version of the pinned USDM model file the run was against.
- Read by the writer from the manifest entry for `inputs/standards/cdisc/usdm_v4/dataStructure.yml`.
- Holds the recorded sha256, or `(manifest entry not readable)`.

### `pinned_usdm_present`
- Says whether that pinned file was on the machine.
- Read by the writer from the file system.
- Holds `present` or `absent`.

### `python_version`, `pytest_version`, `platform`
- Record the Python version, the pytest version and the operating system the run used.
- Read by the writer from the running interpreter.
- Hold the versions and the platform string as the tools report them.

## Verdicts

- `PASS`: pytest exited 0.
- `FAIL`: pytest exited with any other number.

## Outcomes

- `passed`: the check ran and every assertion held.
- `failed`: the check ran and an assertion did not hold.
- `skipped`: the check did not run, by its own skip marker or because a pinned file it names was not downloaded or no longer matches its manifest entry.
- `error`: the check's set-up or clean-up broke, whatever the check itself did.
- `none`: no check ran at all. The report then has this one row, and `exit_meaning` says why nothing ran.

A later step never makes a row better. A check whose assertions held but whose clean-up broke is `error`. A check that failed and then broke in its clean-up is `error` too, and `outcome_reason` keeps the failure alongside the clean-up, so the later step cannot hide the earlier one.

## Exit meanings

- `0`: all tests passed.
- `1`: one or more tests failed or errored.
- `2`: the run was interrupted.
- `3`: pytest hit an internal error.
- `4`: pytest was given a bad command line.
- `5`: no tests were collected.
