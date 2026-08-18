# study-definition-graph

Reconstructing structured clinical study definitions from unstructured protocol documents, and linking them across documents in a knowledge graph.

A clinical trial protocol contains a Schedule of Activities: a grid where rows are activities, columns are visits, and an X means the activity happens at that visit. That grid is a lossy rendering of a directed graph. Everything the schedule expresses as a footnote or as prose ("only if ALT above twice the upper limit of normal", "repeat every 21 days until progression") has no cell in the table.

The project's premise is that CDISC's USDM model has a typed structural home for each of those things. Rebuilding that graph is the point of this project.

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

## Setup

```powershell
conda env create -f environment.yml
conda activate sdg
docker compose up -d
Copy-Item .env.example .env
```

Fill in `ANTHROPIC_API_KEY` in `.env`. Neo4j Browser is at <http://localhost:7474> (user `neo4j`, password `studydefinition`).

`data/` is gitignored and rebuilds from `data/manifests/`. Check it with `python scripts/verify_manifests.py`.

## Where to look

| For | Read |
| --- | --- |
| Domain context and design constraints | [BACKGROUND.md](BACKGROUND.md) |
| Build sequence and decision record | [PLAN.md](PLAN.md) |
| Working rules | [CLAUDE.md](CLAUDE.md) |
| Which pinned file answers which question | [docs/sources.md](docs/sources.md) |
| How the standards feed each other | [docs/standards_map.html](docs/standards_map.html) |
| USDM guide section map | [docs/usdm_ig_map.md](docs/usdm_ig_map.md) |

The scripts describe themselves: `python scripts/read_pdf.py --help`, likewise `read_xlsx.py` and `verify_manifests.py`.
