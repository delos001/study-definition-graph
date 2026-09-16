# study-definition-graph

## Overview

This project translates unstructured clinical documents into USDM-standard structure and loads them into a knowledge graph. Read as prose, the information from unstructured documents exists as a mental graph, for a person who has read them all. The result is variation and limitations to efficiently operationalizing the often extensive information, in that form.

Text extraction is a fairly well solved problem, but with that process, content and relationships within and across unstructured files dissipate.

The goal of this project is to recover and preserve both content and the relationships within and across documents that have been extracted to a computer-readable and queryable format. It builds on published USDM standards, not a novel ontology invented here.

See [BACKGROUND.md](BACKGROUND.md) for why the project exists and the problem in full.

## How it works

The pipeline runs as five stages, each taking the previous stage's output as its input. Each stage is one folder under `src/sdg/`.

1. **Acquire** (`sources/`): pull protocols and SAPs from ClinicalTrials.gov, record each one in a manifest, and check every pinned file against its fingerprint.
2. **Locate** (`locate/`): find section boundaries and the schedule grid, with no AI, so a later error can be traced to reading or to prompting but not both.
3. **Classify** (`classify/`): decide the document's type and what each section is about, with AI.
4. **Extract** (`extract/`): turn classified content into USDM structures, with every fact carrying where it came from.
5. **Graph** (`graph/`): load the structures into Neo4j, link a protocol to its SAP, and answer a question that spans both.

The Schedule of Activities is built last, because it depends on every stage above it working first.

See [PLAN.md](PLAN.md) for the phases, what each produces, and how each is verified.

A validation system is included in this workflow. Validation of process outputs is critical, but input stability and script behavior are also important to show accuracy and consistency and to withstand audit scrutiny. See [validation/README.md](validation/README.md) for the automated checks and how validation reports are written.

## Status

This project is IN DEVELOPMENT.

The project has six phases, Phase 0 to Phase 5, described in [PLAN.md](PLAN.md).

- Current status and the task backlog live in [GitHub Issues](https://github.com/delos001/study-definition-graph/issues);
- the build sequence and per-phase verification are in [PLAN.md](PLAN.md).

## Where to look

| For | Read |
| --- | --- |
| Which pinned file answers which question | [docs/sources_index.md](docs/sources_index.md) |
| Every map and inventory the project keeps | [docs/README.md](docs/README.md) |
| What each repo tool does, and how to run it | [repo_tools/README.md](repo_tools/README.md) |
| Which fields the project adds to USDM, and why | [local_definitions/README.md](local_definitions/README.md) |
| Which codes identify clients, therapeutic areas and document types | [registries/README.md](registries/README.md) |

## Setup

Commands are PowerShell. The same steps work on macOS or Linux with that shell's syntax.

### You need:
- Git,
- [Miniconda or Anaconda](https://docs.conda.io/projects/miniconda/),
- [Docker Desktop](https://www.docker.com/products/docker-desktop/),
- your own [Anthropic API key](https://console.anthropic.com/).

### Setup
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
#    Note: this command does not overwrite existing files so it is safe to re-run if needed.
acquire_sources
```

### Neo4j
Neo4j Browser is at <http://localhost:7474>, user `neo4j`, password `studydefinition`.
That password is set in `docker-compose.yml` and is for local development only.

```
# To start/restart the database:
docker compose up -d

# To stop the database but keep your data:
docker compose down

# To stop the database and discard your data:
docker compose down -v
```

### Setup Verification
Each command should exit 0:

```powershell
# Confirms every pinned file is present and matches its manifest entry; downloads nothing.
acquire_sources --dry-run

# Confirms nothing exists in inputs/ that a manifest does not record.
python repo_tools/find_unrecorded_files.py

# Recomputes every number (e.g. page count, class count) stated in the project's documents
# (e.g. README.md, PLAN.md, CLAUDE.md, and docs/) from the pinned documents under inputs/
# and reports any figure that no longer agrees.
python repo_tools/check_facts.py

# Confirms the pinned USDM model file inputs/standards/cdisc/usdm_v4/dataStructure.yml
# loads and has the correct shape. It prints the class names it found, and on any
# failure, it prints the cause and the appropriate resolution.
usdm_spec --list-classes

# Confirms the Neo4j database is running, accepts the login in .env, and is the version
# pinned in docker-compose.yml. Needs Docker running with the container up (step 6).
python repo_tools/check_neo4j.py

# Runs the automated checks in validation/; validation/README.md explains them.
pytest
```

## Working in this repo
Rules below are critical. See [CLAUDE.md](CLAUDE.md) for the full rule set, including the rules every Python file follows.

- Everything under `inputs/` is pinned and never edited.
- Every pinned file is downloaded and recorded in `manifests/` as it happens.
- `inputs/` is gitignored apart from its READMEs, so an unrecorded file cannot be restored.
- Pinned versions never move.
  - This includes the standards, the Neo4j image, and model identifiers.
  - A version that changes mid-project makes a failure unattributable.

## Layout

```
study-definition-graph/
  README.md                # this file
  BACKGROUND.md            # why the project exists, and the problem
  PLAN.md                  # build plan, phase by phase
  DECISIONS.md             # project development decisions made, and why
  CLAUDE.md                # rules for working in this repo
  environment.yml          # conda environment definition
  pyproject.toml           # sdg package, lint settings, and check settings
  docker-compose.yml       # Neo4j container definition
  .env.example             # copy this to .env and add your keys
  .gitignore               # what git leaves out, including inputs/ and .env
  .mcp.json                # GitHub server a Claude Code session connects to
  .claude/                 # rules and hooks for Claude Code sessions
  .githooks/               # checks that run before a commit
  docs/                    # project reference documents
    draft/                 #   diagrams and notes in progress
  manifests/               # where each pinned file came from, and its fingerprint
    study_documents/       #   records for each study's pinned documents
  inputs/                  # pinned source files the project reads; gitignored
    standards/             #   published standards used by this project (e.g. USDM, ICH M11)
    worked_examples/       #   real protocols CDISC mapped to USDM, with their mappings
    study_documents/       #   study-specific documents (e.g. protocols and SAPs)
  local_definitions/       # definitions this project adds to published standards; draft
    usdm_extensions/       #   fields added to USDM through its extension mechanism
  registries/              # codes for clients, therapeutic areas and document types; draft
  data/                    # pipeline products; gitignored
    interim/               #   files passed between pipeline stages
    processed/             #   finished pipeline output
  eval/                    # expected results the pipeline is scored against
  prompts/                 # prompts sent to the model (e.g. classification and extraction)
  src/                     # Python source
    sdg/                   #   pipeline package, one folder per stage
      classify/            #     decide a document's type and what each section is about
      extract/             #     turn classified content into USDM structures
      graph/               #     load structures into Neo4j and query them
      locate/              #     find section boundaries and the schedule grid
      sources/             #     fetch the pinned files and check them
      usdm/                #     read the USDM standard
      view/                #     print part of a pinned document or workbook
  repo_tools/              # tools that keep this repo in order
  validation/              # checks that prove the code works
    claude_hooks/          #   validation for the hooks in .claude/hooks/
    fixtures/              #   throwaway repos used during a validation run
    reports/               #   results of a full validation run, archived
    repo_tools/            #   validation for the tools in repo_tools/
    sources/               #   validation for src/sdg/sources/
    usdm/                  #   validation for src/sdg/usdm/
    view/                  #   validation for src/sdg/view/
```
