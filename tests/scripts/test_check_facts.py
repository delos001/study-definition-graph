"""
Script:      test_check_facts.py
Description: Automated checks for scripts/check_facts.py, the hand-run check
             that every count stated in the project's documents can be
             re-derived from the pinned files. The script is a list of
             measurements and a loop that compares each to what the documents
             say; the checks here replace that list with one small fake fact
             (a measurement that returns, or raises, whatever the check needs)
             and a one-line document in a temporary folder, then assert the
             report and the exit code. One check runs the real thing against
             the real corpus and skips when data/ is not downloaded.

Inputs:      data/raw/**  (read-only; the one real-corpus check only, skips if absent)

Outputs:     Writes nothing to disk. Temporary files go to pytest's own folder.

Usage:       pytest tests/test_check_facts.py
                 run these checks
             pytest tests/test_check_facts.py -v
                 one line per check with its result

Exit codes:  pytest's own: 0 all passed, 1 some failed

Date:        2026-09-04
Owner:       Jason Delosh
"""

from __future__ import annotations

import pytest

import check_facts as cf
from sdg.pinned import IntegrityError, NotInRepoError
from sdg.usdm_spec import PINNED_LOCAL, SpecShapeError

positive = pytest.mark.positive
negative = pytest.mark.negative

needs_pinned_file = pytest.mark.skipif(
    not (cf.REPO_ROOT / PINNED_LOCAL).exists(),
    reason="pinned corpus not downloaded; run scripts/fetch_sources.py",
)


#######################################################################################
### Helpers ###


@pytest.fixture
def fact(tmp_path, monkeypatch):
    """Produces a function that takes a measurement (a callable), the text of
    one document, and optionally the regex that finds the figure, and installs
    them as the script's only fact and only document; the check then calls
    main()."""
    monkeypatch.setattr(cf, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(cf, "DOCS", ["facts.md"])

    def install(measure, doc_text: str, pattern: str = r"(\d+) widgets") -> None:
        (tmp_path / "facts.md").write_text(doc_text, encoding="utf-8")
        monkeypatch.setattr(cf, "FACTS", [("widgets", measure, pattern)])

    return install


#######################################################################################
### Comparing a figure to the documents ###


@positive
def test_matching_figure_exits_0(fact, capsys):
    """A document stating the measured number passes: exit 0, and --verbose
    shows the 'ok' line naming the fact, the file and the value."""
    fact(lambda: 3, "We hold 3 widgets.\n")
    assert cf.main(["--verbose"]) == 0
    out = capsys.readouterr().out
    assert "ok            widgets in facts.md: 3" in out
    assert "1 fact(s) checked, 0 drifted, 0 asserted nowhere." in out


@negative
def test_drifted_figure_exits_1(fact, capsys):
    """A document stating a different number is reported DRIFTED with the
    stated and measured values, exit 1."""
    fact(lambda: 3, "We hold 4 widgets.\n")
    assert cf.main([]) == 1
    out = capsys.readouterr().out
    assert "DRIFTED       widgets in facts.md: says 4, actual 3" in out
    assert "1 drifted" in out


@negative
def test_every_occurrence_is_checked(fact, capsys):
    """When the same figure appears twice and one copy is stale, the stale one
    is reported; a correct first copy does not hide it."""
    fact(lambda: 3, "We hold 3 widgets. Elsewhere: 5 widgets.\n")
    assert cf.main([]) == 1
    assert "says 5, actual 3" in capsys.readouterr().out


@positive
def test_unasserted_fact_is_reported_but_passes(fact, capsys):
    """A fact no document states is reported NOT ASSERTED with its measured
    value but does not fail the run (exit 0): the documents are not wrong,
    the script is just tracking something they do not claim."""
    fact(lambda: 3, "Nothing about them here.\n")
    assert cf.main([]) == 0
    out = capsys.readouterr().out
    assert "NOT ASSERTED  widgets: measured 3, no document states it" in out
    assert "1 asserted nowhere" in out


@positive
def test_number_written_as_a_word_is_read(fact):
    """A small count written as a word ("three") matches the measured 3, so
    prose is not forced to use digits."""
    fact(lambda: 3, "We hold three widgets.\n", pattern=r"(?:(\d+)|(?i:(three))) widgets")
    assert cf.main([]) == 0


#######################################################################################
### When a measurement cannot be made, one exit code per cause ###


@pytest.mark.parametrize(
    "raised, code, word",
    [
        (FileNotFoundError("gone.pdf"), 2, "UNMEASURABLE"),
        (IntegrityError("cannot verify x: no manifest entry records it"), 3, "UNVERIFIED"),
        (SpecShapeError("class 'X' is missing Modifier"), 4, "WRONG SHAPE"),
        (NotInRepoError("sdg is not running from inside its repo"), 6, "NOT IN REPO"),
    ],
    ids=["missing-2", "unverified-3", "wrong-shape-4", "not-in-repo-6"],
)
@negative
def test_each_measurement_failure_has_its_own_exit_code(fact, capsys, raised, code, word):
    """A measurement that raises is reported under a label naming the cause,
    with the exception's own message, and the run exits with that cause's
    code: 2 file missing, 3 cannot be verified, 4 wrong shape, 6 not in repo."""

    def measure():
        raise raised

    fact(measure, "We hold 3 widgets.\n")
    assert cf.main([]) == code
    out = capsys.readouterr().out
    assert f"{word}" in out and str(raised) in out


@negative
def test_package_not_installed_exits_7_before_measuring(fact, monkeypatch, capsys):
    """When the sdg package could not be imported, the run exits 7 with the
    install command before any measurement runs."""

    def measure():
        raise AssertionError("must not be called")

    fact(measure, "We hold 3 widgets.\n")
    monkeypatch.setattr(cf, "SDG_MISSING", ImportError("No module named 'sdg'"))
    assert cf.main([]) == 7
    out = capsys.readouterr().out
    assert "the sdg package is not installed" in out and "pip install -e ." in out


#######################################################################################
### The real corpus ###


@needs_pinned_file
@positive
def test_real_documents_match_real_corpus():
    """Against the pinned corpus and the committed documents, every stated
    figure re-derives: exit 0. This is the same run README.md asks for after
    setup, and it proves every pinned file the script reads still verifies."""
    assert cf.main([]) == 0
