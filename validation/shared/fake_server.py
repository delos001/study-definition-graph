"""
Script:      fake_server.py
Description: A fake download server, for checks that download without reaching the
             network. It holds the url a staged download asks for, the bytes the
             fake server sends, the fake response, and the record of what one
             completed download left behind.

             fetch() makes one call to the HTTP library, httpx.stream(...). It uses
             that call in a with block that hands back a response, asks the
             response to raise_for_status(), then reads it with iter_bytes(). The
             fake response stands in for that. Each check tells it how to behave:
             serve these chunks, answer with an error, or break after so many
             chunks.

             The fixtures that install the fake server and run a completed
             download are in validation/conftest.py, because pytest finds a shared
             fixture only there.

Inputs:      Nothing on disk.

Outputs:     Nothing on disk.

Usage:       from validation.shared.fake_server import CHUNKS, URL, FakeResponse
                 use in a check, or in a fixture in validation/conftest.py

Exit codes:  None of its own. It is imported by the checks.

Date:        2026-09-24
Owner:       Jason Delosh
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import httpx

#######################################################################################
### The fake server ###

# The url every check downloads from. Nothing is at it; the fake server below
# answers in its place.
URL = "https://example.invalid/file.pdf"


# The bytes the fake server sends, in two pieces, so a check can see that the
# pieces are joined in order and that a break between them is handled.
CHUNKS = (b"first part, ", b"second part\n")


class FakeResponse:
    """Stands in for the response that httpx.stream yields."""

    def __init__(self, chunks, status_error=None, break_after=None):
        """Keep the chunks to serve, the status error to raise if any, and the chunk index
        at which to break if any.

        Args:
            chunks: The pieces of the body, served one at a time.
            status_error: The error to raise for an error status, or None for a good
                status.
            break_after: The number of chunks to serve before the connection breaks, or
                None to serve them all.
        """
        self.chunks = chunks
        self.status_error = status_error
        self.break_after = break_after

    def raise_for_status(self):
        """Raise the staged status error, if there is one, the way httpx does when a server
        answers with an error status.
        """
        if self.status_error is not None:
            raise self.status_error

    def iter_bytes(self):
        """Hand out the chunks one at a time, and break part way through when the check
        staged that.

        Yields:
            The body, one chunk at a time.

        Raises:
            httpx.ReadError: The staged break point was reached.
        """
        for index, chunk in enumerate(self.chunks):
            if self.break_after is not None and index == self.break_after:
                raise httpx.ReadError("connection reset by peer")
            yield chunk


@dataclass(frozen=True)
class Completed:
    """What one completed call to fetch() left behind."""

    partial: Path  # the path fetch() handed back
    destination: Path  # the final name fetch() was given
    request: dict  # what fetch() asked the HTTP library for
