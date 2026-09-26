"""
Script:      test_finalize_file_technical.py
Description: Automated checks for src/sdg/sources/finalize_file.py, the step
             that brings a finished download to its final name, or deletes a
             download that did not match. Each check proves one promise from
             that module's header: one effect of placing or discarding, or one
             wrong situation that is refused without anything being moved or
             deleted.

Inputs:      none from the repo

Outputs:     Writes nothing to disk. Temporary files go to pytest's own folder.

Usage:       pytest validation/sdg/sources/test_finalize_file_technical.py
                 run these checks
             pytest validation/sdg/sources/test_finalize_file_technical.py -v
                 one line per check with its result

Exit codes:  pytest's own: 0 all passed, 1 some failed

Date:        2026-09-10
Owner:       Jason Delosh
"""

from __future__ import annotations

from pathlib import Path

import pytest

from sdg.sources.fetch_file import partial_path
from sdg.sources.finalize_file import discard, place
from sdgval.labels import category, code, negative, objective, positive
from validation.shared.staged_downloads import CONTENT, Staged

EXISTING = b"the pinned file that is already here\n"


#######################################################################################
### Shared staging ###
#
# Each fixture stages one situation. Each check then asserts one thing about
# what place() or discard() did with it.


@pytest.fixture
def blocked(tmp_path) -> tuple[str, Staged]:
    """Stages a .part file beside a file already at its final name, tries to
    place it, and gives back the refusal message with the staging."""
    final = tmp_path / "file.pdf"
    final.write_bytes(EXISTING)
    partial = partial_path(final)
    partial.write_bytes(CONTENT)
    with pytest.raises(FileExistsError) as caught:
        place(partial)
    return str(caught.value), Staged(partial, final)


@pytest.fixture
def plain_file(tmp_path) -> Path:
    """Writes a file whose name does not end in .part."""
    path = tmp_path / "file.pdf"
    path.write_bytes(CONTENT)
    return path


#######################################################################################
### Positive checks ###
#
# A .part file is placed under its final name, or deleted, as asked.


@code("SA00053")
@category("repository")
@objective("functionality")
@positive
def test_place_hands_back_the_final_path(placed):
    """Placing a file gives back its final path."""
    result, staged = placed
    assert result == staged.final


@code("SA00054")
@category("repository")
@objective("functionality")
@positive
def test_place_removes_the_part_name(placed):
    """After a file is placed, nothing is left under its .part name."""
    _, staged = placed
    assert not staged.partial.exists()


@code("SA00055")
@category("repository")
@objective("functionality")
@positive
def test_discard_deletes_the_part_file(part_file):
    """Discarding a .part file deletes it and gives back nothing."""
    assert discard(part_file.partial) is None
    assert not part_file.partial.exists()


#######################################################################################
### Negative checks ###
#
# A wrong situation is refused before anything is moved or deleted. A pinned
# file is never overwritten, and a file that is not a download is never
# discarded.


@code("SA00056")
@category("repository")
@objective("functionality")
@negative
def test_place_refuses_when_the_final_name_is_taken(blocked):
    """When a file already sits at the final name, placing is refused. The message names
    that file and says to run acquire_sources again after dealing with it."""
    message, staged = blocked
    assert str(staged.final) in message
    assert "acquire_sources" in message


@code("SA00057")
@category("repository")
@objective("functionality")
@negative
def test_refused_place_leaves_the_existing_file_untouched(blocked):
    """When placing a download is refused because a file is already at the final name,
    that file keeps its bytes."""
    _, staged = blocked
    assert staged.final.read_bytes() == EXISTING


@code("SA00058")
@category("repository")
@objective("functionality")
@negative
def test_refused_place_leaves_the_part_file_where_it_was(blocked):
    """When placing a download is refused because a file is already at the final name,
    the .part file stays where it was, with its bytes."""
    _, staged = blocked
    assert staged.partial.read_bytes() == CONTENT


@code("SA00059")
@category("repository")
@objective("functionality")
@negative
def test_place_refuses_a_missing_part_file(tmp_path):
    """Placing a .part file that does not exist is refused, and the message names the
    path."""
    partial = partial_path(tmp_path / "file.pdf")
    with pytest.raises(FileNotFoundError) as caught:
        place(partial)
    assert str(partial) in str(caught.value)


@code("SA00060")
@category("repository")
@objective("functionality")
@negative
def test_place_refuses_a_name_without_the_part_suffix(plain_file):
    """Placing a file whose name does not end in .part is refused, and the message names
    the path."""
    with pytest.raises(ValueError, match=r"not a \.part file") as caught:
        place(plain_file)
    assert str(plain_file) in str(caught.value)


@code("SA00061")
@category("repository")
@objective("functionality")
@negative
def test_place_leaves_a_file_it_refused_untouched(plain_file):
    """A file refused for its name when placing keeps its bytes."""
    with pytest.raises(ValueError):
        place(plain_file)
    assert plain_file.read_bytes() == CONTENT


@code("SA00062")
@category("repository")
@objective("functionality")
@negative
def test_discard_refuses_a_missing_part_file(tmp_path):
    """Discarding a .part file that does not exist is refused, and the message names the
    path."""
    partial = partial_path(tmp_path / "file.pdf")
    with pytest.raises(FileNotFoundError) as caught:
        discard(partial)
    assert str(partial) in str(caught.value)


@code("SA00063")
@category("repository")
@objective("functionality")
@negative
def test_discard_refuses_a_name_without_the_part_suffix(plain_file):
    """Discarding a file whose name does not end in .part is refused, and the message
    names the path."""
    with pytest.raises(ValueError, match=r"not a \.part file") as caught:
        discard(plain_file)
    assert str(plain_file) in str(caught.value)


@code("SA00064")
@category("repository")
@objective("functionality")
@negative
def test_discard_leaves_a_file_it_refused_in_place(plain_file):
    """A file refused for its name when discarding is not deleted, so a pinned file can
    never be discarded by mistake."""
    with pytest.raises(ValueError):
        discard(plain_file)
    assert plain_file.read_bytes() == CONTENT
