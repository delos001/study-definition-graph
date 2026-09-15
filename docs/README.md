# docs/

The project's documentation about itself: maps a working session consults, kept by hand and linked from `CLAUDE.md` and `README.md`. Why the project exists is `BACKGROUND.md`, the build plan is `PLAN.md`, and the record of choices is `DECISIONS.md`, all at the repo root.

| File | What it shows |
| --- | --- |
| `sources_index.md` | Which pinned file answers which question and how to open it, and what was reviewed and not taken. Skim at session start. |
| `sdg_files_inventory.md` | Every file in `src/sdg/`, folder by folder, as a workflow or a step, with what each uses and which are run by hand. |
| `validation_files_inventory.md` | Every file in `validation/`, folder by folder, with the code file each one validates. |
| `repo_tools_files_inventory.md` | Every file in `repo_tools/`, with how each is run and what it uses. |
| `usdm_local_extensions.md` | Every field this project adds to USDM through the standard's extension mechanism, and why the standard had no place for it. |
| `usdm_ig_ledger.md` | Section-by-section routing table for the USDM implementation guide, with a read ledger. |
| `standards_lineage.html` | Diagram of how the pinned standards descend from and feed one another. |
| `draft/` | Work in progress. Nothing here is linked to or relied on. |

Prose is one paragraph per line, never hard-wrapped, so a phrase can be found with `grep`.
