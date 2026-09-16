"""
Script:      read_pdf.py
Description: Reads part of any pinned PDF standard in this repo and prints it as
             plain text, so a working session can consult a specification
             without loading the whole document.

             The documents it can open are listed in lookup_documents.yml
             beside this file, which also states which documents belong there.
             Run --docs to see them and whether each one is downloaded.

             They differ in one way that governs this script's design. The USDM
             IG and E9(R1) carry embedded bookmarks, so they can be addressed by
             section number. The others carry none, so they answer only to
             --find and --pages. That is a property of the source files, not a
             limitation this script can code around, so section modes fail
             loudly on a bookmark-less document rather than returning nothing.

             No PDF is ever converted to another format. Every registered
             document contains diagrams or tables that text extraction cannot
             represent, so wherever a page holds one, this script says so rather
             than silently producing incomplete text.

Inputs:      src/sdg/view/lookup_documents.yml   (read-only, the list of documents)
             manifests/*.json                     (read-only, through the manifest reader,
                                                   which owns each document's path)
             the listed PDFs under inputs/        (read-only, pinned)
             Section numbers and page ranges come from each PDF's own bookmarks.

Outputs:     Plain text on stdout. Writes nothing to disk.

Usage:       read_pdf --docs
                 list the registered documents and whether each is downloaded,
                 exiting 8 when any of them is missing
             read_pdf 4.23
                 print one section of the USDM IG, by number
             read_pdf "Extension"
                 print the section whose title contains the text
             read_pdf --pages 26-31
                 print an explicit page range
             read_pdf --find footnote
                 search every page for a term
             read_pdf --list
                 print the section map
             read_pdf --doc m11-techspec --find "Number of Participants"
                 the same modes on another registered document
             read_pdf --doc m11-template --pages 12-14
             read_pdf --doc model-diagram --find Encounter

Exit codes:  0   success
             1   unhandled error, Python's own
             2   invalid command line, the argument parser's own (this covers a
                 page range that is not a number or two numbers joined by a
                 dash, starts before page 1, runs past the document's last
                 page, or ends before it starts)
             3   a manifest is missing or cannot be read
             6   not running from inside the repo
             8   a pinned file has not been downloaded
             23  the requested section was not found in the PDF
             24  section mode used on a PDF that has no bookmarks
             31  the list of lookup documents is missing or wrongly shaped
             32  the list of lookup documents names a file no manifest records
             The numbers are the repo-wide table in
             validation/exit_codes.csv.

Date:        2026-08-18
Owner:       Jason Delosh
"""

from __future__ import annotations

import argparse
import contextlib
import io
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path

# pymupdf is imported under its legacy name "fitz". It is a conda dependency
# declared in environment.yml, chosen over pypdf because it reports image and
# table positions, which this script needs in order to warn about lost content.
import fitz

# pyyaml is declared in environment.yml. The list of lookup documents is YAML
# so its boilerplate patterns can be written as plain regular expressions.
import yaml

from sdg.console_output import use_utf8_output
from sdg.sources.read_manifests import ManifestError, NotInRepoError, entry_named

#######################################################################################
### Settings ###

# The list of documents this tool can open lives beside it as data, so adding or
# removing one is a row rather than a code change, and so the path on disk keeps
# one owner, the manifest. The file states which documents belong in it.
REGISTRY_FILE = Path(__file__).resolve().parent / "lookup_documents.yml"


class RegistryError(Exception):
    """Raised when the list of lookup documents is missing or wrongly shaped."""


class UnknownFileError(RegistryError):
    """Raised when the list names a file that no manifest records."""


@dataclass(frozen=True)
class Document:
    """One lookup PDF: where it is, what to call it, which manifest records
    it, and the page furniture to strip from every extract."""

    path: Path
    label: str
    manifest: str
    boilerplate: tuple[re.Pattern[str], ...]


def load_registry(registry_file: Path | None = None) -> tuple[dict[str, Document], str]:
    """Read the list of lookup documents and find each file through its manifest.

    The path of each document is resolved from the manifest entry rather than written
    in the list, so a re-pinned file moves in one place and this tool follows.

    Args:
        registry_file: The list to read, or None for the one beside this file.

    Returns:
        The documents by the key a person types, and the key used when --doc is absent.

    Raises:
        RegistryError: The list is missing, cannot be parsed, is shaped wrongly, names
            a default that is not in it, or names a file no manifest records.
    """
    target = registry_file or REGISTRY_FILE
    try:
        content = yaml.safe_load(target.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RegistryError(
            f"the list of lookup documents is missing at {target}.\n"
            "  fix -> restore it from git"
        ) from exc
    except yaml.YAMLError as exc:
        raise RegistryError(f"{target.name} is not valid YAML: {exc}") from exc

    if not isinstance(content, dict) or not isinstance(content.get("documents"), list):
        raise RegistryError(f"{target.name} has no documents list.")

    documents: dict[str, Document] = {}
    for row in content["documents"]:
        missing_fields = [f for f in ("key", "label", "file") if not row.get(f)]
        if missing_fields:
            raise RegistryError(
                f"{target.name} has an entry missing {', '.join(missing_fields)}."
            )
        # The manifest is the only record of where a pinned file lives, so a name
        # it does not carry is a mistake in the list rather than a missing download.
        entry = entry_named(row["file"])
        if entry is None:
            raise UnknownFileError(
                f"{target.name} names {row['file']}, which no manifest records.\n"
                "  fix -> correct the name, or record the file in manifests/"
            )
        documents[row["key"]] = Document(
            path=entry.path,
            label=row["label"],
            manifest=entry.manifest,
            boilerplate=tuple(
                re.compile(pattern) for pattern in row.get("boilerplate") or ()
            ),
        )

    default = content.get("default")
    if default not in documents:
        raise RegistryError(
            f"{target.name} names {default!r} as its default, which is not one of its "
            f"documents."
        )
    return documents, default


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


#######################################################################################
### Table of contents ###


def load_toc(doc: fitz.Document) -> list[dict]:
    """Build the section map from the PDF's embedded bookmarks.

    The bookmarks give a start page per section but no end page, so each section's end
    is inferred as one page before the next section that starts on a later page. The
    "later page" test matters because several IG sections begin on the same page;
    without it, those sections would get a negative or zero-length range.

    An empty result means the PDF has no bookmarks, which is the normal case for the M11
    documents. Callers must treat empty as "this document cannot be addressed by
    section" rather than as "this document has no sections".

    Args:
        doc: The open PDF.

    Returns:
        One dict per bookmark, holding number (the leading section number, such as
            "4.23", or "" if untitled), title (the full bookmark text), start (the first
            page, 1-indexed to match the printed page numbers) and end (the last page,
            1-indexed and inclusive).
    """
    bookmarks = doc.get_toc()  # list of [level, title, start_page]
    sections: list[dict] = []

    for index, (_level, title, start_page) in enumerate(bookmarks):
        # The next bookmark in document order, whatever page it starts on, is
        # what actually bounds this section. Its start page is included, not
        # excluded: a section frequently runs partway into the page where the
        # next one begins, and cutting at next_start - 1 silently discarded
        # that remainder. extract_pages trims the overlap at the heading.
        if index + 1 < len(bookmarks):
            _next_level, next_title, next_start = bookmarks[index + 1]
            end_page = next_start
            next_match = SECTION_NUMBER_PATTERN.match(next_title.strip())
            next_number = next_match.group(1) if next_match else ""
        else:
            end_page = doc.page_count
            next_number = ""

        title = title.strip()
        number_match = SECTION_NUMBER_PATTERN.match(title)

        sections.append(
            {
                "number": number_match.group(1) if number_match else "",
                "title": title,
                "start": start_page,
                "end": end_page,
                "next_number": next_number,
            }
        )

    return sections


def find_section(sections: list[dict], wanted: str) -> dict | None:
    """Resolve a user-supplied string to one section, in two passes.

    Pass 1 is an exact match on the section number, so "4.23" cannot accidentally match
    "4.230" or a section whose body mentions 4.23. Pass 2 is a case-insensitive
    substring match on the title, so a user who remembers "footnote" but not the number
    still gets there. A trailing period is tolerated because "4.23." is a natural way to
    type it.

    Args:
        sections: The section map from load_toc().
        wanted: What the user typed.

    Returns:
        The matching section, or None when nothing matched. The caller reports the
            failure; this function does not print.
    """
    wanted = wanted.strip().rstrip(".")

    for section in sections:
        if section["number"].lower() == wanted.lower():
            return section

    for section in sections:
        if wanted.lower() in section["title"].lower():
            return section

    return None


#######################################################################################
### Text extraction ###


def heading_offset(text: str, number: str) -> int | None:
    """Find where a section's heading begins in a page's text.

    The match is a line that opens with the section number, which is how headings appear
    in every registered document. The number alone is used rather than the full bookmark
    title because the two do not always agree: the USDM IG renders "4.23 Addressing
    Footnotes" on one line, while E9(R1) puts "A.3.3." and "Estimand Attributes" on
    separate lines, so a title match would fail there. The pattern requires a period or
    whitespace after the number; without that, "4.2" would also match the start of
    "4.23", and a request for the shorter section would be cut at the longer one's
    heading.

    Args:
        text: The page's text.
        number: The section number to look for.

    Returns:
        The character offset of the heading, or None when it is not found. None rather
            than a guess, because a wrong boundary chosen silently is the failure this
            function exists to prevent.
    """
    if not number:
        return None

    match = re.search(rf"^[ \t]*{re.escape(number)}[.\s]", text, re.M)
    return match.start() if match else None


def strip_boilerplate(text: str, patterns: tuple[re.Pattern, ...]) -> str:
    """Remove the repeated per-page header and footer lines.

    Patterns are passed in rather than read from a module global because they are per-
    document: the USDM IG has four, the M11 PDFs have none. The work is done line by
    line rather than with a multiline regex, so a pattern that fails to match leaves
    that single line intact instead of silently discarding a block of body text.

    Args:
        text: The page's text.
        patterns: The lines to remove, as compiled patterns. An empty tuple is valid and
            common.

    Returns:
        The text with matching lines removed, or unchanged when there are no patterns.
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
    """Report the diagrams and tables on a page that the text output does not contain.

    This is the safeguard against the failure mode that motivated keeping the PDF as the
    source of truth. Body text frequently says things like "as shown in the following
    diagram"; the diagram is an image, so extracted text ends at that sentence with no
    sign that anything is missing. Naming the loss turns a silent gap into a visible
    one.

    Args:
        page: The page to inspect.

    Returns:
        A bracketed one-line note, or an empty string when the page holds only text.
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
    section: dict | None = None,
) -> str:
    """Extract the text of pages start to end inclusive, one labelled block per page.

    Each block names the document and the page, so any claim sourced from this output
    can cite both, which the project's grounding rule requires. Page numbers are
    converted from 1-indexed, how these documents and their bookmarks number pages, to
    0-indexed, how pymupdf addresses them, at the single point of access inside, so the
    rest of the script works in printed page numbers.

    Args:
        doc: The open PDF.
        start: The first page, 1-indexed.
        end: The last page, 1-indexed and inclusive.
        raw: True to print the pages exactly as extracted, with no boilerplate removed
            and no trimming at the section's edges.
        patterns: The document's boilerplate lines to remove.
        label: The document's name, printed in each block's heading.
        section: The section being extracted, whose own number and the next section's
            number say where to trim the first and last pages. None in page mode, where
            nothing is trimmed.

    Returns:
        The extracted text, one block per page.
    """
    blocks = []
    warnings: list[str] = []

    for page_number in range(start, end + 1):
        page = doc[page_number - 1]
        text = page.get_text()

        if not raw:
            text = strip_boilerplate(text, patterns)

        # Trim the shared pages at the two ends. A section rarely owns a whole
        # page at either boundary: the first page usually opens with the tail of
        # the previous section, and the last page usually ends where the next
        # one begins. Cutting at the headings is what makes two sections that
        # share a page range return different text.
        if section is not None and not raw:
            if page_number == start:
                cut = heading_offset(text, section["number"])
                if cut is not None:
                    text = text[cut:]
                elif section["number"]:
                    warnings.append(
                        f"could not locate the heading for {section['number']} on page "
                        f"{page_number}; that page is shown whole and may open mid-section"
                    )
            if page_number == end and end != start:
                cut = heading_offset(text, section["next_number"])
                if cut is not None:
                    text = text[:cut]
                elif section["next_number"]:
                    warnings.append(
                        f"could not locate the heading for {section['next_number']} on page "
                        f"{page_number}; that page is shown whole and may run past this section"
                    )

        block = f"--- {label} page {page_number} ---\n{text.strip()}"

        lost = describe_lost_content(page)
        if lost:
            block += f"\n{lost}"

        blocks.append(block)

    return "\n\n".join(blocks)


def page_range(text: str, page_count: int) -> tuple[int, int]:
    """Read a page range as a person types it, and refuse one the document cannot serve.

    Pages are checked against the document before anything is printed, because pymupdf
    reads a page number below 1 from the end of the document and a range past the end
    as an error, and a range that ends before it starts prints nothing. Each of those
    would either show the wrong page under the wrong label or read as though the pages
    were empty, which is the silent failure this command exists to prevent.

    Args:
        text: The range as typed, one page such as 26 or two joined by a dash such as
            26-31.
        page_count: How many pages the document has.

    Returns:
        The first and last page, 1-indexed and inclusive.

    Raises:
        ValueError: The range is not numbers, starts before page 1, runs past the
            document, or ends before it starts. The message says which.
    """
    start_text, dash, end_text = text.partition("-")
    if not start_text.isdigit() or (dash and not end_text.isdigit()):
        raise ValueError(
            f"page range {text!r} is not a page number or two joined by a dash, such as 26-31"
        )
    start = int(start_text)
    end = int(end_text) if end_text else start
    if start < 1:
        raise ValueError(f"page range {text!r} starts before page 1")
    if end > page_count:
        raise ValueError(
            f"page range {text!r} runs past the document, which has {page_count} pages"
        )
    if start > end:
        raise ValueError(f"page range {text!r} ends before it starts")
    return start, end


#######################################################################################
### Search ###


def searchable(text: str) -> str:
    """Give a form of the text suitable for matching, not for display.

    Some PDFs store typographic ligatures as single characters, so the word "Definition"
    is really "De" + U+FB01 + "nition" and a plain substring search for it silently
    finds nothing. That is the worst failure mode available here: not an error, just an
    empty result that reads as "the document does not mention this". Of the registered
    documents only the model diagram is affected, with 21 ligatures, but normalising
    costs nothing and a missed hit is a wrong conclusion. NFKD decomposes ligatures back
    into their letters and is applied to both the search term and the page text, so the
    two are always compared on the same footing.

    Text that gets printed is never passed through this, so what the reader sees is
    still exactly what the PDF holds.

    Args:
        text: The page text, or the search term.

    Returns:
        The text with ligatures decomposed into their letters and case folded.
    """
    return unicodedata.normalize("NFKD", text).casefold()


def search_pages(doc: fitz.Document, sections: list[dict], term: str) -> list[str]:
    """Find every page whose text contains the term, case-insensitively.

    This exists so a document can be searched without converting it to a text file. A
    converted copy would drop every diagram and flatten every table, and would then need
    to be kept in step with the PDF; searching in place avoids both problems. It is also
    the only usable access path for the M11 documents, which carry no bookmarks: the M11
    Technical Specification is a reference of data elements rather than a linear read,
    so term lookup is the access pattern it wants.

    Args:
        doc: The open PDF.
        sections: The section map, so a hit can name the section its page falls in.
            Empty for a document without bookmarks.
        term: What to look for.

    Returns:
        One line per hit, naming the page, the section where known, and the first
            matching line, so the caller can decide what is worth reading in full.
    """
    needle = searchable(term)
    hits = []

    for page_index in range(doc.page_count):
        page_number = page_index + 1
        text = doc[page_index].get_text()

        if needle not in searchable(text):
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
            (line.strip() for line in text.splitlines() if needle in searchable(line)),
            "",
        )
        if len(snippet) > 110:
            snippet = snippet[:110] + "..."

        hits.append(f"p.{page_number:>3}  {section_title}\n        {snippet}")

    return hits


#######################################################################################
### Command line ###


def main(argv: list[str] | None = None) -> int:
    """Parse the arguments, run one mode, and give back the exit code.

    Modes are checked in order of specificity: --docs, --list and --find are explicit
    requests, --pages bypasses section lookup, and a bare positional argument is
    resolved as a section. Running with no arguments prints the section map, on the
    assumption that a user who does not know what to ask for wants the menu.

    Args:
        argv: The command-line arguments, or None to read the real ones.

    Returns:
        The exit code, as the header block lists them.
    """
    # Standard text carries characters the Windows console mangles; see
    # sdg.console_output for why.
    use_utf8_output()

    # The registry is read before the parser is built, because --doc offers the
    # keys it holds and falls back to the default it names.
    try:
        documents, default_document = load_registry()
    except UnknownFileError as exc:
        print(exc, file=sys.stderr)
        return 32
    except RegistryError as exc:
        print(exc, file=sys.stderr)
        return 31
    except NotInRepoError as exc:
        print(exc, file=sys.stderr)
        return 6
    except ManifestError as exc:
        print(exc, file=sys.stderr)
        return 3

    parser = argparse.ArgumentParser(
        description="Read part of one of the PDFs listed in lookup_documents.yml, by section, page range or search term."
    )
    parser.add_argument(
        "section",
        nargs="?",
        help='section number or title fragment, e.g. "4.23" or "Extension"',
    )
    parser.add_argument(
        "--doc",
        default=default_document,
        choices=sorted(documents),
        help=f"which document to read (default: {default_document})",
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
    args = parser.parse_args(argv)

    # Mode: list the registry. Answered before opening any file, so it still
    # works on a fresh clone where inputs/ has not been downloaded.
    if args.docs:
        # The listing reports a missing document through the exit code as well as
        # on screen, so a run in a verification block fails rather than leaving a
        # person to read the lines and notice.
        missing = 0
        for key, entry in documents.items():
            state = "present" if entry.path.exists() else "NOT DOWNLOADED"
            if not entry.path.exists():
                missing += 1
            print(f"  {key:16} {entry.label:42} {state}")
        if missing:
            print(
                f"\n{missing} document(s) not downloaded.\n  fix -> run acquire_sources"
            )
            return 8
        return 0

    document = documents[args.doc]

    # Fail early and specifically if the pinned file is absent. This is the one
    # error a user is likely to hit on a fresh clone, since inputs/ is gitignored,
    # so the message names the expected path and the manifest to restore from
    # rather than letting pymupdf raise.
    if not document.path.exists():
        print(f"{document.label} not found at {document.path}", file=sys.stderr)
        print(
            f"inputs/ is gitignored. Re-download per manifests/{document.manifest}.",
            file=sys.stderr,
        )
        return 8

    doc = fitz.open(document.path)
    sections = load_toc(doc)

    wants_sections = args.list or args.section or not (args.pages or args.find)

    # A document with no bookmarks cannot be addressed by section. Say so and
    # name the modes that do work, rather than printing an empty section map or
    # reporting "no section matching", either of which would read as though the
    # document lacked the content rather than lacking the navigation data.
    if wants_sections and not sections:
        print(
            f"{document.label} has no embedded bookmarks, so it cannot be "
            f"addressed by section.",
            file=sys.stderr,
        )
        print(
            f"Use --find TERM to search its {doc.page_count} pages, "
            f"or --pages N-M to read a known range.",
            file=sys.stderr,
        )
        return 24

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
        print(f"{len(hits)} page(s) in {document.label} contain {args.find!r}:\n")
        print("\n".join(hits))
        return 0

    # Mode: an explicit page range, bypassing the section map. Used when the
    # bookmarks are too coarse, which happens where sections share a start page,
    # and it is the only page-addressed mode available for the M11 documents.
    # Page mode addresses pages, not sections, so nothing is trimmed.
    section_for_trim = None

    if args.pages:
        # A range the document cannot serve is a mistake in the command line, so
        # it is reported the way the parser reports one, exit 2.
        try:
            start_page, end_page = page_range(args.pages, doc.page_count)
        except ValueError as exc:
            parser.error(str(exc))
        label = f"pages {args.pages}"

    # Mode: resolve a section number or title fragment.
    else:
        found = find_section(sections, args.section)
        if found is None:
            print(
                f"No section matching {args.section!r}. Run with --list to see all.",
                file=sys.stderr,
            )
            return 23
        start_page = found["start"]
        end_page = found["end"]
        label = found["title"]
        section_for_trim = found

    print(f"### {document.label} | {label} | pages {start_page}-{end_page}\n")
    print(
        extract_pages(
            doc,
            start_page,
            end_page,
            args.raw,
            document.boilerplate,
            document.label,
            section_for_trim,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
