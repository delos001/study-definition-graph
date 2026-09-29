"""
Script:      test_console_output_technical.py
Description: Checks for src/sdg/console_output.py, the one function every command
             calls before its first print so that characters from the pinned
             standards come out intact on Windows. The function switches standard
             output to UTF-8 when it is Python's real text-file class, and does
             nothing when it is something else, which is what standard output
             becomes when another program has captured it.

             Each check stands in its own object for standard output and puts the
             real one back afterwards, so nothing the run itself prints is
             affected.

Inputs:      Nothing real.

Outputs:     Writes nothing to disk.

Usage:       pytest validation/sdg/test_console_output_technical.py
                 run these checks
             pytest validation/sdg/test_console_output_technical.py -v
                 one line per check with its result

Exit codes:  None of its own. It runs inside pytest.

Date:        2026-09-16
Owner:       Jason Delosh
"""

from __future__ import annotations

import io
import sys

from sdg.console_output import use_utf8_output
from sdgval.labels import category, code, objective, positive

#######################################################################################
### Positive checks ###
#
# The right thing works: a real text stream is switched to UTF-8, and anything else
# is left as it is without an error.


@code("SA00239")
@category("repository")
@objective("functionality")
@positive
def test_a_real_text_stream_is_switched_to_utf8(monkeypatch):
    """When standard output is a normal text stream, it is switched to UTF-8 for the
    rest of the run."""
    stream = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
    monkeypatch.setattr(sys, "stdout", stream)
    use_utf8_output()
    assert stream.encoding == "utf-8"


@code("SA00240")
@category("repository")
@objective("functionality")
@positive
def test_a_captured_stream_is_left_alone_without_error(monkeypatch):
    """When standard output is not a normal text stream, as when another program has
    captured it, it is left as it was and no error is raised."""
    stream = io.StringIO()
    monkeypatch.setattr(sys, "stdout", stream)
    use_utf8_output()
    assert sys.stdout is stream
