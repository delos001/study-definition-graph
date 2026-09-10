"""
Script:      test_fetch_file.py
Description: Automated checks for src/sdg/sources/fetch_file.py, the step that
             downloads one file from one url to a temporary .part name. Each
             check stages one kind of server, calls fetch(), and compares what
             happened to what the module's header promises: the bytes under the
             .part name on success, and on failure a FetchError that names the
             url and the cause, with no half-written file left behind.

             No check touches the network. The one call the module makes to the
             HTTP library, httpx.stream, is replaced for the length of each check
             by a fake that serves bytes, answers with an error, or breaks part
             way through, as that check needs.

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
from pathlib import Path

import httpx
import pytest

from sdg.sources import fetch_file
from sdg.sources.fetch_file import FetchError, fetch, partial_path

positive = pytest.mark.positive
negative = pytest.mark.negative

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
### Positive checks ###
#
# A download the server completes lands where the header says, under the
# temporary name, and the request is made the way the header says.


@positive
def test_download_lands_under_the_part_name(tmp_path, server):
    """The bytes the server sends are written to <destination>.part, that path
    is handed back, and nothing appears under the final name."""
    server(FakeResponse(CHUNKS))
    destination = tmp_path / "inputs" / "file.pdf"

    partial = fetch(URL, destination)

    assert partial == destination.with_name("file.pdf.part")
    assert partial.read_bytes() == b"".join(CHUNKS)
    assert not destination.exists()


@positive
def test_destination_folders_are_created(tmp_path, server):
    """A destination several folders deep works on an empty repo, because the
    folders on the way are created."""
    server(FakeResponse(CHUNKS))
    destination = tmp_path / "inputs" / "standards" / "cdisc" / "usdm_v4" / "USDM-IG.pdf"

    partial = fetch(URL, destination)

    assert partial.is_file()
    assert partial.parent == destination.parent


@positive
def test_leftover_part_file_is_overwritten(tmp_path, server):
    """A .part file left by an earlier run is replaced by the new download, not
    added to, because a .part file is by definition unfinished."""
    server(FakeResponse(CHUNKS))
    destination = tmp_path / "file.pdf"
    leftover = partial_path(destination)
    leftover.write_bytes(b"old unfinished bytes, longer than the new download")

    fetch(URL, destination)

    assert leftover.read_bytes() == b"".join(CHUNKS)


@positive
def test_request_asks_to_follow_redirects_and_sets_the_timeout(tmp_path, server):
    """fetch() asks the HTTP library to follow a redirect and to give up after
    the module's timeout, which is how a file the server has moved is still
    found."""
    record = server(FakeResponse(CHUNKS))

    fetch(URL, tmp_path / "file.pdf")

    assert record["method"] == "GET"
    assert record["url"] == URL
    assert record["follow_redirects"] is True
    assert record["timeout"] == fetch_file.TIMEOUT_SECONDS


@positive
def test_partial_path_is_the_destination_plus_part():
    """partial_path() adds .part to the file name and keeps the folder, so the
    naming rule lives in one place."""
    assert partial_path(Path("a/b/c.pdf")) == Path("a/b/c.pdf.part")


#######################################################################################
### Negative checks ###
#
# Every way a download can fail ends the same way: one FetchError naming the url
# and the cause, and no .part file left on disk to be mistaken for a finished
# download.


@negative
def test_server_error_is_a_fetch_error(tmp_path, server):
    """A server that answers with an error status raises FetchError naming the
    url and the status, and leaves no .part file."""
    status_error = httpx.HTTPStatusError(
        "404 Not Found",
        request=httpx.Request("GET", URL),
        response=httpx.Response(404),
    )
    server(FakeResponse(CHUNKS, status_error=status_error))
    destination = tmp_path / "file.pdf"

    with pytest.raises(FetchError) as caught:
        fetch(URL, destination)

    message = str(caught.value)
    assert URL in message
    assert "404" in message
    assert not partial_path(destination).exists()


@negative
def test_unreachable_server_is_a_fetch_error(tmp_path, server):
    """A connection that cannot be made raises FetchError naming the url and the
    cause, and leaves no .part file."""
    server(httpx.ConnectError("name or service not known"))
    destination = tmp_path / "file.pdf"

    with pytest.raises(FetchError) as caught:
        fetch(URL, destination)

    message = str(caught.value)
    assert URL in message
    assert "name or service not known" in message
    assert not partial_path(destination).exists()


@negative
def test_transfer_that_stops_part_way_removes_the_part_file(tmp_path, server):
    """A transfer that breaks after the first chunk raises FetchError, and the
    half-written .part file is removed so it cannot be mistaken for a finished
    download."""
    server(FakeResponse(CHUNKS, break_after=1))
    destination = tmp_path / "file.pdf"

    with pytest.raises(FetchError) as caught:
        fetch(URL, destination)

    assert "connection reset" in str(caught.value)
    assert not partial_path(destination).exists()
