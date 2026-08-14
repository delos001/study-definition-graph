# Background

Context for the study-definition-graph project. Read this at session start.

## Why this project exists

To build hands-on competence in AI-driven ingestion of unstructured clinical
documents into a standards-conformant knowledge graph, by building a working
pipeline rather than reading about one. Code first; the design write-up comes
later, grounded in what actually broke.

## The problem

A clinical trial protocol contains a Schedule of Activities: a grid where rows
are activities, columns are visits, and an X means the activity happens at that
visit.

The grid is a lossy rendering. The real structure is a directed graph of
scheduled-activity and scheduled-decision nodes connected by timing edges.
Reconstructing it is graph reconstruction from a flattened two-dimensional
projection, not table parsing.

How the printed table maps into USDM:

- A column header is an **Encounter**, reached through the scheduled activity
  instance.
- Each X in a cell is an **Activity** id inside that instance.
- The timing row ("Day 1", "Week 4 plus or minus 3 days") is a **Timing** object
  anchored to another instance, with lower and upper window bounds.
- Branching and conditional arms are **scheduled decision instances with
  condition assignments**.
- Repeating cycles are a **nested timeline**.

The consequence that defines the project: everything the printed schedule
expresses as a footnote, an asterisk, or prose ("only if ALT above twice the
upper limit of normal", "repeat every 21 days until progression", "may be
performed within 7 days prior") has a typed structural home in USDM and **no
cell in the table**.

## Target hard cases

The two extraction cases the project aims at, chosen because they are precisely
the content with no cell in the table:

1. **Footnotes containing conditionals.** A footnote marker on a cell that
   changes whether or when the activity happens.
2. **Patient routing rules in large unstructured text.** Dose escalation and
   de-escalation, stratification, rescue branching, expressed as prose.

## USDM essentials

Version 4.0, released 3 June 2025. Aligned to ICH M11. Adopted by no regulator.

**What it is.** A UML logical data model plus an OpenAPI-specified REST
interface, representing a study's design intent as a JSON object graph.

**Shape.** Wrapper, then Study, then StudyVersion, then StudyDesign
(interventional and observational subtypes). Study is the persistent thing,
StudyVersion is the plan at a point in time, StudyDesign carries the design.

**Reusable versus design-scoped.** Reusable items (biomedical concepts,
eligibility criterion items, narrative content items, organizations,
interventions) live at StudyVersion level. Design-specific references to them
live at StudyDesign level. That split is what makes multi-design studies
expressible without duplication.

**The design matrix.** StudyArm by StudyEpoch, intersected by StudyCell, with
StudyElement as the treatment content of a cell. Deliberately isomorphic to
SDTM's trial design structure.

**Scientific content chain.** Objective links to Endpoint. Estimand is
first-class, with a summary measure and relationships to analysis population,
treatment, variable of interest, and intercurrent events. USDM models the ICH
E9(R1) estimand framework structurally.

**Eligibility.** Splits across a design-scoped ordered criterion and a
version-scoped reusable text item.

**Serialization.** JSON is the operative wire format. The payload is normalized,
not deeply nested: one large self-contained JSON document with an internal ID
graph. Every object carries an id and a type discriminator. Relationships are id
or id-list fields within the same document. Schema component names in the
OpenAPI spec carry `-Input` and `-Output` suffixes, with a `Wrapper` envelope.

**Controlled terminology is embedded by value, not by reference.** Every coded
slot is a Code object carrying code, code system, code system version, and
decode.

**Sponsor terminology is inside the standard, not a deviation from it.** USDM
controlled terminology combines CDISC-provided terms with sponsor-defined terms,
and external CT code formats are intended to carry them. There is also a model
extension mechanism. This is the sanctioned route for content that has no
built-in home, and it is where implementation work concentrates.

**Version churn is real.** v1.0 (9 Aug 2022), v2.0 (27 Jun 2023), v3.0 (16 Apr
2024), v4.0 (3 Jun 2025), plus published errata on v3.0 and v4.0. Pin the
version. API version and model version are decoupled: V5 endpoints serve USDM
4.0.

## Design constraints

- **Greenfield ingestion.** Assume no existing document ingestion pipeline to
  build on. Per-document-type handling is built here, not inherited.
- **The ontology is a governed dependency, not ours to change.** In this class
  of system, ontology ownership typically sits with a data science function
  separate from whoever configures a customer. Design so that schema change is a
  release with change control, not a config edit.
- **Two failure modes to design against**, both observed in this product
  category:
  1. Customer-authored prompts reaching production unvalidated, then not
     working. The structural fix is treating customer-authored prompts as in
     scope for validation with a documented go-live gate.
  2. Content with no home in the standard, which the customer experiences as the
     tool being inflexible rather than as a modelling gap.
- **Open question to measure, not assume.** When extraction output is wrong, is
  the dominant cause the prompt, or what got retrieved and linked in the first
  place? Practitioner opinion in this space leans prompt. This project should
  produce evidence rather than inherit the assumption.

## Evaluation and provenance practice

- **Bidirectional verification is the defensible pattern**: conformance and
  schema validation of the produced artifact, *plus* reconciliation back to
  source with field-level traceability from each USDM element to the protocol
  content it came from. The mapping specification itself is the testable
  artifact.
- **Golden dataset entry shape**: input, expert-validated expected output, and
  metadata (category, difficulty, edge-case flag). Practitioner guidance
  suggests 20 to 50 reviewed items catches gross regressions.
- **Acceptance thresholds are agreed before testing begins**, and benchmarked at
  or above the performance of whatever process is being replaced.
- **Pin model versions to immutable identifiers**, never moving aliases, and
  record the identifier in run metadata. Providers retire versions, often within
  roughly 12 to 18 months, without complete changelogs.
- **Prompts are production dependencies.** Versioned immutably, each version
  carrying model, parameters, tool configuration, and the rationale for the
  change. An edit creates a new version rather than altering the old one.
- **Regression evaluation** re-runs a fixed set after every model, prompt,
  retriever, or tool change, compared against the last passing baseline.
- **Named failure mode: silent quality loss.** An edit makes output friendlier
  and drops a required element. Fluent and wrong is worse than obviously broken.
- **An observed evaluation pattern in this product category**: generate section
  by section rather than whole-document; a second model scores each section
  against a configurable checklist; a third rewrites the prompt when the check
  fails. Generation is anchored to a structured definition rather than model
  memory. Structure first, prose second.

## Published benchmarks

- 2026 *Journal of Biomedical Informatics*: retrieval with clinical-tailored
  prompts reached **89.0% weighted accuracy** across six information categories
  versus **62.6%** for a standalone GPT-4o with refined prompts. Peer-reviewed.
- Same study: the Schedule of Assessments problem was addressed with two stages,
  table detection then **vision-based multimodal processing**, because text-only
  methods lose spatial hierarchy.
- Same study: content for a single category is typically spread across different
  sections, which is the justification for retrieval over whole-document
  processing.
- Same study: low-confidence cases routed to human review had the model decision
  confirmed **87%** of the time; reviewers saw a median 60-minute (40%) time
  reduction.
- One AI extraction tool produced accurate detailed timelines for **22 of 29**
  schedules, roughly 76% clean, failures attributed to widely varying table
  formats. Single study, single tool.
- Academic work mapping legacy Schedules of Activities into USDM
  ScheduleTimeline / Encounter / Activity reports high-fidelity automated
  transformation is feasible. Single source, low-to-moderate confidence. Prior
  art exists; this is not unexplored ground.
- **Negative finding**: no published accuracy threshold, validation standard, or
  normative human-review requirement exists for AI-generated USDM content.

## Public artifacts

All free, no CDISC membership required.

- `github.com/cdisc-org/DDF-RA`
  - `Deliverables/API/USDM_API.json` and `.yaml` (OpenAPI, one component schema
    per class)
  - `Deliverables/CT/USDM_CT.xlsx` (controlled terminology)
  - `Deliverables/RULES/` (conformance rule specifications, stable rule IDs)
  - `Deliverables/IG/USDM-IG.pdf` (implementation guide)
- **CORE**, the CDISC Open Rules Engine. MIT licensed, CLI only, no GUI. Same
  engine used for SDTM. The reference implementation exposes a USDM conformance
  validation endpoint.
- ClinicalTrials.gov API v2, plus document CDN at
  `cdn.clinicaltrials.gov/large-docs/{last2ofNCT}/{NCT}/{filename}`.

**Requires a member-tier `CDISC_API_KEY`, therefore out of scope**: the `usdm`
PyPI package and the CDISC Library API. A non-member key authenticates but
returns `"Members-only content"` even on `/mdr/products`. Everything this
project needs is in the public files above.

## Accuracy guards

- USDM conformance rules are reportedly expressed in JSONata rather than the
  YAML used for other CDISC rule sets. Medium-high confidence, effectively
  single-source. Verify before relying on it.
- The CORE rule set is substantially but not fully authored. Do not quote a
  percentage.
- JSON-Schema-based validation of USDM JSON is an open CDISC issue, so schema
  validation is complementary to the rules engine and not yet fully covered.
- Field-level USDM attribute names in circulation often come from CDISC's
  reference Python package, which mirrors the API rather than being normative.
  Check names against the pinned `USDM_API.json`.
- ICH M11 structured protocol content is a regulatory **expectation**, not a
  verified mandate.
