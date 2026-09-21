# Validation inventory dictionary

Defines every column of `validation_inventory.csv` and every value a coded column may hold. The inventory is written by `python repo_tools/build_inventory.py`. The generator overwrites every column it reads on each run and carries the typed columns over unchanged. A generated value is changed at its source, then the inventory is regenerated.

Every row is one check. A column about the check itself has a bare name. The two columns about the file the check covers carry the prefix `target_`.

## Columns

### `category`
- Says what kind of thing the check confirms.
- Read by the generator from the `@category` marker.
- Holds one of the categories below.

### `objective`
- Says what the check confirms about its category.
- Read by the generator from the `@objective` marker.
- Holds one of the objectives below.

### `staged_case`
- Says whether a correctness check that staged its own situation expects success or refusal.
- Read by the generator from the `@positive` or `@negative` marker.
- Holds one of the cases below, or nothing.

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
- Holds three capital letters and four digits, such as `SRC0042`, unique across the inventory. The letters are one of the prefixes below.

### `target_folder_path`
- Names the folder of the code file the test file covers.
- Read by the generator from the test file's path, by the rule in `type_and_target()` in `repo_tools/build_inventory.py`.
- Holds a folder in the repo.

### `target_file_name`
- Names the code file the test file covers.
- Read by the generator from the test file's name with `test_` removed.
- Holds a file in that folder.

### `expected_result`
- States what must be true for the check to pass.
- Read by the generator from the first paragraph of the check's docstring.
- Starts with numeric or text character, never with `=`, `+`, `-` or `@`.

### `version`
- Numbers the check's version.
- Typed by hand in the CSV.
- Holds a whole number from 1 up, by the rule under Versions below.

### `status`
- Says whether what the check guards is still guarded.
- Typed by hand in the CSV.
- Holds one of the statuses below.

### `superseded_by`
- Names the checks that now cover a superseded check.
- Typed by hand in the CSV.
- Holds ids of active checks, separated by semicolons, only when the status is superseded.

### `status_reason`
- Says why a check is inactive or retired.
- Typed by hand in the CSV.
- Holds one sentence, only when the status is inactive or retired.

## Id prefixes

The three letters name the folder of the covered file when the check was first filed. They are part of the id and never change, whatever later happens to the check's category, objective or file, because a filed report joins to the inventory on the id. A new check takes its folder's prefix and the next unused number. A new folder takes a new prefix, added here.

- `SRC`: `src/sdg/sources/`
- `USD`: `src/sdg/usdm/`
- `VIW`: `src/sdg/view/`
- `SDG`: the top of `src/sdg/`
- `HRS`: `repo_tools/`
- `CCH`: `.claude/hooks/`
- `TST`: `validation/` itself, such as `conftest.py` and `select_checks.py`

## Categories

The category is the thing the check confirms. Whatever the check compares it against is the reference, and the reference does not change the category.

- `repository`: the tools, hooks, rules and records that hold the sources, conversions and products to their rules and specifications, so that each behaves as expected. It includes the pinning tools, the pre-commit hook and the validation suite itself.
- `sources`: the materials, data, files, standards and references the project consumes to create and evaluate a product.
- `conversion`: the processes, prompts, and run records that turn the sources into a product, such as reading a document, finding its sections, extracting contents and transforming into USDM structures and loading those into the graph.
- `products`: the deliverables created through source conversions, such as extracted contents, USDM structures with their provenance, mappings, and the graph.

## Objectives

- `correctness`: the thing does, or produces, what it is supposed to, judged against what the right result is.
- `completeness`: the thing includes everything it is supposed to, with nothing missing.
- `conformance`: the thing follows the rule, specification or documentation it is held to.
- `stability`: the thing is unchanged from its own earlier recorded or accepted version.
- `performance`: the thing runs fast enough, or light enough on the machine, on a realistic input.

Completeness is judged against the source. Conformance is judged against a written rule.

Stability compares a thing with its own earlier copy. A comparison of two different things is correctness.

## Cases

Only a correctness check carries a case.

- `positive`: the check staged a working situation and expects the code to succeed.
- `negative`: the check staged a broken situation and expects the code to refuse it for the right reason.
- empty: the check looked at something real rather than staging a situation, or its objective is not correctness.

## Statuses

- `pending`: the check is planned or being built. It is not in use yet.
- `active`: the check exists and runs in every run.
- `inactive`: the check was in use and is switched off for now. It has not been withdrawn. `status_reason` says why it is off.
- `superseded`: other checks now cover what this check guarded, so nothing is lost. `superseded_by` names those checks, and each one is active.
- `retired`: the check was withdrawn, and nothing covers what it guarded. `status_reason` says why the loss was accepted.

A superseded or retired check cannot still be in the test files.

Until the first validation run, a deleted check's row is removed. After it, every row is kept whatever its status.

## Versions

A version starts at 1 and moves to the next whole number when the changed check has passed its validation, its report is filed, and it is in production.

Until the first validation run, every check stays at version 1.
