# CLAUDE.md

Rules for this repo, on top of the global `~/.claude/CLAUDE.md`. `README.md` is what the project is and how to run it; `PLAN.md` is the build sequence and the decision record; `docs/sources.md` is which file answers which question. Keep each to its own job.

Markdown prose is one paragraph per line, never hard-wrapped: `grep` is a primary access path here, and a phrase split across lines silently fails to match.

## Session start

1. `BACKGROUND.md` - why the project exists and the design constraints.
2. `PLAN.md`, "Next session, in order" - what was agreed last time.
3. `docs/sources.md`, first half - every pinned file, and whether it has been read.

## Grounding

**No claim about what a pinned standard means, or how it maps to protocol content, without reading the source first.** `docs/sources.md` routes to it.

**Never read a pinned PDF whole.** 500 pages combined. Take a section, a page range, or a search term.

**Label every claim** as one of:

| Label | Means |
| --- | --- |
| **Source-read** | Read this session. Name the document and the section or page. |
| **Measured** | Computed from a pinned file. Show the command or output. |
| **Inferred** | Reasoned from names or structure. Say so before making the claim, not after being asked. |

**When the guidance runs out**, say which case you are in and keep going:

1. A standard covers it - follow it, cite it.
2. Not covered, but the content must be captured - use USDM's extension mechanism (IG 6.4) and record every extension in `docs/`.
3. A process or design question rather than a data-shape one - decide, label it **unguided**, record it in `PLAN.md`.

## Data

- `data/raw/` is immutable. Downstream reads from it and writes to `data/interim/` or `data/processed/`.
- Every download gets a `data/manifests/` entry in the same breath, never a record inside `data/raw/`. `data/` is gitignored, so an unrecorded file cannot be restored and is indistinguishable from a pinned one.
- Pinned versions never move. Never fetch latest.
- `python scripts/verify_manifests.py` checks them: 0 clean, 1 missing or altered, 2 unrecorded, 3 unreadable manifest.

## Pipeline

- Prompts live in versioned files under `prompts/`, never as string literals. An edit creates a new version.
- Every extracted fact carries provenance: source document, section, page, character span, prompt id and version, model id, timestamp. It exists to trace a wrong answer back to the sentence that caused it.

## Source files

Reading only the comments should give an accurate picture of what a script does. `scripts/read_pdf.py` is the worked example; match it.

Every script opens with:

```
Script:      filename.py
Description: what it does, and any non-obvious constraint it operates under
Inputs:      files or services read, and whether they are read-only
Outputs:     what it writes, or "writes nothing to disk"
Usage:       one line per invocation mode, with a real example
Exit codes:  each code and what causes it
Date:        YYYY-MM-DD
Author:      Jason Delosh
```

And carries:

- `###` banner headers grouping the file into named sections.
- A docstring on every function: what it does, what it returns, and why it works that way where that is not obvious.
- A comment on every non-obvious block, every `try`/`except` (what it absorbs, what happens instead), and every workaround or non-standard library.
- Comments explain why. Never restate the code.

Heavy commenting is not licence for clever code. If a block needs a paragraph to explain, rewrite the block.
