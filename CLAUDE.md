# CLAUDE.md

Standing rules for this repo. Applies to every session, on top of the global `~/.claude/CLAUDE.md`.

This file holds **rules**. `README.md` holds what the project is and how to run it. `PLAN.md` holds the build sequence and the record of why decisions were made. Do not add rules to the other two, and do not restate rules from here in them.

**Markdown prose is not hard-wrapped.** One paragraph is one line; let the editor wrap it. These documents are searched with `grep` as a primary access path, and a phrase broken across a hard-wrapped line never matches, which returns a silent false negative rather than an error. Editing is also cheaper, since a wording change does not require rewrapping the paragraph around it. The usual counter-argument, that line-based diffs are noisier without wrapping, is answered by `git diff --word-diff`. Python source keeps its normal line length; this rule is about `.md` files only.

## Session start

1. Read `BACKGROUND.md`. Why the project exists, the problem, design constraints. It carries no technical content about any standard, on purpose.
2. Read the "Next session, in order" section at the top of `PLAN.md`'s open items. It carries what was agreed last time and why, so a cold start does not need the user to re-explain it.
3. Skim the first half of `docs/sources.md`. It lists every pinned file, the question each one answers, and whether it has actually been read. The second half is a pointer list for things we do not hold; consult it on demand rather than reading it in.

`docs/standards_map.html` shows how the pinned standards feed each other and which of those links has been verified. Open it when the relationship between two standards matters, not routinely.

## Grounding: which USDM source answers which question

Three standards bodies are pinned here, not one. USDM is five official CDISC standards (IG p.6) under `data/raw/usdm_v4/`. ICH M11 defines the protocol a study is authored as, under `data/raw/ich_m11/`. ICH E9(R1) defines the estimand framework USDM models, under `data/raw/ich_e9r1/`. None are interchangeable. Go to the one that holds the answer:

| Question | Source | How to read it |
| --- | --- | --- |
| What does this USDM class or attribute **mean**? | `usdm_v4/uml/dataDictionary.MD` | Grep it. Markdown table, one row per attribute, with definition, cardinality, NCI code, codelist ref. |
| What does this ID **point at**? | `usdm_v4/uml/dataStructure.yml` | Load with pyyaml. Gives target class, cardinality, and `Ref` vs `Value`. |
| How does USDM map to real protocol content? | `usdm_v4/USDM-IG.pdf` | `python scripts/read_pdf.py <section>` |
| What does the payload look like? | `usdm_v4/USDM_API.json` | Shape only. **No semantics.** |
| Which terms are legal for a coded field? | `usdm_v4/USDM_CT.xlsx` | `python scripts/read_xlsx.py USDM_CT --sheet "DDF valid value sets"` |
| Is a document conformant? | `usdm_v4/USDM_CORE_Rules.xlsx` | `python scripts/read_xlsx.py CORE_Rules --sheet ...` |
| What does a real one look like? | `usdm_examples/` | Three real protocols with their USDM JSON and the human-authored source spreadsheet. |
| How did a human decide the mapping? | example `*.xlsx` | `python scripts/read_xlsx.py Alexion --sheet mainTimeline --format records` |
| What **sections** does a protocol have, and what belongs in each? | `ich_m11/ICH_M11_Template.pdf` | `python scripts/read_pdf.py --doc m11-template --find "<heading>"` |
| What is this protocol **data element**, and is it required? | `ich_m11/ICH_M11_TechnicalSpecification.pdf` | `python scripts/read_pdf.py --doc m11-techspec --find "<term>"`. 186 elements, each with definition, data type, cardinality, conformance. |
| What does an **estimand attribute** mean? | `ich_e9r1/ICH_E9R1_Addendum.pdf` | `python scripts/read_pdf.py --doc e9r1 --pages 11-12`. Use the page range, not `A.3.3`: the four attributes (treatment, population, variable, population-level summary) run past the bookmark boundary, and section mode returns only the first. |

**Rule: no claim about what an element of any of these standards means, or how it maps to protocol content, without reading the relevant source first.**

M11 and USDM are maintained by different bodies on different cycles, so they drift. USDM v4.0 (2025-06-03) is aligned to an M11 Step 2 draft; M11 reached Step 4 on 2025-11-19. That is expected and is not a defect to reconcile.

`USDM_API.json` is the trap. It is generated from the model and discards definitions, cardinalities, and the target class of every relationship. Counting things in it describes the file, not the standard. If a question is about meaning, the answer is not in that file.

The pinned PDFs run to 500 pages combined. Never read one whole:

```powershell
python scripts/read_pdf.py --docs         # what is registered
python scripts/read_pdf.py 4.23           # IG, by section number
python scripts/read_pdf.py --find timing  # IG, search all pages
python scripts/read_pdf.py --list         # IG section map
python scripts/read_pdf.py --doc m11-techspec --find "Estimand"
python scripts/read_pdf.py --doc e9r1 --list
```

The USDM IG and E9(R1) carry bookmarks, so they can be addressed by section. The three M11 PDFs carry none, so they answer only to `--find` and `--pages`. The script says so rather than returning an empty section map.

The example workbooks have 25 to 35 sheets each. Search across all of them rather than guessing which sheet holds something:

```powershell
python scripts/read_xlsx.py --all --find "estimand"
python scripts/read_xlsx.py Alexion                        # list its sheets
python scripts/read_xlsx.py Alexion --sheet mainTimeline --format records
```

`mainTimeline` in an example workbook is that study's Schedule of Activities. It runs to 58 columns, so use `--format records`, not the default table.

### Label every claim

Each factual statement about USDM gets one of three labels, stated plainly:

| Label | Means |
| --- | --- |
| **IG-sourced** | Read in the IG this session. Cite section and page. |
| **Measured** | Computed from a pinned file. Show the command or output. |
| **Inferred** | Reasoned from names or structure. Not verified. Say so. |

Unlabelled assertion is the failure mode this rule exists to prevent. If a claim is inferred, say "inferred" before making it, not after being asked.

### When the guidance runs out

USDM does not cover everything, and the IG says so. Three tiers, in order:

1. **The IG covers it.** Follow it. Cite section and page.
2. **The IG does not cover it, but the content must be captured.** Use the extension mechanism, IG §6.4 (pp.100-107): `extensionAttributes` on the class, each entry carrying an `id`, a `url` identifying our extension, and a value. The IG explicitly sanctions this for "a need to overcome issues with the model" (p.100). It also requires that extensions be documented, so record ours in `docs/`.
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
