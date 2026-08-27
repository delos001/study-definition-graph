# Decisions

The document contains the record of choices made and why. This is an append-only log: entries are added as decisions are made and are not rewritten as work progresses.

For the build plan itself, see `PLAN.md`;
For the problem and background, see `BACKGROUND.md`.

## Foundational choices

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

## Which USDM sources we hold, and why

USDM is five official CDISC standards (IG p.6), not one file. The project originally held only the API specification, which is generated from the model and discards every attribute definition, every cardinality, and the target class of every relationship. Design work built on it was reasoning from the one artifact with no semantics in it.

All five are now pinned to DDF-RA commit `aa303cb`, with the worked examples and two crosswalks. Inventory and hashes in `data/manifests/`.

The UML deliverable is the one that mattered most. `dataStructure.yml` types every ID reference (`epochId` to `StudyEpoch`, `activityIds` to `Activity`), which the API specification leaves as a bare string. That is the edge list Phase 4 needs and it is published, not something we have to infer.

## Mapping crosswalks: two taken, three dropped

`Documents/Mappings/` holds five crosswalks between USDM and other standards.

**Taken:**

- `ct-gov_mapping.xlsx`. Phase 1 pulls studies from ClinicalTrials.gov, and every study there already has structured registry fields. Six sheets map those fields to a USDM class, attribute and target path. Structured ground truth for part of every study, with no model call involved.
- `m11_mapping.xlsx`. ICH M11 is an authoring template our source protocols are not written in, so this is reference material rather than a pipeline input. Kept because it is small and holding the complete source is cheaper than re-deciding later.

**Dropped permanently**, so this does not resurface:

- `ctis_mapping.xlsx`. EU CTIS registry submission. Out of scope.
- `cpt_mapping.xlsx`. TransCelerate authoring template. Our sources do not use it.
- `sdtm_mapping.xlsx`. Maps USDM to SDTM, which is downstream of this project and runs in the opposite direction.

One caveat resolved rather than carried: `Documents/README.md` calls all five provisional and v3.1x-era. That README is stale. Both files we took declare USDM v4.0.0 in their own `Readme` sheet, and `m11_mapping` is aligned to the M11 Updated Step 2 Draft of 14 March 2025, matching IG p.8.

## Standards outside CDISC, added 2026-08-18

The source sweep had stopped at one GitHub repository. Widening it found two standards the project needs and did not hold. Both are pinned; `docs/sources.md` says what each answers.

**ICH M11 CeSHarP**, Step 4, adopted 2025-11-19. Earlier reasoning dismissed it as reference-only because our protocols are not authored in it. Too narrow: its template describes protocol structure whether or not a given protocol follows it, and Phases 1 and 2 need that.

**ICH E9(R1)**, Step 4, 2019-12-03. Phase 4 gates on the SAP defining estimands. USDM models the framework without defining it; E9(R1) defines it.

**Drift between the two bodies is expected, not a defect.** USDM v4.0 is aligned to an M11 Step 2 draft; M11 went Step 4 eight months later. Different organisations, different release cycles. Do not try to reconcile them.

**Unverified:** whether M11 Step 4 creates an obligation on protocol authors, and by when. `BACKGROUND.md` still calls it an expectation rather than a mandate. Re-check before relying on either reading.

## Section addressing, fixed 2026-08-18

`read_pdf.py` returned whole pages for a section, so a section starting mid-page arrived with the previous one attached, and one spilling past a page break was silently cut short. E9(R1) A.3.3 returned 1 of its 4 estimand attributes with no sign the rest existed. In the USDM IG, 32 of 54 sections shared a page range with another, and 4.22 and 4.23 returned byte-identical text.

The cause was one line: the section end was set to the page before the next section starts, which discards whatever the section holds on that page. It now ends on that page and `read_pdf.py` trims both shared pages at the headings, matching on the section number because the IG puts number and title on one line while E9(R1) splits them. Where a heading cannot be found the output says so rather than guessing, since a boundary chosen silently is the failure being fixed.

All 66 sections across both bookmarked documents extract cleanly, each starting at its own heading. `docs/usdm_ig_map.md` was regenerated, since 40 of its 52 page ranges changed.

## Declined: section addressing for the M11 PDFs

The M11 PDFs carry no bookmarks, so `read_pdf.py` cannot address them by section. Supporting that needs a different mechanism, not a parameterisation of what exists. Not doing it: the Technical Specification is a lookup reference rather than a linear read, so `--find` is the access pattern it wants and a term search lands on one or two pages.

## Routing complexity, and where LangGraph earns its place

Counting the actual branch points in Phases 0 to 4:

- Section category selects which extraction prompt. That is a dictionary lookup, not routing.
- Confidence below a threshold sends a record to a review queue. One `if`.
- Entity resolution goes candidate, then adjudicate, then merge or queue. One branch.

No cycles. Nothing where the model decides what happens next. That is a fan-out over a list with a dispatch table, and LangGraph around it would be scaffolding on a `for` loop.

A real cycle appears exactly once, in Phase 5: generate, score against a checklist, and if it fails, revise the prompt and regenerate. Cycles are what LangGraph is for.

**Decision:** write every stage as a pure function taking and returning an explicit state object, in plain Python. Adopt LangGraph at Phase 5. Written this way the migration is mechanical, since each function becomes a node. The cost of deferring is near zero; the cost of adopting now is debugging two unfamiliar things at once when only one of them is the subject.

**On cost:** LangGraph adds zero model calls. It is orchestration, not inference. Spend is driven by call count and prompt size, identical either way. One real caveat: a state design that passes the whole accumulated state into every prompt does inflate tokens. Avoidable, but it is the one way this choice touches cost.

## Cost estimate

Current pricing, checked rather than recalled:

| Model | Input per M | Output per M |
| --- | --- | --- |
| Opus 5 | $5.00 | $25.00 |
| Sonnet 5 | $3.00 ($2.00 intro through 2026-08-31) | $15.00 ($10.00 intro) |
| Haiku 4.5 | $1.00 | $5.00 |

One clean pass over 3 studies is roughly 1.6M input and 270K output tokens: about **$6 on Sonnet 5**, about **$15 on Opus 5**. Development iteration multiplies that, but cache reads cost about 0.1x input, and the disk response cache makes re-runs free. Realistic project total is **tens of dollars**. Cost is not a reason to pick one architecture over another here.

Working model assignment, to be tuned: `claude-haiku-4-5` for classification, `claude-sonnet-5` for extraction, `claude-opus-5` for the Phase 5 hard cases.

## Static copy versus live API

It splits cleanly.

**Call live:**
- **ClinicalTrials.gov API v2**, for finding and downloading protocol and SAP PDFs. Maintained, free, no snapshot worth keeping.
- **The DDF conformance validation endpoint.** The CDISC reference implementation exposes an endpoint that checks whether a USDM document is conformant. If publicly reachable, calling it beats reimplementing the rules. Phase 0 confirms reachability without credentials; if it needs a key, we fall back to the published rule specifications.

**Pin a downloaded copy:**
- **The USDM model specification.** This is the one place where "always fetch latest" is actively harmful. USDM has shipped four major versions in under three years (v1.0 Aug 2022, v2.0 Jun 2023, v3.0 Apr 2024, v4.0 Jun 2025) plus errata on v3.0 and v4.0. If a new version lands mid-project, extraction output silently changes shape and you cannot tell whether a new failure came from the prompt or from the standard moving. Same instinct as pinning a library version. We record the commit and update deliberately.

**CDISC Library: checked and closed.** A valid API key exists on a non-member subscription. `GET https://library.cdisc.org/api/mdr/products` returns `"Members-only content"`. That is the top-level catalog, so the tier is gated out of MDR content generally, not out of USDM specifically. The key authenticates (a bad key returns 401), the tier simply grants nothing.

Consequence: none. The `usdm` PyPI package stays out of scope, and the model, controlled terminology, and conformance rule specifications all come from the public `cdisc-org/DDF-RA` repo, which was already the plan. **Membership is not worth buying for this project.**

**Biomedical Concepts: same gate, same resolution, confirmed 2026-08-25.** The COSMoS BC API (`GET .../api/cosmos/v1/mdr/bc/packages`) also returns "Members-only content" (401), so live BC lookups are out too. It does not matter: the full BC set is published in the public `cdisc-org/COSMoS` repo export, now pinned to commit `031429b` (manifest `raw_cdisc_bc.json`). BC mapping is therefore feasible without membership, contrary to the earlier worry. It stays a Phase 3 enrichment layer, not a prerequisite: an `Activity` references a BC by ID, so structural extraction comes first and BC IDs attach afterward. The worked examples confirm it is optional, ECG carries no BC mapping while Vitals does.

## Source navigation, built 2026-08-18

`docs/sources.md` answers "which file holds my answer", which the manifests were never meant to. It has two halves: every pinned file with the question it answers and whether it has been read, then a registry of resources that exist and we do not hold. That registry is the record of what was already reviewed and rejected, so a later session does not re-litigate it; the entries live there, not here.

Three format rules keep the registry from turning into a bibliography: every entry carries a decision rather than a description; only resources actually reviewed are entered; and the second half is never read at session start.

It does not replace `docs/usdm_ig_map.md`, which the original plan said it would. That file holds a per-section read ledger for a 119-page guide, and folding 54 rows into one index row would coarsen it. The index links to it instead, and the same applies to any future document with its own ledger.

Building it settled two things by measurement:

- **Class counts.** The three files do not disagree. `dataStructure.yml` has 86 classes, 80 concrete and 6 abstract. `dataDictionary.MD` has 84, the same set minus the two extension classes, which IG 6.4 places outside the logical model. `USDM_API.json` has the 80 concrete ones plus `Wrapper`, `HTTPValidationError` and `ValidationError`, which are API plumbing. No abstract class serialises. This corrected the "81 classes" recorded in `docs/usdm_ig_map.md`.
- **Codelist references resolve.** All 517 NCI codes in `dataDictionary.MD` appear in `USDM_CT.xlsx`. Nothing dangles.

## The orientation walks, done 2026-08-25

Traced one activity (12-lead ECG, triplicate) through all three forms of the Alexion example: printed SoA grid, hand-authored `mainTimeline` row, USDM JSON objects. Alexion defines no estimand, so a second walk traced the primary endpoint and its estimand through the CDISC_Pilot example. Kept conversational; the value is the five findings, which now shape Phase 1 and are recorded there under "Design inputs" in `PLAN.md`.

The one substantive correction the walks surfaced, kept here because it is a finding about the source material: the single CDISC_Pilot estimand records its intercurrent-event strategy as "Treatment Policy", but the protocol (3.9.1.2 and 4.3.2) restricts the primary analysis to pre-interruption data, which is a "While on Treatment" strategy, the opposite one (E9(R1) A.3.2, source-read). The likely cause is conflating the ITT *population* with the treatment-policy *strategy*. Consequence: the reference examples cannot be treated as infallible ground truth, which is why Phase 5 scoring must be able to flag suspected-bad reference data.
