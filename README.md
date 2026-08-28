# study-definition-graph

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

# 2. Neo4j, pinned to 5.26.29-community. The graph persists in Docker volumes,
#    so `docker compose down` keeps your data and `down -v` discards it.
docker compose up -d

# 3. Secrets. Put your key in ANTHROPIC_API_KEY. Leave CDISC_API_KEY blank:
#    it is optional and a non-member key grants nothing.
Copy-Item .env.example .env

# 4. Source documents. data/ is gitignored, so a fresh clone has none of them.
#    Every pinned file is recorded in data/manifests/ with its URL and sha256.
#    This downloads them all and verifies each hash. Add --dry-run to see what
#    it would fetch without touching the network.
python scripts/fetch_sources.py
```

Nothing here overwrites a file that already exists, so the fetch is safe to re-run and will only ever add what is missing.

The hook line enables `.githooks/pre-commit`, which blocks a commit if `scripts/README.md` is out of date with the scripts it describes. It is read-only, instant, and uses only the standard library, so it works whether or not the `sdg` environment is active.

Then confirm it worked. All three should exit 0:

```powershell
python scripts/verify_manifests.py    # every pinned file present and matching its recorded hash
python scripts/check_facts.py         # every number stated in the docs re-derived from those files
python scripts/read_pdf.py --docs     # lists each registered document as present or NOT DOWNLOADED
```

Neo4j Browser is at <http://localhost:7474>, user `neo4j`, password `studydefinition`. That password is set in `docker-compose.yml` and is for local development only.

## Working in this repo

A few load-bearing rules; [CLAUDE.md](CLAUDE.md) has the full set, including the source-file conventions every script follows.

- `data/raw/` is immutable, and every download is recorded in `data/manifests/` in the same breath.
- `data/` is gitignored, so an unrecorded file cannot be restored.
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
  docs/                      # source navigation and standards maps
  data/
    manifests/               # the only part of data/ that is committed
    raw/                     # never modified after download
    interim/                 # parsed pages, sections
    processed/               # extracted entities, graph load files
    eval/                    # hand-built correct answers
  prompts/                   # one file per prompt, versioned
  src/sdg/
  scripts/                   # run by hand; README.md here is generated
  tests/
```

## Where to look

| For | Read |
| --- | --- |
| Why it exists and the problem | [BACKGROUND.md](BACKGROUND.md) |
| Build sequence and per-phase verification | [PLAN.md](PLAN.md) |
| Decisions made, and why | [DECISIONS.md](DECISIONS.md) |
| Current status and task backlog | [GitHub Issues](https://github.com/delos001/study-definition-graph/issues) |
| Working rules | [CLAUDE.md](CLAUDE.md) |
| Which pinned file answers which question | [docs/sources.md](docs/sources.md) |
| How the standards feed each other | [docs/standards_map.html](docs/standards_map.html) |
| USDM guide section map | [docs/usdm_ig_map.md](docs/usdm_ig_map.md) |
| What each script does | [scripts/README.md](scripts/README.md) |

[scripts/README.md](scripts/README.md) is a generated index of every script and how to invoke it. It is rebuilt from the scripts' own header blocks by `python scripts/build_index.py`, so it cannot drift from them.
