# Running validation

This document says how to choose which checks run, what to do when a check fails, how to measure which code the checks reach, how to prove that the checks can fail, and how to file a validation report. What each column of the inventory and of a report means is not here; that is in [validation_inventory_dictionary.md](validation_inventory_dictionary.md) and [reports/validation_report_dictionary.md](reports/validation_report_dictionary.md). How to write a check, and how to add one, is in `.claude/rules/writing_python_files.md`.

Run every command from the repo root, in the `sdg` environment.

## Running every check

```powershell
pytest
pytest -v
```

`pytest` runs every check under `validation/` and writes nothing. Adding `-v` prints one line per check with its name. Run this whenever you change code or a check, because the pre-commit hook does not.

## Narrowing a run

`--category`, `--objective` and `--id` are spelled as the column they select on, so what you type is what you read in [validation_inventory.csv](validation_inventory.csv). `--group` selects on no column, because a group is a named list of ids.

| Option | The column it selects on | What it takes |
| --- | --- | --- |
| `--category` | `category` | `repository`, `sources`, `processing` or `products` |
| `--aspect` | `quality_aspect` | `conformance`, `integrity` or `technical` |
| `--objective` | `objective` | any objective [README.md](README.md) lists under those aspects, under Validation definitions |
| `--id` | `id` | a check's permanent id, such as `SA00106` |
| `--group` | none | a group named in [validation_groups.yml](validation_groups.yml) |

`--aspect` selects on a column of another name. The column is named `quality_aspect` so that it says which kind of aspect it holds. The option is named `--aspect` because a dash or an underscore inside an option name reads badly.

pytest's own ways of narrowing still work and can be mixed in. Name a check file or a folder as a path, or use `-k` followed by a word that appears in a check's name.

## How the options combine

`--category`, `--aspect` and `--objective` narrow each other. A check runs only when it matches every one of them, so a run can be aimed at one aspect of one kind of thing, and adding an option always makes the run smaller.

`--id` and `--group` add up with each other, because a group is a named list of ids, and both narrow against the other three. A group that breaks the rules written at the top of [validation_groups.yml](validation_groups.yml) stops the run, and the message names the group and what to change.

A comma-separated list on one option, or the same option given twice, means any of those values.

## When a selection matches nothing

The run stops rather than reporting a clean run of nothing, and no report is written, because nothing was validated. Plain `pytest` exits 4, its own number for a refused command line. `validate_technical` exits with the repo's own number for the cause and ends on a line naming its sub-code, and the header of `src/sdgval/validate_technical.py` lists them. The message says which of these cases it is.

- A category, aspect, objective or group that does not exist. The message names the value and lists the ones that do.
- An id that is not among the checks collected. The message says whether no check has that id, whether the check lies outside the files or folders the run was given, or whether a group lists an id no check has.
- Values that each name something real, but no one check satisfies all of them together. The message gives how many checks each option matched on its own, so the option that does not belong is the one with the small number.
- Under an aspect's command, options that match only checks of other aspects. The message says so, and an objective of another aspect is named as such.
- A report run that pytest's own `-k` or `-m` left with no check. The message says to widen or drop `-k` or `-m`.

For example, `pytest --category sources --objective performance` stops with this message, where `<n>` is however many sources checks there are.

```
ERROR: no check matches every option given: --category matched <n>, --objective matched 0, in combination 0. Drop or widen the option that matched fewest.
```

## Seeing what a selection would run, without running it

Add `--collect-only -q` to any selection. It lists one line per check and runs none of them. That is the safe way to try a combination you are unsure of.

A few checks run once for each value in a list, such as the stability check, which runs once per pinned file. The listing shows each value in brackets after the check's name. To run one value only, copy that whole line and give it as the path argument.

## When a check fails

1. Read the failure. The first paragraph of the check's docstring says what must be true for it to pass, and pytest prints the line that did not hold.
2. Run that check alone, with `pytest --id` and its id, or with the line `--collect-only -q` prints for it.
3. Decide which side is wrong. Either the code no longer does what the check says, and the code is fixed, or the check describes something that has changed on purpose, and the check and its first paragraph are updated together.
4. Run `pytest` again, then `build_inventory` if a check changed, so the inventory matches.

A check can also be skipped rather than failed, and its reason says why.

- A reason starting `not downloaded` means a pinned file it reads is not on disk. Run `acquire_sources`.
- A reason starting `blocked` means a pinned file no longer matches its manifest entry. The stability check for that file fails and says which file changed.
- A reason saying the inventory marks the check pending or inactive means the check is switched off in [validation_inventory.csv](validation_inventory.csv), and the reason recorded there says why.

## Measuring which code the checks reach

```powershell
coverage run -m pytest
coverage combine
coverage report -m --skip-covered
```

The first command runs every check while coverage watches, including the separate pytest runs some checks start. The second joins what each run recorded. The third lists each file that has lines no check runs, with their line numbers. It also lists each branch no check takes, where a branch is one way a condition can go, such as the yes or the no of an `if`. What coverage measures is set in `pyproject.toml`. Its data files are ignored by git.

## Proving that the checks can fail

A check that passes whether the code is right or wrong proves nothing. Cosmic Ray proves the checks on one file can fail. It breaks the file in one small way at a time, such as turning `<` into `<=` or `True` into `False`, and runs the checks after each break. A break that no check notices is reported as surviving.

Cosmic Ray writes each break into the file on disk and then puts the file back. A run that is interrupted can leave a break in the code, so it is only ever run on a copy of the repo. The copy takes everything except the tool caches and `.env`, which holds secrets. It includes `.git`, so a check that asks git about the repo sees the same state as in the real one. It includes uncommitted work, so a check being written is proved before it is committed.

The settings are in [cosmic_ray.toml](cosmic_ray.toml). In the copy, set `module-path` to the file under test and `test-command` to the check files that cover it. Then run these commands from the repo root, in the `sdg` environment.

```powershell
$repo = Get-Location
$copy = Join-Path $env:TEMP 'sdg_cosmic_ray'
if (Test-Path $copy) { Remove-Item -Recurse -Force $copy }
robocopy . $copy /E /XD .mypy_cache .ruff_cache .pytest_cache __pycache__ .grimp_cache /XF .env .coverage /NFL /NDL /NJH /NJS
Set-Location $copy
notepad validation\cosmic_ray.toml
$env:PYTHONPATH = "$copy\src"
cosmic-ray init validation/cosmic_ray.toml cosmic_ray.sqlite
cosmic-ray baseline validation/cosmic_ray.toml
cosmic-ray exec validation/cosmic_ray.toml cosmic_ray.sqlite
cr-report cosmic_ray.sqlite --show-diff --surviving-only
Set-Location $repo
Remove-Item Env:PYTHONPATH
Remove-Item -Recurse -Force $copy
```

- The lines up to `Set-Location $copy` make a fresh copy in the temporary folder, removing any copy an earlier run left behind.
- `notepad` opens the copy's settings, where the two lines are set for this run.
- `PYTHONPATH` makes the checks import the copy's code under `src/` rather than the installed code in the real repo.
- `init` lists every break Cosmic Ray will make and writes the list to `cosmic_ray.sqlite`.
- `baseline` runs the checks once with no break and reports whether they pass. Go on only when they pass, because a run over checks that already fail proves nothing.
- `exec` makes each break and runs the checks against it.
- `cr-report` shows each break that survived, as the change it made to the code.
- The lines after `cr-report` return to the repo, clear `PYTHONPATH` and delete the copy.

A break that survives means the checks cannot tell that code from the broken version. Only the breaks in the thing the new or changed check states matter. Each of those must make the check fail. When one does not, strengthen the check in the real repo, then make a fresh copy and run again.

## Filing a validation report

```powershell
validate_technical --validation-report
validate_technical --validation-report --objective functionality
validate_technical --validation-report --category processing
```

A report is the formal record that the code was validated, so it is filed when a milestone is confirmed stable, not after each change made while building. As more is added, a report is filed again before the new work is used for project work. Each aspect of quality has its own command, and the command given `--validation-report` is the only way to file a report. Plain `pytest --validation-report` is refused. The conformance and integrity commands do not exist yet.

`validate_technical` runs the technical checks and writes nothing, and adding `--validation-report` writes the technical report. Every option above except `--aspect` narrows its run the same way. The command only accepts values that include technical checks. A group of another aspect's checks, such as `pinned_integrity`, holds no technical check, so `validate_technical` refuses it.

These rules govern a report.

- The run refuses to start when the working folder holds changes that are not committed, and names them. A report records the commit it validated, and uncommitted work belongs to no commit. Commit the changes, or set them aside with `git stash` and bring them back afterwards with `git stash pop`, then run.
- The run refuses to start when git does not answer, because the report could not name its commit.
- The run records what the selection asked for, and how much of its aspect it covered, in `checks_collected` against `checks_reported`. What each count holds, and which ways of narrowing a run leave the two equal, is defined under `checks_collected` in [reports/validation_report_dictionary.md](reports/validation_report_dictionary.md).
- Two CSV files land in the folder for its aspect inside [reports/](reports/), such as `reports/technical/`. The report, named for the aspect, the date and the commit, as in `technical_2026-09-25_1286c8b.csv`, holds one row per check. The run's own file beside it, `technical_2026-09-25_1286c8b_run.csv`, holds one row with the run's details. Commit both files. [reports/validation_report_dictionary.md](reports/validation_report_dictionary.md) defines every column.

## Worked examples

| What you want | What to run |
| --- | --- |
| Everything | `pytest` |
| Everything, with each check named | `pytest -v` |
| One file's checks | `pytest validation/sdg/sources/test_fetch_file_technical.py` |
| One folder's checks | `pytest validation/sdgtools` |
| Every check whose name mentions manifests | `pytest -k manifest` |
| Every check on the repository's own machinery | `pytest --category repository` |
| Every check asking an integrity question | `pytest --aspect integrity` |
| The integrity checks on the pinned sources only | `pytest --aspect integrity --category sources` |
| The conformance checks on the pinned sources only | `pytest --aspect conformance --category sources` |
| Every stability check | `pytest --objective stability` |
| Two named checks | `pytest --id SA00106,SA00283` |
| Every check that reads a real pinned file, after a re-pin | `pytest --group pinned_integrity,pinned_conformance` |
| What the pre-commit hook enforces, after it refuses a commit | `pytest --group hook_integrity,hook_conformance` |
| A listing of what a selection would run | `pytest --aspect integrity --collect-only -q` |
| One value of a check that runs once per pinned file | copy its line from that listing and give it as the path |
| Which code no check reaches | the `coverage` commands above |
| Whether the checks on one file can fail | the Cosmic Ray commands above |
| Every technical check, writing nothing | `validate_technical` |
| A filed report of every technical check | `validate_technical --validation-report` |
| A filed report of one narrowed technical run | `validate_technical --validation-report --category processing` |
