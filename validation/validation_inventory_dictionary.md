# Validation inventory dictionary

Defines every column of `validation_inventory.csv` and every value a coded column may hold. The inventory is written by the `build_inventory` command. The generator overwrites every column it reads on each run and carries the typed columns over unchanged. A generated value is changed at its source, then the inventory is regenerated.

Every row is one check. A column about the check itself has a bare name. The two columns about the file the check covers carry the prefix `target_`.

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
  - `operation`


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

  - `operation`:
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
- Names the folder the test file sits in, from the repo root.
- Read by the generator from the test file's path.
- Holds a folder under `validation/`.

### `file_name`
- Names the test file.
- Read by the generator from the test file's path.
- Holds `test_<name>.py`.

### `name`
- Names the check's function.
- Read by the generator from the test file.
- Holds `test_<name>`.

### `id`
- Identifies the check permanently. A validation report joins to the inventory on it.
- Read by the generator from the `@code` marker.
- Holds `S`, a suite letter and five digits, such as `SA00042`, unique across the inventory. The two letters are one of the suites listed in `validation/README.md`. The generator refuses an id that breaks any of those three rules.

### `target_folder_path`
- Names the folder of the code file the test file covers.
- Read by the generator from the test file's path, by the rule in `code_folder_and_target()` in `src/sdgval/build_inventory.py`.
- Holds a folder in the repo.

### `target_file_name`
- Names the code file the test file covers.
- Read by the generator from the test file's name with `test_` removed.
- Holds a file in that folder.

### `expected_result`
- States what must be true for the check to pass.
- Read by the generator from the first paragraph of the check's docstring.
- Starts with a letter or a digit, never with `=`, `+`, `-` or `@`, which `src/sdgval/build_inventory.py` refuses because a spreadsheet reads a cell opening with one of them as a formula. Whitespace at the front of a docstring is not refused, because the generator strips it before it looks at the sentence.

### `version`
- Numbers the check's version.
- Typed by hand in the CSV.
- Holds a whole number from 1 up.
- It moves to the next number when
  - the changed check has passed validation,
  - its report is filed,
  - and it is in production.
- Until the first validation run, every check stays at 1.


### `status`
- Says whether what the check guards is still guarded.
- Typed by hand in the CSV.
- Holds one of the statuses below.
- Allowed values:
  - `pending`: the check is planned, pending development or a decision.
  - `active`: the check is in use and runs.
  - `inactive`: the check is switched off for now, and `status_reason` says why.
  - `superseded`: other active checks now cover what this check guarded, and `superseded_by` names them.
  - `retired`: the check is withdrawn with nothing covering what it guarded, and `status_reason` says why.

### `superseded_by`
- Names the checks that now cover a superseded check.
- Typed by hand in the CSV.
- Holds ids of active checks, separated by semicolons, only when the status is superseded.

### `status_reason`
- Says why a check is inactive or retired.
- Typed by hand in the CSV.
- Holds one sentence, only when the status is inactive or retired.




