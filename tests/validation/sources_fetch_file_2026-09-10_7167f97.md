# Validation record: sources_fetch_file

Written by `pytest --validation-report` on 2026-09-10 17:48 Eastern Daylight Time. Design and rationale for these tests: `tests/README.md`.

| | |
| --- | --- |
| Verdict | **PASS**: pytest exit status 0 (all tests passed) |
| Counts | 8 passed, 0 failed, 0 error, 0 skipped, in 0.3 s |
| Component | `src/sdg/sources/fetch_file.py` |
| Code commit | `7167f97` (uncommitted changes present at run time) |
| Test file | `tests/sources/test_fetch_file.py` sha256 `b03a957425fd5cc030c5d17bbcbb6b61b1a56966bb821a997c2c3827c02540d1` |
| Fixtures | `tests/fixtures/usdm_three_classes.yml` sha256 `50f0c08ce0356a6595871e89621497d93302f2d3a5aacf8ea2cdd63303a1aaf1` |
| Pinned USDM data | https://raw.githubusercontent.com/cdisc-org/DDF-RA/aa303cb32f5d3ceecc68a16803e26720d2c1fc26/Deliverables/UML/dataStructure.yml, sha256 `6f49a407aef41a66dd40a82ad3348672a22cd8874849254d7e4f27d6275daca6`, present |
| Command | `pytest tests/sources --validation-report` |
| Run by | Jason Delosh |
| When | 2026-09-10 17:48:26 Eastern Daylight Time |
| Python / pytest | 3.12.13 / 9.1.1 |
| Platform | Windows-11-10.0.26200-SP0 |

| Test | Kind | Proves | Outcome |
| --- | --- | --- | --- |
| `test_download_lands_under_the_part_name` | positive | The bytes the server sends are written to <destination>.part, that path is handed back, and nothing appears under the final name. | passed |
| `test_destination_folders_are_created` | positive | A destination several folders deep works on an empty repo, because the folders on the way are created. | passed |
| `test_leftover_part_file_is_overwritten` | positive | A .part file left by an earlier run is replaced by the new download, not added to, because a .part file is by definition unfinished. | passed |
| `test_request_asks_to_follow_redirects_and_sets_the_timeout` | positive | fetch() asks the HTTP library to follow a redirect and to give up after the module's timeout, which is how a file the server has moved is still found. | passed |
| `test_partial_path_is_the_destination_plus_part` | positive | partial_path() adds .part to the file name and keeps the folder, so the naming rule lives in one place. | passed |
| `test_server_error_is_a_fetch_error` | negative | A server that answers with an error status raises FetchError naming the url and the status, and leaves no .part file. | passed |
| `test_unreachable_server_is_a_fetch_error` | negative | A connection that cannot be made raises FetchError naming the url and the cause, and leaves no .part file. | passed |
| `test_transfer_that_stops_part_way_removes_the_part_file` | negative | A transfer that breaks after the first chunk raises FetchError, and the half-written .part file is removed so it cannot be mistaken for a finished download. | passed |
