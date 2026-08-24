# study-definition-graph

Turning clinical study documents into a knowledge graph, built on published standards rather than an ontology invented here.

A clinical study is described across several documents. The protocol says what will be done, the Statistical Analysis Plan says how the data will be analysed, the Investigator's Brochure carries what is already known about the drug, the synopsis is a compressed retelling of the protocol. They are written at different times by different people, and they refer to the same things in different words. Read as prose, the study only ever exists in a reader's head. The point of this project is to put it somewhere a query can reach: things, and the relationships between them, with every extracted fact traceable back to the sentence it came from.

It starts with the protocol, because that is the densest and most structured of them and because CDISC publishes a model for exactly its content. Other document types follow.

The difficulty is not pulling text out of a PDF. It is that the content carrying the most structure, a Schedule of Activities grid, eligibility criteria, dose modification rules, is exactly what a text extractor flattens. [BACKGROUND.md](BACKGROUND.md) has why the project exists, what it is up against, the design constraints, and what is still open.

## Status

Phase 0: foundation and orientation.

| Phase | What | State |
| --- | --- | --- |
| 0 | Environment, Neo4j, pinned standards, readers | in progress |
| 1 | Fetch protocol + SAP pairs, parse and segment (no AI) | not started |
| 2 | Classify documents and sections | not started |
| 3 | Extract into USDM shape, schema-forced, with provenance | sketch |
| 4 | Load the graph, resolve entities, test the multi-hop query | sketch |
| 5 | Schedule of Activities reconstruction | sketch |

The corpus is protocol and SAP pairs to begin with, because that is the smallest set where classifying a document is a real decision and linking across documents is real. Other document types are added once the pipeline handles two.

## Setup

Commands are PowerShell. The same steps work on macOS or Linux with that shell's syntax.

You need Git, [Miniconda or Anaconda](https://docs.conda.io/projects/miniconda/), [Docker Desktop](https://www.docker.com/products/docker-desktop/) running, and your own [Anthropic API key](https://console.anthropic.com/). Nothing here sits behind a company network or a paid subscription: every source document is public and every service is either local or free.

```powershell
git clone <repo-url> ; cd study-definition-graph
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

The hook line enables `.githooks/pre-commit`, which blocks a commit if `scripts/README.md` is out of date with the scripts it describes, or if a figure stated in the markdown no longer matches the pinned files. Both checks are read-only and take under a second.

Then confirm it worked. All three should exit 0:

```powershell
python scripts/verify_manifests.py    # every pinned file present and matching its recorded hash
python scripts/check_facts.py         # every number stated in the docs re-derived from those files
python scripts/read_pdf.py --docs     # lists each registered document as present or NOT DOWNLOADED
```

Neo4j Browser is at <http://localhost:7474>, user `neo4j`, password `studydefinition`. That password is set in `docker-compose.yml` and is for local development only.

## Working in this repo

- `data/raw/` is immutable. Nothing edits a file there after download. Downstream writes to `data/interim/` or `data/processed/`.
- Every download gets a `data/manifests/` entry in the same breath. `data/` is gitignored, so an unrecorded file cannot be restored and is indistinguishable from a pinned one.
- Pinned versions never move: not the standards, not the Neo4j image, not a model identifier. A version that changes mid-project makes a failure unattributable.
- Any number written into a document has to be recomputable. Add it to `scripts/check_facts.py` and run that after changing the corpus.
- Prompts live in versioned files under `prompts/`, never as string literals in code.
- The repo is de-identified. No company, no people, no locations, no partnerships. Anything learned from a conversation is written up as a design constraint, a target problem, or an open question.

[CLAUDE.md](CLAUDE.md) is the full version of these rules, including the source-file conventions every script follows.

## Layout

```
study-definition-graph/
  README.md                  # this file
  BACKGROUND.md              # why the project exists, and its design constraints
  PLAN.md                    # build sequence and decision record
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
| Why it exists, design constraints, open questions | [BACKGROUND.md](BACKGROUND.md) |
| Build sequence and decision record | [PLAN.md](PLAN.md) |
| Working rules | [CLAUDE.md](CLAUDE.md) |
| Which pinned file answers which question | [docs/sources.md](docs/sources.md) |
| How the standards feed each other | [docs/standards_map.html](docs/standards_map.html) |
| USDM guide section map | [docs/usdm_ig_map.md](docs/usdm_ig_map.md) |
| What each script does | [scripts/README.md](scripts/README.md) |

[scripts/README.md](scripts/README.md) is a generated index of every script and how to invoke it. It is rebuilt from the scripts' own header blocks by `python scripts/build_index.py`, so it cannot drift from them.
