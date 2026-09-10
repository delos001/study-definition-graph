# data/

What the pipeline makes. Nothing here is downloaded: the documents and standards the pipeline reads are in `inputs/`, and what its output is scored against is in `eval/`. Everything here can be regenerated from `inputs/` and the code, so nothing is committed except this file and the `.gitkeep` placeholders.

| Folder | What it holds |
| --- | --- |
| `interim/` | Intermediate outputs between pipeline stages. Empty until Phase 1. |
| `processed/` | Final pipeline outputs. Empty until Phase 1. |
