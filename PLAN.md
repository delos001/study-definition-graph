# study-definition-graph

## Context

A hands-on learning build. The goal is to understand, by building it, how AI
turns unstructured clinical documents into standards-conformant structured data
linked in a knowledge graph. Reading about this does not produce the
understanding; making it break does.

Two deliverables:

1. **`BACKGROUND.md`**, committed in the repo, so context does not have to be
   re-established every session.
2. **A working pipeline**, built in phases.

This plan is a starting point, not a contract. Where it names a tool you have
not used, Phase 0 exists to get hands on it before anything depends on it.
Phases 3 to 5 are deliberately sketches, to be designed when we reach them.

## Location and naming

New standalone repo at `C:\Users\delos\code\study-definition-graph`.

Not in `programming_sandbox`: this needs its own conda environment, a Docker
service, and a `data/` tree, none of which belong in a repo whose README reads
"miscellaneous data wrangling scripts." Splitting git history out later costs
more than starting clean.

`programming_sandbox\digital_data_flow\` is an empty directory. I will not
remove it without asking.

## Plain-English version of the problem

A clinical trial protocol is a long document. Buried in it is a table called the
Schedule of Activities: rows are things done to a patient, columns are visits,
an X means "do this thing at this visit."

That table is not the real structure. The real structure is a network: visits
connected by timing rules, activities hanging off visits, and decision points
that branch depending on the patient. The printed table is a flattened picture
of that network, and flattening loses things. Specifically it loses everything
written as a footnote or as prose: "only if liver enzymes are above twice
normal," "repeat every 21 days until the disease progresses," "may be done up to
7 days early."

USDM, the public CDISC data model, has a proper typed slot for every one of
those lost things. So the job is not "parse the table." The job is **rebuild the
network from a flattened picture plus the footnotes**, and put it in USDM's
shape.

That is the project. Everything else supports it.

## Glossary

- **USDM** (Unified Study Definitions Model): CDISC's data model describing a
  clinical study's *plan*. Version 4.0, released 3 June 2025. Published as an
  OpenAPI specification, so the exact shape of every object is machine-readable
  and downloadable.
- **Schedule of Activities (SoA)**: the visit-by-activity grid in a protocol.
- **SAP** (Statistical Analysis Plan): companion document describing how the
  data will be analyzed. Written later, often by different people, referring
  back to the protocol using different words for the same things. That mismatch
  is what makes linking two documents interesting.
- **Knowledge graph**: data stored as things (nodes) and relationships (edges)
  rather than rows. Good at questions requiring a chain of relationships.
- **Neo4j**: the most widely used graph database. Runs as a server. Ships with
  Neo4j Browser, a web page where you type a query and it draws the result as
  connected dots. That drawing is the reason to use it here: a broken link
  between two documents is obvious in a picture and nearly invisible in code.
- **Cypher**: Neo4j's query language. Roughly what SQL is to a relational
  database.
- **Entity resolution**: deciding whether two differently-named records are the
  same real thing. A protocol says "Intent-to-Treat Population," an SAP says
  "Full Analysis Set." Sometimes identical, sometimes not.
- **Provenance**: recording, for every extracted fact, where it came from and
  how it was produced.

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

USDM is five official CDISC standards (IG p.6), not one file. The project
originally held only the API specification, which is generated from the model
and discards every attribute definition, every cardinality, and the target class
of every relationship. Design work built on it was reasoning from the one
artifact with no semantics in it.

All five are now pinned to DDF-RA commit `aa303cb`, with the worked examples and
two crosswalks. Inventory and hashes in `data/manifests/`.

The UML deliverable is the one that mattered most. `dataStructure.yml` types every
ID reference (`epochId` to `StudyEpoch`, `activityIds` to `Activity`), which the
API specification leaves as a bare string. That is the edge list Phase 4 needs
and it is published, not something we have to infer.

### Mapping crosswalks: two taken, three dropped

`Documents/Mappings/` holds five crosswalks between USDM and other standards.

**Taken:**

- `ct-gov_mapping.xlsx`. Phase 1 pulls studies from ClinicalTrials.gov, and every
  study there already has structured registry fields. Six sheets map those fields
  to a USDM class, attribute and target path. Structured ground truth for part of
  every study, with no model call involved.
- `m11_mapping.xlsx`. ICH M11 is an authoring template our source protocols are
  not written in, so this is reference material rather than a pipeline input.
  Kept because it is small and holding the complete source is cheaper than
  re-deciding later.

**Dropped permanently**, so this does not resurface:

- `ctis_mapping.xlsx`. EU CTIS registry submission. Out of scope.
- `cpt_mapping.xlsx`. TransCelerate authoring template. Our sources do not use it.
- `sdtm_mapping.xlsx`. Maps USDM to SDTM, which is downstream of this project and
  runs in the opposite direction.

One caveat resolved rather than carried: `Documents/README.md` calls all five
provisional and v3.1x-era. That README is stale. Both files we took declare USDM
v4.0.0 in their own `Readme` sheet, and `m11_mapping` is aligned to the M11
Updated Step 2 Draft of 14 March 2025, matching IG p.8.

### Standards outside CDISC, added 2026-08-18

The source sweep had stopped at one GitHub repository. Widening it turned up two
bodies of guidance the project needs and did not hold. Both are now pinned, with
manifests and hashes.

**ICH M11 CeSHarP, Step 4, adopted 2025-11-19.** Three documents:
Guideline (6pp), Template (67pp), Technical Specification (245pp). Taken from
ICH as the primary body; EMA hosts the same three at Step 5. The Template
defines what sections a protocol has and what belongs in each, which Phase 1
section location and Phase 2 section classification both need. The Technical
Specification defines 186 protocol data elements with definition, data type,
cardinality and conformance, and carries NCI C-codes, the same code system USDM
uses. It is structurally the M11 counterpart of the USDM data dictionary.

Earlier reasoning had dismissed M11 as reference-only because our source
protocols are not authored in it. That was too narrow: the template is useful as
a description of protocol structure whether or not a given protocol follows it.

**ICH E9(R1) Estimands Addendum, Step 4, 2019-12-03** (22pp). Phase 4 gates on
the SAP defining estimands. USDM models the estimand framework structurally but
does not define it; E9(R1) does, and §A.3.3 is the attribute definition.

**Drift between bodies is expected, not a defect.** USDM v4.0 (2025-06-03) is
aligned to an M11 Step 2 draft, and `m11_mapping.xlsx` targets the Updated Step 2
Draft of 2025-03-14. M11 went Step 4 eight months later. USDM and M11 are
maintained by different organisations on different release cycles, so a v4.0 pin
pointing at its contemporaneous M11 draft is internally consistent. Recorded in
both manifests so no future session tries to reconcile it.

**Still unverified:** whether M11 Step 4, or the EU's Step 5 listing, creates an
obligation applicable to protocol authors and on what timeline. `BACKGROUND.md`
carries a design constraint saying M11 is "a regulatory expectation, not a
verified mandate". That needs re-checking, not inverting.

### Declined deliberately: section addressing for the M11 PDFs

None of the three M11 PDFs carries embedded bookmarks, so `scripts/read_pdf.py`
cannot address them by section. Supporting that would need a second, different
mechanism: parsing a printed contents page or detecting headings by font size.
It is not a parameterisation of what exists.

**Not doing it.** The Technical Specification is a reference of 186 data elements
rather than a linear read, so term lookup is the access pattern it actually
wants, and `--find` already provides that: a term search lands on one or two
pages. Building section navigation would serve an access pattern the document
does not have. Recorded here as declined rather than overlooked.

### Routing complexity, and where LangGraph earns its place

Counting the actual branch points in Phases 0 to 4:

- Section category selects which extraction prompt. That is a dictionary lookup,
  not routing.
- Confidence below a threshold sends a record to a review queue. One `if`.
- Entity resolution goes candidate, then adjudicate, then merge or queue. One
  branch.

No cycles. Nothing where the model decides what happens next. That is a fan-out
over a list with a dispatch table, and LangGraph around it would be scaffolding
on a `for` loop.

A real cycle appears exactly once, in Phase 5: generate, score against a
checklist, and if it fails, revise the prompt and regenerate. Cycles are what
LangGraph is for.

**Decision:** write every stage as a pure function taking and returning an
explicit state object, in plain Python. Adopt LangGraph at Phase 5. Written this
way the migration is mechanical, since each function becomes a node. The cost of
deferring is near zero; the cost of adopting now is debugging two unfamiliar
things at once when only one of them is the subject.

**On cost:** LangGraph adds zero model calls. It is orchestration, not
inference. Spend is driven by call count and prompt size, identical either way.
One real caveat: a state design that passes the whole accumulated state into
every prompt does inflate tokens. Avoidable, but it is the one way this choice
touches cost.

### Cost estimate

Current pricing, checked rather than recalled:

| Model | Input per M | Output per M |
| --- | --- | --- |
| Opus 5 | $5.00 | $25.00 |
| Sonnet 5 | $3.00 ($2.00 intro through 2026-08-31) | $15.00 ($10.00 intro) |
| Haiku 4.5 | $1.00 | $5.00 |

One clean pass over 3 studies is roughly 1.6M input and 270K output tokens:
about **$6 on Sonnet 5**, about **$15 on Opus 5**. Development iteration
multiplies that, but cache reads cost about 0.1x input, and the disk response
cache makes re-runs free. Realistic project total is **tens of dollars**. Cost
is not a reason to pick one architecture over another here.

Working model assignment, to be tuned: `claude-haiku-4-5` for classification,
`claude-sonnet-5` for extraction, `claude-opus-5` for the Phase 5 hard cases.

### Static copy versus live API

You raised this. It splits cleanly.

**Call live:**
- **ClinicalTrials.gov API v2**, for finding and downloading protocol and SAP
  PDFs. Maintained, free, no snapshot worth keeping.
- **The DDF conformance validation endpoint.** The CDISC reference
  implementation exposes an endpoint that checks whether a USDM document is
  conformant. If publicly reachable, calling it beats reimplementing the rules.
  Phase 0 confirms reachability without credentials; if it needs a key, we fall
  back to the published rule specifications.

**Pin a downloaded copy:**
- **The USDM model specification.** This is the one place where "always fetch
  latest" is actively harmful. USDM has shipped four major versions in under
  three years (v1.0 Aug 2022, v2.0 Jun 2023, v3.0 Apr 2024, v4.0 Jun 2025) plus
  errata on v3.0 and v4.0. If a new version lands mid-project, your extraction
  output silently changes shape and you cannot tell whether a new failure came
  from your prompt or from the standard moving. Same instinct as pinning a
  library version. We record the commit and update deliberately.

**CDISC Library: checked and closed.** A valid API key exists on a non-member
subscription. `GET https://library.cdisc.org/api/mdr/products` returns
`"Members-only content"` — that is the top-level catalog, so the tier is gated
out of MDR content generally, not out of USDM specifically. The key
authenticates (a bad key returns 401), the tier simply grants nothing.

Consequence: none. The `usdm` PyPI package stays out of scope, and the model,
controlled terminology, and conformance rule specifications all come from the
public `cdisc-org/DDF-RA` repo, which was already the plan. **Membership is not
worth buying for this project.**

## Deliverable 1: BACKGROUND.md

Written. See [BACKGROUND.md](BACKGROUND.md).

De-identified deliberately: no company, no people, no locations, no
partnerships. Facts originally sourced from conversations are reframed as design
constraints, target problems, or open questions, which is what they actually are
for this project. Everything else is public standards material or published
research.

## Deliverable 2: the pipeline

### Repository layout

```
study-definition-graph/
  README.md
  BACKGROUND.md
  environment.yml
  docker-compose.yml         # neo4j
  .env.example
  data/
    raw/                     # never modified after download
    interim/                 # parsed pages, sections
    processed/               # extracted entities, graph load files
    eval/                    # hand-built correct answers
  prompts/                   # one file per prompt, versioned
  src/sdg/
  scripts/
  tests/
```

Working conventions for this tree (immutability of `data/raw/`, manifests,
source file style) live in `CLAUDE.md`.

### Build phases

**Phase 0: foundation and orientation.** No pipeline work.
- `git init`, conda env, repo skeleton, `BACKGROUND.md`.
- Neo4j running in Docker. You open Neo4j Browser, create a few nodes and edges
  by hand, and query them. The point is to be comfortable with what a graph
  database is before anything depends on it.
- Download and pin USDM v4.0 artifacts to `data/raw/usdm_v4/`, recording the
  commit.
- Write the loader that reads `USDM_API.json` and lists USDM classes and their
  fields. This also verifies the class names used in `BACKGROUND.md`.
- Check whether the DDF conformance validation endpoint is publicly reachable.
- Install CORE and try to run it. CDISC documents CORE as MIT-licensed and free
  to members and non-members, but also documents the USDM rules as living in the
  CDISC Library, which this subscription cannot reach. Those two facts are in
  tension and only a real run resolves it. If CORE bundles or fetches the rules
  without a member key, conformance checking works. If not, we validate against
  schemas generated from `USDM_API.json` and treat `Deliverables/RULES/` as the
  reference. Neither outcome blocks anything.

**Phase 1: get documents, and read them.**
- Query ClinicalTrials.gov API v2 live for studies posting *separate* protocol
  and SAP PDFs rather than the combined form. Separate files make classifying a
  document a real decision.
- Selection criterion applied here, not later: the SAP must actually define
  estimands. Not all do, and Phase 4 depends on them.
- Extract text and locate sections. No AI in this stage, deliberately: keeping
  it deterministic means every later failure is attributable to either reading
  or prompting.

**Phase 2: classify.**
- Two prompts: what type of document is this, and what is each section about.
- Prompts live in versioned files, not as strings inside code.
- Grow the corpus to about 3 studies here, since classification needs more than
  one example to mean anything.
- Add response caching keyed by prompt version and input hash, so development
  re-runs are free.

**Phase 3 (sketch): extract into USDM shape.** Force model output to match
schemas generated from the pinned `USDM_API.json`, so output is USDM-shaped
because it came from the standard rather than because a prompt asked nicely.
Every extracted fact carries provenance.

**Phase 4 (sketch): build the graph and test whether it earns its place.** Load
Neo4j, resolve entities across the protocol/SAP pair, build cross-document
links, then run the question the project exists to answer.

**Phase 5 (sketch): the Schedule of Activities, done properly.** The real
target, last because everything above is scaffolding for it. Reconstruct the
timing graph from the flattened table *plus* footnotes and prose. Published
evidence says to give the model the page as an image rather than as extracted
text, because text extraction loses spatial hierarchy. Score against a
hand-built answer set.

### Verification per phase

- **P0**: Neo4j Browser reachable at `localhost:7474` and you have run a query
  by hand. `python -m sdg.usdm_spec --list-classes` prints class names read from
  the pinned file.
- **P1**: located sections match the PDF's real table of contents on manual
  check, and the SoA table is found with its footnote markers intact.
- **P2**: document type correct on all 3 studies; section categories
  spot-checked against source.
- **P3**: every extracted record validates against its schema and has non-null
  provenance. Both assertable in `tests/`.
- **P4**: one Cypher query, answered correctly and checked by hand: *which
  protocol endpoints have no corresponding estimand in the SAP, and which
  section did each come from?* Two documents, three relationships. If a plain
  text search answers it just as well, that is a real finding worth recording
  rather than a failure.
- **P5**: bidirectional. Conformance-check the output, *and* reconcile each USDM
  element back to the source text it came from. Score against `data/eval/` as
  precision and recall per case, not one accuracy number. Comparable published
  work sits around 76% clean, so expect it to be bad at first.

## Next session, in order

**1. Build `docs/sources.md`. Done 2026-08-18.** One navigation document covering
every pinned artifact: what question it answers, how to read it, and whether it
has been read or is still unexamined. `CLAUDE.md` now points at it at session
start.

One departure from the plan as written. It was to *replace* `docs/usdm_ig_map.md`.
It does not. That file holds a per-section read ledger for a 119-page guide, and
folding that into a per-artifact index would coarsen it from 54 rows to one.
`sources.md` links to it instead. Same reasoning applies to any future document
with its own internal ledger: the index points at them, it does not absorb them.

The manifests in `data/manifests/` do not do this job and are not meant to. They
record url, format, role and sha256, which answers "is this file authentic and
where did it come from". They do not answer "which file holds my answer".

`docs/sources.md` also absorbs a second job, agreed 2026-08-18: **a registry of
resources that exist and we do not hold.** The problem it solves is demonstrated,
not hypothetical. `cdisc-org/cdisc-jsonata-rules` was found by chance while
checking something else, and it is the reason the CORE scope question stayed open
for weeks; nothing in the repo would have led a session there.

Two sections, one file, because the question a session asks is "where do I find
X" and it should not have to know in advance whether X is pinned.

Format rules, which exist to stop it becoming a bibliography:

- **Every entry carries a decision, never a description.** Three states only:
  *in use* (with where), *not taken* (with the reason, so it does not resurface),
  *unassessed* (name, location, one line on why it might matter, date last
  looked at, and nothing else). The cap on the third tier is what keeps it light.
- **Only things actually reviewed go in.** Named-but-unchecked candidates are not
  entries. An entry states what was observed and when, not what the thing is,
  because a one-line characterisation of an unread resource is the same
  unlabelled-assertion failure that was just cut out of `BACKGROUND.md`.
- **It is never read at session start.** `CLAUDE.md`'s session-start list must not
  include it. It is consulted when a question arises. That single constraint is
  the difference between a pointer file and context bloat.

Entries ready to write, all verified 2026-08-18:

| Resource | State | Observed |
| --- | --- | --- |
| `cdisc-org/cdisc-jsonata-rules` | unassessed, do not pin | 98 `DDF000NN` JSONata rules with fixtures. 93 of the 210 v4-applicable spec rules have an implementation, 44%. Five implemented rules are absent from our pinned spec, one (`DDF00262`) beyond its range, so the rules are ahead of the spec. 8.5 MB, mostly ~1 MB test fixtures per rule. No README, no licence, last pushed 2025-12-19. Pull individual rule files at point of use. |
| `cdisc-org/cdisc-rules-engine` | in use at Phase 0 | The CORE engine. Already scheduled. Version-pin as tooling, not as hashed data. |
| `cdisc-org/usdm` | not taken | Requires `CDISC_API_KEY` for CDISC Library CT and BC lookups, confirmed from its README. Its `usdm_excel` importer is the tool that generated our three worked examples, so its documented workbook format is worth reading even though the package cannot run here. |
| `cdisc-org/usdm_api` | unassessed | "A simple DDF emulation", ships a Dockerfile. Reframes the Phase 0 question from "is a conformance endpoint publicly reachable" to "can we run one locally", same pattern as Neo4j. |
| `cdisc-org/cdisc-open-rules` | not taken | `CORE-000NNN` YAML rules, a different ID space from `DDF000NN`. Not USDM. |
| ClinicalTrials.gov field definitions | deferred to Phase 1 | Needed to use `ct-gov_mapping.xlsx`; that API is called live by decision. |

Building the index is also the first time the sources get checked against each
other. Two discrepancies are now closed, two remain unchased:

- **Class counts. Closed, measured 2026-08-18.** `dataStructure.yml` holds 86
  classes: 80 `Modifier: Concrete` and 6 `Abstract` (`Identifier`,
  `PopulationDefinition`, `QuantityRange`, `ScheduledInstance`, `StudyDesign`,
  `SyntaxTemplate`). `dataDictionary.MD` holds 84, the same set minus
  `ExtensionAttribute` and `ExtensionClass`, consistent with IG §6.4 placing the
  extension mechanism outside the logical model. `USDM_API.json` holds 164
  component schemas reducing to 83 base names after stripping `-Input`/`-Output`:
  the 80 concrete classes plus `Wrapper`, `HTTPValidationError` and
  `ValidationError`, which are API plumbing rather than model classes. No
  abstract class appears in the API. `extensionAttributes` is present on exactly
  those 80 concrete classes, which corrects the "81" previously recorded in
  `docs/usdm_ig_map.md`.
- **The 14 UML diagrams are unindexed and ungreppable.** None has been viewed.
  `Extension.png` and `Timeline.png` are the two the IG points at and cannot
  render in extracted text.
- **Codelist references. Closed, measured 2026-08-18.** Every one of the 517
  distinct NCI C-codes appearing in `dataDictionary.MD` also appears in
  `USDM_CT.xlsx`. Nothing dangles. `USDM_CT.xlsx` carries 634 codes in total, the
  extra 117 being value-set terms rather than class and attribute identifiers.
- **CORE's actual scope is an open question.** 260 rules, unread. The working
  assumption was that CORE exists to check referential integrity the schema
  cannot express. Then `dataStructure.yml` turned out to type every reference.
  What CORE covers is one file read away.

Four further claims arrive here from `BACKGROUND.md`, which was stripped of all
USDM technical content on 2026-08-18 (see below). Each was carried as an
unverified assertion and each is settled by reading a pinned file:

- **Conformance rules are reportedly expressed in JSONata**, not the YAML used
  for other CDISC rule sets. Effectively single-source. `USDM_CORE_Rules.xlsx`
  settles it.
- **The CORE rule set is substantially but not fully authored.** No percentage
  should be quoted until the 260 rows are read. Folds into the CORE scope item
  above.
- **JSON-Schema validation of USDM JSON is an open CDISC issue**, so schema
  validation is complementary to the rules engine rather than a substitute. If
  true this shapes the Phase 3 validation design, so it needs confirming.
- **API version and model version are decoupled**, with V5 endpoints reportedly
  serving USDM 4.0. Checkable in `USDM_API.json` directly.

One claim was dropped rather than moved: "check attribute names against the
pinned `USDM_API.json` rather than against names in circulation from CDISC's
reference Python package". That is already the standing rule in `CLAUDE.md`, and
restating it elsewhere is how rules drift.

### Why BACKGROUND.md no longer describes USDM

`BACKGROUND.md` is read at session start, before any source file is opened. A
USDM summary sitting there is read first and therefore forms a position in
advance of the evidence, which is the exact failure the grounding rule exists to
prevent. Labelling the summary would not fix that; only removing it does.

The test now applied to that file: **if reading a source document could change a
sentence, the sentence does not belong in `BACKGROUND.md`.** It keeps why the
project exists, the problem in plain terms, the target hard cases, design
constraints, evaluation practice and published prior art. All USDM structure is
gone, along with a file list that duplicated `data/manifests/`.

**2. The Alexion walk.** Trace one activity end to end through
`data/raw/usdm_examples/Alexion_NCT04573309_Wilsons/`: from the printed Schedule
of Activities in the protocol PDF, to the row a human wrote in the `mainTimeline`
sheet, to the USDM objects it became in the JSON.

The point is not the artifact. It is that reading a schema does not tell you how
it applies to a protocol, and this is the only place where the same activity can
be seen in all three forms at once. It also defines what Phases 1 to 3 actually
have to reproduce, which is a better input to designing them than a spec is.

**Not next:** `src/sdg/usdm_spec.py`. It was designed against `USDM_API.json`
before the UML deliverable was found. `dataStructure.yml` supplies what that
design was going to reconstruct, so the loader is now smaller and needs
redesigning before it is written.

## Open items

1. **Deferred, not dropped:** the design write-up (taxonomy, prompt library
   spec, ontology governance, evaluation harness design). Revisit after Phase 4,
   when positions can be grounded in what actually broke.
2. **Expect this plan to change.** Phases 3 to 5 are sketches on purpose.
3. `programming_sandbox\digital_data_flow\` is empty and now unused. Removing it
   needs your say-so.
