# validation/ file catalog

This catalog describes every file in `validation/`, folder by folder. `README.md` in this folder gives the overview and defines the terms, and `validation_inventory.csv` lists every check.

## Top level

- `conftest.py`
  - Holds pytest's shared fixtures and configuration for this folder. pytest looks for a file with exactly this name.
  - Adds the `--validation-report` flag and the markers the checks carry: `@code`, `@objective`, `@positive`, `@negative` and `@needs_pinned`.
  - Its fixtures stage manifests and files in a temporary folder, so a staged check never touches the real `manifests/` or `inputs/`.
  - Skips a check marked `@needs_pinned` when a pinned file the check reads is not downloaded or no longer matches its manifest entry, and records the reason. A marker that names a file no manifest records makes the check error instead.
  - Writes the validation report into `reports/` when pytest is run with `--validation-report`.
- `test_validation_report.py`
  - Validates `conftest.py`, covering the validation report it writes and the skipping of checks whose pinned files are missing or changed.
- `test_console_output.py`
  - Validates `src/sdg/console_output.py`, which switches a command's printed output to UTF-8 so characters from the pinned standards, such as bullets and curly quotes, do not print as question marks on Windows.
- `validation_inventory.csv`
  - Lists every check, one row per check. `python repo_tools/build_inventory.py` generates it from the test files.
  - The pre-commit hook, `.githooks/pre-commit`, refuses a commit when it is out of date.
- `validation_inventory_dictionary.csv`
  - Defines every column of `validation_inventory.csv`, one row per column, with an example, where the value comes from and the values it may take.
- `exit_codes.csv`
  - Holds the repo-wide table of exit codes, with one row per code giving the number and the one cause it means.
  - Every Python file's header lists its exit codes with these numbers and this wording, and `repo_tools/verify_headers.py` confirms that they match.

## fixtures/

- `usdm_three_classes.yml`
  - Holds three classes copied verbatim from the pinned `dataStructure.yml`, read in place of the real model.

## sources/

- `test_acquire_sources.py`
  - Validates `src/sdg/sources/acquire_sources.py`.
- `test_fetch_file.py`
  - Validates `src/sdg/sources/fetch_file.py`.
- `test_finalize_file.py`
  - Validates `src/sdg/sources/finalize_file.py`.
- `test_fingerprint_file.py`
  - Validates `src/sdg/sources/fingerprint_file.py`.
- `test_read_manifests.py`
  - Validates `src/sdg/sources/read_manifests.py`, and confirms that every real manifest follows the rules for manifests.
- `test_verify_pinned.py`
  - Validates `src/sdg/sources/verify_pinned.py`, and holds the stability check that confirms every pinned file is unchanged.
- `test_write_manifests.py`
  - Is planned and not written yet. It will validate `src/sdg/sources/write_manifests.py`, which issue #21 tracks.

## usdm/

- `test_usdm_spec.py`
  - Validates `src/sdg/usdm/usdm_spec.py`.

## view/

- `test_read_pdf.py`
  - Validates `src/sdg/view/read_pdf.py`.
- `test_read_xlsx.py`
  - Validates `src/sdg/view/read_xlsx.py`.

## repo_tools/

- `test_build_index.py`
  - Validates `repo_tools/build_index.py`.
- `test_build_inventory.py`
  - Validates `repo_tools/build_inventory.py`.
- `test_check_api_key.py`
  - Validates `repo_tools/check_api_key.py`.
- `test_check_facts.py`
  - Validates `repo_tools/check_facts.py`.
- `test_check_neo4j.py`
  - Validates `repo_tools/check_neo4j.py`.
- `test_check_python_files.py`
  - Validates `repo_tools/check_python_files.py`.
- `test_check_sources_map.py`
  - Validates `repo_tools/check_sources_map.py`.
- `test_find_unrecorded_files.py`
  - Validates `repo_tools/find_unrecorded_files.py`.
- `test_verify_headers.py`
  - Validates `repo_tools/verify_headers.py`.

## claude_hooks/

- `test_deny_pinned_edits.py`
  - Validates `.claude/hooks/deny_pinned_edits.py`.

## reports/

- Holds one CSV file per validation run, one row per check that ran. A file is written only when pytest is run with `--validation-report`.
