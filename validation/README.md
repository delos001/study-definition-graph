# validation/

This folder contains the project's validation check programming and associated records used in the validation procedures.


## Validation definitions
Validation evaluates defined elements of the project to determine whether they meet defined quality expectations, and generates reports with those findings.

There are different aspects of validation, and validation can ask different questions about different elements of a project. These differences can influence who addresses validation issues and how validation reports are designed.

### Categories
Project elements targeted by validation procedures are broken into categories:
- `repository`: covers the tools, hooks, rules and records that keep the project in order, such as pinning tools, pre-commit hooks and the validation checks.
- `sources`: covers documents, data and standards the project uses to create and evaluate its products.
- `processing`: covers the project's staged work from reading a source to a finished graph, including the processes, prompts and run records.
- `products`: covers deliverables the processing creates, including content extractions, data structures and provenance, mappings, and the graph.

### Quality aspects and objectives
Validation is broken into quality aspects, which can impact process order. Each quality aspect groups objectives, the specific questions a check can ask.
- `conformance`: evaluates whether something adheres to defined rules, such as a required shape, format or set of allowed elements or values.
  - `conformance`: does the target adhere to defined rules?

- `integrity`: evaluates whether something is sound: its values match an expected value or range, nothing is missing, it is in the right order, and it is unchanged over time.
  - `correctness`: does the value match a known true value or range held outside the target?
  - `completeness`: are any data or values missing that should be present, judged against a reference?
  - `stability`: have values changed from their earlier recorded or accepted version by more than the allowed amount?
  - `consistency`: do the values or events occur in the correct sequence?

- `operation`: evaluates whether something runs as it is intended or does what it was designed to do.
  - `functionality`: does the target do what it was built to do?
  - `performance`: does the target run fast enough and light enough on a realistic input?
  - `reliability`: does the target keep working, and recover when something fails?
  - `security`: does the target prevent access, use or disclosure it should not allow?
  - `compatibility`: does the target work alongside the other things it has to work with?
  - `maintainability`: can the target be changed safely and without disproportionate effort?
  - `portability`: does the target run in another environment without being rewritten?

### Case staging
Validation can use various methods to answer the objective. Staging a case evaluates an outcome against an expected success or refusal.
- `positive`: the check stages a working situation and expects the target to succeed.
- `negative`: the check stages a broken situation and expects the target to refuse it for the right reason.
- empty: the check examines something real and stages nothing.

## Validation Suites

Every check has an id made of two letters naming its suite and five digits, such as `SA00042`.  Should this project require a completely unique suite of checks, the prefix accommodates for this.  For example, a new suite of checks can start with SB, such as `SB00001`


## Validation Checks

### Configuration
Each check is one pytest function that performs distinct validation: one objective for one element.

### Check ids
An id never changes and is never reused, because filed reports refer to checks by it. A new suite is added to `SUITES` in `src/sdgval/build_inventory.py` and to the list below.

- `SA`: suite A, which holds every check under `validation/`.

### Check naming
a test file is named for the file it validates and its aspect, and a test file holds one aspect only.

### Check folder structure
  The folders mirror src/,

## Additional validation

`src/sdgtools` contains programming that behaves similarly to the validation programming here in this folder but it is different.  The programming there composes repo tools that perform functions

## Packages validation uses

These packages are installed with the rest of the project from `environment.yml`.
- `pytest` finds the checks and runs them. The code in `src/sdgval/` adds this project's own options to it, such as choosing checks by category and writing a report.
- `pytest-cov` shows which lines of the project's code the checks actually run, so code that no check tests can be found.
- `ruff` confirms that every Python file follows the standard layout and style.
- `mypy` confirms that each function is given and gives back the kinds of values its code says it will.
- The `check_python_files` command runs `ruff` and `mypy`, and the pre-commit hook runs that command before every commit. The commands to run them by hand are in `.claude/rules/writing_python_files.md`.
- `grimp` reads the code and lists which files use which other files, so the checks can run in an order that follows those links.
