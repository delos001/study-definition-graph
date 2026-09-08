# manifests/

One record per set of pinned downloads: where each file came from, which version, and its fingerprint. This is what makes every download restorable, and what lets the code refuse a file that is not the one that was pinned. For which file answers which question, see `docs/sources_index.md`; that is the map for a person, this is the record for the code.

| Manifest | Describes | Lands in |
| --- | --- | --- |
| `cdisc_usdm_v4.json` | USDM v4.0, the standard the pipeline conforms to | `standards/cdisc/usdm_v4/` |
| `cdisc_biomedical_concepts.json` | The Biomedical Concepts library | `standards/cdisc/biomedical_concepts/` |
| `crosswalks.json` | Mappings from other systems into USDM | `standards/crosswalks/` |
| `ich_m11_step4.json` | ICH M11, the protocol template, at Step 4 | `standards/ich/m11_step4/` |
| `ich_e9r1.json` | ICH E9(R1), the estimand addendum | `standards/ich/` |
| `usdm_examples.json` | CDISC's three worked examples | `data/usdm_examples/` |

Every manifest has the same shape. At the top: the set name (matching the file name), a description, the publisher, the version, the source, the pinned commit where the source has one, the date retrieved, and the folder the files land in. Remarks that apply to one set only, a caveat or a list of what was deliberately not taken, sit under `notes`. Then `files`, one entry per file: its name, its path at the source, the url it was fetched from, where it sits locally, its format, who reads it (`read_by`: `code`, `person` or `both`), a one-sentence `role`, its size in bytes, and its sha256 fingerprint.

A version never moves. To adopt a new version of a source, its manifest is edited deliberately and the change recorded in `DECISIONS.md`; the fetch script never updates a manifest and never overwrites a file.
