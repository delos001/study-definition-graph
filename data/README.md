# data/

This folder contains pipeline related output documents.

Nothing here is downloaded: the documents and standards read by the pipeline are in `inputs/`, and information used to score the pipeline's output is in `eval/`.

Everything here can be regenerated from `inputs/` and the code, so nothing is committed except this file and the `.gitkeep` placeholders.

| Folder | What it holds |
| --- | --- |
| `interim/` | Intermediate outputs between pipeline stages. Empty until Phase 1. |
| `processed/` | Final pipeline outputs. Empty until Phase 1. |
