# Sources

Where to look. Two sections: what we hold, and what exists that we do not hold.

Skim the first section at session start to see what has and has not been read. The second section is consulted only when a question comes up; it is a pointer list, not context. For how these standards relate to each other, see [standards_map.html](standards_map.html).

Provenance and checksums live in `data/manifests/`, one file per set. This file answers "which file holds my answer"; the manifests answer "is this file authentic". Different questions, different files.

---

## What we hold

`data/` is gitignored. Every file below is restorable from its manifest.

### CDISC USDM v4.0

Pinned to DDF-RA commit `aa303cb`. Manifest: `raw_usdm_v4.json`.

| Question | File | How to read it | Read? |
| --- | --- | --- | --- |
| What does a class or attribute **mean**? | `usdm_v4/uml/dataDictionary.MD` | Grep it. One row per attribute: definition, cardinality, NCI code, codelist ref. | partly |
| What does an ID **point at**? | `usdm_v4/uml/dataStructure.yml` | Load with pyyaml. Gives target class, cardinality, `Ref` vs `Value`. | partly |
| What is the model itself? | `usdm_v4/uml/USDM_UML.xmi` | The hand-authored master. Everything else machine-readable is generated from it. Not directly readable; go to the two files above. | no |
| How does this map to real protocol content? | `usdm_v4/USDM-IG.pdf` | `python scripts/read_pdf.py <section>`. Section map and read ledger: [usdm_ig_map.md](usdm_ig_map.md). | 3 of 54 sections |
| What does the payload look like? | `usdm_v4/USDM_API.json` | Shape only. **No definitions, no cardinalities, no relationship targets.** Never answer a meaning question from this file. | n/a |
| Which values are legal for a coded field? | `usdm_v4/USDM_CT.xlsx` | `python scripts/read_xlsx.py USDM_CT --sheet "DDF valid value sets"` | no |
| Is a document conformant? | `usdm_v4/USDM_CORE_Rules.xlsx` | `python scripts/read_xlsx.py CORE_Rules --sheet "Version 3.0 and 4.0 CORE rules"`. 259 rules. | no |
| What does the whole model look like at once? | `usdm_v4/DDF_USDM_Model_Informative.pdf` | `python scripts/read_pdf.py --doc model-diagram --find "<class>"`. One page, vector, text extracts. **Informative, not complete**: it omits classes the data dictionary has, so never treat an absence here as an absence from the model. | no |
| What changed between v3.0 and v4.0? | `usdm_v4/uml/UML_DELTA_3-0-0_4-0-0.csv` | Grep it. 1302 rows: class, Added/Deleted/Modified, attribute, old value. Needed to read v3.1x-era material such as the crosswalks and the published prior art. | no |
| What does a class diagram look like? | `usdm_v4/uml/UML_Views/*.png` | 14 images. Cannot be grepped or extracted; must be viewed. **None has been opened.** | no |

### CDISC worked examples

Three real protocols, each in three forms. Manifest: `raw_usdm_examples.json`.

| Question | File | How to read it |
| --- | --- | --- |
| What does a real protocol look like? | `usdm_examples/<study>/*.pdf` | `python scripts/read_pdf.py --pages N-M` will not reach these; they are not registered. Open directly. |
| How did a human decide the mapping? | `usdm_examples/<study>/*.xlsx` | `python scripts/read_xlsx.py Alexion --sheet mainTimeline --format records`. 25 to 35 sheets each. `mainTimeline` is that study's Schedule of Activities, 58 columns wide. |
| What did it become? | `usdm_examples/<study>/*.json` | The finished USDM output, generated from the spreadsheet. |

Studies: `Alexion_NCT04573309_Wilsons`, `EliLilly_NCT03421379_Diabetes`, `CDISC_Pilot`. Search across all workbooks with `python scripts/read_xlsx.py --all --find "<term>"`.

### Crosswalks between standards

Manifest: `raw_usdm_mappings.json`. Both run **into** USDM, verified from their column headers.

| Question | File |
| --- | --- |
| How do ClinicalTrials.gov registry fields map to USDM? | `usdm_mappings/ct-gov_mapping.xlsx`, 6 sheets by topic |
| How do ICH M11 fields map to USDM? | `usdm_mappings/m11_mapping.xlsx`, one `Mapping` sheet, 325 rows |

### ICH M11 CeSHarP, Step 4

Adopted 2025-11-19. Manifest: `raw_ich_m11.json`. **No embedded bookmarks**, so these answer only to `--find` and `--pages`, never to a section number.

| Question | File | How to read it | Read? |
| --- | --- | --- | --- |
| What sections does a protocol have, and what goes in each? | `ich_m11/ICH_M11_Template.pdf` | `python scripts/read_pdf.py --doc m11-template --find "<heading>"` | no |
| What is this protocol data element, and is it required? | `ich_m11/ICH_M11_TechnicalSpecification.pdf` | `python scripts/read_pdf.py --doc m11-techspec --find "<term>"`. 186 elements, each with definition, data type, cardinality, conformance. | no |
| What is M11's scope? | `ich_m11/ICH_M11_Guideline.pdf` | `python scripts/read_pdf.py --doc m11-guideline --pages 1-6`. Short; the substance is in the other two. | no |

### ICH E9(R1)

Manifest: `raw_ich_e9r1.json`.

| Question | File | How to read it | Read? |
| --- | --- | --- | --- |
| What is an estimand and what are its parts? | `ich_e9r1/ICH_E9R1_Addendum.pdf` | `python scripts/read_pdf.py --doc e9r1 A.3.3` | §A.3.3 only |

---

## What exists that we do not hold

Only resources actually reviewed appear here. Each carries a decision, not a description. Anything named but unchecked is not an entry.

### In use, or scheduled

| Resource | Where | State |
| --- | --- | --- |
| `cdisc-org/cdisc-rules-engine` | GitHub | The CORE engine. Phase 0 installs and runs it. Version-pin as tooling, not as hashed data. |
| ClinicalTrials.gov API v2 | live | Phase 1 fetches protocols and SAPs from it. Called live by decision; no snapshot worth keeping. |

### Reviewed and not taken

Recorded so these do not resurface.

| Resource | Why not |
| --- | --- |
| `cdisc-org/cdisc-open-rules` | `CORE-000NNN` YAML rules, a different ID space from the `DDF000NN` rules that are ours. Not USDM. Reviewed 2026-08-18. |
| `cdisc-org/usdm` (PyPI `usdm`) | Requires `CDISC_API_KEY` for CDISC Library lookups; our subscription tier returns "Members-only content". Its `usdm_excel` importer is what generated the three worked examples, so its documented workbook format is worth reading even though the package cannot run here. Reviewed 2026-08-18. |
| `ctis_mapping.xlsx` | EU CTIS registry submission. Out of scope. |
| `cpt_mapping.xlsx` | TransCelerate authoring template. Our source protocols do not use it. |
| `sdtm_mapping.xlsx` | USDM to SDTM. Downstream of this project and runs the opposite direction. |
| `Documents/Examples/Devices`, `Observational` | Synthetic test data, not derived from a real protocol, per CDISC's own examples readme. |
| DDF-RA `*_DELTA_*` and `*_Changes` files, except the v3-to-v4 UML delta | Version-migration history between older releases. Only matters if the pin moves, and it does not. ~40 files. The one exception, `UML_DELTA_3-0-0_4-0-0.csv`, is held: it is not about moving the pin but about reading v3.1x-era material correctly, which the crosswalks and the cited prior art both are. Reviewed 2026-08-18. |
| `Deliverables/UML/USDM_UML.png` | The whole-model class diagram as an image, 1.1 MB. Superseded by `DDF_USDM_Model_Informative.pdf`, which is the same view in vector form with extractable text, so it can be searched rather than only looked at. Decided 2026-08-18. |
| `USDM_UML.qea`, `UML_EA.DTD`, `*.graffle`, `HowTos/` | Editor project files and authoring tutorials for CDISC's own toolchain. Reviewed 2026-08-18. |
| `Documents/CORE Test Data Template/` | Was justified as the route into "what does CORE actually check". That question is now largely answered by the JSONata rules below, so the case has weakened. Reviewed 2026-08-18. |

### Unassessed

Named, located, and looked at, but not evaluated for use.

| Resource | Where | What was observed, and when |
| --- | --- | --- |
| `cdisc-org/cdisc-jsonata-rules` | GitHub | The USDM conformance rules that actually run: 93 of the 210 v4-applicable ones, as JSONata with test fixtures. Do not bulk-pin (8.5 MB, unlicensed); pull single rules at point of use. 2026-08-18. |
| `cdisc-org/usdm_api` | GitHub | A DDF emulation with a Dockerfile, so a conformance endpoint may be runnable locally rather than needing a public one. 2026-08-18. |
