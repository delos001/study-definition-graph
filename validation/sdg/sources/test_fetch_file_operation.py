"""
Script:      test_fetch_file_operation.py
Description: Automated checks for src/sdg/sources/fetch_file.py, the step that
             downloads one file from one url to a temporary .part name. Each
             check proves one promise from that module's header: one fact about
             where a completed download lands or how the request is made, or
             one way a failed download is reported and cleaned up.

             No check touches the network. The one call the module makes to the
             Hypertext Transfer Protocol (HTTP) library, httpx.stream, is replaced for the length of each check
             by a fake server that serves bytes, answers with an error, or breaks
             part way through, as that check needs.

Inputs:      none from the repo

Outputs:     Writes nothing to disk. Temporary files go to pytest's own folder.

Usage:       pytest validation/sdg/sources/test_fetch_file_operation.py
                 run these checks
             pytest validation/sdg/sources/test_fetch_file_operation.py -v
                 one line per check with its result

Exit codes:  pytest's own: 0 all passed, 1 some failed

Date:        2026-09-10
Owner:       Jason Delosh
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import httpx
import pytest
from validation.shared.fake_server import CHUNKS, URL, FakeResponse

from sdg.sources import fetch_file
from sdg.sources.fetch_file import FetchError, fetch, partial_path

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
### The fake server ###
#
# fetch() makes one call to the HTTP library, httpx.stream(...). It uses that
# call in a with block that hands back a response, asks the response to
# raise_for_status(), then reads it with iter_bytes(). The fake below stands in
# for that call. Each check tells it how to behave: serve these chunks, answer
# with an error, or break after so many chunks. It also records what fetch()
# asked for, so a check can look at the request.


def error_status() -> httpx.HTTPStatusError:
    """Build the error httpx raises when a server answers 404 Not Found.

    Returns:
        The error, ready to be raised by the fake response.
    """
    return httpx.HTTPStatusError(
        "404 Not Found",
        request=httpx.Request("GET", URL),
        response=httpx.Response(404),
    )


#######################################################################################
### Shared staging ###
#
# One fixture runs a download the server completes. One helper runs a download
# that fails in the way a check chooses. Each check then asserts one thing about
# what was left behind.


@dataclass(frozen=True)
class Failed:
    """What one failed call to fetch() left behind."""

    message: str  # the FetchError's message
    destination: Path  # the final name fetch() was given


def attempt(server, tmp_path, behavior) -> Failed:
    """Stage the given server behaviour, try one download, and expect it to fail.

    Args:
        server: The function that stages the fake server.
        tmp_path: pytest's temporary folder, where the destination is placed.
        behavior: What the fake server does, a FakeResponse or an error.

    Returns:
        The FetchError's message and the destination, as a Failed.
    """
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


@code("SA00034")
@category("repository")
@objective("functionality")
@positive
def test_download_is_written_under_the_part_name(completed):
    """A completed download is written to <destination>.part, and that path is
    handed back."""
    assert completed.partial == completed.destination.with_name("file.pdf.part")
    assert completed.partial.is_file()


@code("SA00036")
@category("repository")
@objective("functionality")
@positive
def test_nothing_appears_under_the_final_name(completed):
    """A completed download does not create the final name; that is the place
    step's job."""
    assert not completed.destination.exists()


@code("SA00037")
@category("repository")
@objective("functionality")
@positive
def test_missing_folders_are_created(completed):
    """The folders on the way to the destination are created when they do not
    exist."""
    assert completed.destination.parent.is_dir()


@code("SA00038")
@category("repository")
@objective("functionality")
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


@code("SA00039")
@category("repository")
@objective("functionality")
@positive
def test_request_is_a_get_on_the_given_url(completed):
    """The request is a GET on the url fetch() was given."""
    assert completed.request["method"] == "GET"
    assert completed.request["url"] == URL


@code("SA00040")
@category("repository")
@objective("functionality")
@positive
def test_request_asks_to_follow_redirects(completed):
    """The request asks the HTTP library to follow a redirect, so a file the
    server has moved is still found."""
    assert completed.request["follow_redirects"] is True


@code("SA00041")
@category("repository")
@objective("functionality")
@positive
def test_request_carries_the_module_timeout(completed):
    """The request gives up after the number of seconds fetch_file.py sets."""
    assert completed.request["timeout"] == fetch_file.TIMEOUT_SECONDS


@code("SA00042")
@category("repository")
@objective("functionality")
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


@code("SA00043")
@category("repository")
@objective("functionality")
@negative
def test_error_status_raises_fetch_error_naming_url_and_status(tmp_path, server):
    """A server that answers with an error status makes fetch() raise
    FetchError, and the message names the url and the status."""
    failed = attempt(
        server, tmp_path, FakeResponse(CHUNKS, status_error=error_status())
    )
    assert URL in failed.message
    assert "404" in failed.message


@code("SA00044")
@category("repository")
@objective("functionality")
@negative
def test_error_status_leaves_no_part_file(tmp_path, server):
    """After an error status, no .part file is left on disk."""
    failed = attempt(
        server, tmp_path, FakeResponse(CHUNKS, status_error=error_status())
    )
    assert not partial_path(failed.destination).exists()


@code("SA00045")
@category("repository")
@objective("functionality")
@negative
def test_unreachable_server_raises_fetch_error_naming_url_and_cause(tmp_path, server):
    """A connection that cannot be made makes fetch() raise FetchError, and the
    message names the url and the cause."""
    failed = attempt(server, tmp_path, httpx.ConnectError("name or service not known"))
    assert URL in failed.message
    assert "name or service not known" in failed.message


@code("SA00046")
@category("repository")
@objective("functionality")
@negative
def test_unreachable_server_leaves_no_part_file(tmp_path, server):
    """After a failed connection, no .part file is left on disk."""
    failed = attempt(server, tmp_path, httpx.ConnectError("name or service not known"))
    assert not partial_path(failed.destination).exists()


@code("SA00047")
@category("repository")
@objective("functionality")
@negative
def test_unparseable_url_raises_fetch_error_naming_url_and_cause(tmp_path, server):
    """A url the HTTP library cannot parse makes fetch() raise FetchError, and the
    message names the url and the cause, so acquire_sources counts it and carries on
    rather than stopping with a traceback."""
    failed = attempt(server, tmp_path, httpx.InvalidURL("Invalid IPv6 URL"))
    assert URL in failed.message
    assert "Invalid IPv6 URL" in failed.message
    assert not partial_path(failed.destination).exists()


@code("SA00048")
@category("repository")
@objective("functionality")
@negative
def test_file_where_the_folder_should_be_raises_fetch_error(tmp_path, server):
    """A plain file sitting where the destination's folder should be makes fetch()
    raise FetchError naming the url, and the file is left as it was."""
    server(FakeResponse(CHUNKS))
    blocker = tmp_path / "folder"
    blocker.write_bytes(b"not a folder")
    with pytest.raises(FetchError) as caught:
        fetch(URL, blocker / "file.pdf")
    assert URL in str(caught.value)
    assert blocker.read_bytes() == b"not a folder"


@code("SA00049")
@category("repository")
@objective("functionality")
@negative
def test_a_failed_cleanup_does_not_mask_the_fetch_error(tmp_path, server, monkeypatch):
    """When the .part file cannot be removed after a failed download, fetch() still
    raises FetchError for the download, not the removal's own error."""

    def refuse(self, missing_ok=False):
        """Stand in for removing a file with a refusal, as a locked file gives."""
        raise PermissionError("cannot remove")

    monkeypatch.setattr(Path, "unlink", refuse)
    failed = attempt(server, tmp_path, httpx.ConnectError("name or service not known"))
    assert "name or service not known" in failed.message


@code("SA00050")
@category("repository")
@objective("functionality")
@negative
def test_broken_transfer_raises_fetch_error_naming_the_cause(tmp_path, server):
    """A transfer that breaks after the first chunk makes fetch() raise
    FetchError, and the message names the cause."""
    failed = attempt(server, tmp_path, FakeResponse(CHUNKS, break_after=1))
    assert "connection reset" in failed.message


@code("SA00051")
@category("repository")
@objective("functionality")
@negative
def test_broken_transfer_removes_the_half_written_part_file(tmp_path, server):
    """After a transfer breaks part way, the half-written .part file is
    removed, so it cannot be mistaken for a finished download."""
    failed = attempt(server, tmp_path, FakeResponse(CHUNKS, break_after=1))
    assert not partial_path(failed.destination).exists()
