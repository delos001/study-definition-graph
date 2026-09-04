# CLAUDE.md

Rules for this repo, on top of the global `~/.claude/CLAUDE.md`. `README.md` is what the project is and how to run it; `PLAN.md` is the build sequence; `DECISIONS.md` is the record of choices made and why; `docs/sources.md` is which file answers which question. Keep each to its own job.

This repo is de-identified: no company, no people, no locations, no partnerships. Anything learned from a conversation is written as a design constraint, a target problem or an open question, which is what it is here.

Markdown prose is one paragraph per line, never hard-wrapped: `grep` is a primary access path here, and a phrase split across lines silently fails to match.

Scripts run in the `sdg` conda environment. `README.md` has the rest of the setup.

## Session start

1. `BACKGROUND.md` - why the project exists and the design constraints.
2. `PLAN.md` - the build plan: phases, scope, and how each is verified.
3. GitHub Issues - current status and what to work on next.
4. `docs/sources.md`, first half - every pinned file, and whether it has been read.

Read all four before doing any work, even when the first message is a concrete task. The orientation reads, `docs/sources.md` above all, are what keep the work grounded; jumping to a named task and pulling only the obviously-relevant files is how ungrounded guessing starts (a figure quoted from an issue instead of the pinned source, a file's location asked for when the map already answers it).

## Issue tracking

GitHub Issues is the live status layer; `PLAN.md` is the stable plan; `DECISIONS.md` records why. Keep them consistent.

- Before working a phase, check its parent issue. If it has no sub-issues, break the phase down and create them first.
- When work deviates from `PLAN.md` (a task added, dropped, or changed), reconcile in the same session: update or close the affected issue(s), and if the plan itself changed, update `PLAN.md` and record why in `DECISIONS.md`.
- Close a phase's parent when its sub-issues are done.

## Grounding

**No claim about what a pinned standard means, or how it maps to protocol content, without reading the source first.**

**Never read a pinned PDF whole.** 460 pages across six of them. Take a section, a page range, or a search term.

**Label every claim** as one of:

| Label | Means |
| --- | --- |
| **Source-read** | Read this session. Name the document and the section or page. |
| **Measured** | Computed from a pinned file. Show the command or output. |
| **Inferred** | Reasoned from names or structure. Say so before making the claim, not after being asked. |

**When the guidance runs out**, say which case you are in and keep going:

1. A standard covers it - follow it, cite it.
2. Not covered, but the content must be captured - use USDM's extension mechanism (IG 6.4) and record every extension in `docs/`.
3. A process or design question rather than a data-shape one - decide, label it **unguided**, record it in `DECISIONS.md`.

## Data

- `data/raw/` is immutable. Downstream reads from it and writes to `data/interim/` or `data/processed/`.
- Every download gets a `data/manifests/` entry in the same breath, never a record inside `data/raw/`. `data/` is gitignored, so an unrecorded file cannot be restored and is indistinguishable from a pinned one.
- Pinned versions never move. Never fetch latest.
- `python scripts/verify_manifests.py` checks them: 0 clean, 1 missing or altered, 2 unrecorded, 3 unreadable manifest.
- Any count written into a document must be recomputable. Add it to `scripts/check_facts.py`, which re-derives every stated figure from the pinned files. Run it after changing the corpus.

## Pipeline

- Prompts live in versioned files under `prompts/`, never as string literals. An edit creates a new version, carrying the model, parameters, tool configuration and the reason for the change.
- Pin model versions to immutable identifiers, never moving aliases, and record the identifier in run metadata. Providers retire versions without complete changelogs.
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
Owner:       Jason Delosh
```

`Date` is the day the file was first committed, and it never changes. When a file last changed is git's answer, not the header's: `git log -1 --format=%cd -- <file>`. A hand-kept "last changed" field is one that is wrong most of the time.

`Owner` is who is accountable for the file and who to ask about it, not who wrote it. Authorship is recorded per commit in git, model attribution included, so it stays accurate as humans and models both edit a file over time. `git log --follow <file>` and `git blame <file>` are the answers to who wrote a given line. `Owner` changes only when ownership actually transfers.

And carries:

- `###` banner headers grouping the file into named sections.
- A docstring on every function that opens with what it reads or takes in and what it produces, then why it works that way where that is not obvious. Naming the inputs it consumes and the result it yields beats "returns a value," which the signature and the final line already show.
- A comment on every non-obvious block, every `try`/`except` (what it absorbs, what happens instead), and every workaround or non-standard library.
- Comments explain why. Never restate the code.

Heavy commenting is not licence for clever code. If a block needs a paragraph to explain, rewrite the block.
