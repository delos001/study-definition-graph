"""
Script:      test_check_neo4j.py
Description: Checks for repo_tools/check_neo4j.py, the hand-run tool that
             confirms the Neo4j database is running, accepts the login in .env,
             and is the version pinned in docker-compose.yml. Each check writes
             a .env and a docker-compose.yml into pytest's own temporary folder,
             points the tool's repo root at it, stands in for the one function
             that asks the database, runs the tool's main() in-process, and
             asserts the exit code or the message the header promises for that
             state.

             No check reaches a database or reads the real .env, so none of
             them needs Docker running.

Inputs:      Nothing real. The .env and docker-compose.yml files are written to
             pytest's own temporary folder, and the call to the database is
             replaced by a stand-in.

Outputs:     Writes nothing to disk. Temporary files go to pytest's own folder.

Usage:       pytest validation/repo_tools/test_check_neo4j.py
                 run these checks
             pytest validation/repo_tools/test_check_neo4j.py -v
                 one line per check with its result

Exit codes:  pytest's own: 0 all passed, 1 some failed

Date:        2026-09-16
Owner:       Jason Delosh
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import neo4j
import pytest

import check_neo4j as script

positive = pytest.mark.positive
negative = pytest.mark.negative
# Every check carries a @code line: its short, permanent id in
# validation/validation_inventory.csv, assigned once and never reused.
code = pytest.mark.code

URI = "bolt://localhost:7687"
USER = "neo4j"
PASSWORD = "test-password-never-printed"
PINNED = script.Release("5.26.29", "community")

ENV_LINES = f"NEO4J_URI={URI}\nNEO4J_USER={USER}\nNEO4J_PASSWORD={PASSWORD}\n"


#######################################################################################
### Shared staging ###
#
# One fixture builds the repo every check starts from: a temporary folder standing in
# for the repo root, with the repo check satisfied so that only the state a check
# stages can decide the outcome. The helpers write the two files the tool reads and
# stand in for the call to the database.


@dataclass(frozen=True)
class Outcome:
    """What one run of the tool produced."""

    exit_code: int
    printed: str


@pytest.fixture
def repo(tmp_path, monkeypatch) -> Path:
    """Give a check a temporary folder standing in for the repo root.

    The tool reads .env and docker-compose.yml from the repo root and refuses to run
    outside the repo. All three are settled here, so each check stages only the one
    thing it is about.

    Returns:
        The folder standing in for the repo root.
    """
    monkeypatch.setattr(script, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(script, "require_repo", lambda: tmp_path)
    return tmp_path


def write_env(repo: Path, lines: str = ENV_LINES) -> None:
    """Write a .env file holding the given lines, with another setting around them.

    Args:
        repo: The folder standing in for the repo root.
        lines: The Neo4j lines to write.
    """
    (repo / ".env").write_text(
        f"# comment\nANTHROPIC_API_KEY=sk-ant-x\n{lines}", encoding="utf-8"
    )


def write_compose(repo: Path, image: str = "neo4j:5.26.29-community") -> None:
    """Write a docker-compose.yml pinning the given image, in the real file's shape.

    Args:
        repo: The folder standing in for the repo root.
        image: The image line to pin.
    """
    (repo / "docker-compose.yml").write_text(
        f"services:\n  neo4j:\n    image: {image}\n    container_name: sdg-neo4j\n",
        encoding="utf-8",
    )


def answer(monkeypatch, release: script.Release = PINNED) -> None:
    """Stand in for the call to the database with one that answers without a network.

    Args:
        monkeypatch: pytest's patcher, which undoes this when the check ends.
        release: What the stand-in should report as the running version and edition.
    """
    monkeypatch.setattr(script, "ask_database", lambda settings: release)


def refuse(monkeypatch, error: Exception) -> None:
    """Stand in for the call to the database with one that raises the given error.

    Args:
        monkeypatch: pytest's patcher, which undoes this when the check ends.
        error: The error the stand-in should raise.
    """

    def raise_it(settings: script.Settings) -> script.Release:
        raise error

    monkeypatch.setattr(script, "ask_database", raise_it)


def run(capsys, *argv: str) -> Outcome:
    """Run the tool in-process with the given arguments.

    Args:
        capsys: pytest's capture of what was printed.
        *argv: The command-line arguments to hand the tool.

    Returns:
        The exit code and what was printed, as an Outcome.
    """
    exit_code = script.main(list(argv))
    return Outcome(exit_code, capsys.readouterr().out)


@pytest.fixture
def working(repo, monkeypatch, capsys) -> Outcome:
    """Stage a complete .env and compose file, with the database answering the pinned
    version, and run the tool."""
    write_env(repo)
    write_compose(repo)
    answer(monkeypatch)
    return run(capsys)


#######################################################################################
### Positive checks ###
#
# The right thing works: a database that answers with the pinned version is reported
# as matching, the password never reaches the screen, the settings and the pin are
# read as written, and the quiet option silences the report without changing the
# exit code.


@code("HRS0105")
@positive
def test_matching_database_exits_0(working):
    """A database that answers with the pinned version gives an exit code of 0."""
    assert working.exit_code == 0


@code("HRS0106")
@positive
def test_matching_database_reports_the_version(working):
    """The report names the address it reached and the version that answered."""
    assert URI in working.printed
    assert str(PINNED) in working.printed


@code("HRS0107")
@positive
def test_the_password_is_never_printed(working):
    """The password itself is never printed, so it cannot end up in a terminal log."""
    assert PASSWORD not in working.printed


@code("HRS0108")
@positive
def test_quoted_settings_are_read(repo):
    """Settings written with quotes around them, as a person might paste them, are
    read without them."""
    write_env(
        repo, f'NEO4J_URI="{URI}"\nNEO4J_USER=\'{USER}\'\nNEO4J_PASSWORD="{PASSWORD}"\n'
    )
    assert script.read_settings(repo / ".env") == script.Settings(URI, USER, PASSWORD)


@code("HRS0109")
@positive
def test_the_pin_is_read_from_the_image_tag(repo):
    """The version and edition are read from the image tag in docker-compose.yml."""
    write_compose(repo, "neo4j:5.26.29-community")
    assert script.read_pinned_release(repo / "docker-compose.yml") == PINNED


@code("HRS0110")
@positive
def test_quiet_prints_nothing(repo, monkeypatch, capsys):
    """With the quiet option, nothing at all is printed."""
    write_env(repo, "NEO4J_URI=\n")
    assert run(capsys, "--quiet").printed == ""


@code("HRS0111")
@positive
def test_quiet_keeps_the_exit_code(repo, monkeypatch, capsys):
    """With the quiet option, the exit code still reports the missing settings."""
    write_env(repo, "NEO4J_URI=\n")
    assert run(capsys, "--quiet").exit_code == 37


#######################################################################################
### Negative checks ###
#
# The wrong thing is refused, and each refusal is its own exit code with a message
# that names the cause and what to do about it. One thing is broken per check.


@code("HRS0112")
@negative
def test_missing_env_file_is_refused(repo, capsys):
    """With no .env file at all, the run exits 27 and the message says to create it
    from the example."""
    outcome = run(capsys)
    assert outcome.exit_code == 27
    assert ".env does not exist" in outcome.printed
    assert "Copy-Item .env.example .env" in outcome.printed


@code("HRS0113")
@negative
def test_missing_settings_are_refused_by_name(repo, capsys):
    """With a .env missing two of the three Neo4j lines, the run exits 37 and the
    message names both missing settings."""
    write_env(repo, f"NEO4J_URI={URI}\n")
    outcome = run(capsys)
    assert outcome.exit_code == 37
    assert "NEO4J_USER, NEO4J_PASSWORD" in outcome.printed
    assert "copy the NEO4J_ lines from .env.example" in outcome.printed


@code("HRS0114")
@negative
def test_missing_compose_file_is_refused(repo, capsys):
    """With no docker-compose.yml, the run exits 13 and the message says to restore
    it from git."""
    write_env(repo)
    outcome = run(capsys)
    assert outcome.exit_code == 13
    assert "docker-compose.yml does not exist" in outcome.printed
    assert "restore it from git" in outcome.printed


@code("HRS0115")
@negative
def test_compose_file_without_an_image_is_refused(repo, capsys):
    """With a docker-compose.yml that names no image for the neo4j service, the run
    exits 13 and the message names the missing line."""
    write_env(repo)
    (repo / "docker-compose.yml").write_text(
        "services:\n  neo4j:\n    container_name: sdg-neo4j\n", encoding="utf-8"
    )
    outcome = run(capsys)
    assert outcome.exit_code == 13
    assert "names no image for the neo4j service" in outcome.printed
    assert "services.neo4j.image" in outcome.printed


@code("HRS0116")
@negative
def test_unpinned_image_tag_is_refused(repo, capsys):
    """With an image written without a version, the run exits 13 and the message
    shows the form the tag has to take."""
    write_env(repo)
    write_compose(repo, "neo4j")
    outcome = run(capsys)
    assert outcome.exit_code == 13
    assert "not in the form neo4j:<version>-<edition>" in outcome.printed


@code("HRS0117")
@negative
def test_unreachable_database_is_reported_as_unreachable(repo, monkeypatch, capsys):
    """When nothing answers at the address, the run exits 38 and the message says to
    start the container with docker compose."""
    write_env(repo)
    write_compose(repo)
    refuse(monkeypatch, neo4j.exceptions.ServiceUnavailable("connection refused"))
    outcome = run(capsys)
    assert outcome.exit_code == 38
    assert f"could not be reached at {URI}" in outcome.printed
    assert "docker compose up -d" in outcome.printed


@code("HRS0118")
@negative
def test_rejected_login_is_reported_as_rejected(repo, monkeypatch, capsys):
    """When the database refuses the user or password, the run exits 39 and the
    message says to match .env to the compose file."""
    write_env(repo)
    write_compose(repo)
    refuse(monkeypatch, neo4j.exceptions.AuthError("unauthorized"))
    outcome = run(capsys)
    assert outcome.exit_code == 39
    assert "rejected the login" in outcome.printed
    assert "match the NEO4J_AUTH line" in outcome.printed
    assert PASSWORD not in outcome.printed


@code("HRS0119")
@negative
def test_other_version_is_reported_with_both_versions(repo, monkeypatch, capsys):
    """When the database answers with a version other than the pin, the run exits 40
    and the message names both the running and the pinned version."""
    write_env(repo)
    write_compose(repo)
    answer(monkeypatch, script.Release("5.27.0", "community"))
    outcome = run(capsys)
    assert outcome.exit_code == 40
    assert "5.27.0 community" in outcome.printed
    assert str(PINNED) in outcome.printed


@code("HRS0120")
@negative
def test_other_edition_is_reported_as_another_version(repo, monkeypatch, capsys):
    """When the database is the pinned version number but another edition, the run
    exits 40, because the pin names the edition too."""
    write_env(repo)
    write_compose(repo)
    answer(monkeypatch, script.Release("5.26.29", "enterprise"))
    assert run(capsys).exit_code == 40


@code("HRS0121")
@negative
def test_outside_the_repo_is_refused(tmp_path, monkeypatch, capsys):
    """When the package is installed from outside the repo, the run exits 6 before it
    looks for a .env file."""

    def not_in_repo() -> Path:
        raise script.NotInRepoError("sdg is not running from inside its repo")

    monkeypatch.setattr(script, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(script, "require_repo", not_in_repo)
    outcome = run(capsys)
    assert outcome.exit_code == 6
    assert "not running from inside its repo" in outcome.printed
