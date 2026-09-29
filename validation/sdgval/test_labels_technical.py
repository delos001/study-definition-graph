"""
Script:      test_labels_technical.py
Description: Checks for src/sdgval/labels.py, the plugin that declares the labels a
             check may carry and reads them off a check.

             Each check writes a tiny check file with pytest's own pytester helper,
             collects it in this process, and reads the labels off what was
             collected, the way the selection options and the report writer do.

Inputs:      Nothing real. Each check file is written to pytest's own temporary
             folder.

Outputs:     Writes nothing to disk outside pytest's temporary folder.

Usage:       pytest validation/sdgval/test_labels_technical.py
                 run these checks
             pytest validation/sdgval/test_labels_technical.py -v
                 one line per check with its result

Exit codes:  None of its own. It runs inside pytest.

Date:        2026-09-26
Owner:       Jason Delosh
"""

from __future__ import annotations

from sdgval.labels import (
    aspect_of,
    case_of,
    category,
    category_of,
    code,
    code_of,
    fixtures_of,
    objective,
    objective_of,
    positive,
)

#######################################################################################
### Shared staging ###

# One check carrying every label, and one carrying none. The labels are written
# the way pytest spells them, because pytest confirms a label is declared when it
# meets that spelling.
LABELLED = """
    import pytest

    @pytest.mark.code("XYZ0501")
    @pytest.mark.category("sources")
    @pytest.mark.objective("stability")
    @pytest.mark.negative
    @pytest.mark.needs_pinned("inputs/set/a.txt")
    @pytest.mark.needs_fixture("one.yml", "two.yml")
    def test_labelled():
        pass

    def test_bare():
        pass
    """


# A check carrying the positive case. The check in LABELLED carries the negative case,
# and a check carries one case at most, so the positive case needs a check of its own.
POSITIVE_CHECK = """
    @pytest.mark.positive
    def test_positive():
        pass
    """


def collected(pytester) -> dict:
    """Write the labelled check file, collect it, and key what was collected by name.

    Args:
        pytester: pytest's helper for staging a check file.

    Returns:
        Each collected check, keyed by its function name.
    """
    return {item.name: item for item in pytester.getitems(LABELLED)}


#######################################################################################
### Positive checks ###
#
# The right thing works: each label is read off a check that carries it, a check
# with no labels reads as empty, and every label is declared to pytest.


@code("SA00508")
@category("repository")
@objective("functionality")
@positive
def test_each_label_is_read_off_a_check_that_carries_it(pytester):
    """Each label a check carries is read as written. That covers its id, its category,
    its objective, the aspect of that objective, its case and the fixtures it names."""
    item = collected(pytester)["test_labelled"]
    assert code_of(item) == "XYZ0501"
    assert category_of(item) == "sources"
    assert objective_of(item) == "stability"
    assert aspect_of(item) == "integrity"
    assert case_of(item) == "negative"
    assert fixtures_of(item) == ["one.yml", "two.yml"]


@code("SA00509")
@category("repository")
@objective("functionality")
@positive
def test_a_check_with_no_labels_reads_as_empty(pytester):
    """A check that carries no label reads as empty for every label, so a missing
    label shows as a blank rather than stopping the run."""
    item = collected(pytester)["test_bare"]
    assert code_of(item) == ""
    assert category_of(item) == ""
    assert objective_of(item) == ""
    assert aspect_of(item) == ""
    assert case_of(item) == ""
    assert fixtures_of(item) == []


@code("SA00510")
@category("repository")
@objective("functionality")
@positive
def test_every_label_is_declared_to_pytest(pytester):
    """A run that refuses any label pytest has not been told about still collects
    checks that carry every label between them, the positive and the negative case
    included, because each one is declared.

    pytest refuses an unknown label while it collects, so the run only collects,
    and the check is never set up."""
    pytester.makepyfile(LABELLED + POSITIVE_CHECK)
    result = pytester.runpytest("--strict-markers", "--collect-only")
    assert result.ret == 0
