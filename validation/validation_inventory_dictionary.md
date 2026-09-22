# Validation inventory dictionary

Defines every column of `validation_inventory.csv` and every value a coded column may hold. The inventory is written by `python repo_tools/build_inventory.py`. The generator overwrites every column it reads on each run and carries the typed columns over unchanged. A generated value is changed at its source, then the inventory is regenerated.

Every row is one check. A column about the check itself has a bare name. The two columns about the file the check covers carry the prefix `target_`.

## Columns

### `category`
- Says what kind of thing the check confirms.
- Read by the generator from the `@category` marker.
- Holds one of the categories below.

### `quality_aspect`
- Says which aspect of quality the check is concerned with.
- Worked out by the generator from the objective, never marked on a check, so an objective can never sit under an aspect it does not belong to.
- Holds one of the aspects below.

### `objective`
- Says which question the check asks about its category.
- Read by the generator from the `@objective` marker.
- Holds one of the objectives below, grouped there under the aspect each belongs to.

### `staged_case`
- Says whether a check that staged its own situation expects success or refusal.
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
- Holds three capital letters and four digits, such as `SRC0042`, unique across the inventory. The letters are one of the prefixes below. The generator refuses an id that breaks any of those three rules.

### `target_folder_path`
- Names the folder of the code file the test file covers.
- Read by the generator from the test file's path, by the rule in `code_folder_and_target()` in `repo_tools/build_inventory.py`.
- Holds a folder in the repo.

### `target_file_name`
- Names the code file the test file covers.
- Read by the generator from the test file's name with `test_` removed.
- Holds a file in that folder.

### `expected_result`
- States what must be true for the check to pass.
- Read by the generator from the first paragraph of the check's docstring.
- Starts with a letter or a digit, never with `=`, `+`, `-` or `@`, which `repo_tools/build_inventory.py` refuses because a spreadsheet reads a cell opening with one of them as a formula. Whitespace at the front of a docstring is not refused, because the generator strips it before it looks at the sentence.

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

The three letters name the folder of the covered file when the check was first filed. They are part of the id and never change, whatever later happens to the check's category, objective or file, because a filed report joins to the inventory on the id. A new check takes its folder's prefix and the next unused number. A new folder takes a new prefix, added to `ID_PREFIXES` in `repo_tools/build_inventory.py` and to the list below.

Choosing the prefix that fits the folder is done by hand and stays that way. The generator confirms that the letters are one of the prefixes below, and no more than that. It cannot confirm that a prefix still fits, because a check that moves keeps the id it was filed under, and nothing records when each check was filed, so a prefix that no longer fits cannot be told from one that was wrong to begin with.

- `SRC`: `src/sdg/sources/`
- `USD`: `src/sdg/usdm/`
- `VIW`: `src/sdg/view/`
- `SDG`: the top of `src/sdg/`
- `HRS`: `repo_tools/`
- `CCH`: `.claude/hooks/`
- `TST`: `validation/` itself, such as `conftest.py` and `select_checks.py`

## Categories

The category is the thing the check confirms. Whatever the check compares it against is the reference, and the reference does not change the category.

- `repository`: the tools, hooks, rules and records that hold the sources, the processing and the products to their rules and specifications, so that each behaves as expected. It includes the pinning tools, the pre-commit hook and the validation suite itself. A shared helper that several of these call, such as the one that makes a command print its text as UTF-8, belongs here too, because it serves whatever calls it rather than doing a stage of the pipeline's work.
- `sources`: the materials, data, files, standards and references the project consumes to create and evaluate a product.
- `processing`: the pipeline's own work, every stage of it, from reading a source in through to the finished graph. It covers the processes, the prompts and the run records, and it does not ask whether a given stage changes anything: reading a document is processing, and so are finding its sections, extracting its contents, transforming those into USDM structures and loading them into the graph. A stage the pipeline gains later is processing too.
- `products`: the deliverables the processing creates, such as extracted contents, USDM structures with their provenance, mappings, and the graph.

## Aspects of quality

Three aspects divide the questions a check can ask. Every objective belongs to exactly one, and the generator fills `quality_aspect` by looking it up, so nobody files an objective under the wrong aspect.

- `conformance`: whether the thing follows the rules it is held to.
- `integrity`: whether what the thing holds is sound, meaning right, whole, unchanged and in the right order.
- `operation`: how the thing runs, rather than what it holds.

Conformance comes before the other two when a thing is assessed. A thing that does not have the shape its rules require is not in a state where asking whether its values are right tells anyone much, so a correctness result on something that failed its conformance checks is not worth reading.

The three are not ISO/IEC 25010's quality characteristics, although several objectives under `operation` take their names and their sense from it. The grouping is the project's own.

## Objectives

A check asks one question. Which question it asks is its objective, and which aspect that objective belongs to is its `quality_aspect`.

### Under `conformance`

- `conformance`: does the thing have the shape, format or structure a rule prescribes? A rule may be written, published or programmed. Structure, format, layout, required fields and allowed values are all conformance. Whether a piece of code does what it was built to do is a different question, asked by `functionality` below.

### Under `integrity`

- `correctness`: does the value match the known true value, or fall within the known true range? The true value or range is held outside the thing under test, such as a file's own bytes, a manifest entry, the headers a document was generated from, an answer key, or what is known to be plausible for the measurement.
- `completeness`: is anything that should be there missing? Judged against whatever held it, such as a document an extraction read, the records another file accounts for, or an answer key an output is scored against.
- `stability`: has the thing changed from its own earlier recorded or accepted version?
- `consistency`: does the record prove the correct sequence of events? This is the sense the United States Food and Drug Administration uses in its data integrity guidance, where consistency means the order of events is demonstrable. It is not the sense the data-management literature gives the word, where consistency means the same fact agreeing across two systems. A check comparing two places is correctness.

### Under `operation`

- `functionality`: does the thing do what it was built to do? This is the question asked of a script, a workflow or a step: it was given a situation, and it did what its own description says it does. A tool that enforces a rule is asked this question about its own behaviour, so a check staging a file with a field missing and confirming the tool refuses it is functionality. Running that same tool over the real repository, to confirm every real file has the shape the rule prescribes, is conformance, because there the thing being confirmed is the files.
- `performance`: does the thing run fast enough, or light enough on the machine, on a realistic input?
- `reliability`: does the thing keep working, and recover when something fails?
- `security`: is the thing protected against access, use or disclosure it should not allow?
- `compatibility`: does the thing work alongside the other things it has to work with?
- `maintainability`: can the thing be changed safely and without disproportionate effort?
- `portability`: does the thing run somewhere else without being rewritten?

Correctness and conformance are the pair that gets confused, because in ordinary speech a thing that follows a rule is often called correct. One test separates them. Can the expected answer change without any rule changing? If it can, something outside holds the true value and the question is correctness: a file's sha256 changes when the file changes, and a blood pressure is implausible whatever any specification says. If it cannot, the rule is the only authority and the question is conformance: a header has eight fields in order only because the rule says eight and that order.

The question decides, not the material the check reads. HRS0046 reads a file's header fields and asks whether they follow the rule that defines a header, so it is conformance. A check reading the same fields to ask whether a count stated elsewhere matches the number actually present would be correctness.

Several of these objectives carry no checks yet. They are written down because the questions they name will be asked once there is extraction, a graph and a running pipeline, and because working out where such a check belongs is easier to do once than to redo each time.

## Cases

The case says how a check was set up, which is a separate thing from the question it asks, so a check of any objective may carry one.

- `positive`: the check staged a working situation and expects the code to succeed.
- `negative`: the check staged a broken situation and expects the code to refuse it for the right reason.
- empty: the check looked at something real rather than staging a situation.

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
