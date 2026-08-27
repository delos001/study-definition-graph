# Study-definition-graph

## Purpose

This file is the stable build plan: what the project builds, in what order, and how each step is proven to work. It is a reference document and changes only when the plan itself changes.

Three companions carry what does not belong here:
- `BACKGROUND.md` for why the project exists and the problem it addresses.
- `DECISIONS.md` for the record of choices made and why.
- GitHub Issues for current status and the working backlog.

## Approach

The pipeline runs as an ordered sequence of stages, each taking the previous stage's output as its input:

- acquire documents from ClinicalTrials.gov,
- locate their sections deterministically, with no AI, so a later error is attributable to reading or to prompting but not both,
- classify document type and section content,
- extract into USDM-conformant structures with full provenance,
- load into a Neo4j graph and query it to answer a question spanning two documents.

The Schedule of Activities, the hardest single case, is built last because it depends on everything above it working first.

Each stage is a self-contained step with an explicit input and output, so a failure names one stage rather than the whole pipeline.

## Build phases

Each phase states its goal, what it produces, and how it is verified. Phases 3 to 5 are sketches, to be detailed when reached.

### Phase 0 — Foundation and orientation

No pipeline work; the point is to stand up the tools and pin the sources, and to get hands-on with anything not used before.

- **Produces:**
  - git repository,
  - conda environment,
  - repo skeleton,
  - Neo4j running in Docker, with a few nodes and edges created and queried by hand,
  - USDM v4.0 artifacts pinned to `data/raw/usdm_v4/` with the commit recorded,
  - loader that lists USDM classes and their fields from the pinned spec,
  - determination of whether the DDF conformance endpoint and CORE are usable without member credentials.
- **Verification:**
  - Neo4j Browser reachable at `localhost:7474` with a query run by hand,
  - `python -m sdg.usdm_spec --list-classes` prints class names read from the pinned file.

### Phase 1 — Acquire documents and locate their content

Get real protocol and SAP pairs and find where their content lives, deterministically.

- **Produces:**
  - protocol and SAP PDFs pulled from the ClinicalTrials.gov API v2, selecting studies that post both protocol and SAP files and whose SAP actually defines estimands,
  - extracted text with section boundaries located without AI,
  - the SoA grid preserved with its footnote markers intact.
- **Design considerations.** Phase 1 is designed against five findings from the orientation walks (recorded in `DECISIONS.md`), not against the specification:
  1. **A heading does not tell you what a section contains.**
     - Estimand content has been found under headings like "Efficacy Criteria" and "Times of Analyses."
     - So Phase 1 locates section *boundaries* but never infers *content* from a title.
     - This is why boundary-finding (Phase 1) and content classification (Phase 2) are separate stages.
  2. **PDF addressability varies.**
     - Some protocols carry bookmarks, some only numbered headings in body text.
     - The locator handles both, and a protocol with no bookmarks degrades to heading detection rather than failing, the same split `read_pdf.py` already draws for the pinned standards.
  3. **Grids need structure-aware extraction.**
     - The SoA collapses to unreadable linear text under a plain extract; `fitz.find_tables()` recovers its rows, columns, and footnote markers.
     - The grid and its footnote links must be preserved.
  4. **A target concept may be absent.**
     - Only one of the three pinned examples defines any estimand at all.
     - Because "defines estimands" is itself unlabeled content (finding 1), acquisition selects for SAPs that define estimands.
     - Acquisition gathers candidates loosely and confirms estimand presence in a later, content-aware pass.
  5. **Worked examples are interpretive and can be wrong.**
     - Downstream scoring must be able to flag suspected-bad reference data rather than penalize a correct extraction that disagrees with a human error.
- **Verification:**
  - located sections match the PDF's real table of contents on manual check,
  - the SoA table is found with its footnote markers intact.

### Phase 2 — Classify

Identify the document type and what each section is about, with AI.

- **Produces:**
  - two prompts, one for document type and one for section topic, in versioned files rather than string literals,
  - the corpus grown to about three studies, since classification needs more than one example to mean anything,
  - a response cache keyed by prompt version and input hash, so development re-runs are free.
- **Verification:**
  - document type correct on all three studies,
  - section categories spot-checked against source.

### Phase 3 (sketch) — Extract into USDM shape

Turn classified content into USDM-conformant structures.

- **Produces:**
  - model output constrained to schemas generated from the pinned USDM spec, so output is USDM-shaped because it came from the standard rather than because a prompt asked,
  - every extracted fact carrying provenance.
- **Design consideration — chunking for prompting** (distinct from Phase 1's deterministic boundaries):
  - how a located section is split or retrieved when fed to the model (semantic chunking),
  - driven by prompt size and the "content spread across sections" finding in `BACKGROUND.md`.
- **Verification:**
  - every record validates against its schema and has non-null provenance,
  - both assertable in `tests/`.

### Phase 4 (sketch) — Build the graph and test whether it earns its place

Load the graph, link across documents, and answer the question the project exists to answer.

- **Produces:**
  - a Neo4j load
  - entity resolution across the protocol/SAP pair
  - cross-document links.
- **Verification:**
  - one Cypher query, checked by hand, *which protocol endpoints have no corresponding estimand in the SAP, and which section did each come from?*
  - If a plain text search answers it just as well, that is a finding worth recording, not a failure to hide.

### Phase 5 (sketch) — The Schedule of Activities, done properly

Reconstruct the timing graph from the flattened grid plus its footnotes and prose.

- **Produces:**
  - the SoA as a directed graph of scheduled activities and decision points connected by timing rules,
  - the page given to the model as an image (multimodal / computer-vision processing) rather than as extracted text:
    - text extraction loses the grid's spatial hierarchy,
    - consistent with the vision-based multimodal result recorded in `BACKGROUND.md`'s benchmarks,
  - a hand-built answer set.
- **Verification:**
  - bidirectional:
    - conformance-check the output,
    - and reconcile each USDM element back to the source text it came from,
  - score against `data/eval/` as precision and recall per case, not one accuracy number,
  - comparable published work sits around 76% clean, so expect it to be poor at first.

## Scope and constraints

- **Greenfield ingestion.**
  - No existing pipeline to inherit,
  - per-document-type handling is built here.
- **Prompts and context are composed, not enumerated.**
  - Variability is high: sponsor × therapeutic area × document type × section, and more.
  - A distinct prompt per combination scales as the *product* of the axes (thousands of files; one update touches hundreds).
  - Goal: define orthogonal axes and compose behavior from them, so the count scales as the *sum* (tens of files; one update touches one).
  - Axes will not be perfectly orthogonal; genuine cross-axis interactions are handled through **adjacency** (a pattern carried from prior work), not by enumerating the product.
  - The axes themselves are not yet known (there may be 3 or 13); they are expected to emerge from real extraction work, not fixed in advance.
- **When an extraction is wrong, measure whether the prompt or the retrieval is at fault.**
  - Is the dominant cause the prompt, or what got retrieved and linked in the first place?
  - Practitioner opinion leans prompt; this project produces evidence rather than inheriting the assumption.
  - The composition principle above is what makes the two axes separable enough to measure.
- **How far USDM reaches beyond the protocol is deliberately undecided.**
  - A protocol fits USDM, a SAP fits partly, an Investigator's Brochure largely does not.
  - Three approaches are visible, none chosen:
    - map only the parts that fit and drop the rest: simple, but silently loses content,
    - extend USDM through its own extension mechanism (IG 6.4): one model, but extensions are carried forever,
    - give non-protocol document types their own target model: fits each better, but makes cross-document linking a translation problem.
  - Settled by working through a real document, not decided in advance.
- **Whether a graph beats a text search is not assumed.**
  - Phase 4 tests it with one cross-document question,
  - a text search winning is a recorded finding.
- **Target hard cases**
  - each being content the document's own layout does not express: footnote conditionals on schedule cells;
  - patient-routing rules written as prose,
  - eligibility logic written as sentences,
  - the same thing under two names across two documents.
- **Deferred, not dropped.**
  - The design write-up is revisited after Phase 4, when positions can be grounded in what actually broke:
    - taxonomy,
    - prompt-library spec,
    - ontology governance,
    - evaluation-harness design
  - Phases 3 to 5 are sketches on purpose.

## Evaluation practice

- **Golden dataset entry:**
  - input, expert-validated expected output, and metadata (category, difficulty, edge-case flag).
  - Practitioner guidance suggests 20 to 50 reviewed items catches gross regressions.
- **Acceptance thresholds** are agreed before testing begins, and benchmarked at or above the performance of whatever process is being replaced.
- **Regression evaluation** re-runs a fixed set after every model, prompt, retriever, or tool change, compared against the last passing baseline.
- **Structure first, prose second.** Generation is anchored to a structured definition, not to model memory.
- **Named failure mode: silent quality loss.**
  - An edit makes output friendlier and drops a required element.
  - Fluent and wrong is worse than obviously broken.
