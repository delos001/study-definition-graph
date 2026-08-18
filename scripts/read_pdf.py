"""
Script:      read_pdf.py
Description: Reads part of any pinned PDF standard in this repo and prints it as
             plain text, so a working session can consult a specification
             without loading the whole document.

             Registered documents are the CDISC USDM Implementation Guide and
             the three ICH M11 Step 4 documents. They differ in one way that
             governs this script's design: the USDM IG carries 54 embedded
             bookmarks, so it can be addressed by section number, and none of
             the M11 PDFs carry any, so they can only be addressed by search or
             by explicit page range. That is a property of the source files, not
             a limitation this script can code around, so section modes fail
             loudly on a bookmark-less document rather than returning nothing.

             No PDF is ever converted to another format. Every registered
             document contains diagrams or tables that text extraction cannot
             represent, so wherever a page holds one, this script says so rather
             than silently producing incomplete text.

Inputs:      data/raw/usdm_v4/USDM-IG.pdf          (read-only, pinned)
             data/raw/ich_m11/ICH_M11_*.pdf        (read-only, pinned)
             Section numbers and page ranges come from each PDF's own bookmarks.

Outputs:     Plain text on stdout. Writes nothing to disk.

Usage:       python scripts/read_pdf.py --docs                 list registered documents
             python scripts/read_pdf.py 4.23                   one IG section
             python scripts/read_pdf.py "Extension"            match on title text
             python scripts/read_pdf.py --pages 26-31          explicit page range
             python scripts/read_pdf.py --find footnote        search all pages
             python scripts/read_pdf.py --list                 print the section map
             python scripts/read_pdf.py --doc m11-techspec --find "Number of Participants"
             python scripts/read_pdf.py --doc m11-template --pages 12-14

Exit codes:  0 success
             1 the PDF is missing, the requested section was not found, or a
               section mode was used on a document that has no bookmarks

Date:        2026-08-18
Author:      Jason Delosh
"""

from __future__ import annotations

import argparse
import contextlib
import io
import re
import sys
from pathlib import Path

# pymupdf is imported under its legacy name "fitz". It is a conda dependency
# declared in environment.yml, chosen over pypdf because it reports image and
# table positions, which this script needs in order to warn about lost content.
import fitz


### Constants ##################################################################

# Paths are resolved from this file's own location rather than the working
# directory, so the script behaves the same whether it is run from the repo root
# or from inside scripts/.
REPO_ROOT = Path(__file__).resolve().parents[1]
RAW = REPO_ROOT / "data" / "raw"

# Every page of the USDM IG repeats the same four lines of header and footer.
# They add roughly 15% noise to any extracted section, so they are stripped
# unless --raw is passed. Each pattern is anchored to the start of a line so
# that genuine body text mentioning the same words is not removed.
USDM_IG_BOILERPLATE = (
    re.compile(r"^CDISC Unified Study Definitions Model Implementation Guide.*$"),
    re.compile(r"^\s*.?\s*2025 Clinical Data Interchange Standards Consortium.*$"),
    re.compile(r"^\s*Page \d+\s*$"),
    re.compile(r"^\s*2025-06-03\s*$"),
)

# The registry of readable documents. Each entry carries:
#   path         where the pinned file lives
#   label        how the document is cited in output, so a claim sourced from
#                this script can name its source and page as CLAUDE.md requires
#   manifest     which manifest to re-download from, named in the missing-file
#                error because data/ is gitignored and a fresh clone has none
#   boilerplate  per-page header and footer patterns to strip
#
# The M11 documents carry an empty boilerplate tuple deliberately. Their pages
# were checked for repeated header and footer lines and have none; the most
# frequently repeated lines in the Technical Specification ("Definition",
# "Data Type", "Cardinality") are field labels in the body. Stripping those
# would delete the content the document exists to convey.
DOCUMENTS = {
    "ig": {
        "path": RAW / "usdm_v4" / "USDM-IG.pdf",
        "label": "USDM-IG v4.0",
        "manifest": "raw_usdm_v4.json",
        "boilerplate": USDM_IG_BOILERPLATE,
    },
    "m11-guideline": {
        "path": RAW / "ich_m11" / "ICH_M11_Guideline.pdf",
        "label": "ICH M11 Guideline (Step 4)",
        "manifest": "raw_ich_m11.json",
        "boilerplate": (),
    },
    "m11-template": {
        "path": RAW / "ich_m11" / "ICH_M11_Template.pdf",
        "label": "ICH M11 Template (Step 4)",
        "manifest": "raw_ich_m11.json",
        "boilerplate": (),
    },
    "m11-techspec": {
        "path": RAW / "ich_m11" / "ICH_M11_TechnicalSpecification.pdf",
        "label": "ICH M11 Technical Specification (Step 4)",
        "manifest": "raw_ich_m11.json",
        "boilerplate": (),
    },
    "e9r1": {
        "path": RAW / "ich_e9r1" / "ICH_E9R1_Addendum.pdf",
        "label": "ICH E9(R1) Estimands Addendum",
        "manifest": "raw_ich_e9r1.json",
        "boilerplate": (),
    },
}

DEFAULT_DOCUMENT = "ig"

# Matches a leading section label at the start of a bookmark title, so a user
# can ask for "4.23" instead of typing the full heading. Three forms are
# accepted because the registered documents number their sections differently:
#   4, 4.23        the USDM IG
#   A.3, A.3.1     ICH E9(R1), whose sections are lettered because the whole
#                  document is an addendum to E9 rather than a standalone guide
#   Appendix B     the USDM IG's back matter
SECTION_NUMBER_PATTERN = re.compile(
    r"^((?:\d+\.)*\d+|[A-Z](?:\.\d+)*|Appendix [A-E])\b"
)


### Table of contents ##########################################################


def load_toc(doc: fitz.Document) -> list[dict]:
    """
    Build the section map from the PDF's embedded bookmarks.

    The bookmarks give a start page per section but no end page, so each
    section's end is inferred as one page before the next section that starts on
    a later page. The "later page" test matters because several IG sections
    begin on the same page; without it, those sections would get a negative or
    zero-length range.

    Returns an empty list for a PDF with no bookmarks, which is the normal case
    for the M11 documents. Callers must treat empty as "this document cannot be
    addressed by section" rather than as "this document has no sections".

    Returns a list of dicts, one per bookmark, each with:
        number  the leading section number, e.g. "4.23", or "" if untitled
        title   the full bookmark text, e.g. "4.23 Addressing Footnotes"
        start   first page, 1-indexed to match the printed page numbers
        end     last page, 1-indexed and inclusive
    """
    bookmarks = doc.get_toc()  # list of [level, title, start_page]
    sections: list[dict] = []

    for index, (_level, title, start_page) in enumerate(bookmarks):
        # Default to the final page, which is correct for the last bookmark and
        # is overwritten below for every other one.
        end_page = doc.page_count

        # Scan forward for the first bookmark that starts on a strictly later
        # page. Bookmarks sharing this section's start page are skipped.
        for _next_level, _next_title, next_start in bookmarks[index + 1 :]:
            if next_start > start_page:
                end_page = next_start - 1
                break

        title = title.strip()
        number_match = SECTION_NUMBER_PATTERN.match(title)

        sections.append(
            {
                "number": number_match.group(1) if number_match else "",
                "title": title,
                "start": start_page,
                "end": end_page,
            }
        )

    return sections


def find_section(sections: list[dict], wanted: str) -> dict | None:
    """
    Resolve a user-supplied string to one section, in two passes.

    Pass 1 is an exact match on the section number, so "4.23" cannot
    accidentally match "4.230" or a section whose body mentions 4.23.
    Pass 2 is a case-insensitive substring match on the title, so a user who
    remembers "footnote" but not the number still gets there.

    A trailing period is tolerated because "4.23." is a natural way to type it.

    Returns the matching section dict, or None if nothing matched. The caller is
    responsible for reporting the failure; this function does not print.
    """
    wanted = wanted.strip().rstrip(".")

    for section in sections:
        if section["number"].lower() == wanted.lower():
            return section

    for section in sections:
        if wanted.lower() in section["title"].lower():
            return section

    return None


### Text extraction ############################################################


def strip_boilerplate(text: str, patterns: tuple[re.Pattern, ...]) -> str:
    """
    Remove the repeated per-page header and footer lines.

    Patterns are passed in rather than read from a module global because they
    are per-document: the USDM IG has four, the M11 PDFs have none. An empty
    tuple is a valid and common argument and returns the text unchanged.

    Operates line by line rather than with a multiline regex so that a pattern
    failing to match leaves that single line intact instead of silently
    discarding a block of body text.
    """
    if not patterns:
        return text

    kept_lines = [
        line
        for line in text.splitlines()
        if not any(pattern.match(line) for pattern in patterns)
    ]
    return "\n".join(kept_lines)


def describe_lost_content(page: fitz.Page) -> str:
    """
    Report diagrams and tables on a page that the text output does not contain.

    This is the safeguard against the failure mode that motivated keeping the
    PDF as the source of truth. Body text frequently says things like "as shown
    in the following diagram"; the diagram is an image, so extracted text ends
    at that sentence with no sign that anything is missing. Naming the loss
    turns a silent gap into a visible one.

    Returns a bracketed one-line note, or an empty string when the page holds
    only text.
    """
    image_count = len(page.get_images(full=True))

    # find_tables() is heuristic and can raise on unusual page structures, so a
    # failure here degrades to "no tables reported" rather than aborting a read
    # the user asked for. Table detection is advisory; the text is the payload.
    #
    # It also prints an unsolicited advisory line to stdout, which would land in
    # the middle of the extracted text and could be mistaken for document
    # content. stdout is redirected to a throwaway buffer for the duration.
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            table_count = len(page.find_tables().tables)
    except Exception:
        table_count = 0

    missing = []
    if image_count:
        missing.append(f"{image_count} image(s)")
    if table_count:
        missing.append(f"{table_count} table(s)")

    if not missing:
        return ""

    return (
        f"[NOT SHOWN IN TEXT: {', '.join(missing)} on this page. "
        f"Open the PDF at this page to see them.]"
    )


def extract_pages(
    doc: fitz.Document,
    start: int,
    end: int,
    raw: bool,
    patterns: tuple[re.Pattern, ...],
    label: str,
) -> str:
    """
    Return the text of pages start..end inclusive, one labelled block per page.

    Each block names the document and the page, so any claim sourced from this
    output can cite both, which the project's grounding rule in CLAUDE.md
    requires. The document name matters now that four documents are readable and
    two of them describe overlapping subject matter.

    Page indices are converted from 1-indexed (how these documents and their
    bookmarks number pages) to 0-indexed (how pymupdf addresses them) at the
    single point of access below, so the rest of the script works in printed
    page numbers.
    """
    blocks = []

    for page_number in range(start, end + 1):
        page = doc[page_number - 1]
        text = page.get_text()

        if not raw:
            text = strip_boilerplate(text, patterns)

        block = f"--- {label} page {page_number} ---\n{text.strip()}"

        lost = describe_lost_content(page)
        if lost:
            block += f"\n{lost}"

        blocks.append(block)

    return "\n\n".join(blocks)


### Search #####################################################################


def search_pages(doc: fitz.Document, sections: list[dict], term: str) -> list[str]:
    """
    Find every page whose text contains term, case-insensitively.

    This exists so a document can be searched without converting it to a text
    file. A converted copy would drop every diagram and flatten every table, and
    would then need to be kept in step with the PDF; searching in place avoids
    both problems.

    It is also the only usable access path for the M11 documents, which carry no
    bookmarks. The M11 Technical Specification is a reference of 186 data
    elements rather than a linear read, so term lookup is the access pattern it
    actually wants.

    Each hit reports the page, the section that page falls in where sections are
    known, and the first matching line, so the caller can decide what is worth
    reading in full rather than reading it all.
    """
    needle = term.lower()
    hits = []

    for page_index in range(doc.page_count):
        page_number = page_index + 1
        text = doc[page_index].get_text()

        if needle not in text.lower():
            continue

        # Attribute the page to the last section that starts on or before it.
        # Sections are in document order, so the final match wins. Stays "?" for
        # a document with no bookmarks, where no attribution is possible.
        section_title = "?"
        for section in sections:
            if section["start"] <= page_number <= section["end"]:
                section_title = section["title"]

        # Show the first matching line as context, trimmed so a wide PDF line
        # does not dominate the output.
        snippet = next(
            (line.strip() for line in text.splitlines() if needle in line.lower()),
            "",
        )
        if len(snippet) > 110:
            snippet = snippet[:110] + "..."

        hits.append(f"p.{page_number:>3}  {section_title}\n        {snippet}")

    return hits


### Entry point ################################################################


def main() -> int:
    """
    Parse arguments, dispatch to one mode, and return a shell exit code.

    Modes are mutually exclusive in practice and are checked in order of
    specificity: --docs, --list and --find are explicit requests, --pages
    bypasses section lookup, and a bare positional argument is resolved as a
    section. Running with no arguments prints the section map, on the assumption
    that a user who does not know what to ask for wants the menu.
    """
    # PyMuPDF returns proper Unicode, but a Windows console defaults to a
    # legacy code page and silently replaces anything it cannot encode. That
    # mangles exactly the characters these specifications use structurally:
    # bullets, em dashes and arrows. Forcing UTF-8 on stdout fixes it at the
    # one place it goes wrong.
    sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        description="Read part of a pinned PDF standard (USDM IG or ICH M11)."
    )
    parser.add_argument(
        "section",
        nargs="?",
        help='section number or title fragment, e.g. "4.23" or "Extension"',
    )
    parser.add_argument(
        "--doc",
        default=DEFAULT_DOCUMENT,
        choices=sorted(DOCUMENTS),
        help=f"which document to read (default: {DEFAULT_DOCUMENT})",
    )
    parser.add_argument("--pages", help='explicit page range instead, e.g. "26-31"')
    parser.add_argument("--find", help="search all pages for a term")
    parser.add_argument("--list", action="store_true", help="print the section map")
    parser.add_argument(
        "--docs", action="store_true", help="list the registered documents"
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="keep the repeated page headers and footers",
    )
    args = parser.parse_args()

    # Mode: list the registry. Answered before opening any file, so it still
    # works on a fresh clone where data/ has not been downloaded.
    if args.docs:
        for key, entry in DOCUMENTS.items():
            state = "present" if entry["path"].exists() else "NOT DOWNLOADED"
            print(f"  {key:16} {entry['label']:42} {state}")
        return 0

    document = DOCUMENTS[args.doc]

    # Fail early and specifically if the pinned file is absent. This is the one
    # error a user is likely to hit on a fresh clone, since data/ is gitignored,
    # so the message names the expected path and the manifest to restore from
    # rather than letting pymupdf raise.
    if not document["path"].exists():
        print(f"{document['label']} not found at {document['path']}", file=sys.stderr)
        print(
            f"data/ is gitignored. Re-download per data/manifests/{document['manifest']}.",
            file=sys.stderr,
        )
        return 1

    doc = fitz.open(document["path"])
    sections = load_toc(doc)

    wants_sections = args.list or args.section or not (args.pages or args.find)

    # A document with no bookmarks cannot be addressed by section. Say so and
    # name the modes that do work, rather than printing an empty section map or
    # reporting "no section matching", either of which would read as though the
    # document lacked the content rather than lacking the navigation data.
    if wants_sections and not sections:
        print(
            f"{document['label']} has no embedded bookmarks, so it cannot be "
            f"addressed by section.",
            file=sys.stderr,
        )
        print(
            f"Use --find TERM to search its {doc.page_count} pages, "
            f"or --pages N-M to read a known range.",
            file=sys.stderr,
        )
        return 1

    # Mode: print the section map.
    if args.list or (not args.section and not args.pages and not args.find):
        for section in sections:
            span = (
                str(section["start"])
                if section["start"] == section["end"]
                else f"{section['start']}-{section['end']}"
            )
            print(f"{span:>8}  {section['title']}")
        return 0

    # Mode: search every page.
    if args.find:
        hits = search_pages(doc, sections, args.find)
        if not hits:
            print(f"No pages contain {args.find!r}.")
            return 0
        print(f"{len(hits)} page(s) in {document['label']} contain {args.find!r}:\n")
        print("\n".join(hits))
        return 0

    # Mode: an explicit page range, bypassing the section map. Used when the
    # bookmarks are too coarse, which happens where sections share a start page,
    # and it is the only page-addressed mode available for the M11 documents.
    if args.pages:
        start_text, _, end_text = args.pages.partition("-")
        start_page = int(start_text)
        end_page = int(end_text) if end_text else start_page
        label = f"pages {args.pages}"

    # Mode: resolve a section number or title fragment.
    else:
        section = find_section(sections, args.section)
        if section is None:
            print(
                f"No section matching {args.section!r}. Run with --list to see all.",
                file=sys.stderr,
            )
            return 1
        start_page = section["start"]
        end_page = section["end"]
        label = section["title"]

    print(f"### {document['label']} | {label} | pages {start_page}-{end_page}\n")
    print(
        extract_pages(
            doc,
            start_page,
            end_page,
            args.raw,
            document["boilerplate"],
            document["label"],
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
