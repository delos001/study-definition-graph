# Standards read record

What has been read from each pinned standard, and what each part established. A claim about a standard is grounded only when the part it rests on appears here. Anything not listed has not been consulted, and a claim about it is inference until it is.

One heading per standard. Each row names the part read, where it sits in the document, and what it established, so a later session can rely on the finding without reading the part again, or can go straight to it when the finding needs checking. Which file answers which question, and how to open it, is `docs/sources_index.md`. A document's own section numbers and page ranges come from its bookmarks, printed with `read_pdf --list`.

## USDM Implementation Guide v4.0

`inputs/standards/cdisc/usdm_v4/USDM-IG.pdf`, pinned commit `aa303cb`. Read a section with `read_pdf 4.23`, or `read_pdf 6.4 --raw` to keep the page headers and footers.

### Read and verified

| Section | Pages | What it established |
| --- | --- | --- |
| 2 Fundamentals of the USDM | 6-8 | USDM is 5 official standards, not 1: class diagram, API spec, Controlled Terminology, this IG, Conformance Rule Specifications. `USDM_API.json` is one of the five and the one carrying no semantics. v4.0 is aligned to ICH M11 CeSHarP. Publicly available protocols have been mapped to USDM and published as "USDM GitHub Examples" (p.8). |
| 3.1 Relationship to Other CDISC Standards | 9-10 | USDM draws on BRIDG, supersedes PRM, and feeds SDTM Trial Design datasets. |
| 6.4 Extension Mechanism | 100-107 | Sanctioned route for content the model does not cover, including explicitly "a need to overcome issues with the model". Implemented as `extensionAttributes`, present on all 80 concrete classes (measured 2026-08-18; the 81 previously recorded here was wrong): a list of `ExtensionAttribute` (id, url, value). Not part of the logical model; API-only. Extensions **must be documented** by whoever creates them. |

### Priority unread sections

| Section | Pages | Why it matters here |
| --- | --- | --- |
| 4.14 Study Timing | 26-32 | The timing graph Phase 5 has to rebuild. |
| 4.23 Addressing Footnotes | 44-51 | Footnotes are the stated Phase 5 target. |
| 4.25 Schedule of Activity Views | 57-61 | How CDISC says an SoA is represented. |
| 4.24 Complex Study Designs | 51-57 | Where the model's limits are described. |
| 5 USDM Data Dictionary | 61-99 | Per-class definitions in prose, the semantics `USDM_API.json` omits. |
| 7.5 Use of USDM for Populating Protocol Content | 109 | CDISC's assumed direction is design to document. This project runs document to design. Unverified whether that is a real constraint. |
