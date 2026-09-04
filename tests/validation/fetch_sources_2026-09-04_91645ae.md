# Validation record: fetch_sources

Written by `pytest --validation-report` on 2026-09-04 17:34 Eastern Daylight Time. Design and rationale for these tests: `tests/README.md`.

| | |
| --- | --- |
| Verdict | **PASS**: pytest exit status 0 (all tests passed) |
| Counts | 12 passed, 0 failed, 0 error, 0 skipped, in 7.3 s |
| Component | `scripts/fetch_sources.py` |
| Code commit | `91645ae` (uncommitted changes present at run time) |
| Test file | `tests/test_fetch_sources.py` sha256 `24bde1702948c14b4eef255cd6ae8809e68fcb82306e2cf211f4ca3a5a488487` |
| Fixtures | `tests/fixtures/usdm_three_classes.yml` sha256 `50f0c08ce0356a6595871e89621497d93302f2d3a5aacf8ea2cdd63303a1aaf1` |
| Pinned USDM data | https://raw.githubusercontent.com/cdisc-org/DDF-RA/aa303cb32f5d3ceecc68a16803e26720d2c1fc26/Deliverables/UML/dataStructure.yml, sha256 `6f49a407aef41a66dd40a82ad3348672a22cd8874849254d7e4f27d6275daca6`, present |
| Command | `pytest --validation-report` |
| Run by | Jason Delosh |
| When | 2026-09-04 17:34:47 Eastern Daylight Time |
| Python / pytest | 3.12.13 / 9.1.1 |
| Platform | Windows-11-10.0.26200-SP0 |

| Test | Kind | Proves | Outcome |
| --- | --- | --- | --- |
| `test_missing_file_is_downloaded_verified_and_placed` | positive | A recorded file not on disk is downloaded, its sha256 checked, and only then renamed into place; exit 0, no .part left behind. | passed |
| `test_present_and_matching_file_is_not_fetched` | positive | A file already on disk that matches its manifest is counted as present and the network is never touched; exit 0. | passed |
| `test_dry_run_lists_and_writes_nothing` | positive | --dry-run says what it would fetch, touches no network, writes no file; exit 0. | passed |
| `test_quiet_prints_nothing` | positive | --quiet prints nothing; the exit code is the whole report. | passed |
| `test_present_but_changed_file_is_left_alone_exits_2` | negative | A file on disk whose sha256 disagrees with its manifest is reported and not touched (data/raw/ is immutable; a human decides), exit 2. | passed |
| `test_download_with_wrong_hash_is_discarded_exits_1` | negative | A download whose bytes do not match the recorded sha256 never reaches its final name: reported as HASH MISMATCH, discarded, exit 1. | passed |
| `test_network_failure_is_reported_exits_1` | negative | A url that cannot be fetched is reported FAILED, leaves no .part file, and the run exits 1. | passed |
| `test_failure_outranks_disagreement` | negative | With one download failing and another file disagreeing on disk, the exit code is 1: an incomplete corpus is worse than a known-but-wrong file. | passed |
| `test_entry_missing_a_field_counts_as_disagreement` | negative | A manifest entry with no url cannot be acted on and is reported as a defect in the manifest, exit 2, rather than skipped silently. | passed |
| `test_unreadable_manifest_exits_3` | negative | A manifest that is not valid JSON stops the run with exit 3, since every file location downstream of it is unknown. | passed |
| `test_set_with_no_match_exits_3` | negative | --set naming a manifest that does not exist exits 3 and says so. | passed |
| `test_not_inside_the_repo_exits_6` | negative | When the package is not running from inside its repo, the run exits 6 with the install command instead of reporting 'no manifests found'. | passed |
