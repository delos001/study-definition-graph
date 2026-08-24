# Background

Context for the study-definition-graph project. Read this at session start.

No technical content about any standard belongs here. The test: if reading a source document could change a sentence, it goes in the source, not in this file.

## Why this project exists

To build hands-on competence in AI-driven ingestion of unstructured clinical documents into a standards-conformant knowledge graph, by building a working pipeline rather than reading about one. Code first; the design write-up comes later, grounded in what actually broke.

## The problem

A clinical study is described across several documents. The protocol says what will be done, the Statistical Analysis Plan says how the resulting data will be analysed, the Investigator's Brochure carries what is already known about the drug, the synopsis is a compressed retelling of the protocol. They are written at different times, usually by different people, and they name the same things differently. None of it is addressable by anything but a reader, so a study exists only in the head of whoever has read all of them.

The work is turning that into a graph of things and the relationships between them, queryable, with every fact traceable back to the sentence it came from.

It starts with the protocol, because that is the densest and most structured of the set and because CDISC publishes a model for exactly its content. Nothing about the approach is meant to be protocol-only.

The difficulty is not pulling text out of a PDF. It is that the content carrying the most structure is the content least visible to a text extractor.

The sharpest instance is the Schedule of Activities: a grid where rows are activities, columns are visits, and an X means the activity happens at that visit. The grid is a lossy rendering. The real structure is a directed graph of scheduled activities and decision points connected by timing rules, so rebuilding it is graph reconstruction from a flattened two-dimensional projection, not table parsing. Everything the printed schedule expresses as a footnote, an asterisk, or prose ("only if ALT above twice the upper limit of normal", "repeat every 21 days until progression", "may be performed within 7 days prior") has **no cell in the table**.

That shape recurs outside the schedule and outside the protocol, which is why the project is about documents rather than about one table.

The project's premise is that USDM has a typed structural home for most of this. That is a premise, not an established fact, and how far it holds is worked out from the sources and from CDISC's own worked examples, not asserted here. How far it holds for documents that are not protocols is a separate and genuinely open question, recorded under design constraints below.

## Glossary

- **USDM** (Unified Study Definitions Model): CDISC's data model describing a clinical study's *plan*. Version 4.0, released 3 June 2025. Published as an OpenAPI specification, so the exact shape of every object is machine-readable and downloadable.
- **Protocol**: the document defining what a study will do. The starting point here, not the limit of scope.
- **Schedule of Activities (SoA)**: the visit-by-activity grid in a protocol.
- **SAP** (Statistical Analysis Plan): companion document describing how the data will be analyzed. Written later, often by different people, referring back to the protocol using different words for the same things. That mismatch is what makes linking two documents interesting.
- **IB** (Investigator's Brochure): what is already known about the drug from earlier nonclinical and clinical work. A target document type, and the one least likely to fit USDM cleanly.
- **Protocol synopsis**: a compressed retelling of the protocol, usually a few pages. A target document type, and a useful test of whether extraction from a summary agrees with extraction from the full document.
- **Knowledge graph**: data stored as things (nodes) and relationships (edges) rather than rows. Good at questions requiring a chain of relationships.
- **Neo4j**: the most widely used graph database. Runs as a server. Ships with Neo4j Browser, a web page where you type a query and it draws the result as connected dots. That drawing is the reason to use it here: a broken link between two documents is obvious in a picture and nearly invisible in code.
- **Cypher**: Neo4j's query language. Roughly what SQL is to a relational database.
- **Entity resolution**: deciding whether two differently-named records are the same real thing. A protocol says "Intent-to-Treat Population," an SAP says "Full Analysis Set." Sometimes identical, sometimes not.
- **Provenance**: recording, for every extracted fact, where it came from and how it was produced.

## Target hard cases

The extraction cases the project aims at, chosen because each is content that the document's own layout does not express:

1. **Footnotes containing conditionals.** A footnote marker on a schedule cell that changes whether or when the activity happens.
2. **Patient routing rules in large unstructured text.** Dose escalation and de-escalation, stratification, rescue branching, expressed as prose.
3. **Rules written as sentences.** Eligibility criteria are a set of logical conditions rendered as a bulleted list. Nothing on the page marks which combine, which are thresholds, or which depend on another.
4. **The same thing under two names in two documents.** An endpoint in the protocol and its estimand in the SAP, where neither document states that they correspond.

The first two live inside a protocol's schedule. The second two are the reason the target is documents rather than one table.

## USDM, in one paragraph

USDM is CDISC's data model for a clinical study's *plan*, as distinct from its results. Version 4.0, released 3 June 2025, aligned to ICH M11, adopted by no regulator. It is published as five separate official standards rather than one file, which is why "check USDM" is not a single action. Everything else about the model is read from the pinned files when it is needed.

## Design constraints

- **Greenfield ingestion.** Assume no existing document ingestion pipeline to build on. Per-document-type handling is built here, not inherited.
- **How far USDM reaches beyond the protocol is undecided, on purpose.** USDM models a study's *plan*. A protocol fits it, a SAP fits it partly, an Investigator's Brochure largely does not. Three approaches are visible and none is chosen: map only the parts that fit and drop the rest, which is simple but silently loses content; extend USDM through its own extension mechanism, which keeps everything in one model at the cost of carrying extensions forever; or give non-protocol document types their own target model, which fits each document better but makes cross-document linking a translation problem. This is expected to be settled by working through a real document rather than decided in advance, and it is directly connected to the second failure mode below.
- **The ontology is a governed dependency, not ours to change.** In this class of system, ontology ownership typically sits with a data science function separate from whoever configures a customer. Design so that schema change is a release with change control, not a config edit.
- **ICH M11 structured protocol content is a regulatory expectation, not a verified mandate.** Do not design as though a deadline exists.
- **Two failure modes to design against**, both observed in this product category:
  1. Customer-authored prompts reaching production unvalidated, then not working. The structural fix is treating customer-authored prompts as in scope for validation with a documented go-live gate.
  2. Content with no home in the standard, which the customer experiences as the tool being inflexible rather than as a modelling gap.
- **Open question to measure, not assume.** When extraction output is wrong, is the dominant cause the prompt, or what got retrieved and linked in the first place? Practitioner opinion in this space leans prompt. This project should produce evidence rather than inherit the assumption.
- **Whether a graph beats a text search here is not assumed.** Phase 4 is built to test it with one question needing a chain of relationships across two documents. If a plain text search answers it just as well, that is a finding worth recording rather than a failure to hide.

## Evaluation and provenance practice

- **Golden dataset entry shape**: input, expert-validated expected output, and metadata (category, difficulty, edge-case flag). Practitioner guidance suggests 20 to 50 reviewed items catches gross regressions.
- **Acceptance thresholds are agreed before testing begins**, and benchmarked at or above the performance of whatever process is being replaced.
- **Regression evaluation** re-runs a fixed set after every model, prompt, retriever, or tool change, compared against the last passing baseline.
- **Named failure mode: silent quality loss.** An edit makes output friendlier and drops a required element. Fluent and wrong is worse than obviously broken.
- **An observed evaluation pattern in this product category**: generate section by section rather than whole-document; a second model scores each section against a configurable checklist; a third rewrites the prompt when the check fails. Generation is anchored to a structured definition rather than model memory. Structure first, prose second.

## Published benchmarks

- 2026 *Journal of Biomedical Informatics*: retrieval with clinical-tailored prompts reached **89.0% weighted accuracy** across six information categories versus **62.6%** for a standalone GPT-4o with refined prompts. Peer-reviewed.
- Same study: the Schedule of Assessments problem was addressed with two stages, table detection then **vision-based multimodal processing**, because text-only methods lose spatial hierarchy.
- Same study: content for a single category is typically spread across different sections, which is the justification for retrieval over whole-document processing.
- Same study: low-confidence cases routed to human review had the model decision confirmed **87%** of the time; reviewers saw a median 60-minute (40%) time reduction.
- One AI extraction tool produced accurate detailed timelines for **22 of 29** schedules, roughly 76% clean, failures attributed to widely varying table formats. Single study, single tool.
- Academic work mapping legacy Schedules of Activities into USDM reports high-fidelity automated transformation is feasible. Single source, low-to-moderate confidence. Prior art exists; this is not unexplored ground.
- **Negative finding**: no published accuracy threshold, validation standard, or normative human-review requirement exists for AI-generated USDM content.
