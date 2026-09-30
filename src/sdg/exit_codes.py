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
             row per sub-code with what happened and what to do. No command
             reads it to word what it prints. src/sdgtools/verify_headers.py
             is the one command that reads it, to confirm that the groups here
             match the groups in that table.

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

# Each exit number and the group of failure it names. Every sub-code in a group is
# in docs/exit_codes.csv. The comment above each group is its separating test, which
# places a new failure in exactly one group, so a failure is placed by answering the
# tests rather than by judgment. A new group is added only when no group's test fits,
# here and to the table in the same commit.
GROUPS: dict[int, str] = {
    # Nothing failed.
    0: "the command succeeded",
    # A fault in this repo's own code, whether nothing handled the error or the code
    # caught it, as when a check file errors while it loads.
    1: "this repo's own code failed",
    # What was typed is wrong, whatever the files, settings or folder hold.
    2: "the command line is wrong",
    # The same command, typed the same way, works once the folder changes, as by
    # moving into the repo or committing.
    3: "the working folder is not in the state the command needs",
    # .env does not exist, or has no line for the setting.
    4: "a setting is missing",
    # The setting is there, and the command can see it cannot be right before it
    # contacts anything.
    5: "a setting is invalid",
    # A program the command runs is not on the path, because it is not installed or
    # its environment is not active.
    6: "an outside program cannot be found",
    # The program was found, then errored or did not answer.
    7: "an outside program was found but failed to run",
    # The program answered, and its version is not the one the repo fixes.
    8: "an outside program is not the pinned version",
    # No answer came from a service reached over a connection, or none in time.
    9: "a service did not respond",
    # A service answered by refusing the login, key or permission it was given.
    10: "a service refused the login, key or permission",
    # A service answered with any other error, such as a missing page or a rate limit.
    11: "a service answered with an error",
    # Nothing is at the path.
    12: "a file does not exist",
    # The path exists and opening it fails.
    13: "a file exists but cannot be opened",
    # A file's content or a service's answer breaks the rules of its format, such as
    # JSON, YAML, TOML, Python or PDF.
    14: "content cannot be parsed",
    # The content parses, but a required part is missing or a value is not allowed,
    # found by looking at that content alone.
    15: "content breaks a requirement",
    # A record or document disagrees with the thing it describes, found only by
    # comparing the two.
    16: "a description does not match the thing it describes",
    # A name, number or pattern the person typed matched nothing.
    17: "the parameters given yielded no results",
    # The place the command looks exists, and nothing in it can be acted on.
    18: "the command found no target to act on",
    # The output is already there, and the command refuses on purpose to replace it.
    19: "an output already exists and is not overwritten",
    # Writing the output failed, as on a full disk.
    20: "an output could not be written",
    # A command whose job is to run the validation checks found one or more failing.
    21: "one or more validation checks failed",
    # A run scored against the answer keys in eval/ came in under its agreed
    # threshold.
    22: "an evaluation score fell below its threshold",
    # The run was stopped by a person before it finished.
    23: "the run was interrupted before it finished",
    # The fault is only in how two or more parts relate, such as files that import
    # each other. Each part is fine on its own, and none describes another.
    24: "a relationship breaks a rule",
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
