"""
Script:      test_check_sources_map.py
Description: Checks for repo_tools/check_sources_map.py, the hand-run tool that
             compares docs/sources_index.md with the manifests. Each check stages
             a throwaway repo holding one recorded file and a map written one way,
             points the tool's map at it, runs main() in-process, and asserts the
             exit code or the line the header promises.

             The staged maps are cut down to the two kinds of line the tool reads,
             the location line and the document heading, because nothing else in
             the real map affects the outcome.

Inputs:      Nothing real. The map and the manifests are written to pytest's own
             temporary folder; docs/ and manifests/ are never read.

Outputs:     Writes nothing to disk. Temporary files go to pytest's own folder.

Usage:       pytest validation/repo_tools/test_check_sources_map.py
                 run these checks
             pytest validation/repo_tools/test_check_sources_map.py -v
                 one line per check with its result

Exit codes:  pytest's own: 0 all passed, 1 some failed

Date:        2026-09-15
Owner:       Jason Delosh
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

import check_sources_map as script

positive = pytest.mark.positive
negative = pytest.mark.negative
# Every check carries a @code line: its short, permanent id in
# validation/validation_inventory.csv, assigned once and never reused.
code = pytest.mark.code
# Every check carries an @objective line: why the check exists, one of the
# objectives validation/README.md defines.
objective = pytest.mark.objective

PINNED = "inputs/standards/example/Example_Guide.pdf"
CONTENT = b"pinned bytes\n"

MAP = "\n".join(
    [
        "# Sources",
        "",
        "## Example standard",
        "",
        "- location: inputs/standards/example/",
        "",
        "### Document: Example_Guide.pdf",
        "- purpose: The guide.",
        "",
    ]
)


#######################################################################################
### Shared staging ###
#
# One fixture builds the repo every check starts from: a fake repo holding one recorded
# file, with the tool's map pointed at a temporary file. The helper writes a map and
# runs the tool over it.


@dataclass(frozen=True)
class Outcome:
    """What one run of the tool produced."""

    exit_code: int
    printed: str


@pytest.fixture
def repo(fake_repo, tmp_path, monkeypatch):
    """Give a check a fake repo with one recorded file, and a map of its own.

    The tool works out where the map lives when it is first loaded, so that location
    is pointed at the temporary folder for the length of the check.

    Returns:
        The fake repo.
    """
    fake_repo.file(PINNED, CONTENT)
    fake_repo.manifest("example", [fake_repo.entry(PINNED)])
    monkeypatch.setattr(script, "MAP_FILE", tmp_path / "sources_index.md")
    return fake_repo


def run(capsys, text, *argv):
    """Write the given map and run the tool over it.

    Args:
        capsys: pytest's capture of what was printed.
        text: The map to stage.
        *argv: The command-line arguments to hand the tool.

    Returns:
        The exit code and what was printed, as an Outcome.
    """
    script.MAP_FILE.write_text(text, encoding="utf-8")
    exit_code = script.main(list(argv))
    return Outcome(exit_code, capsys.readouterr().out)


#######################################################################################
### Positive checks ###
#
# The right thing works: a map naming every recorded file passes, a heading may stand
# for a group of files, and a heading may name two files at once.


@code("HRS0094")
@objective("behavior")
@positive
def test_a_map_naming_every_file_exits_0(repo, capsys):
    """A map with a heading for every recorded file, and a location the files live in,
    exits 0."""
    assert run(capsys, MAP).exit_code == 0


@code("HRS0095")
@objective("behavior")
@positive
def test_a_map_naming_every_file_prints_nothing(repo, capsys):
    """When the map and the manifests agree, nothing is printed."""
    assert run(capsys, MAP).printed == ""


@code("HRS0096")
@objective("behavior")
@positive
def test_a_placeholder_heading_covers_a_group(repo, fake_repo, capsys):
    """A heading written with a placeholder stands for every file of that shape, which
    is how one section covers a file per study."""
    fake_repo.file("inputs/worked_examples/StudyOne/StudyOne.pdf", CONTENT)
    fake_repo.manifest(
        "examples", [fake_repo.entry("inputs/worked_examples/StudyOne/StudyOne.pdf")]
    )
    text = MAP + "\n".join(
        [
            "## Worked examples",
            "",
            "- location: inputs/worked_examples/<study>/",
            "",
            "### Document: <study>.pdf",
            "",
        ]
    )
    assert run(capsys, text).exit_code == 0


@code("HRS0097")
@objective("behavior")
@positive
def test_a_starred_heading_covers_a_subfolder(repo, fake_repo, capsys):
    """A heading written with a star and a subfolder covers the files in it, which is
    how one section covers a folder of diagrams."""
    fake_repo.file("inputs/standards/example/uml/Area.png", CONTENT)
    fake_repo.manifest(
        "pictures", [fake_repo.entry("inputs/standards/example/uml/Area.png")]
    )
    assert run(capsys, MAP + "\n### Document: uml/*.png\n").exit_code == 0


@code("HRS0098")
@objective("behavior")
@positive
def test_one_heading_may_name_two_files(repo, fake_repo, capsys):
    """A heading naming two files joined by the word and covers both, as the two
    API files are written."""
    fake_repo.file("inputs/standards/example/API.json", CONTENT)
    fake_repo.file("inputs/standards/example/API.yaml", CONTENT)
    fake_repo.manifest(
        "api",
        [
            fake_repo.entry("inputs/standards/example/API.json"),
            fake_repo.entry("inputs/standards/example/API.yaml"),
        ],
    )
    assert run(capsys, MAP + "\n### Document: API.json and API.yaml\n").exit_code == 0


#######################################################################################
### Negative checks ###
#
# The wrong thing is refused. Each check breaks one thing, and asserts the exit code
# and that the message names what is wrong.


@code("HRS0099")
@objective("behavior")
@negative
def test_a_file_with_no_heading_exits_35(repo, fake_repo, capsys):
    """A recorded file that no heading covers exits 35, and the line names the file,
    which is the failure this tool was written for."""
    fake_repo.file("inputs/standards/example/Forgotten.xlsx", CONTENT)
    fake_repo.manifest(
        "extra", [fake_repo.entry("inputs/standards/example/Forgotten.xlsx")]
    )
    outcome = run(capsys, MAP)
    assert outcome.exit_code == 35
    assert "Forgotten.xlsx" in outcome.printed
    assert "no heading in the map covers it" in outcome.printed


@code("HRS0138")
@objective("behavior")
@negative
def test_a_placeholder_heading_does_not_reach_outside_its_group(
    repo, fake_repo, capsys
):
    """A placeholder heading in one group does not cover a file of the same shape in
    another group, so the run exits 35 and names that file."""
    fake_repo.file("inputs/worked_examples/StudyOne/StudyOne.pdf", CONTENT)
    fake_repo.manifest(
        "examples", [fake_repo.entry("inputs/worked_examples/StudyOne/StudyOne.pdf")]
    )
    # The example standard keeps its location line but loses its heading, so only
    # the worked examples' <study>.pdf could cover Example_Guide.pdf, and must not.
    text = MAP.replace("### Document: Example_Guide.pdf\n- purpose: The guide.\n", "")
    text += "\n".join(
        [
            "## Worked examples",
            "",
            "- location: inputs/worked_examples/<study>/",
            "",
            "### Document: <study>.pdf",
            "",
        ]
    )
    outcome = run(capsys, text)
    assert outcome.exit_code == 35
    assert PINNED in outcome.printed


@code("HRS0100")
@objective("behavior")
@negative
def test_a_location_nothing_lives_in_exits_36(repo, capsys):
    """A location line naming a folder no manifest records a file in exits 36, and the
    line names the folder."""
    text = MAP + "\n- location: inputs/standards/nowhere/\n"
    outcome = run(capsys, text)
    assert outcome.exit_code == 36
    assert "inputs/standards/nowhere" in outcome.printed


@code("HRS0101")
@objective("behavior")
@negative
def test_a_missing_file_outranks_an_empty_location(repo, fake_repo, capsys):
    """When a file has no heading and a location holds nothing, the run exits 35,
    because a file nobody can find is the worse problem."""
    fake_repo.file("inputs/standards/example/Forgotten.xlsx", CONTENT)
    fake_repo.manifest(
        "extra", [fake_repo.entry("inputs/standards/example/Forgotten.xlsx")]
    )
    text = MAP + "\n- location: inputs/standards/nowhere/\n"
    outcome = run(capsys, text)
    assert outcome.exit_code == 35
    assert "Forgotten.xlsx" in outcome.printed
    assert "inputs/standards/nowhere" in outcome.printed


@code("HRS0102")
@objective("behavior")
@negative
def test_a_missing_map_exits_13(repo, capsys):
    """With no map on disk, the run exits 13 and says the map cannot be read, rather
    than reporting every recorded file as unmapped."""
    outcome = Outcome(script.main([]), capsys.readouterr().out)
    assert outcome.exit_code == 13
    assert "cannot be read" in outcome.printed


@code("HRS0146")
@objective("behavior")
@negative
def test_not_inside_repo_exits_6(repo, tmp_path, monkeypatch, capsys):
    """When the sdg package is not running from inside its repo, the run exits 6 with
    the install command, instead of reporting a file with no heading."""
    from sdg.sources import read_manifests

    monkeypatch.setattr(read_manifests, "REPO_ROOT", tmp_path / "elsewhere")
    outcome = run(capsys, MAP)
    assert outcome.exit_code == 6
    assert "pip install -e ." in outcome.printed


@code("HRS0147")
@objective("behavior")
@negative
def test_an_unreadable_manifest_exits_3(repo, fake_repo, capsys):
    """When a manifest is not valid JSON, the run exits 3 and names that manifest as
    the thing that cannot be read, instead of comparing a map against nothing."""
    (fake_repo.root / "manifests" / "broken.json").write_text(
        "{ not json", encoding="utf-8"
    )
    outcome = run(capsys, MAP)
    assert outcome.exit_code == 3
    assert "broken.json" in outcome.printed and "cannot read" in outcome.printed


@pytest.fixture
def quiet_with_a_forgotten_file(repo, fake_repo, capsys):
    """Stage a recorded file the map does not cover, run the tool with the quiet
    option, and hand back what the run produced."""
    fake_repo.file("inputs/standards/example/Forgotten.xlsx", CONTENT)
    fake_repo.manifest(
        "extra", [fake_repo.entry("inputs/standards/example/Forgotten.xlsx")]
    )
    return run(capsys, MAP, "--quiet")


@code("HRS0103")
@objective("behavior")
@positive
def test_quiet_prints_nothing(quiet_with_a_forgotten_file):
    """With the quiet option, nothing is printed even when a recorded file has no
    heading in the map."""
    assert quiet_with_a_forgotten_file.printed == ""


@code("HRS0153")
@objective("behavior")
@positive
def test_quiet_keeps_the_exit_code(quiet_with_a_forgotten_file):
    """With the quiet option, the exit code still reports the recorded file that has
    no heading in the map."""
    assert quiet_with_a_forgotten_file.exit_code == 35


#######################################################################################
### The real map ###
#
# Every check above stages its own map. This one runs the tool over the repo's own map
# and manifests, which is the run that keeps the two in step. It reads real files
# deliberately, the way the header checker's real-folders check does, because a staged
# map cannot prove the real one is right.


@code("HRS0104")
@objective("agreement")
def test_the_real_map_and_manifests_agree():
    """The repo's own sources map, docs/sources_index.md, names every file its manifests record, and every
    location it names holds recorded files."""
    assert script.main(["--quiet"]) == 0
