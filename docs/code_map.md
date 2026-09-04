# Code map

How the code runs: the order of steps, and what each step produces for the next. One high-level workflow first, then one detail sheet per step that has enough inside it to need one. Arrows are files or folders flowing from one step to the next, not imports. A table of imports (what depends on what) is at the bottom for reference. Kept by hand; update it when a step or a file is added. Correct as of 2026-09-04.

## The workflow

```mermaid
flowchart TD
    manifests[("data/manifests/<br/>one JSON per source set:<br/>url, sha256, size")]
    raw[("data/raw/<br/>the pinned files<br/>(gitignored, never edited)")]

    step1["1. Get the pinned sources<br/>fetch_sources.py, verify_manifests.py"]
    step2["2. Read sources by hand<br/>read_pdf.py, read_xlsx.py<br/>(orientation, not pipeline)"]
    step3["3. Pipeline: read the USDM model<br/>pinned.py, usdm_spec.py"]
    later["Later phases, in PLAN.md order:<br/>acquire documents, locate sections,<br/>classify, extract, load the graph<br/>(not built yet)"]
    step4["4. Prove it<br/>pytest, check_facts.py, build_index.py"]

    manifests --> step1
    step1 --> raw
    raw --> step2
    raw --> step3
    manifests --> step3
    step3 --> later
    step3 --> step4
    raw --> step4
```

Step 2 is a side branch: a person runs those two scripts to look at a standard while working; nothing downstream consumes their output. Steps 1, 3 and 4 each have a sheet below.

## Sheet 1. Get the pinned sources

Once per machine, and again whenever a manifest changes. Everything the project reads is downloaded here, verified against its recorded fingerprint, and never edited afterwards.

```mermaid
flowchart TD
    manifests[("data/manifests/*.json")]
    fetch["fetch_sources.py<br/>for each entry: download if missing,<br/>hash, compare to recorded sha256,<br/>put in place only if it matches"]
    raw[("data/raw/")]
    verify["verify_manifests.py<br/>for each entry: present? size? sha256?<br/>and: any file in data/raw/ no manifest records?"]
    report["report on the terminal<br/>exit 0 clean, 1 drifted, 2 unrecorded, 3 bad manifest"]

    manifests --> fetch
    fetch --> raw
    manifests --> verify
    raw --> verify
    verify --> report
```

Both scripts use the same manifest-reading and hashing code, which lives in `src/sdg/pinned.py` (sheet 3), so the check run by hand here is the check the pipeline runs automatically.

## Sheet 3. Pipeline: read the USDM model

The only pipeline step built so far. Everything that needs a fact about USDM goes through `usdm_spec.py`, and everything that needs a pinned file goes through `pinned.py`.

```mermaid
flowchart TD
    manifests[("data/manifests/")]
    raw[("data/raw/usdm_v4/uml/dataStructure.yml")]

    subgraph pinned["pinned.py"]
        p1["require_repo(): am I running<br/>from inside the repo?"]
        p2["find the file's manifest entry"]
        p3["check size, then sha256"]
        p4["PinnedFile: content + identity<br/>(sha256, url with the version)"]
        p1 --> p2 --> p3 --> p4
    end

    subgraph usdm["usdm_spec.py"]
        u1["load(): parse the YAML"]
        u2["shape check: every class has<br/>Modifier and Attributes; every attribute<br/>has Type, Cardinality, Relationship Type"]
        u3["accessors: class_names, is_abstract,<br/>attributes, targets"]
        u1 --> u2 --> u3
    end

    cli["command line<br/>python -m sdg.usdm_spec --list-classes / --attributes"]
    facts["check_facts.py<br/>(the concrete-class count)"]
    tests["tests/"]
    later["later phases: schemas for extraction,<br/>the graph's edge list, provenance stamps"]

    manifests --> p2
    raw --> p3
    p4 --> u1
    u3 --> cli
    u3 --> facts
    u3 --> tests
    u3 --> later
```

Every failure has its own exit code and message: file missing (1), cannot be verified or does not match (3), wrong shape (4), unknown class (5), not running from inside the repo (6). If a source ever comes from an API instead of a manifest, the inside of `pinned.py` changes and nothing to its right does.

## Sheet 4. Prove it

Three separate proofs, run by hand. None feeds the pipeline; each guards something the pipeline or the documents claim.

```mermaid
flowchart TD
    testfiles["tests/test_*.py<br/>+ tests/fixtures/"]
    pytest["pytest<br/>every check, positive and negative"]
    terminal["pass / fail on the terminal<br/>(development runs write nothing)"]
    record["tests/validation/*.md<br/>only with --validation-report:<br/>the auditable record, committed"]

    docs["README.md, BACKGROUND.md, docs/"]
    raw[("data/raw/")]
    facts["check_facts.py<br/>re-derive every number the docs state"]
    factsout["drift report, exit 0 or 1"]

    headers["scripts/*.py header blocks"]
    index["build_index.py"]
    scriptsreadme["scripts/README.md (generated)"]

    testfiles --> pytest --> terminal
    pytest -- "--validation-report" --> record
    docs --> facts
    raw --> facts
    facts --> factsout
    headers --> index --> scriptsreadme
```

## Reference: what imports what

For "if I change this file, what else is affected". Third-party libraries omitted; `environment.yml` lists them.

| File | Imports from the repo | For |
| --- | --- | --- |
| `src/sdg/usdm_spec.py` | `sdg.pinned` | the verified model file and the repo root |
| `scripts/fetch_sources.py` | `sdg.pinned` | manifest reading, hashing, repo root |
| `scripts/verify_manifests.py` | `sdg.pinned` | manifest reading, per-entry check, folder locations |
| `scripts/check_facts.py` | `sdg.usdm_spec`; `read_pdf.py` (by file path, same folder) | the class count; the registered-PDF table |
| `scripts/read_pdf.py`, `read_xlsx.py`, `build_index.py` | nothing | leaves |
| `tests/test_usdm_spec.py` | `sdg.usdm_spec`, `sdg.pinned` | the loader; a temporary manifests folder for failure cases |
| `tests/test_pinned.py` | `sdg.pinned` | every success and failure case |
| `tests/conftest.py` | `sdg.pinned` | the two shared manifest-staging fixtures |
| `tests/test_validation_report.py` | `conftest.py` (copied into throwaway suites) | the record-writer |
