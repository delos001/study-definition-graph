# src/sdg/sources/

This folder gets and keeps the pipeline's inputs. It holds the workflows, each a sequence of the steps below, and the steps, which do one thing each and are shared.

## Workflows

| File | What it does |
| --- | --- |
| `acquire_sources.py` | Fetches every recorded file not yet on disk, and confirms every file already on disk still matches its entry. Run as `acquire_sources`. |
| `verify_pinned.py` | Hands a pipeline stage one pinned file after proving it is the recorded one. It is built from the steps below. |
| `update_sources.py` | Moves a source to a new version: fetch, fingerprint, write its entry. Not written yet; issue #18. |

## Steps

| File | What it does |
| --- | --- |
| `read_manifests.py` | Reads the manifests: which exist, which entry describes a file, what an entry says. |
| `fetch_file.py` | Downloads one url to one destination, under a temporary name. |
| `fingerprint_file.py` | Measures one file, size and sha256, and says whether it matches an entry. |
| `finalize_file.py` | Brings a download to its final state: placed under its final name, or discarded. |
| `write_manifests.py` | Writes or updates one entry. Header drafted; code waits for its first user. |
