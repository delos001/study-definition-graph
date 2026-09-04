# tests/

Automated checks for the code in `src/sdg/`, and the validation records that prove a component was checked at a given point. Kept by hand.

## How to run

From the repo root, in the `sdg` environment:

```powershell
pytest                       # run every check; prints results, writes nothing
pytest -v                    # one line per check
pytest --validation-report   # run every check and write a validation record (see below)
```

## What is here

| Path | What it is |
| --- | --- |
| `conftest.py` | pytest's setup file for this folder. Adds the `--validation-report` flag and the `positive` / `negative` markers. |
| `test_usdm_spec.py` | The checks for `src/sdg/usdm_spec.py`, the loader for the pinned USDM model. |
| `test_validation_report.py` | The checks for the record-writer in `conftest.py`: above all, that a record can never say PASS when pytest said the run failed. |
| `fixtures/usdm_three_classes.yml` | Three classes copied verbatim from the pinned `dataStructure.yml`: `Identifier` (abstract), `StudyIdentifier` (its concrete child, with inherited attributes) and `Condition` (holds the five-way reference). The input for the logic checks. |
| `validation/` | Validation records, one file per component per validated state. Written only when asked; committed. |

## How the checks are designed

Each check sets up a situation, runs the code, and compares what happened to what the code's own documentation promises (its header block, exit codes and docstrings). Each is marked one of two kinds:

- **positive**: the right thing works. A well-formed input gives the documented result.
- **negative**: the broken thing fails, and for the right reason. The input is broken in one described way and the check asserts both the error type and that the message names that cause and not another.

The logic checks use the small fixture file rather than the real pinned file, because they have to break their input on purpose (delete a key, swap a dict for a list) and the fixture is small enough to read whole and see the break. The fixture is not invented: `test_fixture_classes_are_identical_to_pinned` proves each of its classes is key-for-key identical to the pinned file, so the logic checks ran on real USDM shapes. Broken variants are made in memory from the fixture and written to a temporary folder pytest owns; the fixture on disk is never touched, and the change each variant makes is stated in that check's docstring.

The real-file checks read the pinned `dataStructure.yml` in place and assert the measured facts about it. They need `data/` downloaded (`python scripts/fetch_sources.py`) and skip, with that reason, when it is not.

## The checks, by group

The `Proves` column is the first line of each check's docstring; the full docstring in the file says more.

### Reading a well-formed file

| Check | Kind | Proves |
| --- | --- | --- |
| `test_lists_every_class_sorted` | positive | class_names() gives every class in alphabetical order |
| `test_abstract_flag_comes_from_modifier` | positive | is_abstract() reports USDM's own Modifier |
| `test_attributes_keep_file_order_and_inheritance` | positive | attributes() keeps file order and each inherited one names its parent |
| `test_targets_unwraps_one_and_many` | positive | targets() unwraps one target and the five-way one |
| `test_unknown_class_raises_keyerror_naming_it` | negative | an unknown class raises KeyError carrying the name |

### Refusing a wrongly shaped file (`SpecShapeError`, exit 4)

| Check | Kind | Proves |
| --- | --- | --- |
| `test_empty_file_is_refused` | negative | an empty file is refused as empty, not treated as a model with no classes |
| `test_class_without_modifier_is_named` | negative | a class missing Modifier is refused, naming the class |
| `test_unexpected_modifier_value_is_named` | negative | a Modifier other than Concrete/Abstract is refused, quoting it |
| `test_attributes_not_a_mapping_is_named` | negative | Attributes that is not a dict is refused, naming the class |
| `test_attribute_missing_a_key_is_named` | negative | an attribute missing a required key is refused, naming Class.attribute and the key |
| `test_attribute_missing_several_keys_lists_them` | negative | several missing keys are all listed in one message |
| `test_type_that_is_not_a_reference_list_is_named` | negative | a Type holding a plain word instead of a list of `$ref` entries is refused, naming the attribute and field |
| `test_empty_type_list_is_refused` | negative | an empty Type list is refused the same way |
| `test_inherited_from_without_ref_is_named` | negative | an Inherited From entry lacking `$ref` is refused, naming the attribute and field |

### Refusing a file that cannot be trusted (`IntegrityError`, exit 3)

| Check | Kind | Proves |
| --- | --- | --- |
| `test_missing_file_raises_filenotfound` | negative | a path that does not exist is a different failure (exit 1) from a verification failure |
| `test_unrecorded_file_says_no_entry_records_it` | negative | a file no manifest records says so, and does not show the checksum remedy |
| `test_unreadable_manifest_says_unreadable` | negative | a manifest that is not valid JSON is reported as unreadable, remedy points at the manifest |
| `test_absent_manifest_says_not_there` | negative | no manifest file is reported as not there |
| `test_entry_without_sha256_says_malformed` | negative | an entry with no sha256 is reported as malformed |
| `test_checksum_mismatch_shows_both_hashes_and_recovery` | negative | a wrong sha256 shows both values and the three recovery paths |
| `test_size_mismatch_is_reported_as_size` | negative | a wrong byte count is reported as a size difference |

### Command line exit codes

| Check | Kind | Proves |
| --- | --- | --- |
| `test_cli_no_mode_exits_2` | negative | no mode flag exits 2 |
| `test_cli_missing_spec_exits_1` | negative | pinned file not downloaded exits 1 and names fetch_sources.py |
| `test_cli_unverifiable_spec_exits_3` | negative | file present but unverifiable exits 3 |
| `test_cli_wrong_shape_exits_4` | negative | file not shaped like USDM exits 4 |
| `test_cli_malformed_type_exits_4_not_traceback` | negative | malformed Type values make --attributes exit 4 with the attribute named, not a traceback |
| `test_cli_allow_unpinned_reads_the_file` | positive | --allow-unpinned skips the manifest check and lists classes, exit 0 |
| `test_cli_attributes_prints_type_cardinality_kind` | positive | --attributes prints type, cardinality, kind and inheritance, exit 0 |
| `test_cli_unknown_class_exits_5` | negative | an unknown class exits 5 and points at --list-classes |

### The real pinned file (skip when `data/` is absent)

| Check | Kind | Proves |
| --- | --- | --- |
| `test_pinned_file_verifies_and_loads` | positive | the pinned file matches its checksum and passes both shape checks |
| `test_pinned_file_has_86_classes_80_concrete` | positive | 86 classes, 80 concrete, 6 abstract, naming the six |
| `test_pinned_file_types_are_classes_or_five_primitives` | positive | every type is a class or one of five primitives; exactly four multi-target attributes |
| `test_fixture_classes_are_identical_to_pinned` | positive | the fixture's three classes are identical to the pinned ones |

### The record-writer itself (`test_validation_report.py`)

Each check builds a tiny throwaway suite in a temporary folder, gives it a copy of `conftest.py`, runs pytest on it as a separate process with the record pointed at a temporary folder, and reads the record that comes out. Nothing lands in `validation/`.

| Check | Kind | Proves |
| --- | --- | --- |
| `test_passing_run_is_recorded_as_pass` | positive | an all-pass suite gets PASS, exit status 0, one row per test, a skip shown with its reason |
| `test_no_flag_writes_nothing` | positive | without the flag, nothing is written |
| `test_cleanup_failure_is_recorded_as_fail` | negative | a test whose checks pass but whose clean-up throws gives FAIL and an error row, never passed |
| `test_failing_assertion_is_recorded_as_fail` | negative | a failing check gives FAIL and a failed row |
| `test_setup_failure_is_recorded_as_error` | negative | a set-up that throws gives FAIL and an error row |
| `test_file_that_will_not_load_still_gets_a_fail_record` | negative | a test file with a syntax error still produces a record, saying FAIL and that no test ran |

## Validation records

Development runs write nothing. When a component is declared ready, run `pytest --validation-report`. `conftest.py` then writes `validation/<component>_<date>_<commit>.md`. Commit that file. A second run on the same day and commit gets a `-2` suffix rather than overwriting.

A record is meant to be auditable, so it identifies what was tested, how, when, by whom, and the outcome:

- **Verdict**: PASS only when pytest itself exited 0, and the exit status is shown with its meaning. pytest's exit status already accounts for every kind of failure (a test's checks, its set-up, its clean-up, a file that will not load), so the record cannot say PASS when the terminal said fail. Counts of passed / failed / error / skipped and the duration follow. If pytest failed before any test ran, a record is still written saying so, named `run_<date>_<commit>.md`.
- **What was tested**: the component; the code commit, flagged if uncommitted changes were present at run time; the test file and its sha256; every fixture file and its sha256; the pinned USDM data version (the manifest's recorded url, which carries the DDF-RA commit, and sha256), and whether that file was present.
- **How**: the exact command line, Python and pytest versions, operating system.
- **When and by whom**: local timestamp with time zone, git user name.
- **Per check**: name, kind (positive or negative), what it proves (the first paragraph of its docstring), and its outcome, with the reason if skipped.

Because the record is written before the validating commit exists, its commit hash is the parent and it is flagged as having uncommitted changes. The commit that adds the record is the one that says "validated"; `git log` on the record file shows it.

| Component | Record | State it validates |
| --- | --- | --- |
