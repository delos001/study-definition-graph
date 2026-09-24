"""
Script:      test_console_output_operation.py
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

Usage:       pytest validation/sdg/test_console_output_operation.py
                 run these checks
             pytest validation/sdg/test_console_output_operation.py -v
                 one line per check with its result

Exit codes:  pytest's own: 0 all passed, 1 some failed

Date:        2026-09-16
Owner:       Jason Delosh
"""

from __future__ import annotations

import io
import sys

import pytest

from sdg.console_output import use_utf8_output

positive = pytest.mark.positive
negative = pytest.mark.negative
# Every check carries a @code line: its short, permanent id in
# validation/validation_inventory.csv, assigned once and never reused.
code = pytest.mark.code
# Every check carries an @objective line: what the check confirms about its category,
# one of the objectives validation/validation_inventory_dictionary.md defines.
objective = pytest.mark.objective
# Every check carries a @category line: what kind of thing the check confirms, one
# of the categories validation/validation_inventory_dictionary.md defines.
category = pytest.mark.category


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
    """When standard output is Python's real text-file class, use_utf8_output()
    switches its encoding to UTF-8 for the rest of the run."""
    stream = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
    monkeypatch.setattr(sys, "stdout", stream)
    use_utf8_output()
    assert stream.encoding == "utf-8"


@code("SA00240")
@category("repository")
@objective("functionality")
@positive
def test_a_captured_stream_is_left_alone_without_error(monkeypatch):
    """When standard output is not Python's real text-file class, as when another
    program has captured it, use_utf8_output() returns without an error and leaves
    the stream as it was."""
    stream = io.StringIO()
    monkeypatch.setattr(sys, "stdout", stream)
    use_utf8_output()
    assert sys.stdout is stream
