"""
Script:      console_output.py
Description: Makes the console print text as UTF-8, so characters from the
             pinned standards come out intact on Windows. The standards use
             bullets, em dashes, arrows and curly quotes where they carry
             meaning, and the Windows console defaults to an older character
             set that turns those into question marks. Any script that prints
             standard text calls this once, before its first print.

Inputs:      None.

Outputs:     Nothing on disk. Changes the encoding of the running program's
             standard output.

Usage:       Not run directly; imported.
             from sdg.console_output import use_utf8_output
                use_utf8_output()   at the top of main()

Exit codes:  None. Not run on its own, and it never raises.

Date:        2026-09-11
Owner:       Jason Delosh
"""

from __future__ import annotations

import io
import sys

################################################################################
### Set the output encoding ###


def use_utf8_output() -> None:
    """Switch standard output to UTF-8 for the rest of the run.

    The switch exists only on Python's real text-file class. Under pytest, or
    when output is redirected by another program, standard output can be a
    different object with no such switch, and then there is nothing to change
    and nothing to fix, so the call is skipped rather than failing.
    """
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")
