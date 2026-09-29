"""
Script:      test_check_facts_technical.py
Description: Checks for src/sdgtools/check_facts.py, the hand-run script that
             re-derives every figure stated in the project's documents, a count or
             a date, from the pinned files. The script is a list of measurements and a loop that
             compares each to what the documents say. The checks here replace
             that list with one small fake fact, a measurement that returns, or
             raises, whatever the check needs, and a one-line document in a
             temporary folder, then assert the report and the exit code. The
             checks on which documents are read stage a small git repository in
             a temporary folder instead, because git is what lists them. The
             checks on which file a measurement reads stage a small repo of
             pinned files through the fake_repo fixture in
             validation/conftest.py. The run against the real pinned files is in
             test_check_facts_integrity.py, beside this file.

Inputs:      Nothing real. Every document, manifest and pinned file is written to
             pytest's own temporary folder.

Outputs:     Writes nothing to disk. Temporary files go to pytest's own folder.

Usage:       pytest validation/sdgtools/test_check_facts_technical.py
                 run these checks
             pytest validation/sdgtools/test_check_facts_technical.py -v
                 one line per check with its result

Exit codes:  None of its own. It runs inside pytest.

Date:        2026-09-04
Owner:       Jason Delosh
"""

from __future__ import annotations

import json
import subprocess

import openpyxl
import pytest

from sdg.sources.read_manifests import (
    ManifestError,
    NotInRepoError,
    OutsideInputsError,
)
from sdg.sources.verify_pinned import IntegrityError, UnrecordedFileError
from sdg.usdm.usdm_spec import SpecShapeError
from sdgtools import check_facts as cf
from sdgval.labels import category, code, negative, objective, positive

#######################################################################################
### Shared staging ###
#
# One fixture replaces the script's whole list of facts with a single fake one, and
# the documents git would list with a single one-line file, so each check controls
# both the measured number and the stated one. A second fixture stages a real git
# repository instead, for the checks on which documents are read.


@pytest.fixture
def fact(tmp_path, monkeypatch):
    """Give a check a function that installs one fake fact and one document.

    The script's repo root is pointed at a temporary folder, and its listing of tracked
    documents at one file there, for the length of the check.

    Returns:
        The installing function.
    """
    monkeypatch.setattr(cf, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(cf, "tracked_documents", lambda: ["facts.md"])

    def install(measure, doc_text: str, pattern: str = r"(\d+) widgets") -> None:
        """Write the document and make the measurement the script's only fact.

        Args:
            measure: A function that produces the measured number, or raises.
            doc_text: The whole text of the one document.
            pattern: The regular expression that finds the stated figure in it.
        """
        (tmp_path / "facts.md").write_text(doc_text, encoding="utf-8")
        monkeypatch.setattr(cf, "FACTS", [("widgets", measure, pattern)])

    return install


@pytest.fixture
def tracked(tmp_path, monkeypatch):
    """Give a check a function that stages Markdown files in a git repository.

    The script's repo root is pointed at a temporary folder made into a git
    repository, and its only fact counts 3 widgets. The files git is told to track
    are added to its index, which is what git lists as tracked. Nothing is committed.

    Returns:
        The staging function.
    """
    monkeypatch.setattr(cf, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(cf, "FACTS", [("widgets", lambda: 3, r"(\d+) widgets")])
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)

    def stage(files: dict[str, str], untracked: tuple[str, ...] = ()) -> None:
        """Write the files, and add to git's index every one not named as untracked.

        Args:
            files: The Markdown files to write, their text keyed by path from the root.
            untracked: The paths to leave out of git's index.
        """
        for name, text in files.items():
            path = tmp_path / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        added = [name for name in files if name not in untracked]
        subprocess.run(["git", "add", "--", *added], cwd=tmp_path, check=True)

    return stage


#######################################################################################
### Comparing a figure to the documents ###


@code("SA00274")
@category("repository")
@objective("functionality")
@positive
def test_matching_figure_exits_0(fact, capsys):
    """A document stating the measured number passes with exit 0, and the verbose option
    shows a line naming the fact, the file and the value."""
    fact(lambda: 3, "We hold 3 widgets.\n")
    assert cf.main(["--verbose"]) == 0
    out = capsys.readouterr().out
    assert "ok            widgets in facts.md: 3" in out
    assert "1 fact(s) checked, 0 drifted, 0 asserted nowhere." in out


@code("SA00275")
@category("repository")
@objective("functionality")
@negative
def test_drifted_figure_exits_14(fact, capsys):
    """A document stating a different number is reported as drifted, with the stated and
    measured values, and the run exits 14."""
    fact(lambda: 3, "We hold 4 widgets.\n")
    assert cf.main([]) == 14
    out = capsys.readouterr().out
    assert "DRIFTED       widgets in facts.md: says 4, actual 3" in out
    assert "1 drifted" in out


@code("SA00276")
@category("repository")
@objective("functionality")
@negative
def test_every_occurrence_is_checked(fact, capsys):
    """When the same figure appears twice and one copy is out of date, that copy is
    reported. A correct first copy does not hide it."""
    fact(lambda: 3, "We hold 3 widgets. Elsewhere: 5 widgets.\n")
    assert cf.main([]) == 14
    assert "says 5, actual 3" in capsys.readouterr().out


@code("SA00594")
@category("repository")
@objective("functionality")
@negative
def test_a_figure_stated_nowhere_exits_65(fact, capsys):
    """A recorded figure that no document states makes the run exit 65, and the report
    names the fact, its measured value and the fix."""
    fact(lambda: 3, "Nothing about them here.\n")
    assert cf.main([]) == 65
    out = capsys.readouterr().out
    assert "NOT ASSERTED  widgets: measured 3, no document states it" in out
    assert "fix -> state the figure again where the project reasons from it" in out


@code("SA00595")
@category("repository")
@objective("functionality")
@negative
def test_a_drifted_figure_outranks_one_stated_nowhere(fact, monkeypatch, capsys):
    """When one figure has drifted and another is stated in no document, the run exits
    14, and the report still names both."""
    fact(lambda: 3, "We hold 4 widgets.\n")
    monkeypatch.setattr(
        cf,
        "FACTS",
        [
            ("widgets", lambda: 3, r"(\d+) widgets"),
            ("gadgets", lambda: 2, r"(\d+) gadgets"),
        ],
    )
    assert cf.main([]) == 14
    out = capsys.readouterr().out
    assert "DRIFTED       widgets in facts.md: says 4, actual 3" in out
    assert "NOT ASSERTED  gadgets: measured 2, no document states it" in out


@code("SA00278")
@category("repository")
@objective("functionality")
@positive
def test_number_written_as_a_word_is_read(fact):
    """A small count written as a word ("three") matches the measured 3, so
    prose is not forced to use digits."""
    fact(
        lambda: 3, "We hold three widgets.\n", pattern=r"(?:(\d+)|(?i:(three))) widgets"
    )
    assert cf.main([]) == 0


@code("SA00279")
@category("repository")
@objective("functionality")
@positive
def test_a_date_is_compared_as_text(fact):
    """A measurement that gives a date passes when the document states the same date,
    and the run exits 0. A date is compared as text, like a count."""
    fact(
        lambda: "2026-07-14",
        "The folder is widgets_2026-07-14.\n",
        pattern=r"widgets_(\d{4}-\d{2}-\d{2})",
    )
    assert cf.main([]) == 0


@code("SA00280")
@category("repository")
@objective("functionality")
@negative
def test_a_drifted_date_exits_14(fact, capsys):
    """A document naming a different date from the measured one is reported as drifted
    with both dates, and the run exits 14. That is how a folder named for the wrong date
    is caught."""
    fact(
        lambda: "2026-07-14",
        "The folder is widgets_2026-07-21.\n",
        pattern=r"widgets_(\d{4}-\d{2}-\d{2})",
    )
    assert cf.main([]) == 14
    assert "says 2026-07-21, actual 2026-07-14" in capsys.readouterr().out


#######################################################################################
### When a measurement cannot be made, one exit code per cause ###


@code("SA00281")
@category("repository")
@objective("functionality")
@pytest.mark.parametrize(
    "raised, code, word",
    [
        (FileNotFoundError("gone.pdf"), 8, "NOT DOWNLOADED"),
        (PermissionError("locked by another program"), 13, "CANNOT READ"),
        (KeyError("studyDesigns"), 42, "UNEXPECTED SHAPE"),
        (json.JSONDecodeError("Expecting value", "", 0), 42, "UNEXPECTED SHAPE"),
        (AttributeError("'str' object has no attribute 'get'"), 42, "UNEXPECTED SHAPE"),
        (ManifestError("set_a.json: cannot read"), 3, "BAD MANIFEST"),
        (
            OutsideInputsError('set_a.json: entry x has local "inputs/../x"'),
            66,
            "BAD LOCATION",
        ),
        (
            UnrecordedFileError("cannot verify x: no manifest entry records it"),
            10,
            "UNRECORDED",
        ),
        (IntegrityError("x: sha256 differs; manifest says 0000"), 9, "MISMATCH"),
        (SpecShapeError("class 'X' is missing Modifier"), 4, "WRONG SHAPE"),
        (NotInRepoError("sdg is not running from inside its repo"), 6, "NOT IN REPO"),
    ],
    ids=[
        "not-downloaded-8",
        "cannot-read-13",
        "unexpected-shape-42",
        "malformed-json-42",
        "not-an-object-42",
        "bad-manifest-3",
        "outside-inputs-66",
        "unrecorded-10",
        "mismatch-9",
        "wrong-shape-4",
        "not-in-repo-6",
    ],
)
@negative
def test_each_measurement_failure_has_its_own_exit_code(
    fact, capsys, raised, code, word
):
    """A measurement that fails is reported under a label naming the cause, with the
    error's own message. The run exits with that cause's number from
    docs/exit_codes.csv. It runs once for each cause."""

    def measure():
        """Raise the staged error in place of measuring."""
        raise raised

    fact(measure, "We hold 3 widgets.\n")
    assert cf.main([]) == code
    out = capsys.readouterr().out
    assert f"{word}" in out and str(raised) in out


#######################################################################################
### Which documents are read ###
#
# Every Markdown file git tracks is read, apart from the excluded ones. These checks
# stage a git repository whose only fact counts 3 widgets.


@code("SA00596")
@category("repository")
@objective("functionality")
@positive
def test_a_tracked_document_in_any_folder_is_read(tracked, capsys):
    """A figure stated in a tracked Markdown file inside a nested folder is compared, so
    the run exits 0 rather than reporting the figure as stated nowhere."""
    tracked({"notes/deep/facts.md": "We hold 3 widgets.\n"})
    assert cf.main(["--verbose"]) == 0
    assert "ok            widgets in notes/deep/facts.md: 3" in capsys.readouterr().out


@code("SA00597")
@category("repository")
@objective("functionality")
@positive
def test_decisions_md_is_not_read(tracked):
    """A figure in DECISIONS.md is not compared, because that file records what was
    true on a past date, so a different figure there leaves the run at exit 0."""
    tracked(
        {"facts.md": "We hold 3 widgets.\n", "DECISIONS.md": "We held 2 widgets.\n"}
    )
    assert cf.main([]) == 0


@code("SA00598")
@category("repository")
@objective("functionality")
@positive
def test_an_untracked_document_is_not_read(tracked):
    """A Markdown file git does not track is not compared, so a different figure in it
    leaves the run at exit 0."""
    tracked(
        {"facts.md": "We hold 3 widgets.\n", "scratch.md": "We hold 5 widgets.\n"},
        untracked=("scratch.md",),
    )
    assert cf.main([]) == 0


@code("SA00599")
@category("repository")
@objective("functionality")
@negative
def test_git_that_cannot_be_run_exits_22(tracked, monkeypatch, capsys):
    """When git cannot be run, the run exits 22 before any measurement, and the report
    says git could not be run and to install it."""
    tracked({"facts.md": "We hold 3 widgets.\n"})
    monkeypatch.setattr(cf, "GIT", "git-that-does-not-exist")
    assert cf.main([]) == 22
    out = capsys.readouterr().out
    assert "git could not be run" in out
    assert "fix -> install git" in out


@code("SA00641")
@category("repository")
@objective("functionality")
@negative
def test_git_that_does_not_answer_exits_22(tracked, monkeypatch, capsys):
    """When git runs but refuses to list the tracked files, as it does outside a
    repository, the run exits 22 before any measurement, and the report says git did
    not answer and to run check_facts from inside the repo's clone.

    git is pointed at a repository folder that does not exist, which makes it stop
    with an error instead of listing files."""
    tracked({"facts.md": "We hold 3 widgets.\n"})
    monkeypatch.setenv("GIT_DIR", str(cf.REPO_ROOT / "no_such_repository"))
    assert cf.main([]) == 22
    out = capsys.readouterr().out
    assert "git did not answer" in out
    assert "run check_facts from inside the repo's clone" in out


@code("SA00642")
@category("repository")
@objective("functionality")
@positive
def test_a_tracked_document_deleted_from_the_folder_is_passed_over(tracked, capsys):
    """A tracked Markdown file that has been deleted from the working folder, but whose
    deletion is not yet committed, states nothing, so the run compares the documents
    still there and exits 0."""
    tracked({"facts.md": "We hold 3 widgets.\n", "gone.md": "We hold 3 widgets.\n"})
    (cf.REPO_ROOT / "gone.md").unlink()
    assert cf.main([]) == 0


#######################################################################################
### Which file a measurement reads ###


def write_concepts(path, *package_dates):
    """Write a concepts workbook with one package row for each date given.

    Args:
        path: Where the workbook is written. Parent folders are created.
        *package_dates: The date each package row carries, None for an empty cell.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Biomedical Concepts"
    sheet.append(["package_date"])
    for package_date in package_dates:
        sheet.append([package_date])
    workbook.save(path)


@code("SA00607")
@category("repository")
@objective("functionality")
@positive
def test_the_concepts_date_is_read_from_the_file_its_manifest_names(fake_repo):
    """The newest package date is read from the file whose manifest entry carries the
    concepts export's name, wherever that entry says the file lives, so check_facts
    writes no location of its own.

    The one entry places the export in a folder no pinned version has used, so a
    location written into check_facts would miss it."""
    local = "inputs/standards/cdisc/biomedical_concepts_2027-01-01/concepts.xlsx"
    write_concepts(fake_repo.root / local, "2027-01-01")
    fake_repo.manifest("concepts", [fake_repo.entry(local, name=cf.CONCEPTS_NAME)])
    assert cf.concepts_newest_package_date() == "2027-01-01"


@code("SA00626")
@category("repository")
@objective("functionality")
@positive
def test_an_example_folder_with_no_usdm_export_is_passed_over(fake_repo, monkeypatch):
    """A worked-example folder that holds no USDM export is passed over, and the
    studies in the other folders are still counted.

    One folder holds a recorded export that defines an estimand, and another holds
    only a PDF, so the count is 1."""
    examples = fake_repo.root / "inputs" / "worked_examples"
    monkeypatch.setattr(cf, "EXAMPLES", examples)
    study = {"study": {"versions": [{"studyDesigns": [{"estimands": [{"id": "E1"}]}]}]}}
    local = "inputs/worked_examples/with_export/study.json"
    fake_repo.file(local, json.dumps(study).encode("utf-8"))
    fake_repo.file("inputs/worked_examples/no_export/protocol.pdf", b"%PDF-1.7\n")
    fake_repo.manifest("examples", [fake_repo.entry(local)])
    assert cf.examples_with_estimands() == 1


@code("SA00627")
@category("repository")
@objective("functionality")
@negative
def test_no_entry_named_for_the_concepts_export_is_refused(fake_repo):
    """When no manifest entry carries the concepts export's name, as after the record
    was renamed, the date is not measured, and the error names the file name that was
    looked for."""
    local = "inputs/standards/cdisc/biomedical_concepts_2027-01-01/renamed.xlsx"
    write_concepts(fake_repo.root / local, "2027-01-01")
    fake_repo.manifest("concepts", [fake_repo.entry(local, name="renamed.xlsx")])
    with pytest.raises(
        ManifestError, match=f"no manifest entry is named {cf.CONCEPTS_NAME}"
    ):
        cf.concepts_newest_package_date()


@code("SA00628")
@category("repository")
@objective("functionality")
@positive
def test_an_empty_date_cell_is_passed_over(fake_repo):
    """A package row whose date cell is empty is passed over, and the newest date is
    taken from the rows that carry one."""
    local = "inputs/standards/cdisc/biomedical_concepts_2027-01-01/concepts.xlsx"
    write_concepts(fake_repo.root / local, "2027-01-01", None)
    fake_repo.manifest("concepts", [fake_repo.entry(local, name=cf.CONCEPTS_NAME)])
    assert cf.concepts_newest_package_date() == "2027-01-01"
