# Background

Context for the study-definition-graph project. Read this at session start.

**What this file is not.** It carries no technical content about USDM. Class
meanings, attributes, cardinalities, relationship targets, controlled
terminology and conformance rules come from the pinned sources, and only from
there. A summary of them here would be read before the sources are ever opened,
which forms a position in advance of the evidence and defeats the grounding rule
in `CLAUDE.md`. The test applied to every sentence below: if reading a source
document could change it, it does not belong in this file.

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
scheduled activities and decision points connected by timing rules.
Reconstructing it is graph reconstruction from a flattened two-dimensional
projection, not table parsing.

The consequence that defines the project: everything the printed schedule
expresses as a footnote, an asterisk, or prose ("only if ALT above twice the
upper limit of normal", "repeat every 21 days until progression", "may be
performed within 7 days prior") has **no cell in the table**.

The project's premise is that USDM has a typed structural home for each of those
things. That is a premise, not an established fact. How the printed grid maps
into USDM is worked out from the sources and from CDISC's own worked examples,
not asserted here.

## Target hard cases

The two extraction cases the project aims at, chosen because they are precisely
the content with no cell in the table:

1. **Footnotes containing conditionals.** A footnote marker on a cell that
   changes whether or when the activity happens.
2. **Patient routing rules in large unstructured text.** Dose escalation and
   de-escalation, stratification, rescue branching, expressed as prose.

## USDM, in one paragraph

USDM is CDISC's data model for a clinical study's *plan*, as distinct from its
results. Version 4.0, released 3 June 2025, aligned to ICH M11, adopted by no
regulator. It is published as five separate official standards rather than one
file, which is why "check USDM" is not a single action. `CLAUDE.md` holds the
table of which of the five answers which kind of question. Everything else about
the model is read from those files at the moment it is needed.

## Where the material comes from

Everything this project needs is public and free. No CDISC membership is
required, and that was checked rather than assumed: a non-member API key
authenticates against the CDISC Library and returns `"Members-only content"`,
so the Library API and the `usdm` PyPI package are out of scope.

The pinned corpus and its provenance are in `data/manifests/`, one file per set,
with a url and a sha256 per file. Which sources are pinned versus called live,
and why, is in `PLAN.md`.

## Design constraints

- **Greenfield ingestion.** Assume no existing document ingestion pipeline to
  build on. Per-document-type handling is built here, not inherited.
- **The ontology is a governed dependency, not ours to change.** In this class
  of system, ontology ownership typically sits with a data science function
  separate from whoever configures a customer. Design so that schema change is a
  release with change control, not a config edit.
- **ICH M11 structured protocol content is a regulatory expectation, not a
  verified mandate.** Do not design as though a deadline exists.
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
- Academic work mapping legacy Schedules of Activities into USDM reports
  high-fidelity automated transformation is feasible. Single source,
  low-to-moderate confidence. Prior art exists; this is not unexplored ground.
- **Negative finding**: no published accuracy threshold, validation standard, or
  normative human-review requirement exists for AI-generated USDM content.
