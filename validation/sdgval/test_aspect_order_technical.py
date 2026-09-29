"""
Script:      test_aspect_order_technical.py
Description: Checks for src/sdgval/aspect_order.py, the plugin that runs a run
             holding checks of more than one aspect of quality in stages,
             technical, then conformance, then integrity, and holds back a later
             stage when an earlier one did not come through clean.

             Each check writes a small suite of staged checks into pytest's own
             temporary folder, runs it as a separate pytest process, and reads
             what that run printed for each staged check.

Inputs:      Nothing real. Each staged suite is written to pytest's own temporary
             folder.

Outputs:     Writes nothing to disk outside pytest's temporary folder.

Usage:       pytest validation/sdgval/test_aspect_order_technical.py
                 run these checks
             pytest validation/sdgval/test_aspect_order_technical.py -v
                 one line per check with its result

Exit codes:  None of its own. It runs inside pytest.

Date:        2026-09-29
Owner:       Jason Delosh
"""

from __future__ import annotations

import re

import pytest

from sdgval import aspect_order
from sdgval.build_inventory import OBJECTIVES_BY_ASPECT
from sdgval.labels import category, code, negative, objective, positive

#######################################################################################
### Staging a suite ###
#
# A staged check is written with the labels a real check carries. Its objective says
# which aspect, and so which stage, it belongs to. The staged checks are written
# integrity first, so the order they run in shows whether the plugin sorted them.


def staged(name: str, check_id: str, goal: str, body: str = "pass") -> str:
    """Write one staged check.

    Args:
        name: The check's function name, without test_.
        check_id: Its id.
        goal: Its objective, which decides its aspect.
        body: The check's one line of code.

    Returns:
        The check's source.
    """
    return (
        f'@pytest.mark.code("{check_id}")\n'
        f'@pytest.mark.objective("{goal}")\n'
        f"def test_{name}():\n"
        f"    {body}\n\n\n"
    )


def run_suite(pytester: pytest.Pytester, *checks: str) -> pytest.RunResult:
    """Write the staged checks into one file and run them in a separate pytest process.

    Args:
        pytester: pytest's helper for running a separate process.
        *checks: The staged checks' sources.

    Returns:
        The result of the run, run with -v so each check's outcome is printed on a
            line of its own, and with -rs so each skip's reason is printed.
    """
    pytester.makepyfile(test_suite="import pytest\n\n\n" + "".join(checks))
    return pytester.runpytest_subprocess("-v", "-rs", "-p", "no:cacheprovider")


def outcome_lines(result: pytest.RunResult) -> list[str]:
    """List the lines a -v run printed for each staged check, in the order they ran.

    Args:
        result: The result of the run.

    Returns:
        Each check's name and outcome, such as "test_tech PASSED".
    """
    found = []
    for line in result.stdout.lines:
        match = OUTCOME_LINE.match(line)
        if match:
            found.append(f"{match.group(1)} {match.group(2)}")
    return found


# A line -v prints for one check, as in "test_suite.py::test_tech PASSED   [ 33%]".
# The summary pytest prints at the end names checks differently, so it never matches.
OUTCOME_LINE = re.compile(r"^test_suite\.py::(\S+) (PASSED|FAILED|SKIPPED|ERROR)\b")


INTEGRITY = staged("integ", "XYZ0301", "correctness")
CONFORMANCE = staged("conform", "XYZ0201", "conformance")
TECHNICAL = staged("tech", "XYZ0101", "functionality")
FAILING_TECHNICAL = staged("tech", "XYZ0101", "functionality", "assert False")


#######################################################################################
### Positive checks ###
#
# The right thing works: a mixed run is sorted into its stages, a stage runs in full,
# a check switched off in the inventory holds nothing back, and every aspect has a
# stage.


@code("SA00661")
@category("repository")
@objective("functionality")
@positive
def test_a_mixed_run_runs_technical_then_conformance_then_integrity(pytester):
    """A run holding checks of all three aspects runs the technical checks first, then
    the conformance checks, then the integrity checks, whatever order they were
    written in."""
    result = run_suite(pytester, INTEGRITY, CONFORMANCE, TECHNICAL)
    assert outcome_lines(result) == [
        "test_tech PASSED",
        "test_conform PASSED",
        "test_integ PASSED",
    ]


@code("SA00662")
@category("repository")
@objective("functionality")
@positive
def test_a_stage_runs_in_full_after_one_of_its_checks_fails(pytester):
    """A failed check does not stop the rest of its own stage, so every failure in that
    stage is shown."""
    second = staged("tech_two", "XYZ0102", "functionality")
    result = run_suite(pytester, FAILING_TECHNICAL, second)
    assert outcome_lines(result) == ["test_tech FAILED", "test_tech_two PASSED"]


@code("SA00663")
@category("repository")
@objective("functionality")
@positive
@pytest.mark.parametrize("status", ["pending", "inactive"])
def test_a_check_switched_off_holds_nothing_back(pytester, status):
    """A technical check the inventory marks pending or inactive is skipped, and the
    conformance and integrity checks after it still run. It runs once for each of the
    two statuses."""
    inventory = pytester.path / "validation" / "validation_inventory.csv"
    inventory.parent.mkdir()
    inventory.write_text(
        f"id,status,status_reason\nXYZ0101,{status},Switched off on purpose.\n",
        encoding="utf-8",
    )
    result = run_suite(pytester, INTEGRITY, CONFORMANCE, FAILING_TECHNICAL)
    assert outcome_lines(result) == [
        "test_tech SKIPPED",
        "test_conform PASSED",
        "test_integ PASSED",
    ]


@code("SA00664")
@category("repository")
@objective("functionality")
def test_every_aspect_has_a_stage():
    """Every aspect of quality the inventory knows has a stage in the plugin, so no
    aspect's checks are left out of a mixed run."""
    assert set(aspect_order.STAGES) == set(OBJECTIVES_BY_ASPECT)


#######################################################################################
### Negative checks ###
#
# Each staged suite breaks its technical stage in one way. The checks of the later
# stages are then skipped, with a reason naming the stage and the check that stopped
# it.


@code("SA00665")
@category("repository")
@objective("functionality")
@negative
@pytest.mark.parametrize(
    ("body", "stopped"),
    [
        ("assert False", "test_tech failed"),
        ('pytest.skip("not downloaded: inputs/x.pdf")', "test_tech was skipped"),
    ],
    ids=["a failed check", "a skipped active check"],
)
def test_a_technical_stage_that_did_not_pass_holds_back_the_later_stages(
    pytester, body, stopped
):
    """When an active technical check fails, or is skipped, the conformance and
    integrity checks are skipped, and the reason names the technical stage and the
    check that stopped it. It runs once for a failed check and once for a skipped
    one."""
    technical = staged("tech", "XYZ0101", "functionality", body)
    result = run_suite(pytester, INTEGRITY, CONFORMANCE, technical)
    lines = outcome_lines(result)
    assert lines[1:] == ["test_conform SKIPPED", "test_integ SKIPPED"]
    printed = result.stdout.str()
    assert "held back: the technical stage did not pass, because" in printed
    assert stopped in printed


@code("SA00666")
@category("repository")
@objective("functionality")
@negative
def test_a_broken_set_up_holds_back_the_later_stages(pytester):
    """When an active technical check's set-up breaks, the conformance and integrity
    checks are skipped, and the reason says the check broke in its set-up."""
    broken = (
        "@pytest.fixture\n"
        "def broken():\n"
        '    raise RuntimeError("set-up broke")\n\n\n'
        '@pytest.mark.code("XYZ0101")\n'
        '@pytest.mark.objective("functionality")\n'
        "def test_tech(broken):\n"
        "    pass\n\n\n"
    )
    result = run_suite(pytester, INTEGRITY, CONFORMANCE, broken)
    assert outcome_lines(result)[1:] == ["test_conform SKIPPED", "test_integ SKIPPED"]
    assert "test_tech broke in its setup" in result.stdout.str()
