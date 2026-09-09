# src/sdg/

The `sdg` package: the pipeline, as code other code imports. It has one folder per group of work, in the order the pipeline runs. Each folder's `README.md` lists the files in it; each file's header block is the full account of that file. Nothing is described at more than one level.

| Folder | What it does |
| --- | --- |
| `sources/` | Get and keep the pipeline's inputs: acquire recorded files, update a source to a new version, and prove a file is the pinned one before any stage reads it. |
| `usdm/` | Read the USDM standard so the pipeline knows what a class is, what it holds, and what it points at. |
| `locate/` | Phase 1: take a study document and find where its content lives, section boundaries and the schedule grid, with no AI. |
| `classify/` | Phase 2: say what kind of document this is and what each located section is about. |
| `extract/` | Phase 3: turn classified content into USDM-shaped structures, each carrying where it came from. |
| `graph/` | Phase 4: load the structures into Neo4j, link across documents, and answer questions that span them. |

A file used by several stages goes in the root of `sdg/`. When two or more such files are about the same thing, they move into a folder named for that thing. Nothing gets a folder before it has earned one.

A script has one objective. Generally its functionality should be distinct or perform like things. Discrete jobs upstream or downstream of the objective should generally be evaluated to determine whether they belong in a separate callable, reusable script.

Every folder holds two kinds of file. An orchestrator runs steps in order and is what a person or a later stage calls; a piece does one thing and belongs to no orchestrator, so any orchestrator can use it. The whole map, with which orchestrator uses which piece, is `docs/workflow_map_outline.md`.

Installed once with `pip install -e .` (README.md, step 1b). The tools a person runs beside the pipeline are in `scripts/`, and the checks that prove this code works are in `tests/`, which mirrors these folders.
