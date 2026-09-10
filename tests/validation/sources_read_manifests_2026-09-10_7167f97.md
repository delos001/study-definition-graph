# Validation record: sources_read_manifests

Written by `pytest --validation-report` on 2026-09-10 17:48 Eastern Daylight Time. Design and rationale for these tests: `tests/README.md`.

| | |
| --- | --- |
| Verdict | **PASS**: pytest exit status 0 (all tests passed) |
| Counts | 16 passed, 0 failed, 0 error, 0 skipped, in 0.3 s |
| Component | `src/sdg/sources/read_manifests.py` |
| Code commit | `7167f97` (uncommitted changes present at run time) |
| Test file | `tests/sources/test_read_manifests.py` sha256 `c2ad42dd37a84af5e21a95f412b840b2aaefab71d21b0b8f4b118ad254eb06cc` |
| Fixtures | `tests/fixtures/usdm_three_classes.yml` sha256 `50f0c08ce0356a6595871e89621497d93302f2d3a5aacf8ea2cdd63303a1aaf1` |
| Pinned USDM data | https://raw.githubusercontent.com/cdisc-org/DDF-RA/aa303cb32f5d3ceecc68a16803e26720d2c1fc26/Deliverables/UML/dataStructure.yml, sha256 `6f49a407aef41a66dd40a82ad3348672a22cd8874849254d7e4f27d6275daca6`, present |
| Command | `pytest tests/sources --validation-report` |
| Run by | Jason Delosh |
| When | 2026-09-10 17:48:26 Eastern Daylight Time |
| Python / pytest | 3.12.13 / 9.1.1 |
| Platform | Windows-11-10.0.26200-SP0 |

| Test | Kind | Proves | Outcome |
| --- | --- | --- | --- |
| `test_running_from_inside_the_repo` | positive | require_repo() accepts this checkout and gives back its root, the folder that holds pyproject.toml. | passed |
| `test_every_hand_written_manifest_reads` | positive | manifests() reads the six hand-written manifests, each with its name, a landing folder under inputs/, and entries that carry all five required fields and remember which manifest they came from. | passed |
| `test_study_manifests_read_alongside` | positive | A manifest under manifests/study_documents/ is read in the same call as the top-level ones, and is listed after them. | passed |
| `test_listing_order_is_by_path_and_stable` | positive | Manifests come back sorted by path, whatever order they were written in, and two calls give the same order. | passed |
| `test_one_manifest_by_name_with_or_without_suffix` | positive | Asking for one manifest by name gives only that one, whether the name is given with or without its .json suffix. | passed |
| `test_entry_for_finds_a_recorded_file_by_string_or_path` | positive | entry_for() gives the same entry for a repo-relative string, the same string with backslashes, and a full Path, and the entry's path is the file's full path on this machine. | passed |
| `test_entry_for_gives_none_for_an_unrecorded_file` | positive | A file that no manifest records gives None, not an error. | passed |
| `test_as_local_gives_an_outside_path_back_unchanged` | positive | A path outside the repo comes back from as_local() as its full path, unchanged, so a message about it can show where it is. | passed |
| `test_not_inside_the_repo_names_the_install_fix` | negative | A pyproject.toml that does not name the sdg package is refused as not running from inside the repo, with the pip install -e . remedy, before any manifest is looked for. | passed |
| `test_no_manifests_folder_names_the_restore_remedy` | negative | A missing manifests/ folder is reported by name, with the git restore remedy. | passed |
| `test_empty_manifests_folder_says_none_found` | negative | A manifests/ folder with no manifest in it is reported as no manifests found, with the git restore remedy. | passed |
| `test_named_manifest_that_does_not_exist_is_named` | negative | Asking for a manifest by a name no file has is refused with that name in the message. | passed |
| `test_unreadable_manifest_names_the_file` | negative | A manifest that is not valid JSON stops the read with an error naming that file and the restore remedy, rather than being skipped. | passed |
| `test_entry_missing_fields_lists_all_of_them` | negative | An entry lacking required fields is refused with the manifest, the entry and every missing field named in one message, and the repair remedy. | passed |
| `test_size_that_is_not_a_whole_number_is_quoted` | negative | A size written as "12,345" is refused as not a whole number, with the value quoted as written so a person sees their own typo. | passed |
| `test_sha256_that_is_not_lowercase_hex_is_quoted` | negative | A sha256 in uppercase is refused as not 64 lowercase hex characters, with the value quoted as written. | passed |
