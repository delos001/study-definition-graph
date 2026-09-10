# Validation record: sources_acquire_sources

Written by `pytest --validation-report` on 2026-09-10 17:48 Eastern Daylight Time. Design and rationale for these tests: `tests/README.md`.

| | |
| --- | --- |
| Verdict | **PASS**: pytest exit status 0 (all tests passed) |
| Counts | 17 passed, 0 failed, 0 error, 0 skipped, in 0.3 s |
| Component | `src/sdg/sources/acquire_sources.py` |
| Code commit | `7167f97` (uncommitted changes present at run time) |
| Test file | `tests/sources/test_acquire_sources.py` sha256 `f3e9ff477144ab01c225dc3b9d76f6ad08642713e3b4c99bf35135a02bb24fe1` |
| Fixtures | `tests/fixtures/usdm_three_classes.yml` sha256 `50f0c08ce0356a6595871e89621497d93302f2d3a5aacf8ea2cdd63303a1aaf1` |
| Pinned USDM data | https://raw.githubusercontent.com/cdisc-org/DDF-RA/aa303cb32f5d3ceecc68a16803e26720d2c1fc26/Deliverables/UML/dataStructure.yml, sha256 `6f49a407aef41a66dd40a82ad3348672a22cd8874849254d7e4f27d6275daca6`, present |
| Command | `pytest tests/sources --validation-report` |
| Run by | Jason Delosh |
| When | 2026-09-10 17:48:26 Eastern Daylight Time |
| Python / pytest | 3.12.13 / 9.1.1 |
| Platform | Windows-11-10.0.26200-SP0 |

| Test | Kind | Proves | Outcome |
| --- | --- | --- | --- |
| `test_missing_file_is_downloaded_verified_and_placed` | positive | A recorded file not on disk is fetched, hash-checked and placed under its final name, with no .part file left and exit 0. | passed |
| `test_present_and_matching_file_is_not_fetched` | positive | A file already on disk that matches its entry is counted as present, and the network is not touched. | passed |
| `test_dry_run_lists_what_it_would_fetch_and_writes_nothing` | positive | --dry-run names each missing file as would fetch, touches neither the network nor the disk, and exits 1 because the corpus is incomplete. | passed |
| `test_dry_run_on_a_complete_corpus_exits_0` | positive | --dry-run on a corpus with every file present and matching exits 0, so --dry-run --quiet answers whether the corpus is complete from the exit code alone. | passed |
| `test_quiet_prints_nothing` | positive | --quiet prints nothing at all, even when a file is fetched. | passed |
| `test_set_narrows_to_one_manifest` | positive | --set names one manifest, and only that manifest's files are fetched or checked; the other manifest is not read. | passed |
| `test_present_but_changed_file_is_left_alone_exits_2` | negative | A file on disk that no longer matches its entry is reported as a MISMATCH and is neither replaced nor deleted, exit 2. | passed |
| `test_download_with_wrong_hash_is_discarded_exits_1` | negative | A download whose bytes do not match the entry is discarded, never appears under the final name, leaves no .part file, and exits 1. | passed |
| `test_network_failure_is_reported_exits_1` | negative | A url that cannot be fetched is reported as FAILED with the cause, and the run exits 1. | passed |
| `test_failure_outranks_disagreement` | negative | With one file changed on disk and another that cannot be fetched, both are reported and the exit code is 1, because a missing file is worse than a changed one. | passed |
| `test_dry_run_missing_file_outranks_disagreement` | negative | In a dry run too, a file that would need fetching outranks a changed file: both are reported and the exit code is 1, not 2. | passed |
| `test_locked_file_at_a_recorded_path_is_reported_exits_2` | negative | A recorded file that is on disk but cannot be opened, as a workbook Excel has locked, is reported as CANNOT READ with the cause and left alone, exit 2, rather than ending the run with a traceback. | passed |
| `test_folder_at_a_recorded_path_is_reported_exits_2` | negative | A folder where a recorded file should be is reported as CANNOT READ and left alone, exit 2, rather than ending the run with a traceback. | passed |
| `test_entry_missing_a_field_stops_the_run_exits_3` | negative | An entry lacking a required field is a manifest problem: the run stops with exit 3 and the message names the field. | passed |
| `test_unreadable_manifest_exits_3` | negative | A manifest that is not valid JSON stops the run with exit 3 and names the file. | passed |
| `test_set_with_no_match_exits_3` | negative | --set naming a manifest that does not exist exits 3 and names it. | passed |
| `test_not_inside_the_repo_exits_6` | negative | A package not running from inside its repo exits 6 with the install command, before any manifest is read. | passed |
