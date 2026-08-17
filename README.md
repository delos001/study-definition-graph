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
and the design constraints. [PLAN.md](PLAN.md) holds the build sequence and the
decision record. [CLAUDE.md](CLAUDE.md) holds the working conventions.

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

## Reading the pinned USDM Implementation Guide

```powershell
python scripts/read_ig.py --list      # section map
python scripts/read_ig.py 4.23        # one section as text
```

Section-to-page map, and a record of which sections have been read and verified:
[docs/usdm_ig_map.md](docs/usdm_ig_map.md).

## Conventions

Working conventions are in [CLAUDE.md](CLAUDE.md), not duplicated here.
