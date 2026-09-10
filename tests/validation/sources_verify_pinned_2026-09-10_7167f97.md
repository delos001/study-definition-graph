# Validation record: sources_verify_pinned

Written by `pytest --validation-report` on 2026-09-10 17:48 Eastern Daylight Time. Design and rationale for these tests: `tests/README.md`.

| | |
| --- | --- |
| Verdict | **PASS**: pytest exit status 0 (all tests passed) |
| Counts | 12 passed, 0 failed, 0 error, 0 skipped, in 0.3 s |
| Component | `src/sdg/sources/verify_pinned.py` |
| Code commit | `7167f97` (uncommitted changes present at run time) |
| Test file | `tests/sources/test_verify_pinned.py` sha256 `d046307e0928dc45d6ecaa9ecea106c0ef452e3410de1cfaad4a2726b24c7943` |
| Fixtures | `tests/fixtures/usdm_three_classes.yml` sha256 `50f0c08ce0356a6595871e89621497d93302f2d3a5aacf8ea2cdd63303a1aaf1` |
| Pinned USDM data | https://raw.githubusercontent.com/cdisc-org/DDF-RA/aa303cb32f5d3ceecc68a16803e26720d2c1fc26/Deliverables/UML/dataStructure.yml, sha256 `6f49a407aef41a66dd40a82ad3348672a22cd8874849254d7e4f27d6275daca6`, present |
| Command | `pytest tests/sources --validation-report` |
| Run by | Jason Delosh |
| When | 2026-09-10 17:48:26 Eastern Daylight Time |
| Python / pytest | 3.12.13 / 9.1.1 |
| Platform | Windows-11-10.0.26200-SP0 |

| Test | Kind | Proves | Outcome |
| --- | --- | --- | --- |
| `test_real_pinned_file_comes_back_with_its_identity` | positive | The pinned USDM model file verifies and comes back with the sha256 and url its manifest records, the manifest's name, its path on this machine, and readable content. | passed |
| `test_string_and_path_name_the_same_file` | positive | The repo-relative string a manifest writes, the same string with backslashes, and a full Path all give the same record. | passed |
| `test_recorded_file_verifies_and_reads` | positive | A file whose entry carries the right size and sha256 comes back as a PinnedFile with its path, sha256, url and manifest, and its content reads. | passed |
| `test_staged_string_and_path_give_the_same_record` | positive | In the staged repo too, a repo-relative string and a full Path to the same file give the same record. | passed |
| `test_not_inside_the_repo_is_passed_through` | negative | A package not running from inside its repo is refused with NotInRepoError and the install command, not wrapped as an integrity problem. | passed |
| `test_recorded_but_not_downloaded_raises_file_not_found` | negative | A file that a manifest records but that is not on disk raises FileNotFoundError naming the path, which is a different failure from a file that cannot be verified. | passed |
| `test_unrecorded_file_says_no_entry_records_it` | negative | A file that no manifest records is refused saying so, with the remedy of adding an entry, and without the mismatch remedy, which would be wrong. | passed |
| `test_unreadable_manifest_is_a_manifest_problem` | negative | A manifest that cannot be read is reported as that, naming the manifest file and the restore remedy, not as a problem with the pinned file. | passed |
| `test_no_manifests_at_all_says_so` | negative | An empty manifests folder is reported as no manifests found, with the git restore remedy. | passed |
| `test_malformed_entry_names_the_missing_field` | negative | An entry with no sha256 is reported as lacking that field, with the repair remedy, so a person repairs the entry rather than re-downloading the file. | passed |
| `test_fingerprint_mismatch_shows_both_values_and_the_recovery_paths` | negative | A file whose bytes differ from its entry at the same size is refused showing the start of both sha256 values, the manifest that records it, and the three ways back: re-fetch, read unverified once, or re-pin. | passed |
| `test_size_mismatch_is_reported_as_size` | negative | A file whose size differs from its entry is refused as a size difference showing both numbers, which points at a truncated or replaced download. | passed |
