# Validation inventory dictionary

Defines every column of `validation_inventory.csv` and every value a coded column may hold. The inventory is written by the `build_inventory` command. The generator overwrites every column it reads on each run and carries the typed columns over unchanged. A generated value is changed at its source, then the inventory is regenerated.

Every row is one check. A check that pytest runs once per value is still one row. A column about the check itself has a bare name. The two columns about the file the check covers carry the prefix `target_`.

## Columns

### `category`
- Says what kind of thing the check confirms.
- Read by the generator from the `@category` marker.
- Holds one of the categories below.
- Allowed values:
  - `repository`
  - `sources`
  - `processing`
  - `products`

### `quality_aspect`
- Says which aspect of quality the check is concerned with.
- Worked out by the generator from the objective, never marked on a check, so an objective can never sit under an aspect it does not belong to.
- Holds one of the aspects below.
- Allowed values:
  - `conformance`
  - `integrity`
  - `technical`


### `objective`
- Says which question the check asks about its category.
- Read by the generator from the `@objective` marker.
- Stratified by `quality_aspect`.
- Allowed values:
  - `conformance`:
    - `conformance`

  - `integrity`:
    - `correctness`
    - `completeness`
    - `stability`
    - `consistency`

  - `technical`:
    - `functionality`
    - `performance`
    - `reliability`
    - `security`
    - `compatibility`
    - `maintainability`
    - `portability`

### `staged_case`
- Says whether a check that staged its own situation expects success or refusal.
- Read by the generator from the `@positive` or `@negative` marker.
- Holds one of the cases below, or nothing.
- Allowed values:
  - `positive`
  - `negative`
  - empty

### `folder_path`
- Names the folder the check file sits in, from the repo root.
- Read by the generator from the check file's path.
- Holds a folder under `validation/`.

### `file_name`
- Names the check file.
- Read by the generator from the check file's path.
- Holds `test_<name>_<aspect>.py`, where `<name>` is the name of the file the checks cover and `<aspect>` is the aspect of quality of the checks it holds.

### `name`
- Names the check's function.
- Read by the generator from the name pytest gives the check when it collects the check file.
- Holds `test_<name>`.

### `id`
- Identifies the check permanently. A validation report joins to the inventory on it.
- Read by the generator from the `@code` marker.
- Holds `S`, a suite letter and five digits, such as `SA00042`, unique across the inventory. The two letters are one of the suites listed in `SUITES` in `src/sdgval/build_inventory.py`. The generator refuses an id that breaks any of those three rules.

### `target_folder_path`
- Names the folder of the code file the check file covers.
- Read by the generator from the check file's path, by the rule in `code_folder_and_target()` in `src/sdgval/build_inventory.py`.
- Holds a folder in the repo.

### `target_file_name`
- Names the code file the check file covers.
- Read by the generator from the check file's name, with the `test_` prefix and the `_<aspect>` ending removed.
- Holds a file in that folder.

### `expected_result`
- States what must be true for the check to pass.
- Read by the generator from the first paragraph of the check's docstring.
- Starts with a letter or a digit, never with `=`, `+`, `-` or `@`, which `src/sdgval/build_inventory.py` refuses because a spreadsheet reads a cell opening with one of them as a formula. Whitespace at the front of a docstring is not refused, because the generator strips it before it looks at the sentence.

### `version`
- Numbers the check's version.
- Typed by hand in the CSV.
- Holds a whole number from 1 up.
- Moves to the next number when the check changes and `validation/reports/` holds a filed validation report, because a report names the check by its id and version. A change to the check's code, its docstring or its labels counts as a change. In that case `src/sdgval/build_inventory.py` refuses a changed check whose version stayed the same, and it tells the two apart by the `fingerprint` column.

### `fingerprint`
- Identifies the check's code, its docstring and its labels, so a change to any of them can be told apart from a change to how they are laid out.
- Written by the generator from the check's function and the labels pytest reads for it. What the fingerprint covers and what it ignores are listed in the docstring of `fingerprint()` in `src/sdgval/build_inventory.py`.
- Holds `v` and the version the fingerprint was taken at, then `py` and the Python version, major and minor, that took it, then sixteen hexadecimal characters, the three parts joined by colons, such as `v1:py3.12:0f3a9c2b7d4e5a61`.
- Records the Python version because a new Python can write the same code out differently, which moves every fingerprint although no check changed. When `validation/reports/` holds a filed validation report and the running Python differs from the one recorded, `build_inventory` stops with one message rather than refusing every check. `build_inventory --python-changed` then records new fingerprints for the rows the other Python made, without comparing them, so run it in a commit that changes nothing else.
- When `validation/reports/` holds a filed validation report, `build_inventory` refuses a row whose fingerprint is empty or cannot be read, because whether its check changed can no longer be told. Put the cell back as git last recorded it.
- After a check changes while `validation/reports/` holds a filed validation report, raise its `version` by hand and run `build_inventory`, which then records the new fingerprint against the new version. While the folder holds no report, `build_inventory` records the new fingerprint against the version the row already has.

### `status`
- Says whether what the check guards is still guarded.
- Typed by hand in the CSV.
- Holds one of the statuses below.
- Allowed values:
  - `pending`: the check is written but not yet switched on, and `status_reason` says why. A check that is planned but not yet written is tracked in GitHub Issues.
  - `active`: the check is in use and runs.
  - `inactive`: the check is switched off for now, and `status_reason` says why.
  - `superseded`: other active checks now cover what this check guarded, and `superseded_by` names them.
  - `retired`: the check is withdrawn with nothing covering what it guarded, and `status_reason` says why.
- A check marked `pending` or `inactive` is skipped when the checks run, and its report row gives the status and the reason recorded here.
- A check marked `superseded` or `retired` is removed from the check files, and its row is kept when the inventory is regenerated, so a filed report that names it still finds it. When `validation/reports/` holds a filed validation report, `src/sdgval/build_inventory.py` refuses a row whose check is in no check file unless it is marked one of these two. While the folder holds no report, such a row is dropped when the inventory is regenerated.

#### Taking a check out of use
1. In `validation/validation_inventory.csv`, set the check's `status` to `superseded` and name the active checks that now cover it in `superseded_by`, or set it to `retired` and say why in `status_reason`.
2. In the same change, remove the check's function from its check file. `src/sdgval/build_inventory.py` refuses a superseded or retired check that is still in the check files. Its id is never given to another check.
3. Run `build_inventory`. The row is kept with its status, and `build_inventory --check-status` confirms the hand-kept columns follow their rules.

### `superseded_by`
- Names the checks that now cover a superseded check.
- Typed by hand in the CSV.
- Holds the ids of the checks that took over, separated by semicolons, only when the status is superseded. Each is another row of the inventory, whatever its status is now.
- To find what covers a superseded check now, follow `superseded_by` from row to row until it reaches an active check, or a retired one, which means nothing covers it any more.

### `status_reason`
- Says why a check is pending, inactive or retired.
- Typed by hand in the CSV.
- Holds one sentence, only when the status is pending, inactive or retired.




