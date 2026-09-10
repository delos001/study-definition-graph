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
| `conftest.py` | pytest's shared fixtures and configuration for this folder; pytest requires the name. Adds the `--validation-report` flag, the `positive` and `negative` markers, and three fixtures that stage pinned data in a temporary folder: `manifest_dir` and `manifest_recording` stage one manifest for one file, and `fake_repo` builds a whole throwaway repo with its own `manifests/` and `inputs/`. |
| `sources/`, `usdm/`, `scripts/` | One subfolder per code folder, mirroring `src/sdg/sources/`, `src/sdg/usdm/` and `scripts/`. A test file lives at the same relative path as the file it tests and carries its name: `tests/sources/test_fetch_file.py` tests `src/sdg/sources/fetch_file.py`. |
| `sources/test_read_manifests.py` | The checks for `src/sdg/sources/read_manifests.py`, the step that reads the manifests: what is read, in what order, and every way a manifest or an entry is refused. |
| `sources/test_fetch_file.py` | The checks for `src/sdg/sources/fetch_file.py`, the step that downloads one file to a `.part` name, against a fake server. |
| `sources/test_fingerprint_file.py` | The checks for `src/sdg/sources/fingerprint_file.py`, the step that measures a file and compares it to its entry. |
| `sources/test_finalize_file.py` | The checks for `src/sdg/sources/finalize_file.py`, the step that places a finished download under its final name or discards it. |
| `sources/test_verify_pinned.py` | The checks for `src/sdg/sources/verify_pinned.py`, the workflow that proves a pinned file is the recorded one and hands it back with its identity. |
| `sources/test_acquire_sources.py` | The checks for `src/sdg/sources/acquire_sources.py`, the workflow that fetches what is missing and confirms what is present, against a fake network. |
| `usdm/test_usdm_spec.py` | The checks for `src/sdg/usdm/usdm_spec.py`, the loader for the pinned USDM model. Stale: imports the former module path; rewrite pending. |
| `scripts/test_find_unrecorded_files.py` | The checks for `scripts/find_unrecorded_files.py`. Stale: written against the former `scripts/verify_manifests.py`, whose per-entry checks now live in the acquire dry run; rewrite pending. |
| `scripts/test_check_facts.py` | The checks for `scripts/check_facts.py`: drift is caught, and each way a measurement can fail has its own exit code. |
| `scripts/test_build_index.py` | The checks for `scripts/build_index.py`: the generated index and the `--check` the pre-commit hook runs. |
| `test_validation_report.py` | The checks for the record-writer in `conftest.py`: above all, that a record can never say PASS when pytest said the run failed. It stays at the top level because `conftest.py` does. |
| `fixtures/usdm_three_classes.yml` | Three classes copied verbatim from the pinned `dataStructure.yml`: `Identifier` (abstract), `StudyIdentifier` (its concrete child, with inherited attributes) and `Condition` (holds the five-way reference). The input for the logic checks. |
| `validation/` | Validation records, one file per component per validated state. Written only when asked; committed. |

## Rules every test file follows

The rules for every Python file in the repo are in `CLAUDE.md` under "Source files". They are restated here together with the rules that apply only to tests, so that this one list is complete and a test file can be checked against it without opening anything else. The test is whether a reader with no other help can tell what the file, each section and each check is for.

**Layout**

- One test file per code file, at the mirrored path, carrying the code file's name: `tests/sources/test_fetch_file.py` tests `src/sdg/sources/fetch_file.py`.
- The file opens with the full header block: Script, Description, Inputs, Outputs, Usage, Exit codes, Date, Owner. Date is the day the file was first committed and never changes.
- Sections are marked with two-line banners: a full-width line of `#`, then `### Label ###`. The label is short and says what the code in the section does. Context goes in a comment beneath the banner, where a short description of the section is encouraged.
- Positive checks and negative checks sit in separate sections. Checks against the real repo and checks against a staged repo sit in separate sections too. A fake that several checks share gets its own section, before the checks that use it.

**Each check**

- Is marked `@positive` (the right thing works) or `@negative` (the broken thing fails, and for the right reason).
- Proves one promise. If the sentence saying what it proves needs an "and" joining two different claims, it is two checks. A situation that several checks look at is staged once, in a fixture, and each check asserts one thing about it.
- Has a docstring whose first paragraph is one plain sentence saying what the check proves. That sentence is copied into the validation record, so it has to stand on its own.
- Stages exactly one situation, runs the code, and compares what happened to what the code's own header and docstrings promise.
- A negative check breaks exactly one thing, says which in its docstring, and asserts two things: the error type, and that the message names this cause and its remedy rather than another.

**What a check may touch**

- Nothing real. Manifests and files are staged in a temporary folder through the fixtures in `conftest.py`: `fake_repo`, `manifest_dir` and `manifest_recording`. The real `manifests/` and `inputs/` are read by a few checks that say so in their section, and written by none.
- No network. Anything that downloads is replaced by a fake that serves bytes, or raises, per url. A check that must not download installs a fake that fails the check if it is called.
- A workflow is called in-process through its `main()` with an argument list, not through a subprocess, so a failure shows a traceback.
- A check that needs a pinned download skips, with that reason, when the file is absent.
- No count that will drift as the corpus grows. Assert that the known items are present, not that they are the only ones.

**Markup**

- All markup, meaning headers, banners, docstrings and comments, is plain English in a non-technical voice, concise, with basic sentence structure. Full sentences with verbs; no fragments and no colon-labels.
- A long list written inline becomes bullets.
- A docstring opens with what the function takes in and what it gives back, then why it works that way where that is not obvious.
- Every non-obvious block, every fake, and every workaround carries a comment saying why. A comment never restates the code.

## How the checks are designed

Each check sets up a situation, runs the code, and compares what happened to what the code's own documentation promises: its header block, its exit codes and its docstrings. The logic checks for the model loader use the small fixture file rather than the real pinned file, because they have to break their input on purpose and the fixture is small enough to read whole and see the break. The fixture is not invented: a check proves each of its classes is key-for-key identical to the pinned file. The checks against the real pinned model file read it in place; they need it downloaded (`python -m sdg.sources.acquire_sources`) and skip, with that reason, when it is not.

## The checks, by group

The `Proves` column is the first paragraph of each check's docstring, which is also what the validation record shows; the full docstring in the file says more. The groups for the sources package are current. The groups for the model loader and the scripts describe the test files as they were on 2026-09-04 and are rewritten when those tests are.

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

The per-cause messages belong to the pinned-file check, formerly `sdg.pinned` and now `sdg.sources.verify_pinned`, and are proven in `sources/test_verify_pinned.py`. These prove the loader is wired to it.

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

### Reading the manifests (`sources/test_read_manifests.py`)

Two checks read the real `manifests/` folder, which needs no download. The rest stage a pretend repo through `fake_repo`.

| Check | Kind | Proves |
| --- | --- | --- |
| `test_running_from_inside_the_repo` | positive | require_repo() accepts this checkout and gives back its root, the folder that holds pyproject.toml. |
| `test_every_hand_written_manifest_reads` | positive | manifests() reads the six hand-written manifests, each with its name, a landing folder under inputs/, and entries that carry all five required fields and remember which manifest they came from. |
| `test_study_manifests_read_alongside` | positive | A manifest under manifests/study_documents/ is read in the same call as the top-level ones, and is listed after them. |
| `test_listing_order_is_by_path_and_stable` | positive | Manifests come back sorted by path, whatever order they were written in, and two calls give the same order. |
| `test_one_manifest_by_name_with_or_without_suffix` | positive | Asking for one manifest by name gives only that one, whether the name is given with or without its .json suffix. |
| `test_entry_for_finds_a_recorded_file_by_string_or_path` | positive | entry_for() gives the same entry for a repo-relative string, the same string with backslashes, and a full Path, and the entry's path is the file's full path on this machine. |
| `test_entry_for_gives_none_for_an_unrecorded_file` | positive | A file that no manifest records gives None, not an error. |
| `test_as_local_gives_an_outside_path_back_unchanged` | positive | A path outside the repo comes back from as_local() as its full path, unchanged, so a message about it can show where it is. |
| `test_not_inside_the_repo_names_the_install_fix` | negative | A pyproject.toml that does not name the sdg package is refused as not running from inside the repo, with the pip install -e . remedy, before any manifest is looked for. |
| `test_no_manifests_folder_names_the_restore_remedy` | negative | A missing manifests/ folder is reported by name, with the git restore remedy. |
| `test_empty_manifests_folder_says_none_found` | negative | A manifests/ folder with no manifest in it is reported as no manifests found, with the git restore remedy. |
| `test_named_manifest_that_does_not_exist_is_named` | negative | Asking for a manifest by a name no file has is refused with that name in the message. |
| `test_unreadable_manifest_names_the_file` | negative | A manifest that is not valid JSON stops the read with an error naming that file and the restore remedy, rather than being skipped. |
| `test_entry_missing_fields_lists_all_of_them` | negative | An entry lacking required fields is refused with the manifest, the entry and every missing field named in one message, and the repair remedy. |
| `test_size_that_is_not_a_whole_number_is_quoted` | negative | A size written as "12,345" is refused as not a whole number, with the value quoted as written so a person sees their own typo. |
| `test_sha256_that_is_not_lowercase_hex_is_quoted` | negative | A sha256 in uppercase is refused as not 64 lowercase hex characters, with the value quoted as written. |

### Downloading one file (`sources/test_fetch_file.py`)

The one call the step makes to the HTTP library is replaced by a fake server that serves bytes, answers with an error, or breaks part way, as each check needs.

| Check | Kind | Proves |
| --- | --- | --- |
| `test_download_lands_under_the_part_name` | positive | The bytes the server sends are written to <destination>.part, that path is handed back, and nothing appears under the final name. |
| `test_destination_folders_are_created` | positive | A destination several folders deep works on an empty repo, because the folders on the way are created. |
| `test_leftover_part_file_is_overwritten` | positive | A .part file left by an earlier run is replaced by the new download, not added to, because a .part file is by definition unfinished. |
| `test_request_asks_to_follow_redirects_and_sets_the_timeout` | positive | fetch() asks the HTTP library to follow a redirect and to give up after the module's timeout, which is how a file the server has moved is still found. |
| `test_partial_path_is_the_destination_plus_part` | positive | partial_path() adds .part to the file name and keeps the folder, so the naming rule lives in one place. |
| `test_server_error_is_a_fetch_error` | negative | A server that answers with an error status raises FetchError naming the url and the status, and leaves no .part file. |
| `test_unreachable_server_is_a_fetch_error` | negative | A connection that cannot be made raises FetchError naming the url and the cause, and leaves no .part file. |
| `test_transfer_that_stops_part_way_removes_the_part_file` | negative | A transfer that breaks after the first chunk raises FetchError, and the half-written .part file is removed so it cannot be mistaken for a finished download. |

### Measuring a file (`sources/test_fingerprint_file.py`)

Files are written to a temporary folder; entries are built in memory, since the step never opens a manifest.

| Check | Kind | Proves |
| --- | --- | --- |
| `test_fingerprint_measures_size_and_sha256` | positive | fingerprint() gives back one object holding two values, the size in bytes and the sha256, and both agree with an independent measurement. |
| `test_file_larger_than_one_piece_hashes_correctly` | positive | A file bigger than the piece size the module reads in is hashed the same as a whole-file hash, so reading in pieces loses nothing. |
| `test_matching_file_compares_as_matched` | positive | A file whose size and sha256 equal its entry's compares as matched. |
| `test_size_difference_is_reported_first_and_hash_is_not_computed` | negative | A file whose size differs from its entry is reported as a size difference showing both numbers, and the sha256 is not computed at all. |
| `test_same_size_different_content_is_reported_as_sha256` | negative | A file with the right size but different bytes is reported as a sha256 difference, showing the start of both values. |
| `test_missing_file_raises_file_not_found` | negative | Both functions raise FileNotFoundError naming the path for a path that does not exist. |
| `test_folder_is_refused_like_a_missing_file` | negative | A folder at the path is refused with FileNotFoundError naming the path, because only a file can be measured. |

### Placing or discarding a download (`sources/test_finalize_file.py`)

| Check | Kind | Proves |
| --- | --- | --- |
| `test_place_renames_the_part_file_to_its_final_name` | positive | place() removes the .part suffix, hands back the final path, and leaves nothing under the temporary name. |
| `test_discard_deletes_the_part_file` | positive | discard() deletes the .part file and gives back nothing. |
| `test_place_refuses_to_overwrite_a_file_at_the_final_name` | negative | When a file already sits at the final name, place() raises FileExistsError naming that file and the remedy, and moves nothing: the existing file keeps its bytes and the .part file stays where it is. |
| `test_place_refuses_a_missing_part_file` | negative | place() raises FileNotFoundError naming the path when the .part file does not exist. |
| `test_place_refuses_a_file_that_is_not_a_part_file` | negative | place() raises ValueError naming the path when it does not end in .part, and leaves the file as it is. |
| `test_discard_refuses_a_missing_part_file` | negative | discard() raises FileNotFoundError naming the path when the .part file does not exist. |
| `test_discard_refuses_a_file_that_is_not_a_part_file_and_keeps_it` | negative | discard() raises ValueError for a path that does not end in .part and does not delete it, so a pinned file can never be discarded by mistake. |

### Proving a pinned file (`sources/test_verify_pinned.py`)

Two checks read the real pinned model file and skip when it is not downloaded. The rest stage a pretend repo through `fake_repo`.

| Check | Kind | Proves |
| --- | --- | --- |
| `test_real_pinned_file_comes_back_with_its_identity` | positive | The pinned USDM model file verifies and comes back with the sha256 and url its manifest records, the manifest's name, its path on this machine, and readable content. |
| `test_string_and_path_name_the_same_file` | positive | The repo-relative string a manifest writes, the same string with backslashes, and a full Path all give the same record. |
| `test_recorded_file_verifies_and_reads` | positive | A file whose entry carries the right size and sha256 comes back as a PinnedFile with its path, sha256, url and manifest, and its content reads. |
| `test_staged_string_and_path_give_the_same_record` | positive | In the staged repo too, a repo-relative string and a full Path to the same file give the same record. |
| `test_not_inside_the_repo_is_passed_through` | negative | A package not running from inside its repo is refused with NotInRepoError and the install command, not wrapped as an integrity problem. |
| `test_recorded_but_not_downloaded_raises_file_not_found` | negative | A file that a manifest records but that is not on disk raises FileNotFoundError naming the path, which is a different failure from a file that cannot be verified. |
| `test_unrecorded_file_says_no_entry_records_it` | negative | A file that no manifest records is refused saying so, with the remedy of adding an entry, and without the mismatch remedy, which would be wrong. |
| `test_unreadable_manifest_is_a_manifest_problem` | negative | A manifest that cannot be read is reported as that, naming the manifest file and the restore remedy, not as a problem with the pinned file. |
| `test_no_manifests_at_all_says_so` | negative | An empty manifests folder is reported as no manifests found, with the git restore remedy. |
| `test_malformed_entry_names_the_missing_field` | negative | An entry with no sha256 is reported as lacking that field, with the repair remedy, so a person repairs the entry rather than re-downloading the file. |
| `test_fingerprint_mismatch_shows_both_values_and_the_recovery_paths` | negative | A file whose bytes differ from its entry at the same size is refused showing the start of both sha256 values, the manifest that records it, and the three ways back: re-fetch, read unverified once, or re-pin. |
| `test_size_mismatch_is_reported_as_size` | negative | A file whose size differs from its entry is refused as a size difference showing both numbers, which points at a truncated or replaced download. |

### Acquiring the corpus (`sources/test_acquire_sources.py`)

The workflow's download step is replaced by a fake that serves bytes, or raises, per url. A check that must not download installs a fake that fails the check if it is called.

| Check | Kind | Proves |
| --- | --- | --- |
| `test_missing_file_is_downloaded_verified_and_placed` | positive | A recorded file not on disk is fetched, hash-checked and placed under its final name, with no .part file left and exit 0. |
| `test_present_and_matching_file_is_not_fetched` | positive | A file already on disk that matches its entry is counted as present, and the network is not touched. |
| `test_dry_run_lists_what_it_would_fetch_and_writes_nothing` | positive | --dry-run names each missing file as would fetch, touches neither the network nor the disk, and exits 1 because the corpus is incomplete. |
| `test_dry_run_on_a_complete_corpus_exits_0` | positive | --dry-run on a corpus with every file present and matching exits 0, so --dry-run --quiet answers whether the corpus is complete from the exit code alone. |
| `test_quiet_prints_nothing` | positive | --quiet prints nothing at all, even when a file is fetched. |
| `test_set_narrows_to_one_manifest` | positive | --set names one manifest, and only that manifest's files are fetched or checked; the other manifest is not read. |
| `test_present_but_changed_file_is_left_alone_exits_2` | negative | A file on disk that no longer matches its entry is reported as a MISMATCH and is neither replaced nor deleted, exit 2. |
| `test_download_with_wrong_hash_is_discarded_exits_1` | negative | A download whose bytes do not match the entry is discarded, never appears under the final name, leaves no .part file, and exits 1. |
| `test_network_failure_is_reported_exits_1` | negative | A url that cannot be fetched is reported as FAILED with the cause, and the run exits 1. |
| `test_failure_outranks_disagreement` | negative | With one file changed on disk and another that cannot be fetched, both are reported and the exit code is 1, because a missing file is worse than a changed one. |
| `test_dry_run_missing_file_outranks_disagreement` | negative | In a dry run too, a file that would need fetching outranks a changed file: both are reported and the exit code is 1, not 2. |
| `test_locked_file_at_a_recorded_path_is_reported_exits_2` | negative | A recorded file that is on disk but cannot be opened, as a workbook Excel has locked, is reported as CANNOT READ with the cause and left alone, exit 2, rather than ending the run with a traceback. |
| `test_folder_at_a_recorded_path_is_reported_exits_2` | negative | A folder where a recorded file should be is reported as CANNOT READ and left alone, exit 2, rather than ending the run with a traceback. |
| `test_entry_missing_a_field_stops_the_run_exits_3` | negative | An entry lacking a required field is a manifest problem: the run stops with exit 3 and the message names the field. |
| `test_unreadable_manifest_exits_3` | negative | A manifest that is not valid JSON stops the run with exit 3 and names the file. |
| `test_set_with_no_match_exits_3` | negative | --set naming a manifest that does not exist exits 3 and names it. |
| `test_not_inside_the_repo_exits_6` | negative | A package not running from inside its repo exits 6 with the install command, before any manifest is read. |

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


