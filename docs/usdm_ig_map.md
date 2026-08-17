# USDM-IG v4.0 section map

Routing table for `data/raw/usdm_v4/USDM-IG.pdf` (119 pages, pinned commit
`aa303cb`). Purpose: find the right section without reading the whole guide.

Read a section with:

```powershell
python scripts/read_ig.py 4.23
python scripts/read_ig.py 6.4 --raw   # skip header/footer stripping
```

Page ranges come from the PDF's own bookmarks. Where several sections start on
the same page the ranges overlap; that is a limit of the source bookmarks, not
an error. Narrow by reading and trimming.

| Section | Pages |
| --- | --- |
| 1 Introduction | 4-5 |
|   1.1 Purpose | 4-5 |
|   1.2 Organization of this Document | 4-5 |
|   1.3 How to Read this Document | 4-5 |
| 2 Fundamentals of the USDM | 6-8 |
| 3 Relationship to Other Standards and Formats | 9-10 |
|   3.1 Relationship to Other CDISC Standards | 9-10 |
|   3.2 Relationship to Other Standards | 11 |
| 4 USDM Features | 12 |
|   4.1 Overview | 12 |
|   4.2 Principles | 12 |
|   4.3 Naming Conventions | 13 |
|   4.4 Internal Identifiers Within the Model | 14-15 |
|   4.5 Controlled Terminology | 14-15 |
|   4.6 Study, Protocols, and Amendments | 14-15 |
|   4.7 Study Identifiers and Titles | 16-17 |
|   4.8 Study Design | 18-19 |
|   4.9 Study Roles and Organizations | 20-22 |
|   4.10 Arms and Epochs | 23-24 |
|   4.11 Activities | 23-24 |
|   4.12 Procedures | 25 |
|   4.13 Biomedical Concepts | 25 |
|   4.14 Study Timing | 26-31 |
|   4.15 Study Interventions | 32-33 |
|   4.16 Study Objectives and Endpoints | 34 |
|   4.17 Study Estimands | 35-37 |
|   4.18 Populations, Cohorts, and Eligibility Criteria | 35-37 |
|   4.19 Abbreviations | 38-39 |
|   4.20 Unstructured Content | 40-41 |
|   4.21 Syntax Templates | 42-43 |
|   4.22 XHTML Attributes | 44-50 |
|   4.23 Addressing Footnotes | 44-50 |
|   4.24 Complex Study Designs | 51-56 |
|   4.25 Schedule of Activity Views | 57-60 |
| 5 USDM Data Dictionary | 61-98 |
| 6 USDM API | 99 |
|   6.1 General | 99 |
|   6.2 Serialization | 99 |
|   6.3 Additional Attributes and Required Content | 99 |
|   6.4 Extension Mechanism | 100-107 |
| 7 Mapping to Other Standards and Formats | 108 |
|   7.1 Creation of SDTM Trial Design Domains | 108 |
|   7.2 Informing ClinicalTrials.gov Registry | 108 |
|   7.3 Informing CTIS Registry | 109 |
|   7.4 Creation of M11 documents | 109 |
|   7.5 Use of USDM for Populating Protocol Content | 109 |
| Appendices | 110 |
|   Appendix A: USDM Team | 110 |
|   Appendix B: Glossary and Abbreviations | 111-112 |
|   Appendix C: References | 113 |
|   Appendix D: Revision History | 114-118 |
|   Appendix E: Representations and Warranties, Limitations of Liability, and Disclaimers | 119 |

## Read and verified

Sections confirmed read in a prior session. Anything not listed here has **not**
been consulted, and claims about it are inference until it is.

| Section | Pages | What it established |
| --- | --- | --- |
| 2 Fundamentals of the USDM | 6-8 | USDM is 5 official standards, not 1: class diagram, API spec, Controlled Terminology, this IG, Conformance Rule Specifications. `USDM_API.json` is one of the five and the one carrying no semantics. v4.0 is aligned to ICH M11 CeSHarP. Publicly available protocols have been mapped to USDM and published as "USDM GitHub Examples" (p.8). |
| 3.1 Relationship to Other CDISC Standards | 9-10 | USDM draws on BRIDG, supersedes PRM, and feeds SDTM Trial Design datasets. |
| 6.4 Extension Mechanism | 100-107 | Sanctioned route for content the model does not cover, including explicitly "a need to overcome issues with the model". Implemented as `extensionAttributes`, present on all 81 classes: a list of `ExtensionAttribute` (id, url, value). Not part of the logical model; API-only. Extensions **must be documented** by whoever creates them. |

## Priority unread sections

| Section | Pages | Why it matters here |
| --- | --- | --- |
| 4.14 Study Timing | 26-31 | The timing graph Phase 5 has to rebuild. |
| 4.23 Addressing Footnotes | 44-50 | Footnotes are the stated Phase 5 target. |
| 4.25 Schedule of Activity Views | 57-60 | How CDISC says an SoA is represented. |
| 4.24 Complex Study Designs | 51-56 | Where the model's limits are described. |
| 5 USDM Data Dictionary | 61-98 | Per-class definitions in prose, the semantics `USDM_API.json` omits. |
| 7.5 Use of USDM for Populating Protocol Content | 109 | CDISC's assumed direction is design to document. This project runs document to design. Unverified whether that is a real constraint. |
