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
# Every check carries an @objective line: what the check confirms about its category,
# one of the objectives validation/validation_inventory_dictionary.md defines.
objective = pytest.mark.objective
# Every check carries a @category line: what kind of thing the check confirms, one
# of the categories validation/validation_inventory_dictionary.md defines.
category = pytest.mark.category

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
        """Stand in for the database call by raising the staged error."""
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
@category("repository")
@objective("functionality")
@positive
def test_matching_database_exits_0(working):
    """A database that answers with the pinned version gives an exit code of 0."""
    assert working.exit_code == 0


@code("HRS0106")
@category("repository")
@objective("functionality")
@positive
def test_matching_database_reports_the_version(working):
    """The report names the address it reached and the version that answered."""
    assert URI in working.printed
    assert str(PINNED) in working.printed


@code("HRS0107")
@category("repository")
@objective("functionality")
@positive
def test_the_password_is_never_printed(working):
    """The password itself is never printed, so it cannot end up in a terminal log."""
    assert PASSWORD not in working.printed


@code("HRS0108")
@category("repository")
@objective("functionality")
@positive
def test_quoted_settings_are_read(repo):
    """Settings written with quotes around them, as a person might paste them, are
    read without them."""
    write_env(
        repo, f'NEO4J_URI="{URI}"\nNEO4J_USER=\'{USER}\'\nNEO4J_PASSWORD="{PASSWORD}"\n'
    )
    assert script.read_settings(repo / ".env") == script.Settings(URI, USER, PASSWORD)


@code("HRS0109")
@category("repository")
@objective("functionality")
@positive
def test_the_pin_is_read_from_the_image_tag(repo):
    """The version and edition are read from the image tag in docker-compose.yml."""
    write_compose(repo, "neo4j:5.26.29-community")
    assert script.read_pinned_release(repo / "docker-compose.yml") == PINNED


@code("HRS0110")
@category("repository")
@objective("functionality")
@positive
def test_quiet_prints_nothing(repo, monkeypatch, capsys):
    """With the quiet option, nothing at all is printed."""
    write_env(repo, "NEO4J_URI=\n")
    assert run(capsys, "--quiet").printed == ""


@code("HRS0111")
@category("repository")
@objective("functionality")
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
@category("repository")
@objective("functionality")
@negative
def test_missing_env_file_is_refused(repo, capsys):
    """With no .env file at all, the run exits 27 and the message says to create it
    from the example."""
    outcome = run(capsys)
    assert outcome.exit_code == 27
    assert ".env does not exist" in outcome.printed
    assert "Copy-Item .env.example .env" in outcome.printed


@code("HRS0113")
@category("repository")
@objective("functionality")
@negative
def test_missing_settings_are_refused_by_name(repo, capsys):
    """With a .env holding only one of the Neo4j lines, the run exits 37 and the
    message names both missing settings."""
    write_env(repo, f"NEO4J_URI={URI}\n")
    outcome = run(capsys)
    assert outcome.exit_code == 37
    assert "NEO4J_USER, NEO4J_PASSWORD" in outcome.printed
    assert "copy the NEO4J_ lines from .env.example" in outcome.printed


@code("HRS0114")
@category("repository")
@objective("functionality")
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
@category("repository")
@objective("functionality")
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
@category("repository")
@objective("functionality")
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
@category("repository")
@objective("functionality")
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


@code("HRS0149")
@category("repository")
@objective("functionality")
@negative
def test_a_driver_error_is_reported_as_unreachable(repo, monkeypatch, capsys):
    """When the driver fails with its general error rather than the service-unavailable
    one, the run still exits 38 and says to start the container, because that class
    is what the driver raises when a connection is lost part way."""
    write_env(repo)
    write_compose(repo)
    refuse(monkeypatch, neo4j.exceptions.DriverError("connection lost"))
    outcome = run(capsys)
    assert outcome.exit_code == 38
    assert "docker compose up -d" in outcome.printed


@code("HRS0150")
@category("repository")
@objective("functionality")
@negative
def test_a_malformed_address_is_reported_as_the_address(repo, monkeypatch, capsys):
    """When the driver refuses the address before trying to connect, the run exits 44
    and the message names the NEO4J_URI line, rather than saying the database is
    off and telling the person to start the container."""
    write_env(repo)
    write_compose(repo)
    refuse(monkeypatch, neo4j.exceptions.ConfigurationError("URI scheme missing"))
    outcome = run(capsys)
    assert outcome.exit_code == 44
    assert "NEO4J_URI" in outcome.printed
    assert "docker compose" not in outcome.printed


@code("HRS0118")
@category("repository")
@objective("functionality")
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
@category("repository")
@objective("functionality")
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
@category("repository")
@objective("functionality")
@negative
def test_other_edition_is_reported_as_another_version(repo, monkeypatch, capsys):
    """When the database is the pinned version number but another edition, the run
    exits 40, because the pin names the edition too."""
    write_env(repo)
    write_compose(repo)
    answer(monkeypatch, script.Release("5.26.29", "enterprise"))
    outcome = run(capsys)
    assert outcome.exit_code == 40
    assert "5.26.29 enterprise" in outcome.printed
    assert "docker-compose.yml pins" in outcome.printed


@code("HRS0121")
@category("repository")
@objective("functionality")
@negative
def test_outside_the_repo_is_refused(tmp_path, monkeypatch, capsys):
    """When the sdg package is installed from outside the repo, the run exits 6 before it
    looks for a .env file."""

    def not_in_repo() -> Path:
        """Stand in for the repo check with the refusal it gives outside the repo."""
        raise script.NotInRepoError("sdg is not running from inside its repo")

    monkeypatch.setattr(script, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(script, "require_repo", not_in_repo)
    outcome = run(capsys)
    assert outcome.exit_code == 6
    assert "not running from inside its repo" in outcome.printed


#######################################################################################
### Checks on the call to the database itself ###
#
# Every check above replaces ask_database(), so the driver work inside it is never
# exercised. These checks stand in for the neo4j driver instead, one level lower, so
# what the tool asks the driver to do is proven without Docker.


class FakeResult:
    """One answer from the driver, holding the rows a query came back with."""

    def __init__(self, records):
        self.records = records


class FakeDriver:
    """A neo4j driver that records what it was asked to do.

    It stands in for the real driver so that the order of the calls, the settings
    handed to it, and the closing of the connection can all be asserted without a
    database.
    """

    def __init__(self, records=None, fail_on_query=None):
        self.calls: list[str] = []
        self.records = records or [
            {
                "name": script.KERNEL_COMPONENT,
                "versions": ["5.26.29"],
                "edition": "community",
            }
        ]
        self.fail_on_query = fail_on_query

    def verify_connectivity(self) -> None:
        """Record that connectivity was verified."""
        self.calls.append("verify")

    def execute_query(self, query: str) -> FakeResult:
        """Record the query, then answer with the staged rows or raise."""
        self.calls.append("query")
        if self.fail_on_query is not None:
            raise self.fail_on_query
        return FakeResult(self.records)

    def close(self) -> None:
        """Record that the connection was closed."""
        self.calls.append("close")


def stand_in_for_the_driver(monkeypatch, driver: FakeDriver) -> dict:
    """Replace the neo4j driver with one that records what it was asked to do.

    Args:
        monkeypatch: pytest's patcher.
        driver: The fake driver every call gives back.

    Returns:
        The arguments the driver was built with, filled in when it is asked for.
    """
    built: dict = {}

    def build(uri, auth, connection_timeout):
        """Stand in for neo4j.GraphDatabase.driver and record its arguments."""
        built.update(uri=uri, auth=auth, connection_timeout=connection_timeout)
        return driver

    monkeypatch.setattr(neo4j.GraphDatabase, "driver", build)
    return built


SETTINGS = script.Settings(uri=URI, user=USER, password=PASSWORD)


@code("HRS0180")
@category("repository")
@objective("functionality")
@positive
def test_the_driver_is_built_from_the_settings_and_the_timeout(monkeypatch):
    """The driver is built with the address, user and password read from .env, and
    with the connection timeout the tool sets, so a database that is off gives up
    rather than hanging."""
    built = stand_in_for_the_driver(monkeypatch, FakeDriver())
    script.ask_database(SETTINGS)
    assert built["uri"] == URI
    assert built["auth"] == (USER, PASSWORD)
    assert built["connection_timeout"] == script.CONNECT_TIMEOUT_SECONDS


@code("HRS0181")
@category("repository")
@objective("functionality")
@positive
def test_connectivity_is_verified_before_the_query_is_sent(monkeypatch):
    """Connectivity is verified before the query is sent, so nothing answering fails
    at once instead of being retried for seconds with a warning on each attempt."""
    driver = FakeDriver()
    stand_in_for_the_driver(monkeypatch, driver)
    script.ask_database(SETTINGS)
    assert driver.calls == ["verify", "query", "close"]


@code("HRS0182")
@category("repository")
@objective("functionality")
@negative
def test_the_connection_is_closed_even_when_the_query_fails(monkeypatch):
    """A query that raises still leaves the connection closed, and the error reaches
    the caller unchanged so main() can turn it into the right exit code."""
    failure = neo4j.exceptions.ServiceUnavailable("nothing answered")
    driver = FakeDriver(fail_on_query=failure)
    stand_in_for_the_driver(monkeypatch, driver)
    with pytest.raises(neo4j.exceptions.ServiceUnavailable):
        script.ask_database(SETTINGS)
    assert driver.calls == ["verify", "query", "close"]


@code("HRS0183")
@category("repository")
@objective("functionality")
@positive
def test_the_version_is_taken_from_the_kernel_row(monkeypatch):
    """The version and edition come from the row naming the database kernel, not from
    another component's row, because the query answers with one row per component and
    the others carry versions of their own."""
    driver = FakeDriver(
        records=[
            {"name": "browser", "versions": ["1.2.3"], "edition": "other"},
            {
                "name": script.KERNEL_COMPONENT,
                "versions": ["5.26.29"],
                "edition": "community",
            },
        ]
    )
    stand_in_for_the_driver(monkeypatch, driver)
    assert script.ask_database(SETTINGS) == PINNED
