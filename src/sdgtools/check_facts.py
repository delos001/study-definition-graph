"""
Script:      check_facts.py
Description: Recomputes every figure asserted in the project's markdown, a count
             or a date, and compares it against what the documents actually say.

             This exists because two such numbers were found wrong in one
             sitting: CLAUDE.md stated a page total for the pinned PDFs that
             was wrong, and PLAN.md carried a class count that had been
             garbled during an edit. Neither was a typo. Both were figures
             derived once, written as prose, and never re-derived when the
             corpus changed underneath them.

             A number in prose has no owner. This script makes the pinned files
             the owner and the prose the thing that has to keep up.

             Only figures derived from the pinned corpus are checked.
             Judgements, decisions and reasoning are out of scope and always
             will be; those are reviewed by reading. Figures attributed to an
             external source (a cited paper's benchmark, say) are out of scope
             too: they cannot be recomputed from the pinned files, so their
             owner is the citation and its access date, not this script. Such
             figures live behind a [n] reference marker instead.

Inputs:      inputs/**              (read-only, pinned, each verified through verify_pinned)
             manifests/*.json       (read-only, through src/sdg/sources/read_manifests.py)
             the documents named in the DOCS list in this file   (read-only, scanned for the stated figure)

Outputs:     A report on stdout. Writes nothing to disk.

Usage:       check_facts
                 check every fact, report drift
             check_facts --verbose
                 also show facts that match

Exit codes:  0   success (every stated figure matches the source it came from;
                 a fact that no document asserts is reported but does not fail
                 the run)
             1   unhandled error, Python's own
             2   invalid command line, the argument parser's own
             3   a manifest is missing or cannot be read
             4   the pinned model file is not shaped like USDM v4
             6   not running from inside the repo
             7   the sdg package is not installed
             8   a pinned file has not been downloaded
             9   a pinned file on disk does not match its manifest entry
             10  a file under inputs/ that no manifest records
             13  a file on disk cannot be read (a workbook another program has
                 locked, for example)
             14  a stated figure has drifted from the pinned files
             42  a pinned file is not shaped the way a measurement expects (it
                 was read, but lacks what the measurement reaches for)
             The numbers are the repo-wide table in
             docs/exit_codes.csv. A measurement stops at the
             first file it cannot use, so the run reports one cause at a time.

Date:        2026-08-18
Owner:       Jason Delosh
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path

import openpyxl

# The model loader, and the ways it can refuse the pinned file. Guarded rather
# than plain, so that a missing sdg package (never installed) is reported by
# main() as exit 7 with the install command, instead of a traceback before any
# check runs. The five exception classes are imported here so the measurement
# loop can give each cause its own exit code.
try:
    from sdg.console_output import use_utf8_output
    from sdg.sources.read_manifests import ManifestError, NotInRepoError, entry_named
    from sdg.sources.verify_pinned import (
        IntegrityError,
        UnrecordedFileError,
        verify_pinned,
    )
    from sdg.usdm import usdm_spec
    from sdg.usdm.usdm_spec import SpecShapeError

    SDG_MISSING: ImportError | None = None
except ImportError as exc:
    # Nothing is bound in this case. main() reports the missing package and
    # returns before any of the names above is used.
    SDG_MISSING = exc

REPO_ROOT = Path(__file__).resolve().parents[2]
STANDARDS = REPO_ROOT / "inputs" / "standards"
EXAMPLES = REPO_ROOT / "inputs" / "worked_examples"

# Documents scanned for stated figures. Anything under docs/draft/ is left out,
# because nothing there is linked to or relied on.
DOCS = [
    "README.md",
    "BACKGROUND.md",
    "PLAN.md",
    "CLAUDE.md",
    "docs/sources_index.md",
    "docs/standards_read_record.md",
]


#######################################################################################
### Measurements ###
#
# One function per stated fact. Each returns the true value, computed from a
# pinned file. They are deliberately small and independent so that a failing
# measurement names exactly one fact.
#
# Every file is obtained through verify_pinned(), which checks it against
# its manifest before it is read. A figure certified here is only worth
# something if it was derived from the file that was actually pinned; a swapped
# or edited copy fails the check (exit 9) instead of quietly certifying the
# documents against the wrong source.


def usdm_concrete_classes() -> int:
    """Count the concrete USDM classes, through the model loader.

    The count goes through sdg.usdm.usdm_spec, the one doorway to the standard, rather than
    re-parsing dataStructure.yml here, so a single place reads the model.
    extensionAttributes sits on every one of these classes, which is the claim
    docs/standards_read_record.md makes. The loader also checks the file is shaped like USDM v4, the
    one failure only this measurement can raise (exit 4).

    Returns:
        The concrete class count.
    """
    spec = usdm_spec.load()
    return sum(
        1 for c in usdm_spec.class_names(spec) if not usdm_spec.is_abstract(spec, c)
    )


def examples_with_estimands() -> int:
    """Count the worked-example studies whose USDM JSON defines at least one estimand.

    Estimands hang off each studyDesign. Counted because PLAN.md leans on their
    scarcity, only one of the pinned examples defines any, to justify why Phase 1 must
    select for documents that actually define estimands. If the pinned files under inputs/ grow or an
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


def concepts_newest_package_date() -> str:
    """Find the release date of the newest Biomedical Concept package in the pinned export.

    CDISC gives the export no version, so the project names its folder with this
    date: the latest package_date in the Biomedical Concepts sheet, which the
    workbook's ReadMe defines as the date a package was published to production.
    The file is found through its manifest entry rather than through the folder
    name, so a folder named with a date that is not in the file is reported as
    drift, not as a missing file.

    Returns:
        The date as text, in the form 2026-07-14.

    Raises:
        ManifestError: No manifest records the export.
    """
    entry = entry_named("cdisc_biomedical_concepts_latest.xlsx")
    if entry is None:
        raise ManifestError(
            "no manifest entry is named cdisc_biomedical_concepts_latest.xlsx"
        )
    workbook = openpyxl.load_workbook(verify_pinned(entry.path).path, read_only=True)
    rows = workbook["Biomedical Concepts"].iter_rows(values_only=True)
    column = list(next(rows)).index("package_date")
    newest = ""
    for row in rows:
        value = row[column]
        if value is None:
            continue
        # openpyxl hands a date cell back as a datetime and a text cell as a
        # string; both are reduced to the same ten characters before comparing.
        text = value.isoformat() if isinstance(value, datetime) else str(value)
        newest = max(newest, text[:10])
    return newest


# Each entry is (label, measurement, regex capturing the figure as stated).
# The regex must be specific enough that it cannot match an unrelated number;
# a loose pattern would report a false match and defeat the point.
FACTS = [
    ("USDM concrete classes", usdm_concrete_classes, r"all (\d+) concrete class"),
    # The count of examples that define an estimand, as stated in PLAN.md. The
    # trailing literal "of the three pinned examples defines" anchors it so the
    # captured number is the leading count, not the "three" later in the phrase.
    (
        "examples with estimands",
        examples_with_estimands,
        r"(?:(\d+)|(?i:(one)|(two)|(three))) of the three pinned examples defines",
    ),
    # The date in the Biomedical Concepts folder name, as docs/sources_index.md
    # writes the location. It must be the newest package_date in the export,
    # never the day the file was fetched or the commit it was fetched at.
    (
        "Biomedical Concepts newest package date",
        concepts_newest_package_date,
        r"biomedical_concepts_(\d{4}-\d{2}-\d{2})",
    ),
]


#######################################################################################
### Reporting ###


# Small counts are often written as words in prose. Mapping them here keeps the
# check honest without forcing the documents to use digits where words read
# better.
WORD_NUMBERS = {"one": "1", "two": "2", "three": "3", "four": "4"}


def stated_values(pattern: str) -> list[tuple[str, str]]:
    """Find every occurrence of a figure matching the pattern, with the file it is in.

    A list comes back rather than a single value because the same fact is often asserted
    in more than one document, and each occurrence has to agree independently. Reporting
    only the first would hide a stale copy elsewhere.

    Args:
        pattern: The regular expression that finds the figure, with the number as its
            capture group.

    Returns:
        One pair per occurrence: the document's name and the figure it states, as
        text, so a count and a date are compared the same way.
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
            found.append((name, WORD_NUMBERS.get(raw.lower(), raw)))
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
        description="Check the figures stated in the markdown against the pinned files."
    )
    parser.add_argument(
        "--verbose", action="store_true", help="also show facts that match"
    )
    args = parser.parse_args(argv)

    # Reported before any measurement, since one of them needs the sdg package and
    # the fix is the same one-line install either way.
    if SDG_MISSING is not None:
        print(f"the sdg package is not installed ({SDG_MISSING})")
        print("  fix -> from the repo root: pip install -e .")
        return 7

    # Standard text carries characters the Windows console mangles; see
    # sdg.console_output for why. Called after the guard above, since the
    # helper comes from the sdg package that guard reports missing.
    use_utf8_output()

    drifted = unasserted = 0

    for label, measure, pattern in FACTS:
        # Each way a measurement can fail is a different root cause with a
        # different remedy, so each gets its own exit code (see header). None
        # can be reported as drift, because nothing was measured.
        try:
            actual = measure()
        except FileNotFoundError as exc:
            print(f"  NOT DOWNLOADED {label}: {exc}")
            return 8
        except (KeyError, IndexError, TypeError, AttributeError, ValueError) as exc:
            # The file was read but does not hold what the measurement reaches
            # for: a worked example lacking its study designs, a design that is
            # not an object, or JSON that does not parse, which the json module
            # reports as a ValueError. Neither a re-download nor the network
            # would change any of those.
            print(f"  UNEXPECTED SHAPE {label}: {exc}")
            return 42
        except OSError as exc:
            # The file is there but cannot be opened, as a workbook Excel has
            # locked. Listed after the missing-file case, which is one kind
            # of OSError, so that case keeps its own number.
            print(f"  CANNOT READ    {label}: {exc}")
            return 13
        except NotInRepoError as exc:
            print(f"  NOT IN REPO    {label}: {exc}")
            return 6
        except ManifestError as exc:
            print(f"  BAD MANIFEST   {label}: {exc}")
            return 3
        except UnrecordedFileError as exc:
            print(f"  UNRECORDED     {label}: {exc}")
            return 10
        except IntegrityError as exc:
            print(f"  MISMATCH       {label}: {exc}")
            return 9
        except SpecShapeError as exc:
            print(f"  WRONG SHAPE    {label}: {exc}")
            return 4

        occurrences = stated_values(pattern)

        if not occurrences:
            print(f"  NOT ASSERTED  {label}: measured {actual}, no document states it")
            unasserted += 1
            continue

        for name, stated in occurrences:
            if stated != str(actual):
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
    return 14 if drifted else 0


if __name__ == "__main__":
    raise SystemExit(main())
