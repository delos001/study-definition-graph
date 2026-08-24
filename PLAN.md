# study-definition-graph

## Context

Why the project exists is in `BACKGROUND.md`. This file is the build sequence and the record of what was decided and why.

This plan is a starting point, not a contract. Where it names a tool you have not used, Phase 0 exists to get hands on it before anything depends on it. Phases 3 to 5 are deliberately sketches, to be designed when we reach them.

## Location and naming

Standalone repo, not a folder inside `programming_sandbox`: this needs its own conda environment, a Docker service and a `data/` tree, none of which belong in a repo whose README reads "miscellaneous data wrangling scripts." Splitting git history out later costs more than starting clean.

## Decisions made so far

| Decision | Choice | Why |
| --- | --- | --- |
| Output | Working code first | Design write-up deferred, not dropped. |
| Corpus | Protocol + SAP for the same study, growing to about 3 studies | Smallest set where classifying a document is a real decision and linking across documents is real. |
| Graph store | Neo4j in Docker | Docker 29.6.2 already installed. The visual browser is the main argument. |
| Neo4j version | Pinned to `5.26.29-community` (5.26 LTS) | The `5-community` tag floats to the newest 5.x on every pull. Same reasoning as the pinned USDM spec: a version moving mid-project makes a failure unattributable. Digest recorded in `docker-compose.yml`. |
| Standard | USDM v4.0, pinned | Current published version. |
| Model provider | Anthropic (Claude) | Key already in use in `langgraph_sandbox/spike/spike.py` via `langchain_anthropic`. |
| Orchestration | Plain Python through Phase 4, LangGraph at Phase 5 | See the routing-complexity assessment below. |
| Source material | All five official USDM standards pinned, plus CDISC's worked examples | See below. The API specification alone was not enough. |

### Which USDM sources we hold, and why

USDM is five official CDISC standards (IG p.6), not one file. The project originally held only the API specification, which is generated from the model and discards every attribute definition, every cardinality, and the target class of every relationship. Design work built on it was reasoning from the one artifact with no semantics in it.

All five are now pinned to DDF-RA commit `aa303cb`, with the worked examples and two crosswalks. Inventory and hashes in `data/manifests/`.

The UML deliverable is the one that mattered most. `dataStructure.yml` types every ID reference (`epochId` to `StudyEpoch`, `activityIds` to `Activity`), which the API specification leaves as a bare string. That is the edge list Phase 4 needs and it is published, not something we have to infer.

### Mapping crosswalks: two taken, three dropped

`Documents/Mappings/` holds five crosswalks between USDM and other standards.

**Taken:**

- `ct-gov_mapping.xlsx`. Phase 1 pulls studies from ClinicalTrials.gov, and every study there already has structured registry fields. Six sheets map those fields to a USDM class, attribute and target path. Structured ground truth for part of every study, with no model call involved.
- `m11_mapping.xlsx`. ICH M11 is an authoring template our source protocols are not written in, so this is reference material rather than a pipeline input. Kept because it is small and holding the complete source is cheaper than re-deciding later.

**Dropped permanently**, so this does not resurface:

- `ctis_mapping.xlsx`. EU CTIS registry submission. Out of scope.
- `cpt_mapping.xlsx`. TransCelerate authoring template. Our sources do not use it.
- `sdtm_mapping.xlsx`. Maps USDM to SDTM, which is downstream of this project and runs in the opposite direction.

One caveat resolved rather than carried: `Documents/README.md` calls all five provisional and v3.1x-era. That README is stale. Both files we took declare USDM v4.0.0 in their own `Readme` sheet, and `m11_mapping` is aligned to the M11 Updated Step 2 Draft of 14 March 2025, matching IG p.8.

### Standards outside CDISC, added 2026-08-18

The source sweep had stopped at one GitHub repository. Widening it found two standards the project needs and did not hold. Both are pinned; `docs/sources.md` says what each answers.

**ICH M11 CeSHarP**, Step 4, adopted 2025-11-19. Earlier reasoning dismissed it as reference-only because our protocols are not authored in it. Too narrow: its template describes protocol structure whether or not a given protocol follows it, and Phases 1 and 2 need that.

**ICH E9(R1)**, Step 4, 2019-12-03. Phase 4 gates on the SAP defining estimands. USDM models the framework without defining it; E9(R1) defines it.

**Drift between the two bodies is expected, not a defect.** USDM v4.0 is aligned to an M11 Step 2 draft; M11 went Step 4 eight months later. Different organisations, different release cycles. Do not try to reconcile them.

**Unverified:** whether M11 Step 4 creates an obligation on protocol authors, and by when. `BACKGROUND.md` still calls it an expectation rather than a mandate. Re-check before relying on either reading.

### Section addressing, fixed 2026-08-18

`read_pdf.py` returned whole pages for a section, so a section starting mid-page arrived with the previous one attached, and one spilling past a page break was silently cut short. E9(R1) A.3.3 returned 1 of its 4 estimand attributes with no sign the rest existed. In the USDM IG, 32 of 54 sections shared a page range with another, and 4.22 and 4.23 returned byte-identical text.

The cause was one line: the section end was set to the page before the next section starts, which discards whatever the section holds on that page. It now ends on that page and `read_pdf.py` trims both shared pages at the headings, matching on the section number because the IG puts number and title on one line while E9(R1) splits them. Where a heading cannot be found the output says so rather than guessing, since a boundary chosen silently is the failure being fixed.

All 66 sections across both bookmarked documents extract cleanly, each starting at its own heading. `docs/usdm_ig_map.md` was regenerated, since 40 of its 52 page ranges changed.

### Declined: section addressing for the M11 PDFs

The M11 PDFs carry no bookmarks, so `read_pdf.py` cannot address them by section. Supporting that needs a different mechanism, not a parameterisation of what exists. Not doing it: the Technical Specification is a lookup reference rather than a linear read, so `--find` is the access pattern it wants and a term search lands on one or two pages.


### Routing complexity, and where LangGraph earns its place

Counting the actual branch points in Phases 0 to 4:

- Section category selects which extraction prompt. That is a dictionary lookup, not routing.
- Confidence below a threshold sends a record to a review queue. One `if`.
- Entity resolution goes candidate, then adjudicate, then merge or queue. One branch.

No cycles. Nothing where the model decides what happens next. That is a fan-out over a list with a dispatch table, and LangGraph around it would be scaffolding on a `for` loop.

A real cycle appears exactly once, in Phase 5: generate, score against a checklist, and if it fails, revise the prompt and regenerate. Cycles are what LangGraph is for.

**Decision:** write every stage as a pure function taking and returning an explicit state object, in plain Python. Adopt LangGraph at Phase 5. Written this way the migration is mechanical, since each function becomes a node. The cost of deferring is near zero; the cost of adopting now is debugging two unfamiliar things at once when only one of them is the subject.

**On cost:** LangGraph adds zero model calls. It is orchestration, not inference. Spend is driven by call count and prompt size, identical either way. One real caveat: a state design that passes the whole accumulated state into every prompt does inflate tokens. Avoidable, but it is the one way this choice touches cost.

### Cost estimate

Current pricing, checked rather than recalled:

| Model | Input per M | Output per M |
| --- | --- | --- |
| Opus 5 | $5.00 | $25.00 |
| Sonnet 5 | $3.00 ($2.00 intro through 2026-08-31) | $15.00 ($10.00 intro) |
| Haiku 4.5 | $1.00 | $5.00 |

One clean pass over 3 studies is roughly 1.6M input and 270K output tokens: about **$6 on Sonnet 5**, about **$15 on Opus 5**. Development iteration multiplies that, but cache reads cost about 0.1x input, and the disk response cache makes re-runs free. Realistic project total is **tens of dollars**. Cost is not a reason to pick one architecture over another here.

Working model assignment, to be tuned: `claude-haiku-4-5` for classification, `claude-sonnet-5` for extraction, `claude-opus-5` for the Phase 5 hard cases.

### Static copy versus live API

You raised this. It splits cleanly.

**Call live:**
- **ClinicalTrials.gov API v2**, for finding and downloading protocol and SAP PDFs. Maintained, free, no snapshot worth keeping.
- **The DDF conformance validation endpoint.** The CDISC reference implementation exposes an endpoint that checks whether a USDM document is conformant. If publicly reachable, calling it beats reimplementing the rules. Phase 0 confirms reachability without credentials; if it needs a key, we fall back to the published rule specifications.

**Pin a downloaded copy:**
- **The USDM model specification.** This is the one place where "always fetch latest" is actively harmful. USDM has shipped four major versions in under three years (v1.0 Aug 2022, v2.0 Jun 2023, v3.0 Apr 2024, v4.0 Jun 2025) plus errata on v3.0 and v4.0. If a new version lands mid-project, your extraction output silently changes shape and you cannot tell whether a new failure came from your prompt or from the standard moving. Same instinct as pinning a library version. We record the commit and update deliberately.

**CDISC Library: checked and closed.** A valid API key exists on a non-member subscription. `GET https://library.cdisc.org/api/mdr/products` returns `"Members-only content"`. That is the top-level catalog, so the tier is gated out of MDR content generally, not out of USDM specifically. The key authenticates (a bad key returns 401), the tier simply grants nothing.

Consequence: none. The `usdm` PyPI package stays out of scope, and the model, controlled terminology, and conformance rule specifications all come from the public `cdisc-org/DDF-RA` repo, which was already the plan. **Membership is not worth buying for this project.**

### Source navigation, built 2026-08-18

`docs/sources.md` answers "which file holds my answer", which the manifests were never meant to. It has two halves: every pinned file with the question it answers and whether it has been read, then a registry of resources that exist and we do not hold. That registry is the record of what was already reviewed and rejected, so a later session does not re-litigate it; the entries live there, not here.

Three format rules keep the registry from turning into a bibliography: every entry carries a decision rather than a description; only resources actually reviewed are entered; and the second half is never read at session start.

It does not replace `docs/usdm_ig_map.md`, which the original plan said it would. That file holds a per-section read ledger for a 119-page guide, and folding 54 rows into one index row would coarsen it. The index links to it instead, and the same applies to any future document with its own ledger.

Building it also closed two of the four discrepancies below.

Building it settled two things by measurement:

- **Class counts.** The three files do not disagree. `dataStructure.yml` has 86 classes, 80 concrete and 6 abstract. `dataDictionary.MD` has 84, the same set minus the two extension classes, which IG 6.4 places outside the logical model. `USDM_API.json` has the 80 concrete ones plus `Wrapper`, `HTTPValidationError` and `ValidationError`, which are API plumbing. No abstract class serialises. This corrected the "81 classes" recorded in `docs/usdm_ig_map.md`.
- **Codelist references resolve.** All 517 NCI codes in `dataDictionary.MD` appear in `USDM_CT.xlsx`. Nothing dangles.


## The pipeline

### Build phases

**Phase 0: foundation and orientation.** No pipeline work.
- `git init`, conda env, repo skeleton, `BACKGROUND.md`.
- Neo4j running in Docker. You open Neo4j Browser, create a few nodes and edges by hand, and query them. The point is to be comfortable with what a graph database is before anything depends on it.
- Download and pin USDM v4.0 artifacts to `data/raw/usdm_v4/`, recording the commit.
- Write the loader that reads `USDM_API.json` and lists USDM classes and their fields. This also verifies the class names used in `BACKGROUND.md`.
- Check whether the DDF conformance validation endpoint is publicly reachable.
- Install CORE and try to run it. CDISC documents CORE as MIT-licensed and free to members and non-members, but also documents the USDM rules as living in the CDISC Library, which this subscription cannot reach. Those two facts are in tension and only a real run resolves it. If CORE bundles or fetches the rules without a member key, conformance checking works. If not, we validate against schemas generated from `USDM_API.json` and treat `Deliverables/RULES/` as the reference. Neither outcome blocks anything.

**Phase 1: get documents, and read them.**
- Query ClinicalTrials.gov API v2 live for studies posting *separate* protocol and SAP PDFs rather than the combined form. Separate files make classifying a document a real decision.
- Selection criterion applied here, not later: the SAP must actually define estimands. Not all do, and Phase 4 depends on them.
- Extract text and locate sections. No AI in this stage, deliberately: keeping it deterministic means every later failure is attributable to either reading or prompting.

**Phase 2: classify.**
- Two prompts: what type of document is this, and what is each section about.
- Prompts live in versioned files, not as strings inside code.
- Grow the corpus to about 3 studies here, since classification needs more than one example to mean anything.
- Add response caching keyed by prompt version and input hash, so development re-runs are free.

**Phase 3 (sketch): extract into USDM shape.** Force model output to match schemas generated from the pinned `USDM_API.json`, so output is USDM-shaped because it came from the standard rather than because a prompt asked nicely. Every extracted fact carries provenance.

**Phase 4 (sketch): build the graph and test whether it earns its place.** Load Neo4j, resolve entities across the protocol/SAP pair, build cross-document links, then run the question the project exists to answer.

**Phase 5 (sketch): the Schedule of Activities, done properly.** The hardest single case in a protocol, last because it needs everything above it working first. Reconstruct the timing graph from the flattened table *plus* footnotes and prose. Published evidence says to give the model the page as an image rather than as extracted text, because text extraction loses spatial hierarchy. Score against a hand-built answer set.

### Verification per phase

- **P0**: Neo4j Browser reachable at `localhost:7474` and you have run a query by hand. `python -m sdg.usdm_spec --list-classes` prints class names read from the pinned file.
- **P1**: located sections match the PDF's real table of contents on manual check, and the SoA table is found with its footnote markers intact.
- **P2**: document type correct on all 3 studies; section categories spot-checked against source.
- **P3**: every extracted record validates against its schema and has non-null provenance. Both assertable in `tests/`.
- **P4**: one Cypher query, answered correctly and checked by hand: *which protocol endpoints have no corresponding estimand in the SAP, and which section did each come from?* Two documents, three relationships. If a plain text search answers it just as well, that is a real finding worth recording rather than a failure.
- **P5**: bidirectional. Conformance-check the output, *and* reconcile each USDM element back to the source text it came from. Score against `data/eval/` as precision and recall per case, not one accuracy number. Comparable published work sits around 76% clean, so expect it to be bad at first.

## Next session, in order

Phase 0 scaffolding is finished. What follows is pipeline work.

**1. The Alexion walk.** Trace one activity end to end through `data/raw/usdm_examples/Alexion_NCT04573309_Wilsons/`: from the printed Schedule of Activities in the protocol PDF, to the row a human wrote in the `mainTimeline` sheet, to the USDM objects it became in the JSON.

The point is not the artifact. It is that reading a schema does not tell you how it applies to a protocol, and this is the only place where the same activity can be seen in all three forms at once. It also defines what Phases 1 to 3 actually have to reproduce, which is a better input to designing them than a spec is.

**2. Then design Phase 1** against what the walk actually showed, rather than against the specification.

### Still open, none of it blocking

- **The 14 UML class diagrams have never been opened.** They are images, so nothing can grep them. `DDF_USDM_Model_Informative.pdf` now covers the same ground in searchable form and may make them redundant; nobody has checked.
- **What the CORE rules actually check.** 93 of the 210 v4-applicable rules are implemented as JSONata in `cdisc-org/cdisc-jsonata-rules`, which also confirms the rules are JSONata rather than YAML. None has been read.
- **Two claims evicted from `BACKGROUND.md` are still unverified**: whether JSON-Schema validation of USDM JSON is an open CDISC issue, and whether API version and model version are decoupled. Both are checkable in `USDM_API.json`.


**Not next:** `src/sdg/usdm_spec.py`. It was designed against `USDM_API.json` before the UML deliverable was found. `dataStructure.yml` supplies what that design was going to reconstruct, so the loader is now smaller and needs redesigning before it is written.

## Open items

1. **Deferred, not dropped:** the design write-up (taxonomy, prompt library spec, ontology governance, evaluation harness design). Revisit after Phase 4, when positions can be grounded in what actually broke.
2. **Expect this plan to change.** Phases 3 to 5 are sketches on purpose.
3. `programming_sandbox\digital_data_flow\` is empty and now unused. Removing it needs your say-so.
