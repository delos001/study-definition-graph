# src/sdg/sources/

This folder gets and keeps the pipeline's inputs. It holds the workflows, each a sequence of the steps below, and the steps, which do one thing each and are shared.

## Workflows

| File | What it does |
| --- | --- |
| `acquire_sources.py` | Fetches every recorded file not yet on disk, and confirms every file already on disk still matches its entry. Run as `acquire_sources`. |
| `verify_pinned.py` | Hands a pipeline stage one pinned file after proving it is the recorded one. It is built from the steps below. |
| `update_sources.py` | Moves a source to a new version: fetch, fingerprint, write its entry. Not written yet; issue #18. |
| `find_ctgov_studies.py` | Finds the studies on ClinicalTrials.gov that pass the filters in `ctgov_study_filters.yml`, and saves a record of each search. Run as `find_ctgov_studies`. It is built from the four ClinicalTrials.gov steps below. |
| `download_ctgov_study_documents.py` | Downloads the protocol and SAP of each study named on the command line into the review folder set in `.env`. With `--accept`, it pins them under `inputs/study_documents/` and records them in `manifests/study_documents/`. Run as `download_ctgov_study_documents`. |
| `ctgov_study_filters.yml` | The query `find_ctgov_studies.py` sends to the ClinicalTrials.gov API, and the rules it applies to the reply that the API cannot apply itself. |

## Steps

| File | What it does |
| --- | --- |
| `read_manifests.py` | Reads the manifests: which exist, which entry describes a file, what an entry says. |
| `fetch_file.py` | Downloads one url to one destination, under a temporary name. |
| `fingerprint_file.py` | Measures one file, size and sha256, and says whether it matches an entry. |
| `finalize_file.py` | Brings a download to its final state: placed under its final name, or discarded. |
| `write_manifests.py` | Writes one file's entry into a manifest, creating the manifest when it does not exist. |
| `fetch_ctgov_study_records.py` | Sends a query to the ClinicalTrials.gov API and collects the study record of every match. |
| `parse_ctgov_study_records.py` | Pulls single pieces out of a study record, such as its documents or its countries with sites. |
| `narrow_ctgov_study_records.py` | Reads `ctgov_study_filters.yml` and keeps the study records that pass its additional filters. |
| `save_ctgov_search_records.py` | Writes the record of one search to `searches/ctgov/`. |
