# Validation record: sources_finalize_file

Written by `pytest --validation-report` on 2026-09-10 17:48 Eastern Daylight Time. Design and rationale for these tests: `tests/README.md`.

| | |
| --- | --- |
| Verdict | **PASS**: pytest exit status 0 (all tests passed) |
| Counts | 7 passed, 0 failed, 0 error, 0 skipped, in 0.3 s |
| Component | `src/sdg/sources/finalize_file.py` |
| Code commit | `7167f97` (uncommitted changes present at run time) |
| Test file | `tests/sources/test_finalize_file.py` sha256 `5d278b3b7e4c75ddd30d391209e7e1173f6d2e2e836a31e657f60ecbbfc9cc35` |
| Fixtures | `tests/fixtures/usdm_three_classes.yml` sha256 `50f0c08ce0356a6595871e89621497d93302f2d3a5aacf8ea2cdd63303a1aaf1` |
| Pinned USDM data | https://raw.githubusercontent.com/cdisc-org/DDF-RA/aa303cb32f5d3ceecc68a16803e26720d2c1fc26/Deliverables/UML/dataStructure.yml, sha256 `6f49a407aef41a66dd40a82ad3348672a22cd8874849254d7e4f27d6275daca6`, present |
| Command | `pytest tests/sources --validation-report` |
| Run by | Jason Delosh |
| When | 2026-09-10 17:48:26 Eastern Daylight Time |
| Python / pytest | 3.12.13 / 9.1.1 |
| Platform | Windows-11-10.0.26200-SP0 |

| Test | Kind | Proves | Outcome |
| --- | --- | --- | --- |
| `test_place_renames_the_part_file_to_its_final_name` | positive | place() removes the .part suffix, hands back the final path, and leaves nothing under the temporary name. | passed |
| `test_discard_deletes_the_part_file` | positive | discard() deletes the .part file and gives back nothing. | passed |
| `test_place_refuses_to_overwrite_a_file_at_the_final_name` | negative | When a file already sits at the final name, place() raises FileExistsError naming that file and the remedy, and moves nothing: the existing file keeps its bytes and the .part file stays where it is. | passed |
| `test_place_refuses_a_missing_part_file` | negative | place() raises FileNotFoundError naming the path when the .part file does not exist. | passed |
| `test_place_refuses_a_file_that_is_not_a_part_file` | negative | place() raises ValueError naming the path when it does not end in .part, and leaves the file as it is. | passed |
| `test_discard_refuses_a_missing_part_file` | negative | discard() raises FileNotFoundError naming the path when the .part file does not exist. | passed |
| `test_discard_refuses_a_file_that_is_not_a_part_file_and_keeps_it` | negative | discard() raises ValueError for a path that does not end in .part and does not delete it, so a pinned file can never be discarded by mistake. | passed |
