# Validation record: sources_fingerprint_file

Written by `pytest --validation-report` on 2026-09-10 17:48 Eastern Daylight Time. Design and rationale for these tests: `tests/README.md`.

| | |
| --- | --- |
| Verdict | **PASS**: pytest exit status 0 (all tests passed) |
| Counts | 7 passed, 0 failed, 0 error, 0 skipped, in 0.3 s |
| Component | `src/sdg/sources/fingerprint_file.py` |
| Code commit | `7167f97` (uncommitted changes present at run time) |
| Test file | `tests/sources/test_fingerprint_file.py` sha256 `7b7510a0246ba9ec1d8f7f8747a6dc0d4a6c44f316b6c27d17968c98dcde5f5e` |
| Fixtures | `tests/fixtures/usdm_three_classes.yml` sha256 `50f0c08ce0356a6595871e89621497d93302f2d3a5aacf8ea2cdd63303a1aaf1` |
| Pinned USDM data | https://raw.githubusercontent.com/cdisc-org/DDF-RA/aa303cb32f5d3ceecc68a16803e26720d2c1fc26/Deliverables/UML/dataStructure.yml, sha256 `6f49a407aef41a66dd40a82ad3348672a22cd8874849254d7e4f27d6275daca6`, present |
| Command | `pytest tests/sources --validation-report` |
| Run by | Jason Delosh |
| When | 2026-09-10 17:48:26 Eastern Daylight Time |
| Python / pytest | 3.12.13 / 9.1.1 |
| Platform | Windows-11-10.0.26200-SP0 |

| Test | Kind | Proves | Outcome |
| --- | --- | --- | --- |
| `test_fingerprint_measures_size_and_sha256` | positive | fingerprint() gives back one object holding two values, the size in bytes and the sha256, and both agree with an independent measurement. | passed |
| `test_file_larger_than_one_piece_hashes_correctly` | positive | A file bigger than the piece size the module reads in is hashed the same as a whole-file hash, so reading in pieces loses nothing. | passed |
| `test_matching_file_compares_as_matched` | positive | A file whose size and sha256 equal its entry's compares as matched. | passed |
| `test_size_difference_is_reported_first_and_hash_is_not_computed` | negative | A file whose size differs from its entry is reported as a size difference showing both numbers, and the sha256 is not computed at all. | passed |
| `test_same_size_different_content_is_reported_as_sha256` | negative | A file with the right size but different bytes is reported as a sha256 difference, showing the start of both values. | passed |
| `test_missing_file_raises_file_not_found` | negative | Both functions raise FileNotFoundError naming the path for a path that does not exist. | passed |
| `test_folder_is_refused_like_a_missing_file` | negative | A folder at the path is refused with FileNotFoundError naming the path, because only a file can be measured. | passed |
