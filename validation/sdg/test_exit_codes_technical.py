"""
Script:      test_exit_codes_technical.py
Description: Checks for src/sdg/exit_codes.py, the file every command reports a
             failure through. It words the exit line from a group of failure
             and a sub-code, and fail() and finish() print through the function
             a command hands them and give back the exit number.

             Each check hands the file a list to print into, so what would be
             printed can be read back line by line.

Inputs:      Nothing real.

Outputs:     Writes nothing to disk.

Usage:       pytest validation/sdg/test_exit_codes_technical.py
                 run these checks
             pytest validation/sdg/test_exit_codes_technical.py -v
                 one line per check with its result

Exit codes:  None of its own. It runs inside pytest.

Date:        2026-09-29
Owner:       Jason Delosh
"""

from __future__ import annotations

from sdg.exit_codes import exit_line, fail, finish
from sdgval.labels import category, code, objective, positive

#######################################################################################
### Positive checks ###
#
# The right thing works: the exit line names the number, its group and the
# sub-code, one failure prints its problem line then the exit line, and the end of a
# run with several problems prints the exit line alone.


@code("SA00658")
@category("repository")
@objective("functionality")
@positive
def test_the_exit_line_names_the_number_its_group_and_the_sub_code():
    """The exit line names the exit number, the group that number stands for, and the
    sub-code, in that order."""
    assert (
        exit_line(9, "NEO4J-UNREACHABLE")
        == "Exit 9: a service did not respond (NEO4J-UNREACHABLE)"
    )


@code("SA00659")
@category("repository")
@objective("functionality")
@positive
def test_one_failure_prints_its_problem_then_the_exit_line():
    """Reporting one failure prints the message with its sub-code in front, then the
    exit line, and gives back the exit number."""
    printed: list[str] = []
    number = fail(printed.append, 9, "NEO4J-UNREACHABLE", "Neo4j could not be reached")
    assert printed == [
        "NEO4J-UNREACHABLE  Neo4j could not be reached",
        "Exit 9: a service did not respond (NEO4J-UNREACHABLE)",
    ]
    assert number == 9


@code("SA00660")
@category("repository")
@objective("functionality")
@positive
def test_the_end_of_a_run_prints_the_exit_line_alone():
    """Ending a run that has already printed its problems prints the exit line alone,
    and gives back the exit number."""
    printed: list[str] = []
    number = finish(printed.append, 16, "FIGURE-DRIFTED")
    assert printed == [
        "Exit 16: a description does not match the thing it describes (FIGURE-DRIFTED)"
    ]
    assert number == 16
