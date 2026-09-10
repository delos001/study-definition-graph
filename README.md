# study-definition-graph

## Overview

This project translates unstructured clinical documents into USDM-standard structure and loads them into a knowledge graph, preserving the content and the relationships within and across documents while keeping everything computer-readable and queryable. It builds on published USDM standards, not an ontology invented here.

A single study is spread across several planning documents, protocol, Statistical Analysis Plan, Investigator's Brochure, written at different times, from different perspectives and purposes, with different content and structure. Read as prose, the study exists only in the head of whoever has read them all. The challenge is not extracting the text. Instead, the challenge is recovering the structure that extraction destroys or leaves implicit: a Schedule of Activities grid that flattens a timing graph, or one analysis population that appears as "Intent-to-Treat" in one document and "Full Analysis Set" in another. This project aims to produce a method to recover that structure and make it queryable while maintaining data traceability.

See [BACKGROUND.md](BACKGROUND.md) for why the project exists and the problem in full.

## Status

This project has 6 phases (Phase 0-5):
- Current status and the task backlog live in [GitHub Issues](https://github.com/delos001/study-definition-graph/issues);
- the build sequence and per-phase verification are in [PLAN.md](PLAN.md).

## Setup

Commands are PowerShell. The same steps work on macOS or Linux with that shell's syntax.

You need:
- Git, [Miniconda or Anaconda](https://docs.conda.io/projects/miniconda/),
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) running,
- your own [Anthropic API key](https://console.anthropic.com/).
- Nothing here sits behind a company network or a paid subscription: every source document is public and every service is either local or free.

```powershell
git clone <repo-url> ; cd ...\study-definition-graph
git config core.hooksPath .githooks   # pre-commit checks, see below

# 1. Python environment. Python 3.12, pinned in environment.yml.
conda env create -f environment.yml
conda activate sdg

# 1b. Install this repo's own package (src/sdg/) in editable mode, so that
#     `python -m sdg.<module>` resolves and code edits take effect with no
#     reinstall. Dependencies stay owned by environment.yml, not this install.
pip install -e .

# 2. Neo4j, pinned to 5.26.29-community. The graph persists in Docker volumes,
#    so `docker compose down` keeps your data and `down -v` discards it.
docker compose up -d

# 3. Secrets. Put your key in ANTHROPIC_API_KEY. Leave CDISC_API_KEY blank:
#    it is optional and a non-member key grants nothing.
Copy-Item .env.example .env

# 4. Pinned sources. Everything under inputs/ is gitignored, so a fresh clone
#    has none of it. Every pinned file is recorded in manifests/ with its URL
#    and sha256. This downloads them all and verifies each hash. Add --dry-run
#    to see what it would fetch without touching the network.
python -m sdg.sources.acquire_sources
```

Nothing here overwrites a file that already exists, so the fetch is safe to re-run and will only ever add what is missing.

The hook line enables `.githooks/pre-commit`, which blocks a commit if `scripts/README.md` is out of date with the scripts it describes. It is read-only, instant, and uses only the standard library, so it works whether or not the `sdg` environment is active.

Then confirm it worked. All six should exit 0:

```powershell
python -m sdg.sources.acquire_sources --dry-run   # every pinned file present and matching its entry
python scripts/find_unrecorded_files.py           # nothing under inputs/ that a manifest does not record
python scripts/check_facts.py         # every number stated in the docs re-derived from those files
python scripts/read_pdf.py --docs     # lists each registered document as present or NOT DOWNLOADED
python -m sdg.usdm.usdm_spec --list-classes       # lists the USDM classes read from the pinned model spec
pytest                                # runs the automated checks in tests/; tests/README.md explains them
```

Neo4j Browser is at <http://localhost:7474>, user `neo4j`, password `studydefinition`. That password is set in `docker-compose.yml` and is for local development only.

## Working in this repo

A few load-bearing rules; [CLAUDE.md](CLAUDE.md) has the full set, including the source-file conventions every script follows.

- Everything under `inputs/` is pinned and never edited, and every download is recorded in `manifests/` in the same breath.
- `inputs/` is gitignored apart from its READMEs, so an unrecorded file cannot be restored.
- Pinned versions never move: not the standards, not the Neo4j image, not a model identifier. A version that changes mid-project makes a failure unattributable.
- The repo is de-identified: no company, no people, no locations, no partnerships.

## Layout

```
study-definition-graph/
  README.md                  # this file
  BACKGROUND.md              # why the project exists, and the problem
  PLAN.md                    # build sequence and per-phase verification
  DECISIONS.md               # decisions made, and why
  CLAUDE.md                  # working rules
  environment.yml
  docker-compose.yml         # neo4j, pinned
  .env.example
  docs/                      # the project's maps of itself; README.md there lists them
  manifests/                 # one record per set of pinned downloads: source, version, fingerprint
    study_documents/         #   one record per study fetched into inputs/study_documents/, written by the fetch script
  inputs/                    # everything downloaded from outside, pinned and never edited; gitignored
    standards/               #   the standards the project depends on, by publisher: cdisc/, ich/, crosswalks/
    worked_examples/         #   CDISC's three worked examples
    study_documents/         #   protocols and SAPs as fetched, one folder per study
  data/                      # pipeline output, regenerable; gitignored
    interim/                 #   between pipeline stages
    processed/               #   final pipeline output
  eval/                      # hand-built answer keys and acceptance thresholds; committed
  prompts/                   # one file per prompt, versioned
  src/sdg/                   # the sdg Python package (source code), installed with pip install -e .; README.md in src/ and src/sdg/ list what is there
  scripts/                   # run by hand; README.md here is generated
  tests/                     # automated checks and validation records; README.md there explains them
```

## Where to look

| For | Read |
| --- | --- |
| Why it exists and the problem | [BACKGROUND.md](BACKGROUND.md) |
| Build sequence and per-phase verification | [PLAN.md](PLAN.md) |
| Decisions made, and why | [DECISIONS.md](DECISIONS.md) |
| Current status and task backlog | [GitHub Issues](https://github.com/delos001/study-definition-graph/issues) |
| Working rules | [CLAUDE.md](CLAUDE.md) |
| Which pinned file answers which question | [docs/sources_index.md](docs/sources_index.md) |
| Where each pinned file came from, and its fingerprint | [manifests/README.md](manifests/README.md) |
| How the standards feed each other | [docs/standards_lineage.html](docs/standards_lineage.html) |
| USDM guide section map | [docs/usdm_ig_ledger.md](docs/usdm_ig_ledger.md) |
| Which script or module calls which | [docs/workflow_map.md](docs/workflow_map.md) |
| What each script does | [scripts/README.md](scripts/README.md) |

[scripts/README.md](scripts/README.md) is a generated index of every script and how to invoke it. It is rebuilt from the scripts' own header blocks by `python scripts/build_index.py`, so it cannot drift from them.
