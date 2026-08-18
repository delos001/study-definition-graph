# study-definition-graph

Reconstructing structured clinical study definitions from unstructured protocol
documents, and linking them across documents in a knowledge graph.

A clinical trial protocol contains a Schedule of Activities: a grid where rows
are activities, columns are visits, and an X means the activity happens at that
visit. That grid is a lossy rendering of a directed graph. Everything the
schedule expresses as a footnote or as prose ("only if ALT above twice the upper
limit of normal", "repeat every 21 days until progression") has no cell in the
table.

The project's premise is that CDISC's USDM model has a typed structural home for
each of those things. Rebuilding that graph is the point of this project.

See [BACKGROUND.md](BACKGROUND.md) for the domain context and design
constraints. [PLAN.md](PLAN.md) holds the build sequence and the decision
record. [CLAUDE.md](CLAUDE.md) holds the working conventions, including which
pinned source answers which kind of question.

Neither this file nor `BACKGROUND.md` carries technical content about USDM, M11
or E9(R1). That comes from the pinned sources, read at the point of use.

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

Then fill in `ANTHROPIC_API_KEY` in `.env`. Neo4j Browser is at
<http://localhost:7474> (user `neo4j`, password `studydefinition`).

`data/` is gitignored. Every pinned file is recorded in `data/manifests/` with
its url and sha256, so the corpus can be rebuilt and verified from a clean
clone.

## Pinned standards

| Set | What | Where |
| --- | --- | --- |
| CDISC USDM v4.0 | The data model, five official standards plus worked examples and two crosswalks | `data/raw/usdm_v4/`, `usdm_examples/`, `usdm_mappings/` |
| ICH M11 Step 4 | Protocol Guideline, Template and Technical Specification | `data/raw/ich_m11/` |
| ICH E9(R1) | The estimand framework | `data/raw/ich_e9r1/` |

## Reading the pinned PDFs

```powershell
python scripts/read_pdf.py --docs                 # what is registered
python scripts/read_pdf.py --list                 # USDM IG section map
python scripts/read_pdf.py 4.23                   # one IG section as text
python scripts/read_pdf.py --doc m11-techspec --find "Estimand"
python scripts/read_pdf.py --doc e9r1 A.3.3
```

The USDM IG and E9(R1) carry bookmarks and can be addressed by section number.
The M11 PDFs carry none and answer only to `--find` and `--pages`.

Reading the pinned workbooks:

```powershell
python scripts/read_xlsx.py --all --find "estimand"
python scripts/read_xlsx.py Alexion --sheet mainTimeline --format records
```

## Finding your way around the sources

- [docs/sources.md](docs/sources.md) — which file answers which question, whether
  it has been read yet, and what exists that we deliberately did not download.
- [docs/standards_map.html](docs/standards_map.html) — how the four standards
  feed each other, with every connection marked as verified or not.
- [docs/usdm_ig_map.md](docs/usdm_ig_map.md) — section-to-page map for the USDM
  implementation guide, and which sections have been read.

## Conventions

Working conventions are in [CLAUDE.md](CLAUDE.md), not duplicated here.
