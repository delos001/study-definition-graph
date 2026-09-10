# manifests/

One record per set of pinned downloads: where each file came from, which version, and its fingerprint. This is what makes every download restorable, and what lets the code refuse a file that is not the one that was pinned. For which file answers which question, see `docs/sources_index.md`; that is the map for a person, this is the record for the code.

| Manifest | Describes | Lands in |
| --- | --- | --- |
| `cdisc_usdm_v4.json` | USDM v4.0, the standard the pipeline conforms to | `inputs/standards/cdisc/usdm_v4/` |
| `cdisc_biomedical_concepts.json` | The Biomedical Concepts library | `inputs/standards/cdisc/biomedical_concepts/` |
| `crosswalks.json` | Mappings from other systems into USDM | `inputs/standards/crosswalks/` |
| `ich_m11_step4.json` | ICH M11, the protocol template, at Step 4 | `inputs/standards/ich/m11_step4/` |
| `ich_e9r1.json` | ICH E9(R1), the estimand addendum | `inputs/standards/ich/e9r1/` |
| `usdm_examples.json` | CDISC's three worked examples | `inputs/worked_examples/` |
| `study_documents/<NCT>.json` | One study's documents as fetched from ClinicalTrials.gov, written by the fetch script | `inputs/study_documents/<NCT>/` |

The six top-level manifests are written by hand, once each, for a standard or a worked example whose version never moves. `study_documents/` is different in kind: it is named for the folder its records point at, `inputs/study_documents/`, so the link is read off the name. the Phase 1 fetch script writes one file there per study it downloads, and the folder grows with the corpus. They sit apart so that a hand-edited record and a machine-written one are never confused for each other, and they are committed for the same reason the rest are: `inputs/study_documents/` is gitignored, so without these records a fresh clone would not even know which studies to re-download. The shape of a study record is settled when the fetch script is built; whatever it is, every entry carries the url, the size and the sha256, so `acquire_sources` checks it the same way.

Every hand-written manifest has the same shape. At the top: the set name (matching the file name), a description, the publisher, the version, the source, the pinned commit where the source has one, the date retrieved, and the folder the files land in. Remarks that apply to one set only, a caveat or a list of what was deliberately not taken, sit under `notes`. Then `files`, one entry per file: its name, its path at the source, the url it was fetched from, where it sits locally, its format, who reads it (`read_by`: `code`, `person` or `both`), a one-sentence `role`, its size in bytes, and its sha256 fingerprint.

A pinned file keeps its publisher's file name, spaces replaced by underscores and nothing else: `name` is that name, and `local` ends in it. A file then says what it is wherever it is seen, and no download involves a naming decision. One exception, recorded under `notes` in `cdisc_biomedical_concepts.json`: a publisher's name that says `latest` is dropped, because it contradicts the pin.

A version never moves. To adopt a new version of a source, its manifest is edited deliberately and the change recorded in `DECISIONS.md`; the fetch script never updates a manifest and never overwrites a file.
