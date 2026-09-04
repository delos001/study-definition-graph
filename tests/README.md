# tests/

Automated checks for the code in `src/sdg/` and the hand-run scripts in `scripts/`, and the validation records that prove a component was checked at a given point. Kept by hand.

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
| `conftest.py` | pytest's setup file for this folder. Adds the `--validation-report` flag, the `positive` / `negative` markers, and the shared fixtures for staging pinned data in a temporary folder: `manifest_dir` and `manifest_recording` (one manifest for one file) and `fake_repo` (a whole throwaway repo with its own manifests and raw files, for the script checks). |
| `test_pinned.py` | The checks for `src/sdg/pinned.py`, the one way to obtain a pinned file verified against its manifest. |
| `test_usdm_spec.py` | The checks for `src/sdg/usdm_spec.py`, the loader for the pinned USDM model. |
| `test_verify_manifests.py` | The checks for `scripts/verify_manifests.py`: one exit code per state of the corpus. |
| `test_fetch_sources.py` | The checks for `scripts/fetch_sources.py`: download, verify, then place, against a fake network. |
| `test_check_facts.py` | The checks for `scripts/check_facts.py`: drift is caught, and each way a measurement can fail has its own exit code. |
| `test_build_index.py` | The checks for `scripts/build_index.py`: the generated index and the `--check` the pre-commit hook runs. |
| `test_validation_report.py` | The checks for the record-writer in `conftest.py`: above all, that a record can never say PASS when pytest said the run failed. |
| `fixtures/usdm_three_classes.yml` | Three classes copied verbatim from the pinned `dataStructure.yml`: `Identifier` (abstract), `StudyIdentifier` (its concrete child, with inherited attributes) and `Condition` (holds the five-way reference). The input for the logic checks. |
| `validation/` | Validation records, one file per component per validated state. Written only when asked; committed. |

## How the checks are designed

Each check sets up a situation, runs the code, and compares what happened to what the code's own documentation promises (its header block, exit codes and docstrings). Each is marked one of two kinds:

- **positive**: the right thing works. A well-formed input gives the documented result.
- **negative**: the broken thing fails, and for the right reason. The input is broken in one described way and the check asserts both the error type and that the message names that cause and not another.

The logic checks use the small fixture file rather than the real pinned file, because they have to break their input on purpose (delete a key, swap a dict for a list) and the fixture is small enough to read whole and see the break. The fixture is not invented: `test_fixture_classes_are_identical_to_pinned` proves each of its classes is key-for-key identical to the pinned file, so the logic checks ran on real USDM shapes. Broken variants are made in memory from the fixture and written to a temporary folder pytest owns; the fixture on disk is never touched, and the change each variant makes is stated in that check's docstring.

The real-file checks read the pinned `dataStructure.yml` in place and assert the measured facts about it. They need `data/` downloaded (`python scripts/fetch_sources.py`) and skip, with that reason, when it is not.

The script checks call each script's `main()` in-process with an argument list, the way `sdg.usdm_spec.main()` is called, rather than through a subprocess, so a failure shows a Python traceback instead of captured output. `pyproject.toml` puts `scripts/` on pytest's import path for this. Each check stages one state of the corpus in a throwaway repo built by the `fake_repo` fixture (its own `pyproject.toml`, `data/manifests/` and `data/raw/`, with `sdg.pinned` pointed at it), so the real `data/` is never read or written. `fetch_sources.py`'s network is replaced with a function that serves bytes, or raises, per url; no check fetches anything.

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

The per-cause messages belong to `sdg.pinned` and are proven in `test_pinned.py` (below). These prove the loader is wired to it.

| Check | Kind | Proves |
| --- | --- | --- |
| `test_missing_file_raises_filenotfound` | negative | a path that does not exist is a different failure (exit 1) from a verification failure |
| `test_unrecorded_file_is_refused_through_load` | negative | a file no manifest records is refused through `load()` with that message, not the mismatch remedy |
| `test_fingerprint_mismatch_is_refused_through_load` | negative | a wrong sha256 is refused through `load()` with both values and the recovery paths |

### Command line exit codes

| Check | Kind | Proves |
| --- | --- | --- |
| `test_cli_no_mode_exits_2` | negative | no mode flag exits 2 |
| `test_cli_missing_spec_exits_1` | negative | pinned file not downloaded exits 1 and names fetch_sources.py |
| `test_cli_unverifiable_spec_exits_3` | negative | file present but unverifiable exits 3 |
| `test_cli_not_inside_repo_exits_6` | negative | package not running from inside its repo exits 6 with the install command |
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

### Obtaining a pinned file (`test_pinned.py`)

`sdg.pinned.pinned(<path>)` is the one way any code gets a pinned file: it finds the manifest entry, checks size and fingerprint, and returns the file with its identity. The failure cases stage a manifest in a temporary folder (the `manifest_dir` and `manifest_recording` fixtures in `conftest.py`) against the three-class fixture file, which no real manifest records.

| Check | Kind | Proves |
| --- | --- | --- |
| `test_running_from_inside_the_repo` | positive | the folder the package takes to be the repo holds pyproject.toml and data/manifests/ |
| `test_real_pinned_file_comes_back_with_its_identity` | positive | the pinned USDM file verifies and returns the manifest's sha256 and url (skips when `data/` is absent) |
| `test_string_and_path_name_the_same_file` | positive | a repo-relative string and a full path give the same record (skips when `data/` is absent) |
| `test_recorded_fixture_verifies` | positive | a file whose entry has the right size and fingerprint comes back readable |
| `test_not_inside_the_repo_names_the_install_fix` | negative | a package not running from its repo is refused with where it was found and `pip install -e .` |
| `test_recorded_but_not_downloaded_raises_filenotfound` | negative | a recorded file missing from disk raises FileNotFoundError |
| `test_unrecorded_file_says_no_entry_records_it` | negative | a file no manifest records says so, without the mismatch remedy |
| `test_unreadable_manifest_says_unreadable` | negative | a manifest that is not valid JSON is reported as unreadable, remedy points at the manifests folder |
| `test_no_manifests_at_all_says_so` | negative | an empty manifests folder is reported as no manifests found |
| `test_entry_without_sha256_says_malformed` | negative | an entry with no sha256 is reported as malformed |
| `test_fingerprint_mismatch_shows_both_values_and_recovery` | negative | a wrong sha256 shows both values, the manifest that records it, and the three recovery paths |
| `test_size_mismatch_is_reported_as_size` | negative | a wrong byte count is reported as a size difference |

### The corpus check (`test_verify_manifests.py`)

Each check stages one state of a one-file corpus and asserts the exit code and the report line the script's header promises for it.

| Check | Kind | Proves |
| --- | --- | --- |
| `test_clean_corpus_exits_0` | positive | every file present and matching, nothing unrecorded: exit 0 |
| `test_verbose_lists_passing_files` | positive | `--verbose` lists each passing file |
| `test_quiet_prints_nothing` | positive | `--quiet` prints nothing |
| `test_placeholder_and_lock_files_are_not_unrecorded` | positive | `.gitkeep` and Excel `~$` lock files are not reported as unrecorded |
| `test_missing_file_exits_1` | negative | a recorded file not on disk is MISSING, exit 1 |
| `test_changed_content_exits_1` | negative | changed bytes at the same size is a sha256 MISMATCH showing both values, exit 1 |
| `test_unrecorded_file_exits_2` | negative | a file no manifest records is listed by path, exit 2 |
| `test_mismatch_outranks_unrecorded` | negative | with both, exit 1 |
| `test_malformed_entry_is_a_problem` | negative | an entry with no sha256 is MALFORMED, not skipped |
| `test_unreadable_manifest_exits_3` | negative | invalid JSON is MANIFEST UNREADABLE, exit 3, other sets still checked |
| `test_no_manifests_exits_3` | negative | an empty manifests folder exits 3 |
| `test_not_inside_the_repo_exits_6` | negative | package installed wrongly exits 6 with the install command |
| `test_set_checks_one_manifest_and_skips_the_unrecorded_scan` | positive | `--set` narrows to one manifest and skips the unrecorded scan |

### The downloader (`test_fetch_sources.py`)

The network is faked per url. A check that must not download installs a fake that fails the test if called.

| Check | Kind | Proves |
| --- | --- | --- |
| `test_missing_file_is_downloaded_verified_and_placed` | positive | a missing file is fetched, hash-checked, then placed; no `.part` left |
| `test_present_and_matching_file_is_not_fetched` | positive | a matching file is counted as present and the network is not touched |
| `test_dry_run_lists_and_writes_nothing` | positive | `--dry-run` lists what it would fetch, no network, no write |
| `test_quiet_prints_nothing` | positive | `--quiet` prints nothing |
| `test_present_but_changed_file_is_left_alone_exits_2` | negative | a file disagreeing with its manifest is reported and not touched, exit 2 |
| `test_download_with_wrong_hash_is_discarded_exits_1` | negative | a download with the wrong hash never reaches its final name, exit 1 |
| `test_network_failure_is_reported_exits_1` | negative | a dead url is FAILED, no `.part` left, exit 1 |
| `test_failure_outranks_disagreement` | negative | with both, exit 1 |
| `test_entry_missing_a_field_counts_as_disagreement` | negative | an entry with no url is a manifest defect, exit 2 |
| `test_unreadable_manifest_exits_3` | negative | invalid JSON stops the run, exit 3 |
| `test_set_with_no_match_exits_3` | negative | `--set` naming no manifest exits 3 |
| `test_not_inside_the_repo_exits_6` | negative | package installed wrongly exits 6 with the install command |

### The fact check (`test_check_facts.py`)

The script's list of measurements is replaced by one fake fact and one one-line document, so each check controls both the measured and the stated number.

| Check | Kind | Proves |
| --- | --- | --- |
| `test_matching_figure_exits_0` | positive | a correct figure passes; `--verbose` shows the ok line |
| `test_drifted_figure_exits_1` | negative | a wrong figure is DRIFTED with both values, exit 1 |
| `test_every_occurrence_is_checked` | negative | a stale second copy is caught even when the first is correct |
| `test_unasserted_fact_is_reported_but_passes` | positive | a fact no document states is reported, exit 0 |
| `test_number_written_as_a_word_is_read` | positive | "three" matches 3 |
| `test_each_measurement_failure_has_its_own_exit_code` | negative | file missing 2, cannot verify 3, wrong shape 4, not in repo 6, each labelled with its cause |
| `test_package_not_installed_exits_7_before_measuring` | negative | sdg not installed exits 7 before any measurement |
| `test_real_documents_match_real_corpus` | positive | the committed documents match the pinned corpus (skips when `data/` is absent) |

### The index generator (`test_build_index.py`)

| Check | Kind | Proves |
| --- | --- | --- |
| `test_writes_first_paragraph_and_usage_with_indent_kept` | positive | the index holds the first Description paragraph and the Usage block with its indentation |
| `test_scripts_are_listed_in_name_order` | positive | scripts appear alphabetically |
| `test_check_passes_when_index_is_current` | positive | `--check` exits 0 and writes nothing when current |
| `test_check_fails_when_index_is_stale_or_missing` | negative | `--check` exits 1 when the index is missing or stale |
| `test_quiet_prints_nothing` | positive | `--quiet` prints nothing |
| `test_missing_field_exits_2_and_writes_nothing` | negative | a header missing fields exits 2, naming them; index not written |
| `test_no_docstring_exits_2` | negative | no docstring is no header, exit 2 |
| `test_unparseable_script_exits_3_and_outranks_2` | negative | invalid Python exits 3, and outranks 2 |
| `test_no_scripts_exits_3` | negative | an empty folder exits 3 |
| `test_real_index_is_current` | positive | the real `scripts/README.md` is current, the pre-commit hook's check |

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
- **What was tested**: the component (`src/sdg/<x>.py` or `scripts/<x>.py`, whichever `test_<x>.py` names); the code commit, flagged if uncommitted changes were present at run time; the test file and its sha256; every fixture file and its sha256; the pinned USDM data version (the manifest's recorded url, which carries the DDF-RA commit, and sha256), and whether that file was present.
- **How**: the exact command line, Python and pytest versions, operating system.
- **When and by whom**: local timestamp with time zone, git user name.
- **Per check**: name, kind (positive or negative), what it proves (the first paragraph of its docstring), and its outcome, with the reason if skipped.

Because the record is written before the validating commit exists, its commit hash is the parent and it is flagged as having uncommitted changes. The commit that adds the record is the one that says "validated"; `git log` on the record file shows it.

| Component | Record | State it validates |
| --- | --- | --- |
| `src/sdg/pinned.py` | [validation/pinned_2026-09-04_246dfd5.md](validation/pinned_2026-09-04_246dfd5.md) | First version: pinned files behind one function, one message per failure cause, the in-repo check. |
| `src/sdg/usdm_spec.py` | [validation/usdm_spec_2026-09-04_246dfd5.md](validation/usdm_spec_2026-09-04_246dfd5.md) | After the 2026-09-04 review: per-cause errors, reference-shape checks, loading through `pinned.py`, exit code 6. |
| `tests/conftest.py` (the record-writer) | [validation/validation_report_2026-09-04_246dfd5.md](validation/validation_report_2026-09-04_246dfd5.md) | Verdict taken from pytest's exit status; clean-up and set-up failures recorded as error; a record still written when no test ran. |
