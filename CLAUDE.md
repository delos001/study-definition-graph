# CLAUDE.md

Standing rules for this repo. Applies to every session, on top of the global `~/.claude/CLAUDE.md`.

This file holds **rules**. `README.md` holds what the project is and how to run it. `PLAN.md` holds the build sequence and the record of why decisions were made. Do not add rules to the other two, and do not restate rules from here in them.

**Markdown prose is not hard-wrapped.** One paragraph is one line; let the editor wrap it. These documents are searched with `grep` as a primary access path, and a phrase broken across a hard-wrapped line never matches, which returns a silent false negative rather than an error. Editing is also cheaper, since a wording change does not require rewrapping the paragraph around it. The usual counter-argument, that line-based diffs are noisier without wrapping, is answered by `git diff --word-diff`. Python source keeps its normal line length; this rule is about `.md` files only.

## Session start

1. Read `BACKGROUND.md`. Why the project exists, the problem, design constraints. It carries no technical content about any standard, on purpose.
2. Read the "Next session, in order" section at the top of `PLAN.md`'s open items. It carries what was agreed last time and why, so a cold start does not need the user to re-explain it.
3. Skim the first half of `docs/sources.md`. It lists every pinned file, the question each one answers, and whether it has actually been read. The second half is a pointer list for things we do not hold; consult it on demand rather than reading it in.

`docs/standards_map.html` shows how the pinned standards feed each other and which of those links has been verified. Open it when the relationship between two standards matters, not routinely.

## Grounding

**No claim about what an element of any pinned standard means, or how it maps to protocol content, without reading the relevant source first.** Which source answers which question, and the command to read it, is in `docs/sources.md`. That is the only place that routing lives; do not restate it here.

**Never read a pinned PDF whole.** They run to 500 pages combined. Address a section, a page range, or a search term.

### Label every claim

Each factual statement about any pinned standard gets one of three labels, stated plainly:

| Label | Means |
| --- | --- |
| **Source-read** | Read in a pinned source this session. Name the document and the section or page. |
| **Measured** | Computed from a pinned file. Show the command or output. |
| **Inferred** | Reasoned from names or structure. Not verified. Say so. |

Unlabelled assertion is the failure mode this rule exists to prevent. If a claim is inferred, say "inferred" before making it, not after being asked.

### When the guidance runs out

The standards do not cover everything, and they say so. Three tiers, in order:

1. **A standard covers it.** Follow it. Name the document and the section or page.
2. **No standard covers it, but the content must be captured.** Use USDM's extension mechanism, IG §6.4, which explicitly sanctions this. It requires that extensions be documented, so record every one in `docs/`. How it is shaped: `docs/usdm_ig_map.md`.
3. **Neither applies**, because it is a process or design question rather than a data-shape question. Decide, label the decision **unguided**, and record it in `PLAN.md`.

Never stall for lack of guidance. Always say which tier you are in.

## Data

- `data/raw/` is immutable. Nothing writes to it after download, ever. Downstream reads from it and writes to `data/interim/` or `data/processed/`.
- Provenance records live in `data/manifests/`, never inside `data/raw/`, so the rule above has no exceptions. One file per downloaded set, named for the tier: `raw_usdm_v4.json`.
- The USDM specification is pinned to a recorded commit. Never fetch latest.
- **Every downloaded file goes in a manifest in the same breath as the download.** `data/` is gitignored, so a file nobody recorded cannot be restored from a clean clone and is indistinguishable from one that was properly pinned.
- Verify checksums with `python scripts/verify_manifests.py`. Run it after any download, and before trusting a pinned file that a conclusion will rest on. Exit 0 clean, 1 a file is missing or altered, 2 a file is unrecorded, 3 a manifest is unreadable.

## Pipeline

- Prompts live in versioned files under `prompts/`, never as string literals in code. An edit creates a new version.
- Every extracted fact carries provenance: source document, section, page, character span, prompt id and version, model id, timestamp. This is about tracing a wrong answer back to the sentence that caused it. It is unrelated to the IG grounding rule above.

## Source files

Scripts are written to be reviewed by someone who did not write them and does not want to reverse-engineer them. The goal is that reading only the comments gives an accurate picture of what the script does. `scripts/read_pdf.py` is the worked example; match it.

### Required header

Every script opens with a module docstring carrying, in this order:

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

### Required markup

- `###` banner headers grouping the file into named sections.
- A docstring on every function stating what it does, what it returns, and **why it works the way it does** where the approach is not obvious. State the reasoning, not a restatement of the signature.
- A comment on every non-obvious code block explaining the intent behind it.
- A comment on every `try`/`except` saying what failure it absorbs and what happens instead. Never leave a silent `except`.
- A comment wherever a non-standard library, an index convention, or a workaround is used, saying why that choice was made.
- Comments explain *why*. Do not write comments that restate the code.

Simplicity still governs. Heavy commenting is not licence for clever code; if a block needs a paragraph to explain, prefer rewriting the block.
