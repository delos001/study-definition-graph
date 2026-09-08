# data/

Study documents and what the pipeline makes from them. This is the only folder that holds data in the ordinary sense; the standards the pipeline conforms to are in `standards/`, and what output is scored against is in `eval/`.

| Folder | What it holds |
| --- | --- |
| `raw/` | Study documents as fetched, one folder per study, never edited. Each study's download is recorded in `manifests/data_raw/`, so the folder can be rebuilt from a fresh clone. Empty until Phase 1. |
| `usdm_examples/` | CDISC's three worked examples: a real protocol, the spreadsheet a human filled in from it, and the USDM output generated from that spreadsheet. Downloaded and pinned; restorable from `manifests/`. Used as answer keys by `eval/`. |
| `interim/` | Intermediate outputs between pipeline stages. Empty until Phase 1. |
| `processed/` | Final pipeline outputs. Empty until Phase 1. |

Nothing under here is committed except this file; everything is either downloaded from a recorded source or produced by the pipeline.
