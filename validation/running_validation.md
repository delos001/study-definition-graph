# Running validation

This document says how to choose which checks run and how to file a validation report. What each column of the inventory and of a report means is not here; that is in [validation_inventory_dictionary.md](validation_inventory_dictionary.md) and [validation_report_dictionary.md](validation_report_dictionary.md). How to write a check is in `.claude/rules/writing_python_files.md`.

Run every command from the repo root, in the `sdg` environment.

## Running every check

```powershell
pytest
pytest -v
```

`pytest` runs every check under `validation/` and writes nothing. Adding `-v` prints one line per check with its name. Run this whenever you change code or a check, because the pre-commit hook does not.

## The five ways to narrow a run

Four of the five options are spelled as the column they select on, so what you type is what you read in [validation_inventory.csv](validation_inventory.csv).

| Option | The column it selects on | What it takes |
| --- | --- | --- |
| `--category` | `category` | `repository`, `sources`, `processing` or `products` |
| `--aspect` | `quality_aspect` | `conformance`, `integrity` or `operation` |
| `--objective` | `objective` | any objective the dictionary lists under those aspects |
| `--id` | `id` | a check's permanent id, such as `SA00106` |
| `--group` | none | a group named in [validation_groups.yml](validation_groups.yml) |

`--aspect` is the one place a word and a column name differ. The column is `quality_aspect`, because the table holds other kinds of aspect-less column and the word alone would not say which aspect was meant. The option is `--aspect`, because a dash or an underscore inside a command-line flag reads badly. There is no other divergence to remember.

pytest's own ways of narrowing still work and can be mixed in: name a test file or a folder as a path, or use `-k` followed by a word that appears in a check's name.

## How the options combine

`--category`, `--aspect` and `--objective` narrow each other: a check runs only when it matches every one of them. So a run can be aimed at one aspect of one kind of thing, and adding an option always makes the run smaller.

`--id` and `--group` add up with each other, because a group is a named list of ids, and both narrow against the other three.

A comma-separated list on one option, or the same option given twice, means any of those values.

## When a selection matches nothing

The run stops rather than reporting a clean run of nothing. Two cases reach that:

- A value names no category, aspect, objective, group or collected check. The message names the value and lists what does exist.
- Every value names something real, but no one check satisfies all of them together. The message gives how many checks each option matched on its own, so the option that does not belong is the one with the small number.

```
ERROR: no check matches every option given: --category matched 3, --aspect matched 0, in combination 0. Drop or widen the option that matched fewest.
```

Either way pytest exits 4 and no report is written, because nothing was validated.

## Seeing what a selection would run, without running it

Add `--collect-only -q` to any selection. It lists one line per check and runs none of them. That is the safe way to try a combination you are unsure of.

A few checks run once for each value in a list, such as the fixity check, which runs once per pinned file. The listing shows each value in brackets after the check's name. To run one value only, copy that whole line and give it as the path argument.

## Filing a validation report

```powershell
pytest --validation-report
pytest --aspect integrity --validation-report
pytest --category sources --objective stability --validation-report
```

A report is the formal record that the code was validated, so it is filed when the code is declared ready, not as part of the build loop. Adding `--validation-report` to any run above covers exactly the checks that ran and changes nothing else about the run.

Three things govern it.

- The run refuses to start when the working folder holds changes that are not committed, and names them. A report records the commit it validated, and uncommitted work belongs to no commit. Commit or stash, then run.
- The report records what the selection asked for in its `selection` column, and how much of the suite it actually covered in `checks_collected` against `checks_reported`. Those two differ when checks were dropped or the run stopped early, so a partial run cannot read as a whole one.
- One CSV file lands in [reports/](reports/), named for the date and the commit. Commit that file.

## Worked examples

| What you want | What to run |
| --- | --- |
| Everything | `pytest` |
| Everything, with each check named | `pytest -v` |
| One file's checks | `pytest validation/sdg/sources/test_fetch_file_operation.py` |
| One folder's checks | `pytest validation/sdgtools` |
| Every check whose name mentions manifests | `pytest -k manifest` |
| Every check on the repository's own machinery | `pytest --category repository` |
| Every check asking an integrity question | `pytest --aspect integrity` |
| The integrity checks on the pinned sources only | `pytest --aspect integrity --category sources` |
| The conformance checks on the pipeline only | `pytest --aspect conformance --category processing` |
| Every stability check | `pytest --objective stability` |
| Two named checks | `pytest --id SA00106,SA00283` |
| Every check that reads a real pinned file, after a re-pin | `pytest --group pinned` |
| What the pre-commit hook enforces, after it refuses a commit | `pytest --group hook` |
| A listing of what a selection would run | `pytest --aspect integrity --collect-only -q` |
| One value of a check that runs once per pinned file | copy its line from that listing and give it as the path |
| A filed report of the whole suite | `pytest --validation-report` |
| A filed report of one narrowed run | `pytest --category sources --validation-report` |
