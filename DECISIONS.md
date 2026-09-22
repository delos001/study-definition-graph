# Decisions

The document contains the record of choices made and why. This is an append-only log: entries are added as decisions are made and are not rewritten as work progresses.

Some entries mark a decision as **unguided**. That means no published standard covered the question, so the choice was the project's own; the categories are in `CLAUDE.md` under Grounding.

- For the build plan itself, see `PLAN.md`.
- For the problem and background, see `BACKGROUND.md`.

## Foundational choices

| Decision | Choice | Why |
| --- | --- | --- |
| Output | Working code first | Design write-up deferred, not dropped. |
| Corpus | Protocol + SAP for the same study, growing to about 3 studies | Smallest set where document classification can be measured and linking information across documents is possible. |
| Graph store | Neo4j in Docker | Docker 29.6.2 already installed. The visual browser is the main argument. |
| Neo4j version | Pinned to `5.26.29-community` (5.26 LTS) | The `5-community` tag floats to the newest 5.x on every pull. A version moving mid-project makes a failure unattributable. Digest recorded in `docker-compose.yml`. |
| Standard | USDM v4.0, pinned | Current published version. |
| Model provider | Anthropic (Claude) | Key already in use in `langgraph_sandbox/spike/spike.py` via `langchain_anthropic`. |
| Orchestration | Plain Python through Phase 4, LangGraph at Phase 5 | See the routing complexity assessment below. |
| Source material | All five official USDM standards pinned, plus CDISC's worked examples | See below. The API specification alone was not enough. |

## Which USDM sources we hold, and why

USDM is five official CDISC standards (IG p.6), not one file. The model's API specification discards attribute definitions, cardinality, and the target class of every relationship, so it is not a sufficient basis for design work.

All five are now pinned to DDF-RA commit `aa303cb`, with the worked examples and two crosswalks. Inventory and hashes in `manifests/`.

The UML deliverable is the one that mattered most. `dataStructure.yml` types every ID reference (`epochId` to `StudyEpoch`, `activityIds` to `Activity`), which the API specification leaves as a bare string. That is the edge list Phase 4 needs and it is published, not something we have to infer.

## Mapping crosswalks used

`Documents/Mappings/` holds five crosswalks between USDM and other standards. Two were taken. Three were dropped.

**Taken:**

- `ct-gov_mapping.xlsx`. Phase 1 pulls studies from ClinicalTrials.gov, and every study there already has structured registry fields. Six sheets map those fields to a USDM class, attribute and target path. Structured ground truth for part of every study, with no model call involved.
- `m11_mapping.xlsx`. ICH M11 is an authoring template our source protocols are not written in, so this is reference material rather than a pipeline input. Kept because it is small and holding the complete source is cheaper than re-deciding later.

**Dropped permanently**, so this does not resurface:

- `ctis_mapping.xlsx`. EU CTIS registry submission. Out of scope.
- `cpt_mapping.xlsx`. TransCelerate authoring template. Our sources do not use it.
- `sdtm_mapping.xlsx`. Maps USDM to SDTM, which is downstream of this project and runs in the opposite direction.

One caveat resolved rather than carried: `data/raw/usdm_mappings/DDF-RA_Documents_README.md` (CDISC's own, shipped with the crosswalks) calls all five provisional and v3.1x-era. That README is stale. Both files we took declare USDM v4.0.0 in their own `Readme` sheet, and `m11_mapping` is aligned to the M11 Updated Step 2 Draft of 14 March 2025, matching IG p.8.

## Standards outside CDISC, added 2026-08-18

The source sweep had stopped at one GitHub repository. Widening it found two standards the project needs and did not hold. Both are listed below and pinned; `docs/sources_index.md` says what each answers.

**ICH M11 CeSHarP**, Step 4, adopted 2025-11-19. Earlier reasoning dismissed it as reference-only because our protocols are not authored in it. Too narrow: its template describes protocol structure whether or not a given protocol follows it, and Phases 1 and 2 need that.

**ICH E9(R1)**, Step 4, 2019-12-03. Phase 4 gates on the SAP defining estimands. USDM models the framework without defining it; E9(R1) defines it.

**Drift between the two bodies is expected, not a defect.** USDM v4.0 is aligned to an M11 Step 2 draft; M11 went Step 4 eight months later. Different organisations, different release cycles. Do not try to reconcile them.

## Section addressing, fixed 2026-08-18

`read_pdf.py` addressed sections by page range, not by heading, so a section starting mid-page kept the previous one and one spilling past a page break was cut short (E9(R1) A.3.3 returned only 1 of its 4 estimand attributes). The fix: end each section at the next heading, and where a heading cannot be found, say so rather than guess; a silently chosen boundary is the failure being fixed. All 66 sections across both bookmarked documents now extract cleanly, each at its own heading.

## Declined: section addressing for the M11 PDFs

The M11 PDFs carry no bookmarks, so `read_pdf.py` cannot address them by section. Supporting that needs a different mechanism, not a parameterisation of what exists. Not doing it: the Technical Specification is a lookup reference rather than a linear read, so `--find` is the access pattern it wants and a term search lands on one or two pages.

## Routing complexity

The question: does the pipeline need an orchestration framework (LangGraph), and if so when? It turns on control-flow complexity: LangGraph earns its place when there are cycles, or when the model decides what runs next.

In the pipeline as currently planned (Phases 0 to 4), the branch points are few:

- Section category selects which extraction prompt. A dictionary lookup, not routing.
- Confidence below a threshold sends a record to a review queue. One `if`.
- Entity resolution goes candidate, then adjudicate, then merge or queue. One branch.

No cycles, and nothing where the model decides what happens next: a fan-out over a list with a dispatch table, where LangGraph would be scaffolding on a `for` loop. A production workflow would add real routing (QC gates, human-in-the-loop, rework loops, escalation), and those are cycles, exactly where LangGraph would earn its place. That is deferred, not assumed away.

The first real cycle in this build appears in Phase 5: generate, score against a checklist, and if it fails, revise the prompt and regenerate. Cycles are what LangGraph is for.

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
- **The DDF conformance validation endpoint.** The CDISC reference implementation exposes an endpoint that checks whether a USDM document is conformant. If publicly reachable, calling it beats reimplementing the rules. Phase 0 confirms reachability without credentials; if it needs a key, we fall back to the published rule specifications. Moved to Phase 3 on 2026-09-16; see the entry of that date, "The conformance checker question moves from Phase 0 to Phase 3".

**Pin a downloaded copy:**
- **The USDM model specification.** This is the one place where "always fetch latest" is actively harmful. USDM has shipped four major versions in under three years (v1.0 Aug 2022, v2.0 Jun 2023, v3.0 Apr 2024, v4.0 Jun 2025) plus errata on v3.0 and v4.0. If a new version lands mid-project, extraction output silently changes shape and you cannot tell whether a new failure came from the prompt or from the standard moving. Same instinct as pinning a library version. We record the commit and update deliberately.

**CDISC Library: checked and closed.** A valid API key exists on a non-member subscription. `GET https://library.cdisc.org/api/mdr/products` returns `"Members-only content"`. That is the top-level catalog, so the tier is gated out of MDR content generally, not out of USDM specifically. The key authenticates (a bad key returns 401), the tier simply grants nothing.

Consequence: none. The `usdm` PyPI package stays out of scope, and the model, controlled terminology, and conformance rule specifications all come from the public `cdisc-org/DDF-RA` repo, which was already the plan. **Membership is not worth buying for this project.**

**Biomedical Concepts: same gate, same resolution, confirmed 2026-08-25.** The COSMoS BC API (`GET .../api/cosmos/v1/mdr/bc/packages`) also returns "Members-only content" (401), so live BC lookups are out too. It does not matter: the full BC set is published in the public `cdisc-org/COSMoS` repo export, now pinned to commit `031429b` (manifest `cdisc_biomedical_concepts.json`). BC mapping is therefore feasible without membership, contrary to the earlier worry. It stays a Phase 3 enrichment layer, not a prerequisite: an `Activity` references a BC by ID, so structural extraction comes first and BC IDs attach afterward. The worked examples confirm it is optional: ECG carries no BC mapping while Vitals does.

## Source navigation, built 2026-08-18

`docs/sources_index.md` answers "which file holds my answer", which the manifests were never meant to. It has two halves: every pinned file with the question it answers and whether it has been read, then a registry of resources that exist and we do not hold. That registry is the record of what was already reviewed and rejected, so a later session does not re-litigate it; the entries live there, not here.

Three format rules keep the registry from turning into a bibliography: every entry carries a decision rather than a description; only resources actually reviewed are entered; and the second half is never read at session start.

It does not replace `docs/standards_read_record.md`, which the original plan said it would. That file holds a per-section read ledger for a 119-page guide, and folding 54 rows into one index row would coarsen it. The index links to it instead, and the same applies to any future document with its own ledger.

Building it settled two things by measurement:

- **Class counts.** The three files do not disagree. `dataStructure.yml` has 86 classes, 80 concrete and 6 abstract. `dataDictionary.MD` has 84, the same set minus the two extension classes, which IG 6.4 places outside the logical model. `USDM_API.json` has the 80 concrete ones plus `Wrapper`, `HTTPValidationError` and `ValidationError`, which are API plumbing. No abstract class serialises. This corrected the "81 classes" recorded in `docs/standards_read_record.md`.
- **Codelist references resolve.** All 517 NCI codes in `dataDictionary.MD` appear in `USDM_CT.xlsx`. Nothing dangles.

## The orientation walks, done 2026-08-25

Traced one activity (12-lead ECG, triplicate) through all three forms of the Alexion example: printed SoA grid, hand-authored `mainTimeline` row, USDM JSON objects. Alexion defines no estimand, so a second walk traced the primary endpoint and its estimand through the CDISC_Pilot example. Kept conversational; the value is the five findings, which now shape Phase 1 and are recorded there under "Design considerations" in `PLAN.md`.

The one substantive correction the walks surfaced, kept here because it is a finding about the source material: the single CDISC_Pilot estimand records its intercurrent-event strategy as "Treatment Policy", but the protocol (3.9.1.2 and 4.3.2) restricts the primary analysis to pre-interruption data, which is a "While on Treatment" strategy, the opposite one (E9(R1) A.3.2, source-read). The likely cause is conflating the ITT *population* with the treatment-policy *strategy*. Consequence: the reference examples cannot be treated as infallible ground truth, which is why Phase 5 scoring must be able to flag suspected-bad reference data.

## Superset check: dataStructure.yml against dataDictionary.MD, 2026-09-02

Issue 7 leaned on `dataStructure.yml` carrying everything `dataDictionary.MD` has, so the redesigned loader could read the one file. Checked by script rather than assumed, comparing every dictionary row against the UML file. The claim holds structurally and fails in two specific places, so it is recorded qualified rather than as a flat "superset".

Holds: all 84 dictionary classes are in the UML file (which adds the two extension classes for 86), every dictionary attribute is present (matched through the UML `Model Name`, since the dictionary names a relationship by its logical name `previous` where the UML uses the id-key `previousId`), and data type, cardinality, definition and inherited-from agree on every attribute. Zero structural mismatches.

Fails in two places, both measured 2026-09-02. **Codelist bindings:** 67 attributes carry a `Codelist Ref` in the dictionary (e.g. `Address.country` to ISO 3166-1) that the UML file has no field for; the per-attribute pointer lives only in the dictionary, the values themselves in `USDM_CT.xlsx`. **Abstract-class codes:** for 27 attributes across the six abstract classes, the UML file's `NCI C-Code` and `Preferred Term` are copied from a concrete child and are wrong at the abstract level. Abstract `Identifier.text` carries `C215581` "Administrable Product Identifier Text" where the dictionary correctly has `C215450` "Identifier Text"; concrete-class codes are correct.

Consequence: the loader and concrete-class extraction need only the UML file, since abstract classes never serialise and concrete codes are right. Anything that binds coded values (a Phase 3 enrichment) needs the dictionary or `USDM_CT.xlsx`, not the UML file. This qualifies the earlier note above (line ~123) that "the three files do not disagree", which was about class counts, not per-attribute codes.

## Phase 1 design, decided 2026-09-03

Phase 1 reads a downloaded protocol or statistics plan and turns it into one structured hand-off document that the next phase consumes. This entry records the design in plain terms. The full working detail sits in GitHub issue #11; this is the readable summary.

### What the hand-off holds

For each document we keep:

- Which document it is: the study number, the document type (protocol vs. statistics plan), a version marker, and a version date. This is the minimum needed so two documents from the same study, like an original protocol and its amendment, never get mistaken for each other.
- A check-value of the file's raw bytes, kept only to prove the file has not changed since we fetched it. It is an integrity check, not part of the document's identity: the same document saved as Word vs. PDF has different bytes, so this value names a file, not a document.
- The list of sections. For each section: its title, where it starts and stops, and its text (the words under that heading).
- The Schedule of Activities kept as a real grid, rows and columns, not flattened into one long line. The little footnote letters stay attached to the words they mark, and the footnote definitions below the grid are captured too.
- A short list of what each section is made of: plain text, images, tables, unusual characters. This is mechanical, no judgment, and it exists so a later step knows which reader to send a section to.

What the hand-off never holds is any judgment about what a section means or is for. That is the next phase's job, and keeping it out is the whole reason the reading step and the judging step are separate: if a later answer is wrong, we can tell whether the reading or the judging caused it.

### The schedule now, and the schedule later

Right now the grid is pulled out with an automatic table reader and stamped "extracted, not verified", with a page number pointing back to the source. That reader is imperfect on messy tables, so we never trust it blind; a person checks it against the real page. The accurate version of the schedule is built much later (Phase 5) by handing the page to the model as a picture, which avoids the garbage that pulling it out as text produces. The hand-off describes the schedule by what it is, not by how it was made, so the better method can later fill the same slot without breaking anything downstream. We only switch the schedule over to the accurate method once it is actually measured to beat the current one.

### How studies are chosen

Two hard requirements and one soft preference.

- Hard: the study must post both a protocol and a statistics plan. This is checkable straight from the catalog, no reading inside the files.
- Hard: the statistics plan must actually define estimands. This is not in the catalog, so it is a content check done by reading the candidates that pass the first requirement.
- Soft: prefer variety across sponsor, disease area, and study phase. Start strict, and loosen only if too few studies qualify.

Choosing which documents to build against is set-up work, not part of the pipeline itself, so it is free to use AI or manual review. The pipeline that runs on every document stays AI-free, for the attribution reason above; picking a good test set once does not.

### How sections are found

Two paths, both first-class, not a main way with a backup.

- If a document has a built-in table of contents, use it. This already exists in `scripts/read_pdf.py`.
- If it does not, find the sections by spotting numbered heading lines in the text, like "2. INTRODUCTION" or "1.3 Schedule of Activities". The hard part is telling a real heading from a line that merely starts with a number, like "3.5 mg was administered".

Documents with no table of contents are rare across protocols, statistics plans, and investigator's brochures, so the second path is built lean. It is tested by taking a document that has a table of contents, stripping it out, and checking that the second path rebuilds the same sections the built-in one gave.

The code layout (one file or several) is deliberately not fixed yet. It will follow from how much the two paths actually share once both are written, rather than being guessed from one example.

## Tests and validation records, decided 2026-09-04

The Phase 0 loader was reviewed before Phase 1 work began, and the review found the module had five exit codes and three error types that had only ever been checked by hand, in throwaway scripts, with one exit code already recorded wrongly in an issue comment. Two decisions follow, both process rather than data-shape, so **unguided**.

**Automated checks live in `tests/`, in two kinds.** Every check is marked positive (the right thing works) or negative (the broken thing fails, and the error names the right cause). Logic checks run on a small fixture file, three classes copied verbatim from the pinned USDM model, because they must break their input on purpose and the real file must never be touched; a real-file check proves the fixture is identical to the pinned classes, so the small file is a sample, not a stand-in. Checks that need the pinned download skip with a reason when `data/` is absent, so the rest still run on a fresh clone. Development runs write nothing.

**A validation record is written only on request.** `pytest --validation-report` writes one Markdown file per test file to `tests/validation/`, committed, holding what was tested (component, commit, sha256 of the test file and fixtures, the pinned data version), how (command, versions, platform), when and by whom, and the outcome per check. The verdict is PASS only when pytest itself exited 0, after an adversarial review showed a tally of per-test results would have certified a run with a failing clean-up step as PASS. This is the proof that a component was validated at a given state; it is not produced on every run, which would be noise.

## Pinned files behind one function, decided 2026-09-04

The same review found `usdm_spec.py` reaching into `scripts/verify_manifests.py` by file path to borrow the fingerprint check, and computing the repo location by walking up from its own file with nothing confirming it had landed in the repo. Installed without `pip install -e .`, it would fail with the wrong message ("spec not found; run fetch_sources.py"). Three shapes were considered: move all of `verify_manifests.py` into the package; leave it in `scripts/` and keep the by-path import with a guard; or build a file-or-API abstraction now. Decision, **unguided**:

**One function, `sdg.pinned.pinned(<path>)`, is the only way any code obtains a pinned file.** It finds the manifest entry, checks size and fingerprint, and returns the file with its identity (sha256 and the url it was fetched from, which carries the source version). Every cause of failure has its own message and remedy. The manifest is the mechanism, not the contract: if a source is one day fetched from an API, the body of `pinned()` changes to ask the API and report its version identifier, and callers do not change. No API seam is built now; one call site with a fixed return shape is the seam.

**Only what the pipeline needs moved into the package.** Manifest reading, entry checking and hashing now live in `src/sdg/pinned.py`, shared by `verify_manifests.py`, `fetch_sources.py` and `usdm_spec.py`, so the check run by hand is the check run automatically. Corpus-wide tooling (walking `data/raw/` for unrecorded files, downloading, the printed report) stays in `scripts/`. A `require_repo()` check confirms the package is running from inside its repo before any path is used, and names the install command if not (exit 6 from the loader). Consequence: the two scripts now need the editable install to run at all, which the README already requires; without it they fail immediately with Python's own "No module named sdg", a correct diagnosis.

## Audit of the scripts and package, decided 2026-09-04

A second review, after the tests-and-pinned work above landed, found four problems and made one process choice. All **unguided**.

**Exit code 6 was unreachable.** The loader checked whether the model file existed before it checked whether the package was running from inside its repo. Installed the wrong way, the file is looked for under the wrong root, so the run said "not downloaded, run fetch_sources.py", the exact wrong message the previous entry claims to have fixed. The test that certified exit 6 had pointed the spec at a file that exists, a state that cannot occur. Fix: the in-repo check runs first, in every mode, and the test stages the real state.

**One exit code per root cause, the same number everywhere.** `check_facts.py` caught only a missing file; an unverifiable, wrongly shaped or wrongly installed corpus ended in a traceback whose exit code, 1, means "a figure drifted". Each cause now has its own code with the cause and the fix printed: 2 file missing, 3 cannot be verified, 4 wrong shape, 6 installed without `-e`, 7 not installed. Codes 3, 4 and 6 mean the same in `sdg.usdm_spec`, and `fetch_sources.py` and `verify_manifests.py` now return 6 for the same cause, so a number learned once holds across the repo. Code 5 is left unassigned in the scripts because it already means "unknown class" in the loader. The rule going forward: a new failure gets a new number, never a shared one, because the reader of an exit code has nothing else to go on.

**The certifying script goes through the door.** `check_facts.py` read nine pinned files directly, so it could re-derive a figure from a swapped or edited file and report the documents correct. Every file it reads is now obtained through `sdg.pinned.pinned()`, the rule the previous entry set. `read_pdf.py` and `read_xlsx.py` still read directly: they are orientation tools a person reads by eye, and nothing downstream consumes their output. That exemption is now stated rather than implied.

**Scripts are tested like modules.** The four scripts that share code with the package had no tests, including the new exit codes. Each now has a test file in the same positive/negative style, calling the script's `main()` in-process with an argument list (each script's `main()` now takes one, as the loader's already did) against a throwaway repo, with `fetch_sources.py`'s network faked per url. No test reads or writes the real `data/`. The two hand-run readers are not tested; they have no exit-code contract beyond found or not found, and their output is judged by reading it.

## Repository folders reorganised by what each holds, decided 2026-09-08

A review of the scripts began with the folder they read from and found that `data/` held no data. Everything in it was a published standard, a guideline, a worked example, or a record about one of those, filed under a raw/interim/processed layout meant for documents flowing through a pipeline. The scripts had been written against that layout, so the confusion in the folders had become confusion in the code. The folders were settled first; the scripts and manifests follow. All **unguided**.

**Standards get their own folder, grouped by publisher.** `standards/` holds the published material the project depends on: `cdisc/` for USDM and the Biomedical Concepts library, `ich/` for M11 and E9(R1). A standard with several files gets a subfolder; a single document sits in the publisher folder. Publisher was chosen over role because it is the one grouping a newcomer can apply without knowing the project. The distinction that matters to the code, whether a file is read by a program or by a person, is a property of the file and will be recorded per file in the manifests rather than expressed as a folder tier.

**Versions stay in folder names.** `usdm_v4` and `m11_step4` carry their version because two versions of a standard can plausibly be held at once: a sponsor is not required to move in-flight studies to a new standard, so a production pipeline could run v4 and v5 side by side. E9(R1) is one file whose name already carries its revision. The cost is that paths change on upgrade; the alternative, version only in the manifest, would make side-by-side impossible.

**Crosswalks are the one exception to publisher grouping.** A crosswalk has two parents, so filing by author would scatter mappings to USDM across `cdisc/`, `hl7/` and whoever else writes one. `standards/crosswalks/` holds every mapping regardless of author, with the author recorded in the manifest. CDISC's own readme for the folder the crosswalks came from was dropped; it was held only so a quote from it was traceable, and the quote now sits in a README beside the crosswalks with its url and access date.

**Manifests move to the root.** A manifest describes a download wherever the download lands, and downloads now land under both `standards/` and `data/`. One `manifests/` folder at the root keeps "do I hold everything I pinned" a single check. `docs/sources_index.md`, which answers a similar question for a person, stays in `docs/`: the scripts treat every file in `manifests/` as a manifest, and a prose file among them would be a special case.

**`data/` holds only study documents and pipeline output.** `raw/` for documents as fetched, `interim/` and `processed/` for what the pipeline makes, `usdm_examples/` for CDISC's three worked examples, which are downloads. Nothing under it is committed, because everything under it is re-fetchable or regenerable, and git is the wrong store for a growing corpus of PDFs.

**Hand-built evaluation material gets a committed home.** `eval/` at the root, beside `prompts/`, for answer keys a person writes and for the acceptance thresholds fixed before testing. These cannot be regenerated, so they cannot live under the ignored `data/`. The worked examples were moved out of it and back under `data/` for the same reason in reverse: they are downloads.

**Documents named for what they show.** `code_map.md` became `workflow_map.md` because it shows the order steps run in and what flows between them, and that description holds when a step is not Python. `sources.md` became `sources_index.md`, `usdm_ig_map.md` became `standards_read_record.md`, `standards_map.html` became `standards_lineage.html`. Working drafts moved to `docs/draft/`. Links inside earlier entries of this file were updated to the new names, a departure from append-only: a dead link is a broken pointer, not a historical figure.

## Study documents get their own manifests, decided 2026-09-08

The reorganisation above left one question open: Phase 1 will download real protocols and SAPs into `data/raw/`, that folder is gitignored, and the rule is that every gitignored download has a record in `manifests/`. The six manifests there are each written by hand, once, for a standard whose version never moves. A study document is fetched by a script, one record per study, and the number grows with the corpus, so the two do not belong in the same list. Three places for the study records were weighed, all **unguided**.

**Beside the documents**, as `data/raw/<NCT>/manifest.json`: easiest to find, but it sits in the ignored tree, so it is lost with the PDFs and a fresh clone does not know which studies to re-download. Rejected, because restorability from a clone is the reason `manifests/` exists at all.

**One growing file**, `manifests/studies.json`: every download rewrites the one file, so the corpus history is unreadable in git and a partial write damages every study's record at once. Rejected.

**One file per study under a subfolder**, `manifests/data_raw/<NCT>.json`, committed and machine-written. Chosen. The subfolder is named for the folder its records point at, `data/raw/` with the slash replaced, so the link is read off the name; `studies` and `raw_studies` were considered and passed over because neither mirrors the path, and a reader in `manifests/` should not need the README to find where a record's files land. The subfolder carries the hand-edited versus machine-written distinction, the top-level manifests stay untouched, and "do I hold everything I pinned" stays one folder walk. The shape of a study record is decided with the fetch script (Phase 1, acquisition); whatever it is, each entry carries the url, size and sha256 so the same verify check applies. Nothing moved; the folder exists with a placeholder, and the READMEs for `manifests/` and `data/` and the sources index say where study records go.

## One folder per standard, and files keep their publisher's names, decided 2026-09-08

Two corrections to the reorganisation entry above, from the audit of it. Both **unguided**.

**One folder per standard, whatever the file count.** The rule had been that a standard with several files gets a subfolder and a single document sits in the publisher folder, which put E9(R1) at `standards/ich/ICH_E9R1_Addendum.pdf` beside the `m11_step4/` folder. That makes a standard's location depend on how much of it is held: the day a second E9(R1) document is pinned, the addendum moves, and every reference to it moves with it. It also left `ich_e9r1.json` as the one manifest landing in a shared folder rather than one of its own. Now `standards/ich/e9r1/`, so every manifest maps to exactly one folder readable off its name, the same property `manifests/data_raw/` was given in the entry above.

**Files keep their publisher's names.** The four ICH documents had been renamed on download (`ICH_Step4_M11_Final_Template_2025_1119.pdf` became `ICH_M11_Template.pdf`), which stripped the step and adoption date that ICH put in the name. A pinned file's name is part of its provenance: opened in a viewer or named in a provenance stamp, it should say what it is without its folder around it. Putting the version in file names by hand was considered and rejected: CDISC's names carry none (`USDM-IG.pdf`), and inventing one would be a name the publisher never used. The rule is therefore mechanical: keep the publisher's name, replace spaces with underscores, change nothing else. Version is guaranteed by our folder name and carried by the file name whenever the publisher put it there. The `_step4` marker stays on the M11 folder for the same reason `_v4` stays on USDM's: the folder is the unit a version is added or dropped as, and a rule with exceptions is one the reader has to memorise.

One exception, recorded in the manifest's notes: CDISC publishes the Biomedical Concepts export as `cdisc_biomedical_concepts_latest.xlsx`, and it stays pinned as `cdisc_biomedical_concepts.xlsx`. A suffix that says the file moves is wrong on a copy that does not, and a reader of the folder would take the pin to be broken. The version is the pinned commit.

## The worked examples get an authored README, decided 2026-09-08

Every folder in the reorganised layout has a committed `README.md` saying what it holds, except `data/usdm_examples/`, where the `README.md` was CDISC's own file: pinned, gitignored, and describing two examples (Devices, Observational) that were deliberately not taken. It was held only so the sentence calling those two synthetic was traceable. The crosswalks had the same arrangement and the reorganisation entry above resolved it by dropping CDISC's README from the pin and quoting it, with url and access date, in an authored README beside the files. The same is done here, **unguided**: the entry leaves `usdm_examples.json` (10 files to 9), the file is deleted, and `data/usdm_examples/README.md` is now authored and committed, unignored by one specific line in `.gitignore` rather than a wildcard, so a README a future download ships is not committed by accident. Renaming CDISC's file out of the way was not an option: a pinned file keeps its publisher's name.

## Everything pinned lives under one folder, inputs/, decided 2026-09-10

The audit of the 2026-09-09 session found that the two pieces of code which need to know which folders are pinned, the Claude Code hook that refuses edits to pinned files and `scripts/find_unrecorded_files.py`, worked it out by reading each manifest's `local_dir` and keeping only its first folder name. From `data/usdm_examples` that is `data`, so the whole of `data/` was treated as pinned, including `data/interim/` and `data/processed/`, which are the pipeline's own output folders. Verified by running the hook: a write to `data/interim/out.json` was refused as a pinned file. The unrecorded-files check would have reported every pipeline output the same way from the first Phase 1 run onward.

Keeping a list of pinned folders was rejected: the repo will grow, and a list is something a person has to remember to extend each time a new source is pinned. The alternative is a layout in which the rule needs no list because there is only one place pinned files can be. The break between what is downloaded from outside and recorded in a manifest, and what the pipeline produces and can regenerate, is complete: no file under the old `data/` was neither. Four layouts were weighed, all **unguided**. Splitting `data/` into `data/input/` and the two output folders still left pinned files under two roots, `standards/` and `data/input/`. A new top-level folder for the non-standard downloads did the same and added a third root. Moving the output folders into `eval/` was ruled out: `eval/` is committed because its answer keys cannot be regenerated, and pipeline output is gitignored because it always can be. Chosen: one top-level folder for everything downloaded, standards included, so the rule is a file is pinned if it is under that folder.

The folder is `inputs/`. `sources/` was the first candidate, because the package that fetches and verifies these files is `sdg/sources/` and the map of them is `docs/sources_index.md`, but `src/` is the Python packaging convention for the code folder and `src/` beside `sources/` would read as the same word twice. `pinned/` names a property and `downloads/` names a mechanism; `inputs/` names the role, and it holds for the next addition: anything pinned in future is an input, and anything the pipeline produces is not. The three subfolders are `inputs/standards/` unchanged inside, `inputs/worked_examples/` for what was `data/usdm_examples/`, and `inputs/study_documents/` for what was `data/raw/`. Both renames replace a name that said less: `usdm_examples` did not say they are CDISC's worked examples, which is how the sources index refers to them, and `raw` is a pipeline-stage word for what are protocols and SAPs. The study manifests move with their folder, from `manifests/data_raw/` to `manifests/study_documents/`, by the existing rule that the subfolder is named for the folder its records point at. `data/` is left holding `interim/` and `processed/` only.

Two things came out in the sweep. The hook took the repo root from the call's working directory, which follows any `cd` run in the session; from a subfolder it found no manifests and allowed everything, verified by running it. It now takes the root from `CLAUDE_PROJECT_DIR`, which Claude Code sets once per session, and reads no files at all. And `read_pdf.py`, `read_xlsx.py`, `check_facts.py` and `usdm_spec.py` still carried paths from before the 2026-09-08 reorganisation, `data/raw/usdm_v4/` and the pre-rename ICH file names, so the two readers had been unable to find any standard for two days. Their paths and the registered file names were corrected in the same sweep; the two readers run again, and the loader and fact checker wait on the module rewiring that the 2026-09-09 session left open.

## Audit of the sources package, decided 2026-09-10

The 2026-09-09 session replaced `scripts/fetch_sources.py`, `scripts/verify_manifests.py` and `src/sdg/pinned.py` with the `sdg/sources/` package of two workflows and five steps. It was audited on three measures: complexity, how the workflow scales as the repo grows, and how easily a failure can be located and fixed. The largest finding, that all of `data/` was being treated as pinned, is the entry above. The rest, all **unguided**:

**A dry run reports the corpus incomplete.** `acquire_sources --dry-run` counted a missing file as "would fetch" and then exited 0, so a fresh clone with nothing downloaded passed. The old `verify_manifests.py` had reported a missing file as a problem, and that check was lost in the rewrite. A new exit code was considered and rejected: a file that would be fetched means the corpus is incomplete, which is what exit 1 already means after a real run, so a dry run now exits 1 when at least one file would be fetched. `--dry-run --quiet` answers whether the corpus is complete and intact from the exit code alone.

**A file that cannot be read is reported, not raised.** A folder at a recorded path, or a workbook Excel has locked, made the compare step raise and ended the run with a traceback and Python's exit 1, the number the header gives to a failed fetch. The workflow now reports "cannot read" with the cause, counts it with the on-disk disagreements, and carries on to exit 2. The step is unchanged, by the rule that a step decides nothing and a workflow turns errors into outcomes.

**A hand-typed value that can never match is named as written.** The manifest reader checked that the five fields were present but converted the size without checking it, so a size like `"12,345"` raised Python's own error. It now reports a size that is not a whole number, and a sha256 that is not 64 lowercase hex characters, as manifest errors that quote the value as written, so a person sees their own typo and not a claim that the field is missing. The sha256 check was added because a wrong-shaped hash would otherwise surface later as a mismatch and send a person to re-download a file that is fine.

**The repo check lives in the reader only.** The two workflows and the pinned-file check each called the repo check and then the manifest reader, which calls the same check on its first line. Every mode of all three reads the manifests, so the explicit call and the comment giving its reason were removed. The reader's docstring is the one place that says the install is checked first.

**The hook's coverage is stated, not extended.** The Claude Code hook sees Write and Edit and not shell commands, and in this repo's permission mode edits are made through the shell wherever possible, so the hook covers the route used least. Matching shell command text for a pinned path was considered and rejected: it would both miss cases and block innocent commands. The acquire workflow's mismatch report is the guard that holds; the hook stays because it is cheap and stops the editor route.

**Tests come before the loader refactor.** The suite has not imported since the 2026-09-09 session. The order is: fixtures pointed at the reader, one test file per file under `tests/sources/`, the three fixes above proven there, and only then the loader rewired to `verify_pinned`, so a red test in the loader pass has one possible cause.

## Standard conventions for Python files, and tools that enforce them, decided 2026-09-11

The docstring convention in use until this session, open with what the function takes in and produces and never write what it returns, was invented for this project. The Google layout already existed, gives the same information plus the errors a function raises, and is what editors and documentation tools read. Rewriting every docstring to the invented shape had cost a full round of rework, so the rule is now the general one: where a standard convention exists, the project follows it, and departs from it only where the rule says so and says why. **Unguided**, and the reason it bears on later work is that every file written from here on is checked against these conventions before it can be committed.

**The rule moved out of CLAUDE.md into a path-scoped rule file.** `.claude/rules/writing_python_files.md` loads only when a Python file under `src/`, `scripts/` or `tests/` is touched, so sixteen rules about headers and docstrings no longer cost context in a session about reading standards. A skill was considered and rejected: a skill loads when invoked, and the failure mode is an edit made without invoking it, so the rules would not hold. CLAUDE.md keeps one paragraph pointing at the rule. The old heading, "Source files", was retired because "sources" means the pinned inputs everywhere else in this repo.

**The conventions adopted.** PEP 8 for layout and names, the Google layout for docstrings, type hints on every signature, specific exceptions, ruff for formatting and linting, and mypy for type checking. Five published rule sets were read for anything they had that this project lacked; those six were the additions. None of them covered a header block, section banners, comments that say why, or how a check is built, so the project's own rules on those stand.

**Two departures from the tools' defaults.** Checks under `tests/` are exempt from the type-hint requirement, because a check's arguments are the situation pytest staged for it and a hint on each would only repeat the argument's name. ruff's long-line check is off, because the formatter already wraps everything it can, and what it cannot wrap is a string; a message split across lines is harder to grep for, which matters in this repo.

**The pre-commit hook gates on all three tools.** `scripts/check_python_files.py` runs ruff format, ruff check and mypy and reports each verdict, and the hook calls it. The hook's earlier constraint, standard library only so it runs from any terminal, was relaxed for this one check: the script finds the tools on the path when the `sdg` environment is active and runs them through `conda run` when it is not, about one second against eight, both measured.

**Four files are excluded from mypy until the loader refactor lands.** `check_facts.py`, `usdm_spec.py` and their two test files still import the retired `sdg.pinned` module, so mypy cannot read them. Excluding them is what lets the hook gate on mypy now rather than after issues 19 and 20. The exclusion is one line in `pyproject.toml` with a comment naming the refactor, and it is removed with it. A warning-only gate was considered and rejected: a gate that does not gate is noise.

## The sources map carries no counts, decided 2026-09-14

Issue #22 asked for five new measurements in `scripts/check_facts.py`, one for each count stated in `docs/sources_index.md`: how many diagram images, how many rules apply to v4, how many rows in a mapping sheet, how wide a workbook sheet is, how many sheets a workbook has. Working through them showed that the file had been written as a specification when it is a map. Its job is to say which pinned file answers which question and how to open it. The counts were there to tell a reader what they were about to open, and no decision in the project rests on any of them. One of them, the width of a sheet, was true for one of three workbooks and false for the other two, which a map does not need to get right and a specification cannot afford to get wrong.

The file was rewritten without counts: one section per document, with its purpose and the commit it was pinned from, and a table of questions and the command that answers each. The read-status column was removed. It tracked which files had been read in past sessions, which is a record of activity, and a reference document is not a tracker. The only reading progress that matters, through the implementation guide, has its own ledger.

The rule in CLAUDE.md that every written count must be recomputable still stands, and the way a map satisfies it is to state no counts. A figure goes to the fact checker when the project reasons from it: the page total that scales the never-read-whole rule, the one-of-three estimand figure that shapes Phase 1's selection, the shared-code count that settles whether two standards are interchangeable. A figure that only describes a file's size or shape is left out of the prose instead.

The check the map does need is that it lists every file the manifests record, because the rewrite found one pinned file the old map had never mentioned. That is #27, to be built when the next source is pinned. #22 is closed as not planned.

## One exit code per cause across the whole repo, decided 2026-09-14

The 2026-09-04 audit set the rule that a new failure gets a new number, never a shared one, and applied it to the scripts that read the pinned corpus. Issue #24 found that the rule had not held outside that family. Code 3 meant "a manifest cannot be read" in four files and "a Python file cannot be parsed" in three others. Code 2 was given a meaning of its own in five files, when the argument parser every script uses already exits 2 on a bad command line, so in those five an exit of 2 had two possible causes and the number alone could not say which. And within a script, one number often covered several causes with different fixes: the pinned-file check raised one error for a manifest that cannot be read, a file no manifest records, and a file that does not match its entry.

Two designs were weighed. The first reserves only the numbers every script can hit, 0, 1, 2, 6 and 7, and leaves every other number to its script. It is simpler to keep, but it allows the same number to mean different things in different scripts, which is what made troubleshooting hard in the first place, and it was rejected on that ground. The second is a single table for the whole repo: one number, one cause, and a new cause takes the next unused number. That is what was adopted. The table lives in `validation/exit_codes.csv`, and a header lists only the codes its file can return, using the table's wording.

Two numbers are Python's own and are recorded as such: 1 is an unhandled error and 2 is a bad command line. Neither is assigned to anything else. Code 1 in particular gave up its old shared meaning of "the check found the problem it looks for"; a drifted figure, a stale index and a bad header each have their own number now, because two scripts that detect the same problem should exit the same number, and a number should not need the script's name to be read.

Making the split real needed one change in a step. `verify_pinned.py` raised a single IntegrityError for three causes. It now lets the manifest reader's own error through unchanged, raises a new UnrecordedFileError when no manifest entry records the file, and keeps IntegrityError for a file that does not match its entry. The two programs that call it map each to its number without reading the message. One message changed as a result: a manifest problem no longer carries the "cannot verify <file>:" prefix, because it is not about the file.

Renumbering was done in one commit, before any validation record exists, so no recorded run refers to an old number. Check names that carried a number in them were renamed to the new one and the inventory regenerated; ids did not change. The two usage mistakes in `read_xlsx.py` that used to exit 1, `--all` without `--find` and no workbook named, now go through the parser and exit 2 like every other usage mistake. Nothing enforces the table yet; that is #28, to be built after this lands so the check has something true to check.

## Code lives in one of three places, by who runs it, decided 2026-09-14

Code goes where its user is. `src/sdg/` holds what the project's user runs or imports, including the two viewing commands `read_pdf` and `read_xlsx`, now in `src/sdg/view/`. `validation/`, formerly `tests/`, holds the procedures that prove the code and the held files are as expected. `repo_tools/`, formerly `scripts/`, holds what only a maintainer runs to keep the repository in order. No other top-level code folder is added.

## Local extensions and registries get their own folders, decided 2026-09-16

The fields this project adds to USDM are treated as a standard, because that is what they are, only not published by CDISC. They moved from `docs/usdm_local_extensions.md` to `local_definitions/usdm_extensions/`, since `docs/` holds maps and these are definitions the pipeline's output depends on. An extension is never edited once added, and a change is a new version.

The codes that scope an extension, for clients, therapeutic areas and document types, went into `registries/` rather than beside the extensions. `PLAN.md` already names sponsor, therapeutic area and document type as prompt axes, so the same codes are expected to serve prompts too, and a shared folder avoids moving them later. The rules for the codes are in `registries/README.md`.

Both structures are drafts and may be realigned by the prompt axis work in #15. Validation waits until they are stable, so the checks are not rewritten each time the structure moves. Settling them is #30 and #31, and the validation is #32.

## The Neo4j deliverable gets a repo check, decided 2026-09-16

The Phase 0 audit ran every command the repo says should pass and found one Phase 0 product with no check at all: the Neo4j database. `PLAN.md` verified it by reaching the browser and running a query by hand. On the day of the audit the pinned container had been stopped for four weeks, and pressing the run button in Docker Desktop had started a bare copy of the image with no ports, no password, no saved data and no version pin, which the browser address could not reach. Nothing in the repo could have said so.

Two options were weighed. Keeping the hand check costs nothing but leaves one Phase 0 item that cannot be re-proven, and Phase 4 depends on that item. A repo check costs a small tool and needs Docker running when it is run. The repo check was chosen.

`repo_tools/check_neo4j.py` reads the three connection settings from `.env`, asks the database its version and edition, and compares the answer with the image tag pinned in `docker-compose.yml`. Reaching the database and logging in are proven on the way. The version comparison is the point: the compose file pins the version so a failure can be attributed, and a container started outside the compose file does not carry that pin, which is exactly what the audit found running. Each cause has its own exit code, added to `validation/exit_codes.csv` as 37 to 40.

The tool is not in the pre-commit hook, because a commit should not need Docker. It joins the setup verification list in `README.md`, and the Phase 0 verification line in `PLAN.md` now names it in place of the hand check.

## The Claude Code hooks are the fourth kind of Python file, decided 2026-09-16

The writing rule in `.claude/rules/writing_python_files.md` said it covered every Python file the project writes and named three folders. The Phase 0 audit found a fourth kind outside all three: the Claude Code hook in `.claude/hooks/`, which refuses an edit to a pinned file. It carried the header block, and `.claude/README.md` said it did, but the header checker never read that folder, so the block held only while someone remembered. It also had no checks, and neither did `repo_tools/check_python_files.py`, the tool that holds every other file to the formatter, linter and type checker.

Two options were weighed. Recording the hook as exempt costs nothing, but the one script that guards the pinned files is the wrong place for an exemption. Extending the rule costs one folder in each tool's configuration and two files of checks. The rule was extended.

The hooks folder is now the fourth folder the rule names, and the header checker, ruff, mypy and pytest all read it. The one wrinkle is where the hook's checks live. Every other code file has its checks at the same relative path under `validation/`, but pytest does not look inside a folder whose name starts with a dot, so `validation/.claude/hooks/` would never run. The checks live in `validation/claude_hooks/` instead, and the inventory generator maps that folder back to `.claude/hooks/`. The rule states the exception and why.

This amends the entry above, "Code lives in one of three places, by who runs it". There are four places, and the fourth is code that Claude Code itself runs.

## The IG ledger becomes a read record for every standard, decided 2026-09-16

`docs/usdm_ig_ledger.md` held two things. The first was a table of the implementation guide's sections with their page ranges, copied from the guide's bookmarks. The reader prints the same table live with `read_pdf --list`, so the copy was a maintained version of a derivable list, the pattern already rejected for the tools index and the workflow map, and its second table had drifted from its first. That table is dropped. The second thing was a record of which sections had been read and what each established. That is grounding material: a claim about a standard is grounded only when the part it rests on has been read and recorded. The file is renamed `docs/standards_read_record.md` and opened up to every pinned standard, one heading each, because the M11 and E9(R1) documents have been read in parts too and had no record. It joins the session-start reads when a phase works against the standard, which is Phase 3; until then `docs/sources_index.md`, which is read at session start, points at it.

## A pinned folder is named with the publisher's version, never a fetch date, decided 2026-09-16

The Phase 0 audit of the top-level documents found that the rule in `CLAUDE.md` for naming a standard's folder, one folder per standard named with its version, had gained a second clause in the 2026-09-15 rewrite: a standard with no publisher version is named with its export date. No decision was recorded for the clause, and the one folder it applied to, the Biomedical Concepts export, did not follow it. Working the case showed the clause could not be followed, because the date the manifest called the export date was the date of the pinned repository commit, and that commit changed an exclude list, not the export.

Three dates were available. The commit date and the retrieval date were rejected: a file fetched again tomorrow is the same file, and a name that changes when the content does not is not a version. The date kept is the newest `package_date` in the export's Biomedical Concepts sheet, which the workbook's own ReadMe sheet defines as the date a concept package was published to production. It changes only when CDISC publishes a package, so it is the publisher's date for the content. The folder is now `inputs/standards/cdisc/biomedical_concepts_2026-07-14/`, the manifest's version field says what the date is, and the clause is replaced by one sentence saying what a version is. The curation guide pinned beside the export carries its own version, 2026-06-30, in its ReadMe sheet; it is a separate document and does not date the export.

Every list of folders or files names the folder as it is, with the date. Prose that points at the concepts in general gives no version, so it does not go stale when a later export is pinned beside this one; that rule is in `CLAUDE.md`. The date is a figure derived from a pinned file, so `repo_tools/check_facts.py` measures it and compares it with the location the sources index states. That closes the chain: the workbook owns the date, the sources index is checked against the workbook, the index's location is checked against the manifest by `repo_tools/check_sources_map.py`, and the manifest is checked against the disk by `acquire_sources`.

## The conformance checker question moves from Phase 0 to Phase 3, decided 2026-09-16

The Phase 0 audit compared the list of what Phase 0 was to produce in `PLAN.md` against the repo and found one item with no answer recorded anywhere: whether CDISC's own conformance checker can be used without a paid membership. The question may well have been looked into and the answer never written down, since the plan already leans on the pinned rules spreadsheet as the fallback. Rather than guess, the item moves to Phase 3, where there is USDM output to check and the answer is first needed. It is a sub-issue of the Phase 3 issue, and the pinned spreadsheet stays the fallback if the checker needs a membership.

## Every check is classified by its objective, decided 2026-09-18

A review of `validation/validation_inventory.csv` found that every check was marked positive or negative, including checks that fit neither. A positive check sets up a working situation and expects the code to succeed. A negative check sets up a broken situation and expects the code to refuse for the right reason. Some checks do neither. They look at the real repo and ask whether it is in order, for example whether `repo_tools/README.md` still matches the headers it is generated from. Pipeline checks in later phases will add more that fit neither, such as scoring output against the answer keys in `eval/`. No standard covered the question, so the choice is **unguided**.

Checks are now grouped by their objective, meaning why the check exists, not what it looks at. The same file can be checked for different reasons. How a check is set up, what fixes a failure and who fixes it all follow from the reason. The objectives are defined in `validation/README.md`.

- Four objectives are in use: behavior, stability, agreement and conformance.
- Four more are defined but not in use yet: accuracy, performance, regression and environment readiness.
- Positive and negative now apply only to behavior checks, in a column renamed `behavior_case`.
- Behavior means what the code does when it runs, in a situation the check sets up. Speed is kept out of it, because a speed check is set up, judged and fixed differently.

A check has one objective, and its objective is decided before the check is written. A check found to serve two objectives is split when the parts would have different fixes or different owners. The review produced these changes:

- USD0027 checked the pinned USDM file's checksum and its shape in one step. It keeps only the shape check, and the checksum moves to a new stability check.
- HRS0046 ran the whole header checker, which tests both the header layout and the exit codes a header lists. It becomes two checks.
- SRC0071 and USD0028 added nothing that other checks do not already cover, so they are removed.
- HRS0018 stays whole. It verifies the pinned files it reads only as a precondition, because a figure measured from a changed file cannot be trusted.

A check that reads a pinned file which no longer matches its manifest is now skipped as blocked, not failed. Without this, one changed file would show up in a report as many separate failures. One new stability check, run once per pinned file, is the only check that fails when a pinned file has changed.

Each check has one of five statuses: pending, active, inactive, superseded or retired. Superseded and retired are kept apart on purpose. A superseded check stops because other checks now cover what it guarded. A retired check stops and nothing covers what it guarded, which is a loss of capability, so the inventory must record why that was accepted. The inventory gains `superseded_by` for the ids of the covering checks and `status_reason` for the reason. The reasoning belongs in the inventory rather than here, because this file records how the project was built and the inventory is what a later validation is read against.

A check's version is a whole number. It moves to the next number when a changed check passes its validation, its report is filed and it goes into production. Until the first validation run, every check stays at version 1 and a deleted check's row is removed. After that run, rows are kept whatever their status.

## Every check names its target and its objective, decided 2026-09-21

The objectives set on 2026-09-18 proved too fine to apply without long instructions. Behavior, agreement and accuracy all asked whether a thing produced the right result, and they were kept apart only because the thing differed: staged code, a generated record, a product. Carrying what the check looks at inside the objective is what made the rules grow, and the length of those rules was the sign that the split was at the wrong level. Issue #38 raised this. No standard covered the question, so the choice is **unguided**.

A check now carries two classifications. The target says what kind of thing the check confirms. The objective says what the check confirms about it. Neither is inferred from where a check sits; each is a marker on the check.

There are four targets.

- Repository: the tools, hooks, rules and records that hold the sources, conversions and products to their rules and specifications, so that each behaves as expected. It includes the pinning tools, the pre-commit hook and the validation suite itself.
- Sources: the materials, data, files, standards and references the project consumes to create and evaluate a product.
- Conversion: the processes, prompts, and run records that turn the sources into a product, such as reading a document, finding its sections, extracting contents and transforming into USDM structures and loading those into the graph.
- Products: the deliverables created through source conversions, such as extracted contents, USDM structures with their provenance, mappings, and the graph.

The environment the project runs in, such as the Neo4j server, the conda environment and the API key, is not a target. The project does not make it, and it is confirmed by hand with `repo_tools/check_neo4j.py` and `repo_tools/check_api_key.py` before a run. A fifth target can be added if that ever changes.

The target is the thing the check sets out to confirm. Whatever the check compares it against is the reference, and the reference does not change the target. A check that compares what the USDM loader expects with the pinned model is a conversion check with the pinned file as its reference. A record goes with the thing it describes, so `docs/sources_index.md` is under sources and `repo_tools/README.md` is under repository. The manifests are the one exception: they are the project's control over its own files, the same job the pre-commit hook does for code, so they are repository. Something the conversion made and a later step consumes, such as the located sections that classification reads, is a product, because the sources are what the project takes in rather than what it makes. The answer keys in `eval/` and the local definitions under `local_definitions/` are sources, although the project writes them, because they are references and standards the conversion works from.

There are five objectives.

- Correctness: the thing does, or produces, what it is supposed to, judged against what the right result is.
- Completeness: the thing includes everything it is supposed to, with nothing missing.
- Conformance: the thing follows the rule, specification or documentation it is held to.
- Stability: the thing is unchanged from its own earlier recorded or accepted version.
- Performance: the thing runs fast enough, or light enough on the machine, on a realistic input.

Behavior, agreement and accuracy all become correctness. Regression becomes stability with a product as its target. Environment readiness goes with the environment. Quality was considered for the first row and rejected, because in the established quality models it names the whole and the other rows are its parts, so a reader could file any check under it.

Positive and negative now say that a correctness check staged its own situation and expects success or a refusal. A correctness check may carry positive, negative or neither, and a check of any other objective carries neither. Neither means the check looked at something real.

Three boundaries were tested and written down so they do not have to be worked out again.

- Completeness against conformance: completeness asks whether everything the source holds was captured, and its reference is the source. Conformance asks whether a thing has the shape a written rule requires, and its reference is the rule. An extracted fact with no provenance is conformance. A fact the document states that no record captures is completeness.
- Stability against correctness: stability's reference is an earlier copy of the same thing. A check that compares two different things, a record with what it describes or a protocol term with a SAP term, is correctness.
- A comparison of a product with its answer key gives precision and recall. Precision is correctness and recall is completeness, so that is two checks over one comparison, which a fixture makes once. A failure then says which of the two fell short, which is the prompt-against-retrieval evidence `PLAN.md` asks for.

Applied to the checks that exist, the readers `src/sdg/usdm/usdm_spec.py`, `src/sdg/view/read_pdf.py` and `src/sdg/view/read_xlsx.py` are conversion, because reading a document and pulling content out of it is the first step of one. Every other check is repository, except the pinned-file fixity check, the re-derived figures in the committed documents and the sources map, which are sources. HRS0170 becomes conformance, because it holds a header to the exit-code table. HRS0104 and HRS0079 become completeness, because each asks whether anything is missing. Every staged check becomes correctness with its case kept.

The inventory gains a `validation_target` column before `validation_objective`, and every check gains an `@target` marker beside its `@objective` marker. The generator refuses a check that lacks either, or whose case breaks the rule above.

One follow-up is noted rather than designed: a stability check on a product needs a record of the accepted version to compare against, and nothing records one yet. It belongs to the phase that first declares a product accepted.

## The inventory's columns are bare, and the first classification is called category, decided 2026-09-21

The layout written into `validation/validation_inventory.csv` earlier today was reviewed by hand and changed in four ways before the documents were written. Nothing in the classification itself changed. This is a question of naming and layout, so the choice is **unguided**.

- The first classification is `category`, not `validation_target`, and its marker is `@category`. With the columns `target_folder_path` and `target_file_name` already meaning the code file a test file covers, the word target meant two things in one header.
- The case column is `staged_case`, not `behavior_case`. Behavior is no longer an objective, and the word staged says what the column records: whether the check staged a working or a broken situation, with an empty cell meaning it staged nothing.
- Every column about the check itself has a bare name: `category`, `objective`, `staged_case`, `folder_path`, `file_name`, `name`, `id`, `expected_result`, `version`, `status`, `superseded_by`, `status_reason`. Only the two columns about the covered file carry a prefix. A prefix on some of the check's columns and not others reads as two sets of columns, and the file's name already says what a row is.
- The order is the classification, then where the check lives, then what it covers, then its result, then its standing: `category`, `objective`, `staged_case`, `folder_path`, `file_name`, `name`, `id`, `target_folder_path`, `target_file_name`, `expected_result`, `version`, `status`, `superseded_by`, `status_reason`.

The validation report's check columns take the same names, so a report row still joins to the inventory by `id`. The dictionary for the inventory is `validation/validation_inventory_dictionary.md`, in the outline shape rather than tables, because a dictionary entry is a sentence and a table row holding a sentence does not read in the raw file.

## Checks are selected in the inventory's own terms, decided 2026-09-21

pytest selects checks by path and by words in names, which cannot say "the sources checks", "the stability checks in these two folders" or "SRC0128 again, now that it is fixed". A validation report of five hundred rows is the wrong answer to a question about three checks. No standard covered the question, so the choice is **unguided**.

Four options select checks by the columns the inventory already has: `--category`, `--objective` and `--id`, spelled as the columns are, and `--group`, which names a set that no folder, category or objective can express on its own. Categories and objectives narrow each other, ids and groups add up, and the report's `selection` column records what was asked for, so a narrowed run cannot pass for a full one. A value that names no category, objective, group or collected check stops the run rather than running nothing, and a refused command line leaves no report, because it validated nothing.

The options live in `validation/select_checks.py`, a pytest plugin that `pyproject.toml` loads at startup by its dotted name, rather than in `validation/conftest.py`. pytest reads the command line before it loads a conftest below the root folder, so an option a conftest adds is unknown at that moment and its value is taken for a path. The dotted name is the one mypy already uses for these files, so mypy's path did not change. The plugin also holds the readers for the code, category and objective markers, which the report writer imports.

Groups are written in `validation/validation_groups.yml`, one entry per group with a sentence saying what it is for and the ids of its checks. Ids rather than rules, so what a group holds is written down and reviewable, and an id no check carries stops the run. Two groups exist: `pinned`, every check that reads a real pinned file, to run after a re-pin, and `hook`, the checks that reproduce what the pre-commit hook enforces, to run when the hook refuses a commit.

A test file at the top level of `validation/` now targets the file of the same name in `validation/` itself when one is there, which covers `conftest.py` and `select_checks.py` with one rule instead of a named exception.

## A validation report is written only on a clean working folder, decided 2026-09-21

A report names the commit it validated, in its `commit` column and in its file name. When the working folder holds uncommitted changes, the code that ran matches no commit, and the name the report would give is wrong with no sign that it is. No standard covered the question, so the choice is **unguided**.

`validation/conftest.py` therefore refuses a run asked for a report when git reports changed, staged or untracked files, before any check is collected, so the refusal costs seconds rather than the whole run. It names the files and says to commit or stash. The reports folder itself does not count, so an earlier report not yet committed never blocks the next. The working sequence is commit the code, run the report, commit the report, and nothing depends on the report being committed straight away, because the report points at the code commit from its own contents.

Two related choices were made at the same time. `run_id` is the report's file name without `.csv`, numbered suffix included, because two runs on the same day and commit were getting one id. A listing run, `--collect-only`, writes no report, because nothing ran.

## A run that would validate nothing is refused, and the report claims no cause it cannot know, decided 2026-09-22

The selection options decided yesterday were audited today. Two defects came out of it, with one theme. A guard that asks about its inputs cannot speak for its result, and a record that states a cause has to know one. No standard covered either question, so both choices are **unguided**.

The first defect is in `validation/select_checks.py`. Four guards each confirmed that one value named something real, and nothing confirmed that anything survived once the options were combined. `pytest --category sources --id HRS0010` names a real category and a real id that no one check carries together, so all 514 collected checks were deselected and the run finished clean on nothing. That is the outcome the guards exist to prevent, reached by a route they do not cover.

Guarding each option's own contribution was considered and rejected on its own, because each option in that command matched something and only the combination was empty. The guard is therefore on the result: when no check survives, the run is refused the same way a bad value is refused. The refusal reports how many checks each option matched alone, because that is what names the option that does not belong, and the counts are of checks rather than runs so they read against `validation/validation_inventory.csv`. The three filters are held in one small table of the option's name, its values and the function that reads that value off a check, so a fifth selection option is one more entry and neither the filtering nor the refusal changes.

One consequence is accepted deliberately. A category with no checks yet, such as products, is now refused rather than running nothing. That matches the rule already in force for an id no check carries, which is also just "there are none".

The second defect is in `validation/conftest.py`. When no check produced an outcome the report wrote one row reading "no check ran: pytest failed before any test ran". The writer cannot know that. `pytest validation/fixtures` reaches that row with exit 5, having failed at nothing, and fixing the selection guard does not close it, because that route uses no selection option at all. The row now says only that no check ran. Why nothing ran stays in `exit_meaning`, which is derived from the exit number and is right for every one of them. Adding a branch per exit number was rejected, because it would leave two columns both trying to state a cause and would still be guessing wherever the number is ambiguous.

## A report counts what the run covered, rather than listing the options that narrowed it, decided 2026-09-22

The `selection` column decided yesterday was given the job of making sure a partial run could not pass for a full one. It cannot do that job, because it is built by listing the options known to narrow a run. Two runs were staged against a suite of three checks. pytest's own `--deselect` dropped one, and the report held two rows and said `all`. `-x` stopped the run at the first failure, and the report held one row, said `all`, and said FAIL. The second is the worse of the two, because a reader sees a complete-looking run with one failure and no sign that the rest never ran. No standard covered the question, so the choice is **unguided**.

Adding `--deselect`, `--ignore`, `-x` and `--maxfail` to the list was rejected. It is the same mistake as the selection guard recorded above, and pytest and its plugins will keep adding options, so the list is wrong between every revision. Refusing to write a report for a run that was cut short was also rejected, because narrowed runs are legitimate and documented, and refusing would mean deciding which narrowings are allowed rather than letting a reader see what happened.

A report now carries two counts beside `selection`. `checks_collected` says how many checks the run set out to cover, and `checks_reported` says how many it holds a row for. They are equal on a whole run and differ whenever checks were dropped or the run stopped before reaching them. Neither is derived from the options typed. The dropped checks are counted from the hook pytest fires for every deselection, whatever caused it, so a narrowing option this project has never heard of is counted the same as one it added itself.

`selection` keeps its place and its contents, because what was asked for is what a reader needs to run the same thing again. What it no longer claims is that the run was whole. That claim now rests on the two counts.

One limit is accepted and written into the dictionary rather than worked around. A file kept out of collection, as `--ignore` does, is never seen by the run, so the counts cannot notice it. Closing that would mean comparing the run against `validation/validation_inventory.csv` for how many checks exist, which would tie a report to the table being current and would not work for the throwaway suites that have no table.

## The category conversion is renamed processing, decided 2026-09-22

Conversion was chosen as a name for the pipeline's own work, not for a stage that changes something. The definition written for it did not say so. Its headline read "the processes, prompts, and run records that turn the sources into a product", which frames the category as production, and the word pipeline appeared nowhere in it. The audit in issue #41 then read the definition as written and argued that the two reading commands under `src/sdg/view/` do not turn a source into a product and so were misfiled. The argument was wrong, and it was a fair reading of the document, which is the defect. No standard covered the question, so the choice is **unguided**.

The category is now `processing`, and its definition says it is the pipeline's own work, every stage of it, from reading a source in through to the finished graph, and that it does not ask whether a given stage changes anything. Four alternatives were rejected. `pipeline` had already been retired for saying nothing. `build` is what `PLAN.md` calls the project's own phases and is an issue label. `production` collides with the sense of a deployed environment. `derivation` is the most precise of them, because every product is derived from a source and the project already leans on provenance, but it is more formal than the rest of the repo's voice.

Splitting the category further, into processing and graphing, was considered and not done. Neither an extraction check nor a graph check exists yet, so a later split moves no existing rows and is purely additive, while splitting now means fixing a boundary with no code to place it against. The next two phases both straddle that boundary: `PLAN.md` puts entity resolution beside the Neo4j load in Phase 4, and deciding whether two differently-named populations are the same subjects is content work rather than graph work, while Phase 5 reconstructs the Schedule of Activities by reading a document and produces a graph from it.

The design supports that split whenever the work proves it is wanted. A check's category is a marker on the check rather than something inferred from where it sits, so a split edits markers and one list in `repo_tools/build_inventory.py`. Ids do not move, because they name the folder of the covered file rather than the category. The named groups in `validation/validation_groups.yml` do not move, because they list ids. A filed report records the category as it was at run time, so earlier reports stay accurate about the runs they describe and still join on the id. One question is left open for that day: whether re-categorising a check counts as a change that moves its version. It is moot until the first validation run, while every check stays at version 1.

## Correctness and conformance are drawn on the data-quality split, and a staged case is untied from correctness, decided 2026-09-22

The objectives set on 2026-09-21 folded behavior, agreement and accuracy into one called correctness, and the definition had to stretch to cover all three. What it stretched to was "the thing does, or produces, what it is supposed to", which cannot be told apart from conformance, because "supposed to" names a rule and following a rule is what conformance is. In ordinary speech a thing that follows a rule is often called correct, which is the ambiguity that had to be removed rather than lived with.

A published standard covers this, so unlike the 2026-09-21 entry this choice is **guided**. The data-quality dimensions, DAMA's six in the Data Management Body of Knowledge and the equivalent characteristics in ISO/IEC 25012, separate validity, the degree to which values comply with rules, from accuracy, the degree to which a value reflects the real-world thing it describes or an agreed-upon source of truth. This project keeps its own words for the two, because conformance is what CDISC calls the same thing and accuracy is already used in `BACKGROUND.md` for extraction figures, but the boundary is the standard's.

One test applies the boundary. Can the expected answer change without any rule changing? If it can, something outside the thing under test holds the true value, and the question is correctness: a file's sha256 changes when the file changes, and `repo_tools/README.md` should say something different when a script's header changes. If it cannot, the rule is the only authority and the question is conformance: a header has eight fields in order only because the rule says eight and that order. Structure, format, layout, required fields and prescribed behaviour are therefore always conformance. Correctness was also widened from a true value to a true value or range, because a measurement can be judged against what is known to be plausible rather than against a single number.

Applied to the checks that exist, 439 of 456 are conformance and 15 are correctness. The fifteen are the ones that compare a value with an authority outside the code: a size or a sha256 against an independent measure, bytes written against bytes sent, values returned against what a manifest entry records, `repo_tools/README.md` and `validation/validation_inventory.csv` against the sources they were generated from, the figures in the committed documents against the pinned files, and the small fixture against the pinned model. Correctness is expected to grow as extraction and graph work arrive, because those compare against documents and answer keys.

A staged case is no longer tied to correctness. A case says how a check was set up, a working situation or a broken one, which is a separate thing from the question the check asks, and the tie only ever existed because behavior had been folded into correctness. Any objective may now carry `@positive` or `@negative`, and 432 rows do. The generator's rule refusing a case outside correctness is gone, and the check that asserted it, HRS0159, is replaced by HRS0178 asserting the opposite. The id is not reused, because a filed report joins to the inventory on it.

## A check's objective sits under an aspect of quality, decided 2026-09-22

The five objectives were peers, so conformance sat beside correctness as though the two were alternatives of the same kind. They are not. Conformance asks whether a thing has the shape its rules require, and that question comes before the others, because a thing that fails it is not in a state where asking whether its values are right tells anyone much. Nothing in the repo said so. No standard settles the grouping, so the choice is **unguided**, although several of the objectives under it take their names and their sense from ISO/IEC 25010.

Three aspects now group the objectives. Conformance asks whether the thing follows the rules it is held to. Integrity asks whether what the thing holds is sound, meaning right, whole, unchanged and in the right order, which is close to the United States Food and Drug Administration's definition of data integrity as completeness, consistency and accuracy. Operation asks how the thing runs rather than what it holds. Quality was considered as the name for the middle group and rejected, because in the data-management literature validity is a quality dimension like the others, so calling one subset quality would claim that conformance is not a quality concern.

The aspect is not marked on a check. A check carries `@category` and `@objective`, and the generator looks the aspect up, so an objective can never be filed under an aspect it does not belong to. The list of objectives is itself derived from that lookup table rather than typed a second time, so the two cannot drift and no rule is needed to hold them together. The new column is `quality_aspect`, and the selection option that matches it is `--aspect`, spelled short because a dash or an underscore inside a flag reads badly on a command line.

Six objectives were added with no checks behind them: consistency under integrity, and reliability, security, compatibility, maintainability and portability under operation, beside the performance objective that was already there. They are placeholders, written down because the questions they name will be asked once there is extraction, a graph and a running pipeline, and because working out where such a check belongs is easier done once than redone each time it comes up. Consistency is written in the Food and Drug Administration's sense, the order of events being demonstrable, and the dictionary says so, because the data-management literature gives the same word a different meaning, the same fact agreeing across two systems, and a check of that kind is correctness here.

This takes the objectives from five to eleven, which reverses the direction of the 2026-09-21 change that cut them from eight to five. The reason it should not repeat that failure is that the three the project could not apply, behavior, agreement and accuracy, all asked the same question about different material, whereas these six are mutually distinct and each has a published definition to point at. A person also never chooses from eleven at once, because the dictionary presents them under their three aspects.
