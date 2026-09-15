# CLAUDE.md

This file holds the rules for this repo, on top of the global `~/.claude/CLAUDE.md`. Every document has one job and keeps to it. The Layout section of the root [README.md](README.md) says what each job is.

This repo is de-identified: no company, no people, no locations, no partnerships. Anything communicated by the user that goes into a repo document is written there as a design constraint, a target problem or an open question, never as who said it or where it came from.

Markdown prose is one paragraph per line, never hard-wrapped: `grep` is a primary access path here, and a phrase split across lines silently fails to match.

Run every command in this repo from the `sdg` conda environment. The root [README.md](README.md) has the rest of the setup.

## Session start

Read everything listed below before doing any work, even when the first message is a concrete task:

1. `BACKGROUND.md`
2. `PLAN.md`
3. GitHub Issues
4. `docs/sources_index.md`

## Grounding

The session-start reads are what keep decisions and choices grounded. Jumping to a named task and pulling only the obviously-relevant files is how guessing starts. Two examples:

- A figure is quoted from an issue instead of the pinned file it should come from.
- A file's location is asked for when `docs/sources_index.md` already answers it.

### Claims

No claim is made without reading the source first. This holds for anything in the repo, not only the pinned standards: a file's contents, what a script does, what a document says. If nothing available answers the question, tell the user, and suggest searching the web for a reliable source to close the gap.

Label every claim as one of the following. Inference is the last resort, never a shortcut past a file that could have answered the question: it is for what no available source contains. When you infer, say so as part of the claim, not after being asked.

| Label | Means |
| --- | --- |
| **Source-read** | Read this session. Name the document and the section or page. |
| **Measured** | Computed from a pinned file. Show the command or output. |
| **Inferred** | Reasoned from names or structure, where no source could answer. |

When you face a decision about how something should be modelled or handled, categorize it as one of the following cases and keep going:

| Category | Action |
| --- | --- |
| A standard covers it | Follow it and cite it. |
| No standard covers it, but the content must be captured | Use USDM's extension mechanism (IG 6.4) and record every extension in [docs/usdm_local_extensions.md](docs/usdm_local_extensions.md). |
| It is a question about process or design rather than how data is structured | Decide, and record it in `DECISIONS.md` as a decision no standard guided. |

## Issue tracking

GitHub Issues, `PLAN.md`, and `DECISIONS.md` must remain consistent.

- Before working a phase, read that phase's issue. If it has no sub-issues, break the phase down and create them first.
- Close the phase's issue when its sub-issues are done.
- When the work stops matching `PLAN.md`, because a task was added, dropped or changed, put the records right in the same session.
  - Create, update or close the affected issues.
  - Update `PLAN.md` if the plan itself changed.
  - Record in `DECISIONS.md` why the plan changed.

## Pinned files

A pinned file is one downloaded from outside and frozen at a single version, with its url, size and checksum recorded in `manifests/`.

### What is pinned

- Everything under `inputs/` is pinned: the standards, the worked examples and the study documents.
- Only the tools that fetch and record pinned files write to `inputs/`, and they only add files that are missing. Nothing else writes there, and nothing ever edits a file already on disk.
- The pipeline reads from `inputs/` and writes to `data/interim/` or `data/processed/`.

### Recording and naming

- Every download gets a `manifests/` entry as it happens, never a record beside the file.
- `inputs/` is gitignored apart from its READMEs, so an unrecorded file cannot be restored and cannot be told apart from a pinned one.
- A pinned file keeps its publisher's file name, with spaces replaced by underscores and nothing else changed.
- Each standard gets one folder, named with the standard's version where the publisher gives one and with the export date where it does not, whatever the file count.
- Files that are not a standard, such as the crosswalks, get a folder named for what they are.
- Once a file is pinned, it stays at that version. Never fetch whatever the publisher currently calls the latest release; fetch the exact version the manifest records.

### Reading and checking

- Never read a pinned PDF whole, because they can be very long. Take a section, a page range, or a search term.
- `acquire_sources` fetches what is missing and checks what is present against its manifest entry.
- `python repo_tools/find_unrecorded_files.py` lists files under `inputs/` that no manifest records.
- Any count written into a document must be recomputable. Add a measurement for it to `repo_tools/check_facts.py`, which re-derives every stated figure from the pinned files. Run that tool after changing the corpus.

## Pipeline

- Hand-built answer keys go in `eval/`, which is committed, because they cannot be regenerated.
- Prompts live in versioned files under `prompts/`, never as string literals. An edit of a prompt creates a new version, carrying the model, parameters, tool configuration and the reason for the change.
- Pin model versions to immutable identifiers, never moving aliases, and record the identifier in run metadata. Providers retire versions without complete changelogs.
- Every extracted fact carries provenance: source document, section, page, character span, prompt id and version, model id, timestamp. It exists to trace a wrong answer back to the sentence that caused it.

## Python files

Code is split by who runs it: `src/sdg/` is the pipeline, `repo_tools/` is hand-run repo maintenance tools, and `validation/` contains automated checks. Every Python file follows the rule in `.claude/rules/writing_python_files.md`. Read that rule before creating or changing any Python file. It loads on its own when a file under those folders is opened, but a new file matches no path until it exists, so read it deliberately before writing one.
