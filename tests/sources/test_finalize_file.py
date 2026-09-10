"""
Script:      test_finalize_file.py
Description: Automated checks for src/sdg/sources/finalize_file.py, the step
             that brings a finished download to its final name, or deletes a
             download that did not match. Each check stages one .part file, and
             sometimes a file at the final name beside it, calls place() or
             discard(), and compares what happened to what the module's header
             promises: the file under its final name, or gone, and a refusal
             that moves or deletes nothing when the situation is wrong.

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

import pytest

from sdg.sources.fetch_file import partial_path
from sdg.sources.finalize_file import discard, place

positive = pytest.mark.positive
negative = pytest.mark.negative

# The bytes a staged download holds.
CONTENT = b"downloaded bytes\n"


#######################################################################################
### Positive checks ###
#
# A .part file is placed under its final name, or deleted, as asked.


@positive
def test_place_renames_the_part_file_to_its_final_name(tmp_path):
    """place() removes the .part suffix, hands back the final path, and leaves
    nothing under the temporary name."""
    final = tmp_path / "file.pdf"
    partial = partial_path(final)
    partial.write_bytes(CONTENT)

    assert place(partial) == final
    assert final.read_bytes() == CONTENT
    assert not partial.exists()


@positive
def test_discard_deletes_the_part_file(tmp_path):
    """discard() deletes the .part file and gives back nothing."""
    partial = partial_path(tmp_path / "file.pdf")
    partial.write_bytes(CONTENT)

    assert discard(partial) is None
    assert not partial.exists()


#######################################################################################
### Negative checks ###
#
# A wrong situation is refused before anything is moved or deleted. A pinned
# file is never overwritten, and a file that is not a download is never
# discarded.


@negative
def test_place_refuses_to_overwrite_a_file_at_the_final_name(tmp_path):
    """When a file already sits at the final name, place() raises
    FileExistsError naming that file and the remedy, and moves nothing: the
    existing file keeps its bytes and the .part file stays where it is."""
    final = tmp_path / "file.pdf"
    existing = b"the pinned file that is already here\n"
    final.write_bytes(existing)
    partial = partial_path(final)
    partial.write_bytes(CONTENT)

    with pytest.raises(FileExistsError) as caught:
        place(partial)

    message = str(caught.value)
    assert str(final) in message
    assert "acquire_sources" in message
    assert final.read_bytes() == existing
    assert partial.read_bytes() == CONTENT


@negative
def test_place_refuses_a_missing_part_file(tmp_path):
    """place() raises FileNotFoundError naming the path when the .part file
    does not exist."""
    partial = partial_path(tmp_path / "file.pdf")
    with pytest.raises(FileNotFoundError) as caught:
        place(partial)
    assert str(partial) in str(caught.value)


@negative
def test_place_refuses_a_file_that_is_not_a_part_file(tmp_path):
    """place() raises ValueError naming the path when it does not end in .part,
    and leaves the file as it is."""
    other = tmp_path / "file.pdf"
    other.write_bytes(CONTENT)

    with pytest.raises(ValueError, match=r"not a \.part file"):
        place(other)

    assert other.read_bytes() == CONTENT


@negative
def test_discard_refuses_a_missing_part_file(tmp_path):
    """discard() raises FileNotFoundError naming the path when the .part file
    does not exist."""
    partial = partial_path(tmp_path / "file.pdf")
    with pytest.raises(FileNotFoundError) as caught:
        discard(partial)
    assert str(partial) in str(caught.value)


@negative
def test_discard_refuses_a_file_that_is_not_a_part_file_and_keeps_it(tmp_path):
    """discard() raises ValueError for a path that does not end in .part and
    does not delete it, so a pinned file can never be discarded by mistake."""
    other = tmp_path / "file.pdf"
    other.write_bytes(CONTENT)

    with pytest.raises(ValueError, match=r"not a \.part file"):
        discard(other)

    assert other.read_bytes() == CONTENT
