# docs/

This folder contains the project's documentation about itself.

A document lives here when it cuts across more than one part of the pipeline, so it does not belong beside any one code folder or validation folder. Every document here is kept by hand except `commands.md`, which the `build_index` command generates.

| File | What it shows |
| --- | --- |
| `sources_index.md` | Which pinned file answers which question, how to open it, and which files were reviewed and not taken. |
| `standards_read_record.md` | What has been read from each pinned standard and what it established, so a claim about a standard can be told from an inference. |
| `commands.md` | What each installed command does and how to run it. |
| `exit_codes.csv` | What each exit code means, one row per code, used by every script in the repo. |
| `draft/` | Work in progress. Nothing here is linked to or relied on. |

Prose is one paragraph per line, never hard-wrapped, so a phrase can be found with `grep`.
