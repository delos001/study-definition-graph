"""
Script:      test_check_sources_map_technical.py
Description: Checks for src/sdgtools/check_sources_map.py, the hand-run tool that
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

Usage:       pytest validation/sdgtools/test_check_sources_map_technical.py
                 run these checks
             pytest validation/sdgtools/test_check_sources_map_technical.py -v
                 one line per check with its result

Exit codes:  None of its own. It runs inside pytest.

Date:        2026-09-15
Owner:       Jason Delosh
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from sdg.exit_codes import exit_line
from sdgtools import check_sources_map as script
from sdgval.labels import category, code, negative, objective, positive
from validation.shared.staged_manifests import CONTENT

PINNED = "inputs/standards/example/Example_Guide.pdf"

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


def run(capsys: pytest.CaptureFixture[str], text: str, *argv: str) -> Outcome:
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


@code("SA00316")
@category("repository")
@objective("functionality")
@positive
def test_a_map_naming_every_file_exits_0(repo, capsys):
    """A map with a heading for every recorded file, and a location the files live in,
    exits 0."""
    assert run(capsys, MAP).exit_code == 0


@code("SA00317")
@category("repository")
@objective("functionality")
@positive
def test_a_map_naming_every_file_prints_nothing(repo, capsys):
    """When the map and the manifests agree, nothing is printed."""
    assert run(capsys, MAP).printed == ""


@code("SA00318")
@category("repository")
@objective("functionality")
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


@code("SA00319")
@category("repository")
@objective("functionality")
@positive
def test_a_starred_heading_covers_a_subfolder(repo, fake_repo, capsys):
    """A heading written with a star and a subfolder covers the files in it, which is
    how one section covers a folder of diagrams."""
    fake_repo.file("inputs/standards/example/uml/Area.png", CONTENT)
    fake_repo.manifest(
        "pictures", [fake_repo.entry("inputs/standards/example/uml/Area.png")]
    )
    assert run(capsys, MAP + "\n### Document: uml/*.png\n").exit_code == 0


@code("SA00320")
@category("repository")
@objective("functionality")
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


@code("SA00321")
@category("repository")
@objective("functionality")
@negative
def test_a_file_with_no_heading_exits_16(repo, fake_repo, capsys):
    """A recorded file that no heading covers exits 16, and the line names the file,
    which is the failure this tool was written for."""
    fake_repo.file("inputs/standards/example/Forgotten.xlsx", CONTENT)
    fake_repo.manifest(
        "extra", [fake_repo.entry("inputs/standards/example/Forgotten.xlsx")]
    )
    outcome = run(capsys, MAP)
    assert outcome.exit_code == 16
    assert exit_line(16, "SOURCES-MAP-HEADING-MISSING") in outcome.printed
    assert "Forgotten.xlsx" in outcome.printed
    assert "no heading in the map covers it" in outcome.printed


@code("SA00322")
@category("repository")
@objective("functionality")
@negative
def test_a_placeholder_heading_does_not_reach_outside_its_group(
    repo, fake_repo, capsys
):
    """A placeholder heading in one group does not cover a file of the same shape in
    another group, so the run exits 16 and names that file."""
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
    assert outcome.exit_code == 16
    assert exit_line(16, "SOURCES-MAP-HEADING-MISSING") in outcome.printed
    assert PINNED in outcome.printed


@code("SA00323")
@category("repository")
@objective("functionality")
@negative
def test_a_location_nothing_lives_in_exits_16(repo, capsys):
    """A location line naming a folder no manifest records a file in exits 16, and the
    line names the folder."""
    text = MAP + "\n- location: inputs/standards/nowhere/\n"
    outcome = run(capsys, text)
    assert outcome.exit_code == 16
    assert exit_line(16, "SOURCES-MAP-LOCATION-UNRECORDED") in outcome.printed
    assert "inputs/standards/nowhere" in outcome.printed


@code("SA00324")
@category("repository")
@objective("functionality")
@negative
def test_a_missing_file_outranks_an_empty_location(repo, fake_repo, capsys):
    """When a file has no heading and a location holds nothing, the run exits 16,
    because a file nobody can find is the worse problem."""
    fake_repo.file("inputs/standards/example/Forgotten.xlsx", CONTENT)
    fake_repo.manifest(
        "extra", [fake_repo.entry("inputs/standards/example/Forgotten.xlsx")]
    )
    text = MAP + "\n- location: inputs/standards/nowhere/\n"
    outcome = run(capsys, text)
    assert outcome.exit_code == 16
    assert exit_line(16, "SOURCES-MAP-HEADING-MISSING") in outcome.printed
    assert "Forgotten.xlsx" in outcome.printed
    assert "inputs/standards/nowhere" in outcome.printed


@code("SA00325")
@category("repository")
@objective("functionality")
@negative
def test_a_missing_map_exits_12(repo, capsys):
    """With no map on disk, the run exits 12, says the map is missing and to restore it
    from git, rather than reporting every recorded file as unmapped."""
    outcome = Outcome(script.main([]), capsys.readouterr().out)
    assert outcome.exit_code == 12
    assert exit_line(12, "SOURCES-MAP-MISSING") in outcome.printed
    assert "is missing" in outcome.printed
    assert "restore it from git" in outcome.printed


@code("SA00326")
@category("repository")
@objective("functionality")
@negative
def test_not_inside_repo_exits_3(repo, tmp_path, monkeypatch, capsys):
    """When the sdg package is not running from inside its repo, the run exits 3 with
    the install command, instead of reporting a file with no heading."""
    from sdg.sources import read_manifests

    monkeypatch.setattr(read_manifests, "REPO_ROOT", tmp_path / "elsewhere")
    outcome = run(capsys, MAP)
    assert outcome.exit_code == 3
    assert exit_line(3, "NOT-IN-REPO") in outcome.printed
    assert "pip install -e ." in outcome.printed


@code("SA00327")
@category("repository")
@objective("functionality")
@negative
def test_an_unparseable_manifest_exits_14(repo, fake_repo, capsys):
    """When a manifest is not valid JSON, the run exits 14 and names that manifest as
    what is not valid, instead of comparing a map against nothing."""
    (fake_repo.root / "manifests" / "broken.json").write_text(
        "{ not json", encoding="utf-8"
    )
    outcome = run(capsys, MAP)
    assert outcome.exit_code == 14
    assert exit_line(14, "MANIFEST-UNPARSEABLE") in outcome.printed
    assert "broken.json" in outcome.printed and "is not valid JSON" in outcome.printed


@code("SA00328")
@category("repository")
@objective("functionality")
@negative
def test_quiet_file_with_no_heading_exits_16_and_prints_nothing(
    repo, fake_repo, capsys
):
    """With the quiet option, a recorded file that has no heading in the map still
    exits 16, and nothing is printed."""
    fake_repo.file("inputs/standards/example/Forgotten.xlsx", CONTENT)
    fake_repo.manifest(
        "extra", [fake_repo.entry("inputs/standards/example/Forgotten.xlsx")]
    )
    outcome = run(capsys, MAP, "--quiet")
    assert outcome.exit_code == 16
    assert outcome.printed == ""


#######################################################################################
### Every refusal with the quiet option ###
#
# With the quiet option, each refusal prints nothing and still exits with its own
# code. One check runs once per refusal.


@code("SA00522")
@category("repository")
@objective("functionality")
@negative
@pytest.mark.parametrize(
    "refusal",
    ["outside the repo", "unreadable manifest", "location outside inputs", "no map"],
)
def test_every_refusal_is_silent_under_quiet(
    repo, fake_repo, tmp_path, monkeypatch, capsys, refusal
):
    """With the quiet option, a refusal prints nothing and still exits with its own
    code. It runs once each for an install outside the repo, an unreadable manifest, a
    manifest location that does not stay under inputs/, and an unreadable map."""
    from sdg.sources import read_manifests

    if refusal == "outside the repo":
        monkeypatch.setattr(read_manifests, "REPO_ROOT", tmp_path / "elsewhere")
        outcome, expected = run(capsys, MAP, "--quiet"), 3
    elif refusal == "unreadable manifest":
        (fake_repo.root / "manifests" / "broken.json").write_text(
            "{ not json", encoding="utf-8"
        )
        outcome, expected = run(capsys, MAP, "--quiet"), 14
    elif refusal == "location outside inputs":
        fake_repo.manifest(
            "stray",
            [fake_repo.entry("inputs/../elsewhere.txt", bytes=1, sha256="0" * 64)],
        )
        outcome, expected = run(capsys, MAP, "--quiet"), 15
    else:
        outcome, expected = (
            Outcome(script.main(["--quiet"]), capsys.readouterr().out),
            12,
        )
    assert outcome.printed == ""
    assert outcome.exit_code == expected


#######################################################################################
### A heading with no location ###


@code("SA00528")
@category("repository")
@objective("functionality")
@negative
def test_a_heading_with_no_location_covers_no_file(repo, capsys):
    """A document heading with no location line above it covers no recorded file, so
    the file it names is reported as having no heading and the run exits 16."""
    text = MAP.replace("- location: inputs/standards/example/\n", "")
    outcome = run(capsys, text)
    assert outcome.exit_code == 16
    assert exit_line(16, "SOURCES-MAP-HEADING-MISSING") in outcome.printed
    assert "Example_Guide.pdf" in outcome.printed


#######################################################################################
### Upper and lower case in a name ###
#
# A name in the map matches a recorded path only when every letter has the same case,
# on Windows as on every other system.


@code("SA00592")
@category("repository")
@objective("functionality")
@negative
def test_a_heading_in_another_case_covers_no_file(repo, capsys):
    """A document heading whose file name differs from the recorded file only in upper
    and lower case does not cover it, so the run exits 16 and names the file."""
    text = MAP.replace("Document: Example_Guide.pdf", "Document: example_guide.pdf")
    outcome = run(capsys, text)
    assert outcome.exit_code == 16
    assert exit_line(16, "SOURCES-MAP-HEADING-MISSING") in outcome.printed
    assert PINNED in outcome.printed


@code("SA00593")
@category("repository")
@objective("functionality")
@negative
def test_a_location_in_another_case_holds_no_file(repo, capsys):
    """A location line whose folder differs from a recorded folder only in upper and
    lower case holds no recorded file, so the run exits 16 and names the location."""
    text = MAP + "\n- location: inputs/standards/EXAMPLE/\n"
    outcome = run(capsys, text)
    assert outcome.exit_code == 16
    assert exit_line(16, "SOURCES-MAP-LOCATION-UNRECORDED") in outcome.printed
    assert "inputs/standards/EXAMPLE" in outcome.printed


@code("SA00612")
@category("repository")
@objective("functionality")
@negative
def test_a_manifest_location_outside_inputs_exits_15(repo, fake_repo, capsys):
    """When a manifest records a location that does not stay under inputs/, the run
    exits 15 and quotes the location, instead of comparing a map against it."""
    fake_repo.manifest(
        "stray", [fake_repo.entry("inputs/../elsewhere.txt", bytes=1, sha256="0" * 64)]
    )
    outcome = run(capsys, MAP)
    assert outcome.exit_code == 15
    assert exit_line(15, "MANIFEST-LOCATION-OUTSIDE-INPUTS") in outcome.printed
    assert "does not stay under inputs/" in outcome.printed
