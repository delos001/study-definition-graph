# Validation record: validation_report

Written by `pytest --validation-report` on 2026-09-04 17:34 Eastern Daylight Time. Design and rationale for these tests: `tests/README.md`.

| | |
| --- | --- |
| Verdict | **PASS**: pytest exit status 0 (all tests passed) |
| Counts | 6 passed, 0 failed, 0 error, 0 skipped, in 7.3 s |
| Component | `tests/test_validation_report.py` itself |
| Code commit | `91645ae` (uncommitted changes present at run time) |
| Test file | `tests/test_validation_report.py` sha256 `dda1a9686b7a7d3ab354295c04dd1e110e2e9862ec8680af2c7150f27f3b349e` |
| Fixtures | `tests/fixtures/usdm_three_classes.yml` sha256 `50f0c08ce0356a6595871e89621497d93302f2d3a5aacf8ea2cdd63303a1aaf1` |
| Pinned USDM data | https://raw.githubusercontent.com/cdisc-org/DDF-RA/aa303cb32f5d3ceecc68a16803e26720d2c1fc26/Deliverables/UML/dataStructure.yml, sha256 `6f49a407aef41a66dd40a82ad3348672a22cd8874849254d7e4f27d6275daca6`, present |
| Command | `pytest --validation-report` |
| Run by | Jason Delosh |
| When | 2026-09-04 17:34:47 Eastern Daylight Time |
| Python / pytest | 3.12.13 / 9.1.1 |
| Platform | Windows-11-10.0.26200-SP0 |

| Test | Kind | Proves | Outcome |
| --- | --- | --- | --- |
| `test_passing_run_is_recorded_as_pass` | positive | A suite whose tests all pass gets a record saying PASS with pytest exit status 0, one row per test showing its kind and what it proves, and a skipped test shown as skipped with its reason. | passed |
| `test_no_flag_writes_nothing` | positive | Without --validation-report, a run writes no record at all, so development runs leave no trace. | passed |
| `test_cleanup_failure_is_recorded_as_fail` | negative | A test whose own checks pass but whose clean-up step throws is a failed run to pytest (exit 1). The record says FAIL, and that test's row says error with 'clean-up failed', never passed. | passed |
| `test_failing_assertion_is_recorded_as_fail` | negative | A test whose checks fail gives a FAIL record with that row marked failed. | passed |
| `test_setup_failure_is_recorded_as_error` | negative | A test whose set-up step throws never runs; the record says FAIL and the row says error. | passed |
| `test_file_that_will_not_load_still_gets_a_fail_record` | negative | When a test file cannot even be loaded (a syntax error), no test runs and pytest exits 2. A record is still written, says FAIL, and says that no test outcomes were recorded, so a broken run cannot pass unnoticed by leaving no record behind. | passed |
