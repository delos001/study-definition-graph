"""
Script:      test_finalize_file.py
Description: Automated checks for src/sdg/sources/finalize_file.py, the step
             that brings a finished download to its final name, or deletes a
             download that did not match. Each check proves one promise from
             that module's header: one effect of placing or discarding, or one
             wrong situation that is refused without anything being moved or
             deleted.

Inputs:      none from the repo

Outputs:     Writes nothing to disk. Temporary files go to pytest's own folder.

Usage:       pytest tests/sources/test_finalize_file.py
                 run these checks
             pytest tests/sources/test_finalize_file.py -v
                 one line per check with its result

Exit codes:  pytest's own: 0 all passed, 1 some failed

Date:        2026-09-10
Owner:       Jason Delosh
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from sdg.sources.fetch_file import partial_path
from sdg.sources.finalize_file import discard, place

positive = pytest.mark.positive
negative = pytest.mark.negative

# The bytes a staged download holds, and the bytes of a file that is already
# at the final name when a check needs one there.
CONTENT = b"downloaded bytes\n"
EXISTING = b"the pinned file that is already here\n"


#######################################################################################
### Shared staging ###
#
# Each fixture stages one situation. Each check then asserts one thing about
# what place() or discard() did with it.


@dataclass(frozen=True)
class Staged:
    """One download staged under its .part name, and the final name it is for."""

    partial: Path
    final: Path


@pytest.fixture
def part_file(tmp_path) -> Staged:
    """Writes one .part file with nothing at its final name."""
    final = tmp_path / "file.pdf"
    partial = partial_path(final)
    partial.write_bytes(CONTENT)
    return Staged(partial, final)


@pytest.fixture
def placed(part_file) -> tuple[Path, Staged]:
    """Places the staged .part file and gives back what place() handed back,
    with the staging."""
    return place(part_file.partial), part_file


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


@positive
def test_place_puts_the_file_under_its_final_name(placed):
    """After place(), the bytes are at the final name."""
    _, staged = placed
    assert staged.final.read_bytes() == CONTENT


@positive
def test_place_hands_back_the_final_path(placed):
    """place() gives back the final path."""
    result, staged = placed
    assert result == staged.final


@positive
def test_place_removes_the_part_name(placed):
    """After place(), nothing is left under the .part name."""
    _, staged = placed
    assert not staged.partial.exists()


@positive
def test_discard_deletes_the_part_file(part_file):
    """discard() deletes the .part file and gives back nothing."""
    assert discard(part_file.partial) is None
    assert not part_file.partial.exists()


#######################################################################################
### Negative checks ###
#
# A wrong situation is refused before anything is moved or deleted. A pinned
# file is never overwritten, and a file that is not a download is never
# discarded.


@negative
def test_place_refuses_when_the_final_name_is_taken(blocked):
    """When a file already sits at the final name, place() raises
    FileExistsError, and the message names that file and says to run
    acquire_sources again after dealing with it."""
    message, staged = blocked
    assert str(staged.final) in message
    assert "acquire_sources" in message


@negative
def test_refused_place_leaves_the_existing_file_untouched(blocked):
    """The file already at the final name keeps its bytes."""
    _, staged = blocked
    assert staged.final.read_bytes() == EXISTING


@negative
def test_refused_place_leaves_the_part_file_where_it_was(blocked):
    """The .part file stays where it was, with its bytes."""
    _, staged = blocked
    assert staged.partial.read_bytes() == CONTENT


@negative
def test_place_refuses_a_missing_part_file(tmp_path):
    """place() raises FileNotFoundError naming the path when the .part file
    does not exist."""
    partial = partial_path(tmp_path / "file.pdf")
    with pytest.raises(FileNotFoundError) as caught:
        place(partial)
    assert str(partial) in str(caught.value)


@negative
def test_place_refuses_a_name_without_the_part_suffix(plain_file):
    """place() raises ValueError naming the path when the name does not end in
    .part."""
    with pytest.raises(ValueError, match=r"not a \.part file"):
        place(plain_file)


@negative
def test_place_leaves_a_file_it_refused_untouched(plain_file):
    """A file place() refused for its name keeps its bytes."""
    with pytest.raises(ValueError):
        place(plain_file)
    assert plain_file.read_bytes() == CONTENT


@negative
def test_discard_refuses_a_missing_part_file(tmp_path):
    """discard() raises FileNotFoundError naming the path when the .part file
    does not exist."""
    partial = partial_path(tmp_path / "file.pdf")
    with pytest.raises(FileNotFoundError) as caught:
        discard(partial)
    assert str(partial) in str(caught.value)


@negative
def test_discard_refuses_a_name_without_the_part_suffix(plain_file):
    """discard() raises ValueError naming the path when the name does not end
    in .part."""
    with pytest.raises(ValueError, match=r"not a \.part file"):
        discard(plain_file)


@negative
def test_discard_leaves_a_file_it_refused_in_place(plain_file):
    """A file discard() refused for its name is not deleted, so a pinned file
    can never be discarded by mistake."""
    with pytest.raises(ValueError):
        discard(plain_file)
    assert plain_file.read_bytes() == CONTENT
