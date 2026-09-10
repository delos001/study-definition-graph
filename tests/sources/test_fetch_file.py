"""
Script:      test_fetch_file.py
Description: Automated checks for src/sdg/sources/fetch_file.py, the step that
             downloads one file from one url to a temporary .part name. Each
             check proves one promise from that module's header: one fact about
             where a completed download lands or how the request is made, or
             one way a failed download is reported and cleaned up.

             No check touches the network. The one call the module makes to the
             HTTP library, httpx.stream, is replaced for the length of each check
             by a fake server that serves bytes, answers with an error, or breaks
             part way through, as that check needs.

Inputs:      none from the repo

Outputs:     Writes nothing to disk. Temporary files go to pytest's own folder.

Usage:       pytest tests/sources/test_fetch_file.py
                 run these checks
             pytest tests/sources/test_fetch_file.py -v
                 one line per check with its result

Exit codes:  pytest's own: 0 all passed, 1 some failed

Date:        2026-09-10
Owner:       Jason Delosh
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
from pathlib import Path

import httpx
import pytest

from sdg.sources import fetch_file
from sdg.sources.fetch_file import FetchError, fetch, partial_path

positive = pytest.mark.positive
negative = pytest.mark.negative
# Every check carries a @code line: its short, permanent id in
# tests/validation_inventory.csv, assigned once and never reused.
code = pytest.mark.code

# The url every check downloads from. Nothing is at it; the fake server below
# answers in its place.
URL = "https://example.invalid/file.pdf"

# The bytes the fake server sends, in two pieces, so a check can see that the
# pieces are joined in order and that a break between them is handled.
CHUNKS = (b"first part, ", b"second part\n")


#######################################################################################
### The fake server ###
#
# fetch() makes one call to the HTTP library, httpx.stream(...). It uses that
# call as a context manager that yields a response, asks the response to
# raise_for_status(), then reads it with iter_bytes(). The fake below stands in
# for that call. Each check tells it how to behave: serve these chunks, answer
# with an error, or break after so many chunks. It also records what fetch()
# asked for, so a check can look at the request.


class FakeResponse:
    """Stands in for the response that httpx.stream yields."""

    def __init__(self, chunks, status_error=None, break_after=None):
        """Keeps the chunks to serve, the status error to raise if any, and the
        chunk index at which to break if any."""
        self.chunks = chunks
        self.status_error = status_error
        self.break_after = break_after

    def raise_for_status(self):
        """Raises the staged status error, if there is one, the way httpx does
        when a server answers with an error status."""
        if self.status_error is not None:
            raise self.status_error

    def iter_bytes(self):
        """Hands out the chunks one at a time, and breaks part way through when
        the check staged that."""
        for index, chunk in enumerate(self.chunks):
            if self.break_after is not None and index == self.break_after:
                raise httpx.ReadError("connection reset by peer")
            yield chunk


def error_status() -> httpx.HTTPStatusError:
    """Builds the error httpx raises when a server answers 404 Not Found."""
    return httpx.HTTPStatusError(
        "404 Not Found",
        request=httpx.Request("GET", URL),
        response=httpx.Response(404),
    )


@pytest.fixture
def server(monkeypatch):
    """Gives a check a function for staging the fake server.

    Calling the function with a FakeResponse serves that response. Calling it
    with an exception makes the connection itself fail, before any response
    arrives. The function replaces httpx.stream for the length of the check and
    gives back a record that is filled in with the method, url and settings
    fetch() used when the call happens."""
    record = {}

    def stage(behavior):
        """Installs a fake httpx.stream that behaves as given and gives back the
        record of what fetch() asked for."""

        @contextlib.contextmanager
        def fake_stream(method, url, **settings):
            """Records the request, then fails the connection or yields the
            staged response."""
            record.update(method=method, url=url, **settings)
            if isinstance(behavior, Exception):
                raise behavior
            yield behavior

        monkeypatch.setattr(fetch_file.httpx, "stream", fake_stream)
        return record

    return stage


#######################################################################################
### Shared staging ###
#
# One fixture runs a download the server completes. One helper runs a download
# that fails in the way a check chooses. Each check then asserts one thing about
# what was left behind.


@dataclass(frozen=True)
class Completed:
    """What one completed call to fetch() left behind."""

    partial: Path  # the path fetch() handed back
    destination: Path  # the final name fetch() was given
    request: dict  # what fetch() asked the HTTP library for


@dataclass(frozen=True)
class Failed:
    """What one failed call to fetch() left behind."""

    message: str  # the FetchError's message
    destination: Path  # the final name fetch() was given


@pytest.fixture
def completed(tmp_path, server) -> Completed:
    """Runs one download that the fake server completes, to a destination
    several folders deep that does not exist yet."""
    request = server(FakeResponse(CHUNKS))
    destination = tmp_path / "inputs" / "standards" / "cdisc" / "file.pdf"
    partial = fetch(URL, destination)
    return Completed(partial, destination, request)


def attempt(server, tmp_path, behavior) -> Failed:
    """Stages the given server behaviour, tries one download, expects a
    FetchError, and gives back its message and the destination."""
    server(behavior)
    destination = tmp_path / "file.pdf"
    with pytest.raises(FetchError) as caught:
        fetch(URL, destination)
    return Failed(str(caught.value), destination)


#######################################################################################
### Positive checks ###
#
# A download the server completes lands where the header says, under the
# temporary name, and the request is made the way the header says.


@code("SRC0031")
@positive
def test_download_is_written_under_the_part_name(completed):
    """A completed download is written to <destination>.part, and that path is
    handed back."""
    assert completed.partial == completed.destination.with_name("file.pdf.part")
    assert completed.partial.is_file()


@code("SRC0032")
@positive
def test_download_holds_the_bytes_the_server_sent(completed):
    """The .part file holds exactly the bytes the server sent, in order."""
    assert completed.partial.read_bytes() == b"".join(CHUNKS)


@code("SRC0033")
@positive
def test_nothing_appears_under_the_final_name(completed):
    """A completed download does not create the final name; that is the place
    step's job."""
    assert not completed.destination.exists()


@code("SRC0034")
@positive
def test_missing_folders_are_created(completed):
    """The folders on the way to the destination are created when they do not
    exist."""
    assert completed.destination.parent.is_dir()


@code("SRC0035")
@positive
def test_leftover_part_file_is_replaced(tmp_path, server):
    """A .part file left by an earlier run is replaced by the new download, not
    added to."""
    server(FakeResponse(CHUNKS))
    destination = tmp_path / "file.pdf"
    leftover = partial_path(destination)
    leftover.write_bytes(b"old unfinished bytes, longer than the new download")

    fetch(URL, destination)

    assert leftover.read_bytes() == b"".join(CHUNKS)


@code("SRC0036")
@positive
def test_request_is_a_get_on_the_given_url(completed):
    """The request is a GET on the url fetch() was given."""
    assert completed.request["method"] == "GET"
    assert completed.request["url"] == URL


@code("SRC0037")
@positive
def test_request_asks_to_follow_redirects(completed):
    """The request asks the HTTP library to follow a redirect, so a file the
    server has moved is still found."""
    assert completed.request["follow_redirects"] is True


@code("SRC0038")
@positive
def test_request_carries_the_module_timeout(completed):
    """The request gives up after the number of seconds the module sets."""
    assert completed.request["timeout"] == fetch_file.TIMEOUT_SECONDS


@code("SRC0039")
@positive
def test_partial_path_adds_part_to_the_file_name():
    """partial_path() adds .part to the file name and keeps the folder."""
    assert partial_path(Path("a/b/c.pdf")) == Path("a/b/c.pdf.part")


#######################################################################################
### Negative checks ###
#
# Every way a download can fail ends the same way: one FetchError naming the url
# and the cause, and no .part file left on disk to be mistaken for a finished
# download.


@code("SRC0040")
@negative
def test_error_status_raises_fetch_error_naming_url_and_status(tmp_path, server):
    """A server that answers with an error status makes fetch() raise
    FetchError, and the message names the url and the status."""
    failed = attempt(server, tmp_path, FakeResponse(CHUNKS, status_error=error_status()))
    assert URL in failed.message
    assert "404" in failed.message


@code("SRC0041")
@negative
def test_error_status_leaves_no_part_file(tmp_path, server):
    """After an error status, no .part file is left on disk."""
    failed = attempt(server, tmp_path, FakeResponse(CHUNKS, status_error=error_status()))
    assert not partial_path(failed.destination).exists()


@code("SRC0042")
@negative
def test_unreachable_server_raises_fetch_error_naming_url_and_cause(tmp_path, server):
    """A connection that cannot be made makes fetch() raise FetchError, and the
    message names the url and the cause."""
    failed = attempt(server, tmp_path, httpx.ConnectError("name or service not known"))
    assert URL in failed.message
    assert "name or service not known" in failed.message


@code("SRC0043")
@negative
def test_unreachable_server_leaves_no_part_file(tmp_path, server):
    """After a failed connection, no .part file is left on disk."""
    failed = attempt(server, tmp_path, httpx.ConnectError("name or service not known"))
    assert not partial_path(failed.destination).exists()


@code("SRC0044")
@negative
def test_broken_transfer_raises_fetch_error_naming_the_cause(tmp_path, server):
    """A transfer that breaks after the first chunk makes fetch() raise
    FetchError, and the message names the cause."""
    failed = attempt(server, tmp_path, FakeResponse(CHUNKS, break_after=1))
    assert "connection reset" in failed.message


@code("SRC0045")
@negative
def test_broken_transfer_removes_the_half_written_part_file(tmp_path, server):
    """After a transfer breaks part way, the half-written .part file is
    removed, so it cannot be mistaken for a finished download."""
    failed = attempt(server, tmp_path, FakeResponse(CHUNKS, break_after=1))
    assert not partial_path(failed.destination).exists()
