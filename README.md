# study-definition-graph

## Overview

This project translates unstructured clinical documents into USDM-standard structure and loads them into a knowledge graph. Read as prose, the information from unstructured documents exists as a mental graph, for a person who has read them all. The result is variation and limitations to efficiently operationalizing the often extensive information, in that form.

Text extraction is a fairly well solved problem, but with that process, content and relationships within and across unstructured files dissipate.

The goal of this project is to recover and preserve both content and the relationships within and across documents that have been extracted to a computer-readable and queryable format. It builds on published USDM standards, not a novel ontology invented here.

Future work may include operational documents as well.

See [BACKGROUND.md](BACKGROUND.md) for why the project exists and the problem in full.

## Status

This project is IN DEVELOPMENT.

This project has 6 phases (Phase 0-5):
- Current status and the task backlog live in [GitHub Issues](https://github.com/delos001/study-definition-graph/issues);
- the build sequence and per-phase verification are in [PLAN.md](PLAN.md).

## Setup

Commands are PowerShell. The same steps work on macOS or Linux with that shell's syntax.

You need:
- Git,
- [Miniconda or Anaconda](https://docs.conda.io/projects/miniconda/),
- [Docker Desktop](https://www.docker.com/products/docker-desktop/),
- your own [Anthropic API key](https://console.anthropic.com/).

Nothing here sits behind a company network or a paid subscription: every source document is public and every service is either local or free.

```powershell
# 1. Clone the repo then navigate to it.
git clone <repo-url> && cd study-definition-graph

# 2. Turn on the pre-commit checks. They block a commit when a generated file is out of
#    date or a Python file breaks the repo's rules.
#    `.githooks/README.md` lists every check.
git config core.hooksPath .githooks

# 3. Create the Python environment. Python 3.12 comes from the pinned environment.yml.
conda env create -f environment.yml

# 4. Activate the sdg conda environment.
conda activate sdg

# 5. Install the package defined in the src/ folder in editable mode, so that the repo's
#    commands like usdm_spec and read_pdf work correctly and code edits take effect with
#    no reinstall.
#    Dependencies stay owned by environment.yml, not this install.
pip install -e .

# 6. Start the Neo4j container. Its version, two ports (browser and driver), and
#    password come from docker-compose.yml in the repo folder, pinned to 5.26.29-community.
#    The graph persists in Docker volumes.
docker compose up -d

# 7. Create your secrets file using the command below.
#    Then obtain an Anthropic API key from https://console.anthropic.com/
#    Open .env and paste the key directly after the ANTHROPIC_API_KEY field.
#    Leave CDISC_API_KEY blank because it is optional and a non-member key grants nothing.
Copy-Item .env.example .env

# 8. Verify the key reaches the Claude API. Running the script below sends one small
#    message via the API. It needs a working network and costs a fraction of a cent.
python repo_tools/check_api_key.py

# 9. Acquire pinned sources. Everything under inputs/ is gitignored, so a fresh clone
#    has none of it. Every pinned file is recorded in manifests/ with its URL and sha256.
#    The command below downloads them all and verifies each hash.
#    Add --dry-run to see what it would fetch without touching the network.
#    The sdg environment must be active (step 4 above).
acquire_sources
```

Nothing here overwrites a file that already exists, so the fetch is safe to re-run and will only ever add what is missing.

Then confirm it worked. All six should exit 0:

```powershell
acquire_sources --dry-run   # every pinned file present and matching its entry
python repo_tools/find_unrecorded_files.py           # nothing under inputs/ that a manifest does not record
python repo_tools/check_facts.py         # every number stated in the docs re-derived from those files
read_pdf --docs     # lists each registered document as present or NOT DOWNLOADED
usdm_spec --list-classes       # lists the USDM classes read from the pinned model spec
pytest                                # runs the automated checks in validation/; validation/README.md explains them
```

Neo4j Browser is at <http://localhost:7474>, user `neo4j`, password `studydefinition`. That password is set in `docker-compose.yml` and is for local development only.
- `docker compose down` keeps your data
- `down -v` discards it.

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
  repo_tools/                   # run by hand; README.md here is generated
  validation/                     # automated checks and validation records; README.md there explains them
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
| Which files are in the sdg package, and what each uses | [docs/sdg_files_inventory.md](docs/sdg_files_inventory.md) |
| What each script does | [repo_tools/README.md](repo_tools/README.md) |

[repo_tools/README.md](repo_tools/README.md) is a generated index of every script and how to invoke it. It is rebuilt from the scripts' own header blocks by `python repo_tools/build_index.py`, so it cannot drift from them.
