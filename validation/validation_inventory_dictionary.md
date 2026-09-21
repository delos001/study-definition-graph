# Validation inventory dictionary

Defines every column of `validation_inventory.csv` and every value a coded column may hold. The inventory is written by `python repo_tools/build_inventory.py`. A value is changed at the source the column names, then the inventory is regenerated. The hand-kept columns are edited in the CSV itself.

## Columns

| Column | Definition | Source | Values |
| --- | --- | --- | --- |
| `validation_folder_path` | The folder the test file sits in, from the repo root. | The test file's path. | A folder under `validation/`. |
| `validation_file_name` | The test file's name. | The test file's path. | `test_<name>.py`. |
| `target_folder_path` | The folder of the code file the test file validates. | The test file's path, by the rule in `type_and_target()` in `repo_tools/build_inventory.py`. | A folder in the repo. |
| `target_file_name` | The code file the test file validates. | The test file's name with `test_` removed. | A file in that folder. |
| `validation_check_name` | The check's function name. | The test file. | `test_<name>`. |
| `validation_check_id` | The check's permanent id. A validation report joins to the inventory on it. | The `@code` marker. | Three capital letters and four digits, such as `SRC0042`, unique across the inventory. |
| `validation_target` | What kind of thing the check confirms. | The `@target` marker. | One of the Targets below. |
| `validation_objective` | What the check confirms about its target. | The `@objective` marker. | One of the Objectives below. |
| `behavior_case` | Whether a correctness check that staged its own situation expects success or refusal. | The `@positive` or `@negative` marker. | One of the Cases below, or empty. |
| `expected_result` | What must be true for the check to pass. | The first paragraph of the check's docstring. | A sentence that starts with a word, never with `=`, `+`, `-` or `@`. |
| `status` | Whether what the check guards is still guarded. | Hand-kept. | One of the Statuses below. |
| `superseded_by` | The checks that now cover a superseded check. | Hand-kept. | Ids of active checks, separated by semicolons. Filled only when the status is superseded. |
| `status_reason` | Why a check is inactive or retired. | Hand-kept. | One sentence. Filled only when the status is inactive or retired. |
| `version` | The check's version. | Hand-kept. | A whole number from 1 up. See Versions below. |

## Targets

The target is the thing the check confirms. Whatever the check compares it against is the reference, and the reference does not change the target.

| Value | Definition |
| --- | --- |
| `repository` | The tools, hooks, rules and records that hold the sources, conversions and products to their rules and specifications, so that each behaves as expected. It includes the pinning tools, the pre-commit hook and the validation suite itself. |
| `sources` | The materials, data, files, standards and references the project consumes to create and evaluate a product. |
| `conversion` | The processes, prompts, and run records that turn the sources into a product, such as reading a document, finding its sections, extracting contents and transforming into USDM structures and loading those into the graph. |
| `products` | The deliverables created through source conversions, such as extracted contents, USDM structures with their provenance, mappings, and the graph. |

## Objectives

| Value | Definition |
| --- | --- |
| `correctness` | The thing does, or produces, what it is supposed to, judged against what the right result is. |
| `completeness` | The thing includes everything it is supposed to, with nothing missing. |
| `conformance` | The thing follows the rule, specification or documentation it is held to. |
| `stability` | The thing is unchanged from its own earlier recorded or accepted version. |
| `performance` | The thing runs fast enough, or light enough on the machine, on a realistic input. |

Completeness is judged against the source. Conformance is judged against a written rule.

Stability compares a thing with its own earlier copy. A comparison of two different things is correctness.

## Cases

Only a correctness check carries a case.

| Value | Definition |
| --- | --- |
| `positive` | The check staged a working situation and expects the code to succeed. |
| `negative` | The check staged a broken situation and expects the code to refuse it for the right reason. |
| empty | The check looked at something real rather than staging a situation, or its objective is not correctness. |

## Statuses

| Value | Definition | What else the row must hold |
| --- | --- | --- |
| `pending` | The check is planned or being built. It is not in use yet. | Nothing else. |
| `active` | The check exists and runs in every run. | Nothing else. |
| `inactive` | The check was in use and is switched off for now. It has not been withdrawn. | `status_reason` says why it is off. |
| `superseded` | Other checks now cover what this check guarded, so nothing is lost. | `superseded_by` names those checks, and each one is active. |
| `retired` | The check was withdrawn, and nothing covers what it guarded. | `status_reason` says why the loss was accepted. |

A superseded or retired check cannot still be in the test files.

Until the first validation run, a deleted check's row is removed. After it, every row is kept whatever its status.

## Versions

A version starts at 1 and moves to the next whole number when the changed check has passed its validation, its report is filed, and it is in production.

Until the first validation run, every check stays at version 1.
