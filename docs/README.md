# docs/

This folder contains the project's documentation about itself.

The information is usually kept by hand and stored here when a the information is cross cutting across more than one pipeline component not directly related to another pipeline or validation component in a way that requires it to be stored next to that component.

| File | What it shows |
| --- | --- |
| `sources_index.md` | Which pinned file answers which question, how to open it, and which files were reviewed and not taken. |
| `sdg_files_inventory.md` | Every file in `src/sdg/`, folder by folder, as a workflow or a step, with what each uses and which are run by hand. |
| `validation_files_inventory.md` | Every file in `validation/`, folder by folder, with the code file each one validates. |
| `repo_tools_files_inventory.md` | Every file in `repo_tools/`, with how each is run and what it uses. |
| `standards_read_record.md` | What has been read from each pinned standard and what it established, so a claim about a standard can be told from an inference. |
| `draft/` | Work in progress. Nothing here is linked to or relied on. |

Prose is one paragraph per line, never hard-wrapped, so a phrase can be found with `grep`.
