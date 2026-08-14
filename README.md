# study-definition-graph

Reconstructing structured clinical study definitions from unstructured protocol
documents, and linking them across documents in a knowledge graph.

A clinical trial protocol contains a Schedule of Activities: a grid where rows
are activities, columns are visits, and an X means the activity happens at that
visit. That grid is a lossy rendering of a directed graph. Everything the
schedule expresses as a footnote or as prose ("only if ALT above twice the upper
limit of normal", "repeat every 21 days until progression") has a typed home in
CDISC's USDM model and no cell in the table.

Rebuilding that graph is the point of this project.

See [BACKGROUND.md](BACKGROUND.md) for the domain context, the USDM essentials,
and the design constraints. Read it at session start.

## Status

Phase 0: foundation and orientation.

| Phase | What | State |
| --- | --- | --- |
| 0 | Environment, Neo4j, pinned USDM v4.0 spec, spec loader | in progress |
| 1 | Fetch protocol + SAP pairs, parse and segment (no AI) | not started |
| 2 | Classify documents and sections | not started |
| 3 | Extract into USDM shape, schema-forced, with provenance | sketch |
| 4 | Load the graph, resolve entities, test the multi-hop query | sketch |
| 5 | Schedule of Activities reconstruction | sketch |

## Setup

```powershell
conda env create -f environment.yml
conda activate sdg
docker compose up -d
Copy-Item .env.example .env
```

Then fill in `ANTHROPIC_API_KEY` in `.env`. Neo4j Browser is at
<http://localhost:7474> (user `neo4j`, password `studydefinition`).

## Conventions

- `data/raw/` is immutable. Nothing writes to it after download. Everything
  downstream reads from it and writes to `data/interim/` or `data/processed/`.
- The USDM specification is **pinned to a recorded commit**, not fetched latest.
  USDM has shipped four major versions in under three years; a version moving
  mid-project would silently change extraction output. See
  `data/raw/usdm_v4/manifest.json`.
- Prompts live in versioned files under `prompts/`, never as string literals in
  code. An edit creates a new version.
- Every extracted fact carries provenance: source document, section, page, char
  span, prompt id and version, model id, timestamp.
