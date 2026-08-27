# Background

In recent years, CDISC, Trancelerate and others organizations have collaborated to develop USDM.  USDM is CDISC's data model for a clinical study's *plan*. Version 4.0, released 3 June 2025, aligned to ICH M11, but has not been required by a regulatory body. Additionally, corresponding complement process guidance, conformance support, and relationship mapping to other industry standards have been developed.

Development and release of these models and resources provide an opportunity to extract and transform the requirements in study planning and design documents to be utilized by almost all downstream processes withing drug and device development.  Combined with technology, including AI, these standards and process have the potential to positively disrupt the industry's ability to bring treatments quickly and safely to patients.  This is a capability possessed by a number of organizations such as IQVIA, Veeva, Medidata who are utilizing AI to generate USDM compliant computer readable documents from existing clinical documents and/or generate USDM standard documents from scratch.

## Why this project exists

The project's premise is that USDM has a typed structural home for much of the information contained within a protocol and possibly for key information contained within other documents such as Investigator Brochurs and Statistical Analysis Plans. How far the premise holds will be worked out from the sources and from CDISC's own worked examples.  Creating methods to presever data relationships via knowledge mapping will be targeted with the goal of understanding how the method can be leveraged by downstream activity use cases.

To attack the premise, unstructured clinical documents will be ingested into a standards-conformant knowledge graph, by building a working pipeline.  It is believed that this approach will yield use-cases in some or even all activities downstream from study planning. As they become more concrete through the work of this project, they may be documented and this project may be expanded or new projects initiated.  Below is an initial list of potential targets where standardization and/or knowledge graphing could see quality and timeline gains to deliver:

- Data Acquisition: define data needs, oversight and risk, procure data sources/providers, verify data conformance
- Clinical Monitoring: site management, SDR, protocol compliance, regulatory compliance
- Data Quality: data validation, clinical validation for centralized and decentralized data
- Standardization Mapping
- Data Analysis
- Medical Writing

Further, this project is quasi-exploratory so competency building in the domain(s) will be observed in the methods and technology choices.

This project will utilize USDM and is not claiming to be a novel approach by such use.

## The problem

Over time, the industry has experienced steady increases in complexity of trial design and data, a proliferation of decentralized data sources, vendors, and capture technologies, and evolving regulatory expectations to evaluate trial objectives and protect study participants.  The result is a substantial increase in logistical and technical complexity that translates to resource burden, risk and increased costs.

The methods by which a study will be evaluated and patient rights and well-being will be protected are described across several 'planning' documents. The protocol says what will be done, the Statistical Analysis Plan says how the resulting data will be analysed, and the Investigator's Brochure carries what is known about the disease and/or interventions. They are written at different times, usually by different people, and contain some of the same information written in a differnt manner or perspective.  Consequentially, all downstream actions and decisions are rooted in some way in one or all of these documents.

Information in study planning documents is human readable.  Depending on how well the document is structured and written, relationships between the information within and across planning documents can be understood reasonably well by a human reader. However, as a workflow moves to downstream activities and across functional objectives, information is manually extracted and aggregated into new documents, sources and formats in a 'copy-of-a-copy-of-a-copy' mechanism to that requires substantial resources to create, and does not adqueately mitigate the risk assocaited with complexity trends in the industry.

Automation has long been believed to be an important tool to see gains in trial delivery effectiveness and reductions in resource burden, but the unstructred shapes and non-standard formats for study planning documents are not well suited for computer readability. The difficulty is not pulling text out of an unstructured format nor is it translating unstructured study documents to USDM. The work is to extract unstructured information and organize it into a standard format that is queryable, traceable, and shows both the information and relationships while mitigating the loss of human readability.

The sharpest instance is the Schedule of Activities: a grid where rows are activities, columns are visits. The grid is a lossy rendering while real structure is a directed graph of scheduled activities and decision points connected by timing rules.  Rebuilding it is graph reconstruction from a flattened two-dimensional projection, not table parsing. Everything the printed schedule expresses as a footnote, an asterisk, or prose ("only if ALT above twice the upper limit of normal", "repeat every 21 days until progression", "may be performed within 7 days prior") has no cell in the table and presents the challenge of identifying and documenting the correct relationship to the corresponding table element.

That shape recurs outside the schedule and outside the protocol, which is why the project is about documents rather than about one table.

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


## Published benchmarks

- 2026 *Journal of Biomedical Informatics*: retrieval with clinical-tailored prompts reached **89.0% weighted accuracy** across six information categories versus **62.6%** for a standalone GPT-4o with refined prompts. Peer-reviewed.
- Same study: the Schedule of Assessments problem was addressed with two stages, table detection then **vision-based multimodal processing**, because text-only methods lose spatial hierarchy.
- Same study: content for a single category is typically spread across different sections, which is the justification for retrieval over whole-document processing.
- Same study: low-confidence cases routed to human review had the model decision confirmed **87%** of the time; reviewers saw a median 60-minute (40%) time reduction.
- One AI extraction tool produced accurate detailed timelines for **22 of 29** schedules, roughly 76% clean, failures attributed to widely varying table formats. Single study, single tool.
- Academic work mapping legacy Schedules of Activities into USDM reports high-fidelity automated transformation is feasible. Single source, low-to-moderate confidence. Prior art exists; this is not unexplored ground.
- **Negative finding**: no published accuracy threshold, validation standard, or normative human-review requirement exists for AI-generated USDM content.
