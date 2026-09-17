# Sources

Which pinned file answers which question, and how to open it. Each group below is one folder under `inputs/`. Where a file came from and its fingerprint are in `manifests/`, one file per group.

The reading commands run from the repo root in the `sdg` environment. `read_pdf` opens only the documents listed in `src/sdg/view/lookup_documents.yml`, which also says which documents belong there. `read_xlsx` finds any workbook under `inputs/` by part of its name.

---

## CDISC USDM v4.0

- version: USDM 4.0, released 2025-06-03
- location: inputs/standards/cdisc/usdm_v4/

### Document: dataDictionary.MD
- purpose: Defines every class and attribute in the model in plain words.
- commit: aa303cb

| Question | How to Read |
| --- | --- |
| What does a class or attribute mean? | Search the file for the term. |
| Which allowed-value list does a coded field use? | Search the file for the attribute. Its row names the list. |

### Document: dataStructure.yml
- purpose: Says what each attribute points at and how many values it may hold.
- commit: aa303cb

| Question | How to Read |
| --- | --- |
| Which classes exist? | `usdm_spec --list-classes` |
| What does an attribute point at? | `usdm_spec --attributes <class>` |

### Document: USDM-IG.pdf
- purpose: The implementation guide. Shows how the model applies to the content of a real protocol.
- commit: aa303cb

| Question | How to Read |
| --- | --- |
| How does a piece of protocol content map into the model? | `read_pdf <section>`, with `read_pdf --list` for the section numbers. What has already been read, and what it established, is in [standards_read_record.md](standards_read_record.md). |

### Document: USDM_CT.xlsx
- purpose: The allowed values for every coded field.
- commit: aa303cb

| Question | How to Read |
| --- | --- |
| Which values are legal for a coded field? | `read_xlsx USDM_CT --sheet "DDF valid value sets"` |

### Document: USDM_CORE_Rules.xlsx
- purpose: The conformance rules a USDM document is checked against. Covers v3.0 and v4.0 together; column F marks the rules that apply to v4.0.
- commit: aa303cb

| Question | How to Read |
| --- | --- |
| Which rules does a document have to satisfy? | `read_xlsx CORE_Rules --sheet "Version 3.0 and 4.0 CORE rules"` |

### Document: DDF_USDM_Model_Informative.pdf
- purpose: A one-page picture of the whole model. It leaves some classes out, so a class missing here may still exist in the model.
- commit: aa303cb

| Question | How to Read |
| --- | --- |
| Where does a class sit in the model? | `read_pdf --doc model-diagram --find "<class>"` |

### Document: UML_DELTA_3-0-0_4-0-0.csv
- purpose: Every change from v3.0 to v4.0, one row each. Needed when reading material written against v3.
- commit: aa303cb

| Question | How to Read |
| --- | --- |
| What changed on a class between v3.0 and v4.0? | Search the file for the class name. |

### Document: uml/*.png
- purpose: The class diagrams, one image per subject area.
- commit: aa303cb

| Question | How to Read |
| --- | --- |
| How do the classes in one area relate? | Open the image for that area in an image viewer. |

### Document: uml/USDM_UML.xmi
- purpose: The master model. The machine-readable files above are generated from it.
- commit: aa303cb

| Question | How to Read |
| --- | --- |
| None. | Not readable by hand. Use dataDictionary.MD or dataStructure.yml instead. |

### Document: USDM_API.json and USDM_API.yaml
- purpose: The shape of a USDM data file, in two formats. Holds no definitions, so it cannot answer what anything means.
- commit: aa303cb

| Question | How to Read |
| --- | --- |
| What does a USDM data file look like? | Open the file. |

---

## CDISC worked examples

- version: Published alongside USDM 4.0
- location: inputs/worked_examples/<study>/
- studies: Alexion_NCT04573309_Wilsons, EliLilly_NCT03421379_Diabetes, CDISC_Pilot

Each study is one real protocol in three forms: the protocol as published, the spreadsheet a person filled in to map it into USDM, and the USDM data file generated from that spreadsheet.

### Document: <study>.pdf
- purpose: The protocol as published.
- commit: aa303cb

| Question | How to Read |
| --- | --- |
| What does a real protocol look like? | Open the file. These are not in `read_pdf`'s list of lookup documents. |

### Document: <study>.xlsx
- purpose: The spreadsheet a person filled in to map the protocol into USDM, one sheet per part of the model. The mainTimeline sheet is the Schedule of Activities.
- commit: aa303cb

| Question | How to Read |
| --- | --- |
| How did a person decide the mapping for one part of the model? | `read_xlsx <study> --sheet <sheet> --format records` |
| Where does a term appear across every study? | `read_xlsx --all --find "<term>"` |

### Document: <study>.json
- purpose: The finished USDM data file, generated from the spreadsheet.
- commit: aa303cb

| Question | How to Read |
| --- | --- |
| What did the protocol become in USDM? | Open the file. |

---

## CDISC Biomedical Concepts

- version: 2026-07-14, the newest package release date in the export. The export is rolling, so the copy is fixed by the pinned commit.
- location: inputs/standards/cdisc/biomedical_concepts_2026-07-14/

A Biomedical Concept defines one clinical idea, such as a blood pressure measurement, once, so that data standards can refer to it instead of redefining it. In USDM an Activity refers to a Biomedical Concept by its ID. The CDISC Library API for these is members-only, so the files come from the public repository export.

### Document: cdisc_biomedical_concepts.xlsx
- purpose: The full list of Biomedical Concepts, one row per concept parameter, with a Logical Observation Identifiers Names and Codes (LOINC) code, the standard vocabulary for laboratory and clinical observations, where the concept is a measurement.
- commit: 031429b

| Question | How to Read |
| --- | --- |
| What standardized concept does an activity measure? | `read_xlsx cdisc_biomedical_concepts --sheet "Biomedical Concepts"` |

### Document: BC_Curation_Principles_and_Completion_GLs.xlsx
- purpose: The field dictionary for the list above. Says what each column means and how it was filled in.
- commit: 031429b

| Question | How to Read |
| --- | --- |
| What does a column in the concept list mean? | `read_xlsx BC_Curation_Principles_and_Completion_GLs` |

### Document: BC_Overview_Training.pdf
- purpose: CDISC's own introduction to what a Biomedical Concept is.
- commit: 031429b

| Question | How to Read |
| --- | --- |
| What is a Biomedical Concept? | Open the file. It is not in `read_pdf`'s list of lookup documents. |

---

## Crosswalks into USDM

- version: Published alongside USDM 4.0
- location: inputs/standards/crosswalks/

Each crosswalk maps another standard's fields onto USDM. Both run into USDM, not out of it.

### Document: ct-gov_mapping.xlsx
- purpose: Maps ClinicalTrials.gov registry fields onto USDM, one sheet per topic.
- commit: aa303cb

| Question | How to Read |
| --- | --- |
| Where does a registry field land in USDM? | `read_xlsx ct-gov_mapping` to list the sheets, then `--sheet <topic>`. |

### Document: m11_mapping.xlsx
- purpose: Maps the ICH M11 protocol template's elements onto USDM.
- commit: aa303cb

| Question | How to Read |
| --- | --- |
| Where does an M11 element land in USDM? | `read_xlsx m11_mapping --sheet Mapping` |

---

## ICH M11 protocol template

- version: Step 4, adopted 2025-11-19
- location: inputs/standards/ich/m11_step4/

The M11 documents have no bookmarks, so `read_pdf` reaches them only by search term or page range, never by section number.

### Document: ICH_Step4_M11_Final_Template_2025_1119.pdf
- purpose: The protocol template itself: the sections a protocol has and what goes in each.
- commit: none; ICH publishes the file at a fixed web address with no version control, so the pin is its fingerprint and the date retrieved

| Question | How to Read |
| --- | --- |
| What goes in a given protocol section? | `read_pdf --doc m11-template --find "<heading>"` |

### Document: ICH_Step4_M11_Final_TechnicalSpecification_2025_1119.pdf
- purpose: Defines each protocol data element, with its data type, how many values it takes, and whether it is required.
- commit: none; ICH publishes the file at a fixed web address with no version control, so the pin is its fingerprint and the date retrieved

| Question | How to Read |
| --- | --- |
| What is this protocol data element, and is it required? | `read_pdf --doc m11-techspec --find "<term>"` |

### Document: ICH_Step4_M11_Final_Guideline_2025_1119.pdf
- purpose: The short guideline that sets M11's scope. The substance is in the other two documents.
- commit: none; ICH publishes the file at a fixed web address with no version control, so the pin is its fingerprint and the date retrieved

| Question | How to Read |
| --- | --- |
| What does M11 cover? | `read_pdf --doc m11-guideline --pages 1-6` |

---

## ICH E9(R1) estimands

- version: Step 4, dated 2019-12-03
- location: inputs/standards/ich/e9r1/

### Document: E9-R1_Step4_Guideline_2019_1203.pdf
- purpose: Defines what an estimand is and what its parts are.
- commit: none; ICH publishes the file at a fixed web address with no version control, so the pin is its fingerprint and the date retrieved

| Question | How to Read |
| --- | --- |
| What is an estimand and what are its parts? | `read_pdf --doc e9r1 A.3.3` |

---

## Not held

Resources that were looked at and not pinned. Listed so the same question is not asked twice.

### Used live, not pinned

| Resource | Where | Why not pinned |
| --- | --- | --- |
| cdisc-rules-engine | github.com/cdisc-org | The CDISC Open Rules Engine (CORE), the conformance engine. It is a tool rather than data, so if it is adopted it will be pinned by version like the other software, not fingerprinted. Whether it can be used without a membership is issue #35. |
| ClinicalTrials.gov API v2 | live | Phase 1 fetches protocols and SAPs from it. The documents it returns are pinned under `inputs/study_documents/`; the API responses are not kept. |

### Reviewed and not taken

| Resource | Why not |
| --- | --- |
| cdisc-open-rules | A different rule family with its own ID space. Not USDM. |
| usdm package on PyPI | Needs a CDISC Library API key our subscription does not have. Its workbook format is what produced the worked examples, so its documentation is still worth reading. |
| ctis_mapping.xlsx | Maps to the European Union's Clinical Trials Information System (CTIS). Out of scope. |
| cpt_mapping.xlsx | Maps from an authoring template our source protocols do not use. |
| sdtm_mapping.xlsx | Maps USDM out to the Study Data Tabulation Model (SDTM), the CDISC standard for submission datasets. Downstream of this project and the opposite direction. |
| DDF-RA device and observational examples | Synthetic test data, not from a real protocol. |
| DDF-RA change and delta files for older releases | Only matter if the pin moves, and it does not. The one v3.0-to-v4.0 delta is held because it helps read v3-era material. |
| USDM_UML.png | The whole-model diagram as an image. The informative PDF is the same picture with searchable text. |
| DDF-RA editor files and how-tos | CDISC's own authoring toolchain. |
| CORE test data template | Its question, what CORE actually checks, is better answered by the rules below, which are written in JSONata, a query language for JSON. |
| COSMoS SDTM dataset specializations | Map concepts to SDTM variables. COSMoS (Conceptual and Operational Standards Metadata Services) is the CDISC project that publishes the Biomedical Concepts. Downstream of this project. |
| COSMoS concept hierarchy file | Already present as sheets inside the pinned concepts workbook. |
| COSMoS CRF specializations | Marked draft by CDISC, and on the side of data collection forms, the Clinical Data Acquisition Standards Harmonization (CDASH), rather than study definition. |
| COSMoS governance documents | How CDISC authors concepts. This project uses concepts, it does not author them. |
| LOINC database | The concepts workbook already carries LOINC codes inline, and the database needs a licence. |

### Looked at, not yet evaluated

| Resource | Where | What it is |
| --- | --- | --- |
| cdisc-jsonata-rules | github.com/cdisc-org | The USDM conformance rules that actually run, as JSONata with test fixtures. Pull single rules at point of use rather than the whole repository. |
| usdm_api | github.com/cdisc-org | A DDF emulation with a Dockerfile, so a conformance endpoint may be runnable locally. |
