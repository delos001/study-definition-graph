"""
Script:      check_facts.py
Description: Recomputes every countable fact asserted in the project's markdown
             and compares it against what the documents actually say.

             This exists because two such numbers were found wrong in one
             sitting: CLAUDE.md claimed the pinned PDFs run to 500 pages when
             they run to 460, and PLAN.md carried a class count that had been
             garbled during an edit. Neither was a typo. Both were figures
             derived once, written as prose, and never re-derived when the
             corpus changed underneath them.

             A number in prose has no owner. This script makes the pinned files
             the owner and the prose the thing that has to keep up.

             Only countable claims derived from the pinned corpus are checked.
             Judgements, decisions and reasoning are out of scope and always
             will be; those are reviewed by reading. Figures attributed to an
             external source (a cited paper's benchmark, say) are out of scope
             too: they cannot be recomputed from the pinned files, so their
             owner is the citation and its access date, not this script. Such
             figures live behind a [n] reference marker instead.

Inputs:      inputs/**              (read-only, pinned, each verified through verify_pinned)
             manifests/*.json       (read-only, through the manifest reader)
             *.md and docs/*.md     (read-only, scanned for the stated figure)

Outputs:     A report on stdout. Writes nothing to disk.

Usage:       python scripts/check_facts.py
                 check every fact, report drift
             python scripts/check_facts.py --verbose
                 also show facts that match

Exit codes:  0  every stated figure matches the source it came from
             1  at least one figure has drifted. A fact that no document
                asserts is reported but does not fail the run
             2  a pinned file needed for a check is missing
             3  a pinned file needed for a check is on disk but is not the
                pinned one, or the manifest recording it is unreadable or has
                no entry for it; the message names the file, which of those it
                is, and how to recover
             4  the USDM model file is the pinned one but is not shaped like
                USDM v4; the message names the class or attribute that broke
             5  not used here. In sdg.usdm.usdm_spec it means an unknown class name,
                which cannot happen in this script; left unassigned so the
                number keeps one meaning across the repo
             6  the sdg package is installed but not from inside its repo
                (installed without -e), so it cannot find inputs/; the message
                gives the install command
             7  the sdg package is not installed at all

             Codes 3, 4 and 6 mean the same thing as in sdg.usdm.usdm_spec, so one
             number names one cause wherever it appears.

Date:        2026-08-18
Owner:       Jason Delosh
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

# pymupdf is imported under its legacy name "fitz", matching read_pdf.py.
import fitz
import openpyxl

# The model loader, and the three ways it can refuse the pinned file. Guarded
# rather than plain, so that a missing sdg package (never installed) is reported
# by main() as exit 7 with the install command, instead of a traceback before
# any check runs. The three exception classes are needed at module level so the
# measurement loop can give each cause its own exit code.
try:
    from sdg.console_output import use_utf8_output
    from sdg.sources.read_manifests import NotInRepoError
    from sdg.sources.verify_pinned import IntegrityError, verify_pinned
    from sdg.usdm import usdm_spec
    from sdg.usdm.usdm_spec import SpecShapeError

    SDG_MISSING: ImportError | None = None
except ImportError as exc:
    usdm_spec = verify_pinned = None
    IntegrityError = NotInRepoError = SpecShapeError = ()  # never matched
    SDG_MISSING = exc

REPO_ROOT = Path(__file__).resolve().parents[1]
STANDARDS = REPO_ROOT / "inputs" / "standards"
EXAMPLES = REPO_ROOT / "inputs" / "worked_examples"

# Documents scanned for stated figures. docs/standards_lineage.html is included:
# it is linked from docs/sources_index.md and a session acts on what it says, so its
# numbers need the same guard as the prose. Being HTML makes no difference to a
# regex looking for a figure.
DOCS = [
    "README.md",
    "BACKGROUND.md",
    "PLAN.md",
    "CLAUDE.md",
    "docs/sources_index.md",
    "docs/usdm_ig_ledger.md",
    "docs/standards_lineage.html",
]


#######################################################################################
### Measurements ###
#
# One function per countable fact. Each returns the true value, computed from a
# pinned file. They are deliberately small and independent so that a failing
# measurement names exactly one fact.
#
# Every file is obtained through verify_pinned(), which checks it against
# its manifest before it is read. A figure certified here is only worth
# something if it was derived from the file that was actually pinned; a swapped
# or edited copy fails the check (exit 3) instead of quietly certifying the
# documents against the wrong source.


def pinned_pdf_pages() -> int:
    """Count the pages across every PDF registered in read_pdf.py.

    The registry is read from read_pdf.py rather than listing PDFs on disk, so that a
    PDF present but unregistered does not silently inflate the count that CLAUDE.md's
    "never read one whole" rule is scaled against.

    Returns:
        The page count.
    """
    # A plain import resolves because Python puts the running script's own folder
    # (scripts/) first on its search path, and read_pdf.py does nothing at import
    # time beyond defining its table.
    from read_pdf import DOCUMENTS

    return sum(
        len(fitz.open(verify_pinned(entry.path).path)) for entry in DOCUMENTS.values()
    )


def ig_sections() -> int:
    """Count the bookmarks in the USDM Implementation Guide, which is what a section is.

    Returns:
        The bookmark count.
    """
    return len(
        fitz.open(
            verify_pinned(STANDARDS / "cdisc" / "usdm_v4" / "USDM-IG.pdf").path
        ).get_toc()
    )


def core_rules() -> int:
    """Count the rows carrying a rule ID in the conformance rules workbook.

    Returns:
        The rule count.
    """
    sheet = openpyxl.load_workbook(
        verify_pinned(STANDARDS / "cdisc" / "usdm_v4" / "USDM_CORE_Rules.xlsx").path,
        read_only=True,
    )["Version 3.0 and 4.0 CORE rules"]
    return sum(1 for row in list(sheet.iter_rows(values_only=True))[1:] if row[0])


def m11_elements() -> int:
    """Count the data elements in the M11 Technical Specification.

    Counted by the "Term (Variable)" label that opens each element block, which is the
    document's own delimiter rather than a heuristic of ours.

    Returns:
        The element count.
    """
    text = "".join(
        page.get_text()
        for page in fitz.open(
            verify_pinned(
                STANDARDS
                / "ich"
                / "m11_step4"
                / "ICH_Step4_M11_Final_TechnicalSpecification_2025_1119.pdf"
            ).path
        )
    )
    return len(re.findall(r"Term \(Variable\)\s*\n\s*<([^>]{1,80})>", text))


def uml_delta_rows() -> int:
    """Count the lines in the v3.0-to-v4.0 change file, header included, as quoted.

    Returns:
        The line count.
    """
    path = STANDARDS / "cdisc" / "usdm_v4" / "UML_DELTA_3-0-0_4-0-0.csv"
    return len(verify_pinned(path).read_text().splitlines())


def dictionary_codes() -> int:
    """Count the distinct NCI C-codes named in the data dictionary.

    Returns:
        The code count.
    """
    text = verify_pinned(
        STANDARDS / "cdisc" / "usdm_v4" / "dataDictionary.MD"
    ).read_text()
    return len(set(re.findall(r"\b(C\d{4,6})\b", text)))


def usdm_concrete_classes() -> int:
    """Count the concrete USDM classes, through the model loader.

    The count goes through sdg.usdm.usdm_spec, the one doorway to the standard, rather than
    re-parsing dataStructure.yml here, so a single place reads the model.
    extensionAttributes sits on every one of these classes, which is the claim
    usdm_ig_ledger.md makes. The loader also checks the file is shaped like USDM v4, the
    one failure only this measurement can raise (exit 4).

    Returns:
        The concrete class count.
    """
    spec = usdm_spec.load()
    return sum(
        1 for c in usdm_spec.class_names(spec) if not usdm_spec.is_abstract(spec, c)
    )


def shared_codes() -> int:
    """Count the NCI codes appearing in both the M11 Technical Specification and USDM's CT.

    Guarded because it is the one figure on the standards map that contradicts an
    intuition: both standards use NCI codes, so they look interchangeable, and they are
    not. If this number ever drifts toward either total it would change the conclusion,
    not just the caption.

    Returns:
        The shared code count.
    """
    text = "".join(
        page.get_text()
        for page in fitz.open(
            verify_pinned(
                STANDARDS
                / "ich"
                / "m11_step4"
                / "ICH_Step4_M11_Final_TechnicalSpecification_2025_1119.pdf"
            ).path
        )
    )
    m11 = set(re.findall(r"\b(C\d{4,6})\b", text))

    terminology = set()
    for sheet in openpyxl.load_workbook(
        verify_pinned(STANDARDS / "cdisc" / "usdm_v4" / "USDM_CT.xlsx").path,
        read_only=True,
    ):
        for row in sheet.iter_rows(values_only=True):
            for cell in row:
                if cell:
                    terminology.update(re.findall(r"\b(C\d{4,6})\b", str(cell)))
    return len(m11 & terminology)


def worked_examples() -> int:
    """Count the worked example studies, one directory each.

    A count of folders, not a read of any file's contents, so there is nothing for the
    pinned-file check to verify here; the files inside are verified where they are read,
    in examples_with_estimands.

    Returns:
        The study count.
    """
    return len([d for d in EXAMPLES.iterdir() if d.is_dir()])


def examples_with_estimands() -> int:
    """Count the worked-example studies whose USDM JSON defines at least one estimand.

    Estimands hang off each studyDesign. Counted because PLAN.md leans on their
    scarcity, only one of the three examples defines any, to justify why Phase 1 must
    select for documents that actually define estimands. If the corpus grows or an
    example gains an estimand, that argument has to move with it.

    Returns:
        The count of studies with an estimand.
    """
    count = 0
    for directory in EXAMPLES.iterdir():
        if not directory.is_dir():
            continue

        # An example ships a PDF, an .xlsx and one USDM export; the export is
        # the only .json, so the glob cannot pick up the wrong file.
        exports = list(directory.glob("*.json"))
        if not exports:
            continue

        document = json.loads(verify_pinned(exports[0]).read_text())
        designs = document["study"]["versions"][0]["studyDesigns"]
        if any(design.get("estimands") for design in designs):
            count += 1
    return count


# Each entry is (label, measurement, regex capturing the figure as stated).
# The regex must be specific enough that it cannot match an unrelated number;
# a loose pattern would report a false match and defeat the point.
FACTS = [
    ("pinned PDF pages", pinned_pdf_pages, r"(\d+) pages across"),
    ("IG sections", ig_sections, r"of (\d+) sections"),
    ("CORE rules", core_rules, r"(\d+) rules\b"),
    ("M11 data elements", m11_elements, r"(\d+) elements"),
    ("UML delta rows", uml_delta_rows, r"(\d+) rows:"),
    ("dataDictionary codes", dictionary_codes, r"(\d+) NCI codes|all (\d+) codes"),
    ("USDM concrete classes", usdm_concrete_classes, r"all (\d+) concrete class"),
    ("M11 and USDM shared codes", shared_codes, r"(\d+) codes in common"),
    # Written as a word in prose, so the check accepts either form. Kept narrow
    # enough that "three" elsewhere in a sentence cannot match.
    (
        "worked example studies",
        worked_examples,
        r"(?:(\d+)|(?i:(three)|(two)|(four))) (?:real protocols|worked example)",
    ),
    # The count of examples that define an estimand, as stated in PLAN.md. The
    # trailing literal "of the three pinned examples defines" anchors it so the
    # captured number is the leading count, not the "three" later in the phrase.
    (
        "examples with estimands",
        examples_with_estimands,
        r"(?:(\d+)|(?i:(one)|(two)|(three))) of the three pinned examples defines",
    ),
]


#######################################################################################
### Reporting ###


# Small counts are often written as words in prose. Mapping them here keeps the
# check honest without forcing the documents to use digits where words read
# better.
WORD_NUMBERS = {"one": "1", "two": "2", "three": "3", "four": "4"}


def stated_values(pattern: str) -> list[tuple[str, int]]:
    """Find every occurrence of a figure matching the pattern, with the file it is in.

    A list comes back rather than a single value because the same fact is often asserted
    in more than one document, and each occurrence has to agree independently. Reporting
    only the first would hide a stale copy elsewhere.

    Args:
        pattern: The regular expression that finds the figure, with the number as its
            capture group.

    Returns:
        One pair per occurrence: the document's name and the number it states.
    """
    found = []
    for name in DOCS:
        path = REPO_ROOT / name
        if not path.exists():
            continue
        for match in re.finditer(pattern, path.read_text(encoding="utf-8")):
            # Alternation groups leave unmatched branches as None; take the one
            # that fired.
            raw = next(g for g in match.groups() if g is not None)
            value = WORD_NUMBERS.get(raw.lower(), raw)
            found.append((name, int(value)))
    return found


def main(argv: list[str] | None = None) -> int:
    """Recompute every fact, compare each to what the documents say, and give back the exit
    code.

    Args:
        argv: The command-line arguments, or None to read the real ones.

    Returns:
        The exit code, as the header block lists them.
    """
    parser = argparse.ArgumentParser(
        description="Check countable claims in the markdown against the pinned files."
    )
    parser.add_argument(
        "--verbose", action="store_true", help="also show facts that match"
    )
    args = parser.parse_args(argv)

    # Reported before any measurement, since one of them needs the package and
    # the fix is the same one-line install either way.
    if SDG_MISSING is not None:
        print(f"the sdg package is not installed ({SDG_MISSING})")
        print("  fix -> from the repo root: pip install -e .")
        return 7

    # Standard text carries characters the Windows console mangles; see
    # sdg.console_output for why. Called after the guard above, since the
    # helper comes from the package that guard reports missing.
    use_utf8_output()

    drifted = unasserted = 0

    for label, measure, pattern in FACTS:
        # Each way a measurement can fail is a different root cause with a
        # different remedy, so each gets its own exit code (see header). None
        # can be reported as drift, because nothing was measured.
        try:
            actual = measure()
        except (FileNotFoundError, KeyError, OSError) as exc:
            print(f"  UNMEASURABLE  {label}: {exc}")
            return 2
        except NotInRepoError as exc:
            print(f"  NOT IN REPO   {label}: {exc}")
            return 6
        except IntegrityError as exc:
            print(f"  UNVERIFIED    {label}: {exc}")
            return 3
        except SpecShapeError as exc:
            print(f"  WRONG SHAPE   {label}: {exc}")
            return 4

        occurrences = stated_values(pattern)

        if not occurrences:
            print(f"  NOT ASSERTED  {label}: measured {actual}, no document states it")
            unasserted += 1
            continue

        for name, stated in occurrences:
            if stated != actual:
                print(
                    f"  DRIFTED       {label} in {name}: says {stated}, actual {actual}"
                )
                drifted += 1
            elif args.verbose:
                print(f"  ok            {label} in {name}: {actual}")

    print()
    print(
        f"{len(FACTS)} fact(s) checked, {drifted} drifted, {unasserted} asserted nowhere."
    )

    # A fact nobody asserts is not an error in the documents; it just means this
    # script is tracking something the prose does not claim. Only real drift
    # fails the run.
    return 1 if drifted else 0


if __name__ == "__main__":
    raise SystemExit(main())
