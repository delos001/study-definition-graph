# Validation record: verify_manifests

Written by `pytest --validation-report` on 2026-09-04 17:34 Eastern Daylight Time. Design and rationale for these tests: `tests/README.md`.

| | |
| --- | --- |
| Verdict | **PASS**: pytest exit status 0 (all tests passed) |
| Counts | 13 passed, 0 failed, 0 error, 0 skipped, in 7.3 s |
| Component | `scripts/verify_manifests.py` |
| Code commit | `91645ae` (uncommitted changes present at run time) |
| Test file | `tests/test_verify_manifests.py` sha256 `e5ff3de4fad55a83f86a9e5c7b6abd8c233342199442ad36c683fe3354e1ab53` |
| Fixtures | `tests/fixtures/usdm_three_classes.yml` sha256 `50f0c08ce0356a6595871e89621497d93302f2d3a5aacf8ea2cdd63303a1aaf1` |
| Pinned USDM data | https://raw.githubusercontent.com/cdisc-org/DDF-RA/aa303cb32f5d3ceecc68a16803e26720d2c1fc26/Deliverables/UML/dataStructure.yml, sha256 `6f49a407aef41a66dd40a82ad3348672a22cd8874849254d7e4f27d6275daca6`, present |
| Command | `pytest --validation-report` |
| Run by | Jason Delosh |
| When | 2026-09-04 17:34:47 Eastern Daylight Time |
| Python / pytest | 3.12.13 / 9.1.1 |
| Platform | Windows-11-10.0.26200-SP0 |

| Test | Kind | Proves | Outcome |
| --- | --- | --- | --- |
| `test_clean_corpus_exits_0` | positive | Every recorded file present and matching, nothing unrecorded: exit 0 and a summary saying so. | passed |
| `test_verbose_lists_passing_files` | positive | --verbose adds one 'ok' line per file that passed. | passed |
| `test_quiet_prints_nothing` | positive | --quiet prints nothing at all; the exit code is the whole report. | passed |
| `test_placeholder_and_lock_files_are_not_unrecorded` | positive | A .gitkeep placeholder and an Excel ~$ lock file under data/raw/ are editor and git artifacts, not data, and are not reported as unrecorded. | passed |
| `test_missing_file_exits_1` | negative | A recorded file that is not on disk is reported MISSING with its path, exit 1. | passed |
| `test_changed_content_exits_1` | negative | A file whose bytes changed but whose size did not is reported as a sha256 MISMATCH showing both fingerprints, exit 1. | passed |
| `test_unrecorded_file_exits_2` | negative | A file under data/raw/ that no manifest records is listed by path with the reminder that it cannot be restored from a clone, exit 2. | passed |
| `test_mismatch_outranks_unrecorded` | negative | With both a corrupted pin and an unrecorded file, the exit code is 1: a corrupted pin is the worse problem. | passed |
| `test_malformed_entry_is_a_problem` | negative | A manifest entry with no sha256 verifies nothing and is reported as MALFORMED rather than skipped, exit 1. | passed |
| `test_unreadable_manifest_exits_3` | negative | A manifest that is not valid JSON is reported MANIFEST UNREADABLE and the run exits 3, even though every other manifest was still checked. | passed |
| `test_no_manifests_exits_3` | negative | An empty manifests folder exits 3 and names the folder it looked in. | passed |
| `test_not_inside_the_repo_exits_6` | negative | When the package is not running from inside its repo, the run exits 6 with the install command instead of reporting 'no manifests found'. | passed |
| `test_set_checks_one_manifest_and_skips_the_unrecorded_scan` | positive | --set checks only the named manifest and does not run the unrecorded scan, since every other set's files would otherwise be reported as unrecorded. Accepts the stem with or without .json. | passed |
