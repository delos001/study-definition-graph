# Background

USDM (Unified Study Definitions Model) is CDISC's clinical study plan data model developed with TransCelerate through the Digital Data Flow (DDF) initiative [1][2]. Version 4.0, released June 2025 [3], aligns with ICH M11 [1], but is not mandatory as of Q2 2026. Complementary process guidance, conformance support, and relationship mapping to other industry standards have been developed concurrently [1].

Development and release of these models and resources provide an opportunity to extract and transform the requirements in study planning and design documents to be utilized by almost all downstream processes within drug and device development.  Combined with technology, such as AI and careful deterministic programming, these standards and processes have the potential to disrupt the status quo, substantially improving the speed and safety with which the industry brings treatments to patients.  Commercial vendors already generate USDM-conformant outputs from clinical documents using AI and/or generate USDM standard documents from scratch [4].

## Why this project exists

The project's premise is that USDM has a typed structural home for much of the information contained within a protocol and possibly for key information contained within other documents such as Investigator Brochures and Statistical Analysis Plans. From this structure, relationships between data can persist and be demonstrated.  It's possible this approach can be extended to other traditional documents such as operational plans and specifications. How far the premise holds will be worked out from the sources and from CDISC's own worked examples.

To attack the premise, unstructured clinical documents will be ingested into a standards-conformant knowledge graph, by building a working pipeline.  This approach is expected to surface use cases downstream of study planning, and the project aims to identify and evaluate them.  Candidate areas include:

- Data Acquisition: define data needs, oversight and risk, procure data sources/providers, verify data conformance
- Clinical Monitoring: site management, SDR, protocol compliance, regulatory compliance
- Data Quality: data validation, clinical validation for centralized and decentralized data
- Standardization Mapping
- Data Analysis
- Medical Writing

Further, this project is quasi-exploratory so competency building in the domains will be observed in the methods and technology choices.

This project will utilize USDM and is not claiming to be a novel approach by such use.

## The problem

Over time, the industry has experienced steady increases in complexity of trial design and data, a proliferation of decentralized data sources, vendors, and capture technologies, and evolving regulatory expectations to evaluate trial objectives and protect study participants.  The result is a substantial increase in logistical and technical complexity that translates to resource burden, risk and increased costs.

The methods by which a study will be evaluated and patient rights and well-being will be protected are described across several 'planning' documents. The protocol says what will be done, the Statistical Analysis Plan says how the resulting data will be analyzed, and the Investigator's Brochure carries what is known about the disease or interventions. They are written at different times, usually by different people, and contain some of the same information written in a different manner or perspective.  Consequently, all downstream actions and decisions are rooted in some way in one or all of these documents. For example, a protocol may define the analysis set as "Intent-to-Treat (ITT)" population while the SAP describes a "Full Analysis Set (FAS)."  Whether these refer to the same subjects is not clear from the labels and instead depends on how each is defined within the context of the document.  Establishing correspondence, or its absence, is an entity resolution challenge.

Information in study planning documents is human readable.  Depending on how well the document is structured and written, relationships between the information within and across planning documents can be understood reasonably well by a human reader. However, as a workflow moves to downstream activities and across functional objectives, information is manually extracted and aggregated into new documents, sources and formats in a 'copy-of-a-copy' mechanism that requires substantial resources to create, and does not adequately mitigate the risk associated with complexity trends in the industry.

Automation has long been believed to be an important tool to see gains in trial delivery effectiveness and reductions in resource burden, but the unstructured shapes and non-standard formats for study planning documents are not well suited for computer readability. The difficulty is neither pulling text out of an unstructured format nor mapping it into USDM's fields. It's identifying, recovering and maintaining the relationships the unstructured documents only imply, keeping every extracted fact traceable to its respective source, while maintaining the human readability the original documents possess.  The resulting structure must be queryable so a machine can answer questions that span documents, which today requires a human who has read and understood all of them.

The sharpest instance is the Schedule of Activities: a grid where rows are activities, columns are visits. The grid is a lossy rendering whereas the real structure is a directed graph of scheduled activities and decision points connected by timing rules.  Rebuilding it is graph reconstruction from a flattened two-dimensional projection, not table parsing. Everything the printed schedule expresses as a footnote, an asterisk, or prose ("only if ALT above twice the upper limit of normal", "repeat every 21 days until progression", "may be performed within 7 days prior") has no cell in the table and presents the challenge of identifying and documenting the correct relationship to the corresponding table element.

That shape recurs outside the schedule and outside the protocol, which is why the project is about documents rather than about one table.

## Published benchmarks

- 2026 *Journal of Biomedical Informatics*: retrieval with clinical-tailored prompts reached **89.0% weighted accuracy** across six information categories versus **62.6%** for a standalone LLM with refined prompts. Peer-reviewed. [5]
- Same study: the Schedule of Assessments problem was addressed with two stages, table detection then **vision-based multimodal processing**, because text-only methods lose spatial hierarchy.
- Same study: content for a single category is typically spread across different sections, which is the justification for retrieval over whole-document processing.
- Same study: low-confidence cases routed to human review had the model decision confirmed **87%** of the time; reviewers saw a median 60-minute (40%) time reduction.
- One tool (ProtocolMiner) produced accurate, detailed timelines for **22 of 29** legacy schedules (~76%), with minor errors in the rest, and mapped them into USDM (and FHIR) structures. Single study, single tool, so low-to-moderate confidence, but prior art exists: this is not unexplored ground. [6]
- **Negative finding**: no published accuracy threshold, validation standard, or normative human-review requirement exists for AI-generated USDM content.

## Glossary

- **USDM** (Unified Study Definitions Model): CDISC's data model for a clinical study's *plan*, published as a set of formal specifications that include a UML logical model and an API specification.
- **Protocol**: the document defining what a study will do.
- **Schedule of Activities (SoA)**: the visit-by-activity grid in a protocol.
- **SAP** (Statistical Analysis Plan): the document describing how a study's data will be analyzed.
- **IB** (Investigator's Brochure): the document summarizing what is already known about an intervention from earlier nonclinical and clinical work.
- **Protocol synopsis**: a condensed summary of a protocol, usually a few pages.
- **Knowledge graph**: data stored as things (nodes) and relationships (edges) rather than rows.
- **Neo4j**: a graph database that runs as a server, with a browser-based interface for querying and visualizing the graph.
- **Cypher**: Neo4j's query language, analogous to SQL for a relational database.
- **Entity resolution**: deciding whether two differently-named records refer to the same real-world thing.
- **Provenance**: a record, for each extracted fact, of where it came from and how it was produced.

## References

Web sources are living pages; each entry records the date it was accessed. Pinned standards (the USDM artifacts themselves) are tracked in `data/manifests/`, not here.

[1] CDISC. "Digital Data Flow (DDF) for Clinical Trial Protocols." https://www.cdisc.org/ddf (accessed 2026-08-27). Supports the CDISC/TransCelerate collaboration, ICH M11 alignment, and the supporting deliverable suite.

[2] TransCelerate BioPharma. "Digital Data Flow." https://www.transceleratebiopharmainc.com/initiatives/digital-data-flow/ (accessed 2026-08-27). Supports the initiative's origin as a TransCelerate effort.

[3] CDISC. "DDF-RA Releases: USDM v4.0.0, published 03 June 2025." GitHub, cdisc-org/DDF-RA. https://github.com/cdisc-org/DDF-RA/releases (accessed 2026-08-27). Supports the v4.0 release date; this is also the repository the project pins USDM from.

[4] Buntz, Brian. "Medable's Digital Data Flow Agent focuses on protocol translation as the agentic race accelerates." R&D World, 18 June 2026. https://www.rdworldonline.com/medables-digital-data-flow-agent-focuses-on-protocol-translation-as-the-agentic-race-accelerates/ (accessed 2026-08-27). Supports commercial vendors generating USDM-conformant output from clinical documents with AI, within a competitive vendor marketplace.

[5] Babaeipour, Ramtin; Charest, François; Wright, Madison (Banting Health AI). "AI-assisted Protocol Information Extraction for Improved Accuracy and Efficiency in Clinical Trial Workflows." Journal of Biomedical Informatics, 2026. Preprint arXiv:2602.00052. https://arxiv.org/abs/2602.00052 (accessed 2026-08-27). Supports the 89.0% vs 62.6% weighted six-category accuracy (Table 3; 89.0% is the best RAG configuration, 62.6% the standalone baseline), the two-stage table-detection then multimodal SoE approach, the 87% human-confirmation rate for low-confidence cases (N=35), and the median 60-minute (40%) reviewer time reduction.

[6] "Transforming Legacy Clinical Trial Schedules of Activities into Interoperable Digital Formats" (ProtocolMiner). Medical Research Archives, 2025. https://esmed.org/MRA/mra/article/view/7362 (accessed 2026-08-27). Supports accurate, detailed timelines for 22 of 29 legacy schedules (minor errors in the remaining seven) and their mapping into USDM (ScheduleTimeline, Encounter, Activity) and FHIR structures.
