"""
Script:      exit_codes.py
Description: Holds the groups of failure a command exits with, and prints the
             lines a command shows when it fails. Every command in the repo
             uses it, so a group is worded the same way everywhere.

             An exit number names a broad group of failure, such as "a service
             did not respond". A sub-code, a short name in capitals such as
             NEO4J-UNREACHABLE, names the failure itself. Each problem a command
             reports starts with its sub-code, and the last line names the exit
             number, its group and the sub-code that decided it.

             docs/exit_codes.csv is the reference a person reads. It holds one
             row per sub-code with what happened and what to do. Nothing reads
             it while a command runs. src/sdgtools/verify_headers.py confirms
             that the groups here match the groups in that table.

Inputs:      It reads nothing.

Outputs:     Nothing on disk. fail() and finish() print through the function
             they are handed and hand back the exit number.

Usage:       This file is not run directly; other code imports it.
             from sdg.exit_codes import fail, finish, problem_line
                return fail(say, 9, "NEO4J-UNREACHABLE", message)
                                    one failure, reported and ended in one call
                say(problem_line("HEADER-INCOMPLETE", message))
                return finish(say, 15, "HEADER-INCOMPLETE")
                                    several problems, then the exit line

Exit codes:  There are none. This file is not run on its own.

Date:        2026-09-29
Owner:       Jason Delosh
"""

from __future__ import annotations

from collections.abc import Callable

#######################################################################################
### The groups ###

# Each exit number and the group of failure it names. The separating test for each
# group, and every sub-code in it, are in docs/exit_codes.csv. A new group is added
# here and to that table in the same commit.
GROUPS: dict[int, str] = {
    0: "the command succeeded",
    1: "this repo's own code failed",
    2: "the command line is wrong",
    3: "the working folder is not in the state the command needs",
    4: "a setting is missing",
    5: "a setting is invalid",
    6: "an outside program cannot be found",
    7: "an outside program was found but failed to run",
    8: "an outside program is not the pinned version",
    9: "a service did not respond",
    10: "a service refused the login, key or permission",
    11: "a service answered with an error",
    12: "a file does not exist",
    13: "a file exists but cannot be opened",
    14: "content cannot be parsed",
    15: "content breaks a requirement",
    16: "a description does not match the thing it describes",
    17: "the parameters given yielded no results",
    18: "the command found no target to act on",
    19: "an output already exists and is not overwritten",
    20: "an output could not be written",
    21: "one or more validation checks failed",
    22: "an evaluation score fell below its threshold",
    23: "the run was interrupted before it finished",
}


#######################################################################################
### Printing a failure ###


def problem_line(sub_code: str, message: object) -> str:
    """Put a sub-code in front of a problem's message.

    Only the message's first line gets the sub-code. A message that goes on to a
    second line, such as a fix, keeps that line as it was written.

    Args:
        sub_code: The failure's sub-code, as docs/exit_codes.csv lists it.
        message: What went wrong, with the details known only at run time.

    Returns:
        The message with the sub-code and two spaces in front of it.
    """
    return f"{sub_code}  {message}"


def exit_line(code: int, sub_code: str) -> str:
    """Word the last line a failing command prints.

    Args:
        code: The exit number, one of the keys of GROUPS.
        sub_code: The sub-code of the failure that decided the number.

    Returns:
        The line, as in "Exit 9: a service did not respond (NEO4J-UNREACHABLE)".
    """
    return f"Exit {code}: {GROUPS[code]} ({sub_code})"


def fail(say: Callable[[str], None], code: int, sub_code: str, message: object) -> int:
    """Report one failure and end the command with its exit number.

    Args:
        say: What prints a line. A command passes a function that prints nothing
            under --quiet.
        code: The exit number, one of the keys of GROUPS.
        sub_code: The failure's sub-code, as docs/exit_codes.csv lists it.
        message: What went wrong, with the details known only at run time.

    Returns:
        The exit number, for main() to hand back.
    """
    say(problem_line(sub_code, message))
    return finish(say, code, sub_code)


def finish(say: Callable[[str], None], code: int, sub_code: str) -> int:
    """Print the exit line and end the command with its exit number.

    A command that reports several problems prints each with problem_line() as it
    finds it, and calls this once at the end, when it knows which problem decides
    the number.

    Args:
        say: What prints a line. A command passes a function that prints nothing
            under --quiet.
        code: The exit number, one of the keys of GROUPS.
        sub_code: The sub-code of the failure that decided the number.

    Returns:
        The exit number, for main() to hand back.
    """
    say(exit_line(code, sub_code))
    return code
