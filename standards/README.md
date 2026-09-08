# standards/

Published standards the project depends on, pinned to one version each and never edited. The pipeline reads some of these files directly (the USDM model, its legal values, its conformance rules); a person reads the rest. Which is which is recorded per file in the manifests.

Nothing here is study data. Real protocols and what the pipeline makes from them live in `data/`. Where each file came from and its fingerprint is recorded in `manifests/` at the repo root; every file here is restorable from those records.

| Folder | What it holds |
| --- | --- |
| `cdisc/` | CDISC standards: USDM v4 and the Biomedical Concepts library. |
| `ich/` | ICH guidelines: M11 (the protocol template) and E9(R1) (estimands). |
| `crosswalks/` | Mappings from other systems into USDM, whoever wrote them. |

Files are grouped by publisher, one folder per standard whatever its file count. Versions appear in the folder name (`usdm_v4`, `m11_step4`, `e9r1`) because two versions of a standard can plausibly be held at once. Every file keeps its publisher's file name, spaces replaced by underscores and nothing else, so a file names itself the way its source does.
