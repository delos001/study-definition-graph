# inputs/

This folder holds everything the pipeline takes in from outside the repo. Every file here was downloaded from a recorded source and is pinned to one version. Its url, size and sha256 are in `manifests/` at the repo root, so a fresh clone can restore all of it with `acquire_sources`. Nothing here is ever edited, and nothing here is committed except the READMEs and the `.gitkeep` placeholders.

That one rule, everything under `inputs/` is pinned, is what the Claude Code hook `.claude/hooks/deny_pinned_edits.py` and `repo_tools/find_unrecorded_files.py` both rely on. A new pinned source goes in a folder here and gets a manifest, and neither needs to be told.

| Folder | What it holds |
| --- | --- |
| `standards/` | Published standards the project depends on, by publisher: CDISC, ICH, and the crosswalks between them. |
| `worked_examples/` | CDISC's worked examples, one folder per study, each holding a real protocol, the spreadsheet a person filled in from it, and the USDM output generated from that spreadsheet. |
| `study_documents/` | Protocols and SAPs fetched from ClinicalTrials.gov, one folder per study, recorded in `manifests/study_documents/`. Empty until Phase 1. |

What the pipeline produces from these is in `data/`, and what its output is scored against is in `eval/`. Which file answers which question is `docs/sources_index.md`.
