"""
Script:      check_facts.py
Description: Recomputes each figure its list of facts records, a count or a date,
             from the pinned files, and compares it with every place the
             project's Markdown states it. It reads every Markdown file git
             tracks, apart from the files its exclusion list names.

             This exists because two such numbers were found wrong in one
             sitting: CLAUDE.md stated a page total for the pinned PDFs that
             was wrong, and PLAN.md carried a class count that had been
             garbled during an edit. Neither was a typo. Both were figures
             derived once, written as prose, and never re-derived when the
             corpus changed underneath them.

             A number in prose has no owner. This script makes the pinned files
             the owner and the prose the thing that has to keep up.

             Only figures derived from the pinned corpus are confirmed.
             Judgements, decisions and reasoning are out of scope and always
             will be; those are reviewed by reading. Figures attributed to an
             external source (a cited paper's benchmark, say) are out of scope
             too: they cannot be recomputed from the pinned files, so their
             owner is the citation and its access date, not this script. Such
             figures live behind a [n] reference marker instead.

             A recorded figure that no document states any more fails the run.
             Its sentence was most likely reworded, and a figure nothing is
             compared with is one this tool has silently stopped confirming.
             Reporting it and passing would say every figure is confirmed when
             one is not.

             DECISIONS.md is on the exclusion list, because each entry records
             what was true on the day it was written, and a figure there is
             history rather than a claim about the pinned files today.

Inputs:      inputs/**              (read-only, pinned, each verified through verify_file)
             every manifest, read through src/sdg/sources/read_manifests.py
                                    (read-only)
             every Markdown file git tracks, apart from EXCLUDED_DOCUMENTS in
             this file   (read-only, scanned for the stated figures)
             git   (lists the tracked Markdown files)

Outputs:     A report on stdout. Writes nothing to disk.

Usage:       check_facts
                 confirm every fact, report drift
             check_facts --verbose
                 also show facts that match

Exit codes:  0   SUCCEEDED  the command succeeded (every recorded figure is
                 stated, and every statement matches the source it came from)
             1   UNHANDLED-ERROR  Python stopped on an error that nothing
                 handled
             2   COMMAND-LINE-REFUSED  the argument parser refused the command
                 line
             3   NOT-IN-REPO  the sdg package is not running from inside its
                 repo
             6   GIT-NOT-FOUND  git cannot be found on the path (it lists the
                 tracked Markdown files)
             7   GIT-FAILED  git was found but did not answer (the folder is not
                 a git clone, for example)
             12  MANIFEST-MISSING  the manifests folder is missing or holds no
                 manifest
             12  PINNED-FILE-NOT-DOWNLOADED  a pinned file has not been
                 downloaded
             13  MANIFEST-UNREADABLE  a manifest is on disk but cannot be opened
             13  PINNED-FILE-UNREADABLE  a pinned file is on disk but cannot be
                 opened (a workbook another program has locked, for example)
             14  MANIFEST-UNPARSEABLE  a manifest is not valid JSON
             14  USDM-MODEL-UNPARSEABLE  the pinned model file is not valid YAML
             14  PINNED-FILE-UNPARSEABLE  a pinned file a measurement reads is
                 not valid in its format
             15  MANIFEST-INVALID  a manifest's content breaks a requirement
             15  MANIFEST-LOCATION-OUTSIDE-INPUTS  a manifest records a
                 location that does not stay under inputs/
             15  MANIFEST-NAME-SHARED  two manifest entries record the same file
                 name (the name a measurement looks up)
             15  USDM-MODEL-WRONG-SHAPE  the pinned model file is not shaped
                 like the pinned USDM model
             15  PINNED-FILE-WRONG-SHAPE  a pinned file is not shaped the way a
                 measurement expects (it was read, but lacks what the
                 measurement reaches for)
             16  PINNED-FILE-CHANGED  a pinned file on disk no longer matches
                 its manifest entry
             16  FILE-UNRECORDED  a file under inputs/ is recorded by no
                 manifest (or a measurement names a file no manifest records)
             16  FIGURE-DRIFTED  a stated figure has drifted from the pinned
                 files
             16  FIGURE-UNSTATED  a recorded figure is stated in no document
             The wording is the table in docs/exit_codes.csv. A measurement
             stops at the first file it cannot use, so the run reports one
             cause at a time. FIGURE-DRIFTED decides the exit line before
             FIGURE-UNSTATED, because a figure stated wrongly misleads a reader
             now. Both are still named.

Date:        2026-08-18
Owner:       Jason Delosh
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import zipfile
from datetime import datetime
from pathlib import Path

import openpyxl
from openpyxl.utils.exceptions import InvalidFileException

# The model loader, and the ways it can refuse the pinned file. The exception
# classes are imported here so the measurement loop can report each cause with the
# exit number and sub-code it carries.
from sdg.console_output import use_utf8_output
from sdg.exit_codes import fail, finish, problem_line
from sdg.sources.read_manifests import (
    ManifestError,
    NotInRepoError,
    entry_named,
)
from sdg.sources.verify_pinned import (
    IntegrityError,
    UnrecordedFileError,
    verify_file,
)
from sdg.usdm import usdm_spec
from sdg.usdm.usdm_spec import SpecShapeError

REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = REPO_ROOT / "inputs" / "worked_examples"

# The pinned Biomedical Concepts export, by the file name its manifest entry records.
# The manifest alone says where the file lives.
CONCEPTS_NAME = "cdisc_biomedical_concepts_latest.xlsx"

# Every Markdown file git tracks is scanned for stated figures, so a document added
# later is compared without an edit here. These tracked files are left out.
EXCLUDED_DOCUMENTS = {
    # Each entry records what was true on the day it was written, so a figure there
    # is history rather than a claim about the pinned files today.
    "DECISIONS.md",
}

# The command that lists the tracked files. Named here so a check can stand in a
# command that cannot be run.
GIT = "git"


class GitError(Exception):
    """Raised when git was found but does not answer, so the tracked files are unknown.

    It carries the exit number and sub-code the command reports it with, from
    docs/exit_codes.csv.
    """

    exit_code = 7
    sub_code = "GIT-FAILED"


class GitNotFoundError(GitError):
    """Raised when git cannot be found on the path."""

    exit_code = 6
    sub_code = "GIT-NOT-FOUND"


#######################################################################################
### Measurements ###
#
# One function per stated fact. Each returns the true value, computed from a
# pinned file. They are deliberately small and independent so that a failing
# measurement names exactly one fact.
#
# Every file is obtained through verify_file(), which confirms it matches
# its manifest before it is read. A figure certified here is only worth
# something if it was derived from the file that was actually pinned; a swapped
# or edited copy stops the run (exit 16, PINNED-FILE-CHANGED) instead of quietly certifying the
# documents against the wrong source.


def usdm_concrete_classes() -> int:
    """Count the concrete USDM classes, through the model loader.

    The count goes through sdg.usdm.usdm_spec, the one doorway to the standard, rather than
    re-parsing dataStructure.yml here, so a single place reads the model.
    extensionAttributes sits on every one of these classes, which is the claim
    docs/standards_read_record.md makes. The loader also confirms the file is shaped like USDM v4, the
    one failure only this measurement can raise (exit 15, USDM-MODEL-WRONG-SHAPE).

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

        document = json.loads(verify_file(exports[0]).read_text())
        designs = document["study"]["versions"][0]["studyDesigns"]
        if any(design.get("estimands") for design in designs):
            count += 1
    return count


def concepts_newest_package_date() -> str:
    """Find the release date of the newest Biomedical Concept package in the pinned export.

    CDISC gives the export no version, so the project names its folder with this
    date: the latest package_date in the Biomedical Concepts sheet, which the
    workbook's ReadMe defines as the date a package was published to production.
    The file is found by the name its manifest entry records, so its location is
    written only in the manifest. The date is then read from the file itself, so a
    folder named with a date that is not in the file is reported as drift.

    Returns:
        The date as text, in the form 2026-07-14.

    Raises:
        UnrecordedFileError: No manifest records the export.
        ManifestError: Two entries record its name.
    """
    entry = entry_named(CONCEPTS_NAME)
    if entry is None:
        raise UnrecordedFileError(
            f"no manifest entry is named {CONCEPTS_NAME}\n"
            "  fix -> record the file in manifests/, or correct CONCEPTS_NAME in "
            "src/sdgtools/check_facts.py"
        )
    workbook = openpyxl.load_workbook(verify_file(entry.path).path, read_only=True)
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
### Finding the documents ###


def tracked_documents() -> list[str]:
    """List every Markdown file git tracks, apart from the excluded ones.

    git is asked rather than the folders walked, so a file git ignores, such as a
    working note, is never read as a document the project stands behind.

    Returns:
        The files' paths from the repo root, with forward slashes, sorted.

    Raises:
        GitNotFoundError: git could not be found on the path.
        GitError: git was found but did not answer.
    """
    # A missing git and a git that refuses the folder both leave the tracked files
    # unknown, but the first is fixed by installing git and the second by running
    # from inside the clone, so each has its own error.
    try:
        listing = subprocess.run(
            [GIT, "ls-files", "-z", "--", "*.md"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        ).stdout
    except subprocess.CalledProcessError as exc:
        raise GitError(f"git did not answer: {exc.stderr.strip()}") from exc
    except OSError as exc:
        raise GitNotFoundError(f"git could not be run: {exc}") from exc
    return sorted(
        name for name in listing.split("\0") if name and name not in EXCLUDED_DOCUMENTS
    )


#######################################################################################
### Reporting ###


# Small counts are often written as words in prose. Mapping them here keeps the
# comparison honest without forcing the documents to use digits where words read
# better.
WORD_NUMBERS = {"one": "1", "two": "2", "three": "3", "four": "4"}


def stated_values(pattern: str, documents: list[str]) -> list[tuple[str, str]]:
    """Find every occurrence of a figure matching the pattern, with the file it is in.

    A list comes back rather than a single value because the same fact is often asserted
    in more than one document, and each occurrence has to agree independently. Reporting
    only the first would hide a stale copy elsewhere.

    Args:
        pattern: The regular expression that finds the figure, with the number as its
            capture group.
        documents: The documents to read, as paths from the repo root.

    Returns:
        One pair per occurrence: the document's name and the figure it states, as
        text, so a count and a date are compared the same way.
    """
    found = []
    for name in documents:
        path = REPO_ROOT / name
        # A tracked file deleted from the working folder, and not yet committed as
        # deleted, states nothing any more.
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
        description="Confirm that the figures stated in the markdown match the pinned files."
    )
    parser.add_argument(
        "--verbose", action="store_true", help="also show facts that match"
    )
    args = parser.parse_args(argv)

    # Standard text carries characters the Windows console mangles; see
    # sdg.console_output for why.
    use_utf8_output()

    # The documents are listed before anything is measured, because without them
    # no figure can be compared.
    try:
        documents = tracked_documents()
    except GitNotFoundError as exc:
        return fail(print, exc.exit_code, exc.sub_code, f"{exc}\n  fix -> install git")
    except GitError as exc:
        return fail(
            print,
            exc.exit_code,
            exc.sub_code,
            f"{exc}\n  fix -> run check_facts from inside the repo's clone",
        )

    drifted = unasserted = 0

    for label, measure, pattern in FACTS:
        # Each way a measurement can fail is a different root cause with a
        # different remedy, so each has its own sub-code (see header). None can be
        # reported as drift, because nothing was measured.
        try:
            actual = measure()
        except FileNotFoundError as exc:
            return fail(print, 12, "PINNED-FILE-NOT-DOWNLOADED", f"{label}: {exc}")
        except (json.JSONDecodeError, zipfile.BadZipFile, InvalidFileException) as exc:
            # JSON that does not parse is a kind of ValueError, so it is caught
            # before the shape errors below and keeps its own sub-code. A workbook
            # that is not a valid workbook raises either of the other two, which
            # no branch below would catch.
            return fail(print, 14, "PINNED-FILE-UNPARSEABLE", f"{label}: {exc}")
        except (KeyError, IndexError, TypeError, AttributeError, ValueError) as exc:
            # The file was read but does not hold what the measurement reaches
            # for: a worked example lacking its study designs, or a design that
            # is not an object. Neither a re-download nor the network would change
            # either of those.
            return fail(print, 15, "PINNED-FILE-WRONG-SHAPE", f"{label}: {exc}")
        except OSError as exc:
            # The file is there but cannot be opened, as a workbook Excel has
            # locked. Listed after the missing-file case, which is one kind
            # of OSError, so that case keeps its own sub-code.
            return fail(print, 13, "PINNED-FILE-UNREADABLE", f"{label}: {exc}")
        except (
            NotInRepoError,
            ManifestError,
            UnrecordedFileError,
            IntegrityError,
            SpecShapeError,
        ) as exc:
            return fail(print, exc.exit_code, exc.sub_code, f"{label}: {exc}")

        occurrences = stated_values(pattern, documents)

        if not occurrences:
            print(
                problem_line(
                    "FIGURE-UNSTATED",
                    f"{label}: measured {actual}, no document states it\n"
                    "  fix -> state the figure again where the project reasons from "
                    "it, or remove its measurement from FACTS in "
                    "src/sdgtools/check_facts.py",
                )
            )
            unasserted += 1
            continue

        for name, stated in occurrences:
            if stated != str(actual):
                print(
                    problem_line(
                        "FIGURE-DRIFTED",
                        f"{label} in {name}: says {stated}, actual {actual}",
                    )
                )
                drifted += 1
            elif args.verbose:
                print(f"  ok            {label} in {name}: {actual}")

    print()
    print(
        f"{len(FACTS)} fact(s) compared, {drifted} drifted, {unasserted} asserted nowhere."
    )

    # A recorded figure that no document states fails the run, because passing it
    # would report every figure confirmed while one is compared with nothing. Drift
    # outranks it, because a figure stated wrongly misleads a reader now.
    if drifted:
        return finish(print, 16, "FIGURE-DRIFTED")
    if unasserted:
        return finish(print, 16, "FIGURE-UNSTATED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
