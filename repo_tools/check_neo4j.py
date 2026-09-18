"""
Script:      check_neo4j.py
Description: Confirms the project's Neo4j database is running, accepts the login
             in .env, and is the version pinned in docker-compose.yml, so a
             database that is off, was started the wrong way, or has drifted to
             another version is found at setup rather than part way through a
             graph load.

             The check asks the database to name its own version and edition,
             then compares the answer with the image tag in docker-compose.yml.
             Reaching the database and logging in are proven on the way, because
             the question cannot be asked otherwise. The version comparison is
             the point. The compose file pins the version so a failure can be
             attributed. A container started outside the compose file, for
             example from the run button in Docker Desktop, does not carry that
             pin.

             This tool needs Docker running with the container up, so it is not
             part of the pre-commit hook, .githooks/pre-commit. It is one of the checks README.md asks
             a person to run after setup.

Inputs:      .env at the repo root             (read-only; the three NEO4J_ lines)
             docker-compose.yml at the repo root (read-only; the pinned image tag)
             The Neo4j database                (one query, over the local network)

Outputs:     Nothing on disk. Prints whether the database answers and matches
             its pin, and what to do when it does not. The password is never
             printed.

Usage:       python repo_tools/check_neo4j.py
                 ask the database its version and report whether it matches
             python repo_tools/check_neo4j.py --quiet
                 print nothing; use the exit code

Exit codes:  0   success (the database answers and is the pinned version)
             1   unhandled error, Python's own
             2   invalid command line, the argument parser's own
             6   not running from inside the repo
             13  a file on disk cannot be read (docker-compose.yml is missing or
                 names no Neo4j image)
             27  the .env file has not been created
             37  .env has no Neo4j connection settings
             38  Neo4j could not be reached
             39  Neo4j rejected the login
             40  the running Neo4j is not the pinned version
             44  the Neo4j address in .env is not a valid address (the driver
                 refused the NEO4J_URI line before trying to connect)
             The numbers are the repo-wide table in
             validation/exit_codes.csv.

Date:        2026-09-16
Owner:       Jason Delosh
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

import neo4j
import yaml

# The repo root comes from the sdg package, so this script needs the editable
# install (pip install -e ., README.md step 5) the same as the pipeline does.
from sdg.sources.read_manifests import REPO_ROOT, NotInRepoError, require_repo

#######################################################################################
### Settings ###

# The secrets file a person creates by copying .env.example. It is gitignored,
# so it exists only on the machine it was made on.
ENV_FILE = ".env"

# The three lines in that file this script reads. The rest of the file is left alone.
SETTING_NAMES = ("NEO4J_URI", "NEO4J_USER", "NEO4J_PASSWORD")

# The file that pins the database version. The image tag inside it, for example
# neo4j:5.26.29-community, carries the version and the edition after the colon.
COMPOSE_FILE = "docker-compose.yml"
COMPOSE_SERVICE = "neo4j"

# The question put to the database. It answers with one row per component; the
# kernel row carries the server's version and edition.
VERSION_QUERY = "CALL dbms.components() YIELD name, versions, edition RETURN name, versions, edition"
KERNEL_COMPONENT = "Neo4j Kernel"

# How long to wait for the database before deciding it cannot be reached. A
# container that is off refuses at once; this only bounds a hung connection.
CONNECT_TIMEOUT_SECONDS = 10.0


#######################################################################################
### Failures this script reports ###


class EnvFileMissingError(Exception):
    """Raised when the repo has no .env file yet."""


class SettingsMissingError(Exception):
    """Raised when .env exists but one or more Neo4j lines are absent or empty."""


class ComposeFileError(Exception):
    """Raised when docker-compose.yml cannot be read or names no Neo4j image."""


#######################################################################################
### What is read and what is found ###


@dataclass(frozen=True)
class Settings:
    """The three connection settings read from .env."""

    uri: str
    user: str
    password: str


@dataclass(frozen=True)
class Release:
    """One Neo4j release, as a version and an edition, for example 5.26.29 community."""

    version: str
    edition: str

    def __str__(self) -> str:
        """Give the version and edition as one phrase, the way the compose tag reads."""
        return f"{self.version} {self.edition}"


#######################################################################################
### Read the settings ###


def read_settings(env_path: Path) -> Settings:
    """Take the three Neo4j connection settings out of the secrets file.

    Args:
        env_path: The .env file to read.

    Returns:
        The address, user and password, with any surrounding quotes and spaces removed.

    Raises:
        EnvFileMissingError: The file does not exist.
        SettingsMissingError: The file exists but a setting is absent or empty.
    """
    if not env_path.is_file():
        raise EnvFileMissingError(
            f"{ENV_FILE} does not exist at {env_path.parent}.\n"
            "  fix -> create it from the example with: Copy-Item .env.example .env"
        )

    found: dict[str, str] = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        for name in SETTING_NAMES:
            if line.startswith(f"{name}="):
                found[name] = line.split("=", 1)[1].strip().strip("\"'")

    missing = [name for name in SETTING_NAMES if not found.get(name)]
    if missing:
        raise SettingsMissingError(
            f"{ENV_FILE} has no value for {', '.join(missing)}.\n"
            f"  fix -> copy the NEO4J_ lines from .env.example into {ENV_FILE}"
        )

    return Settings(found["NEO4J_URI"], found["NEO4J_USER"], found["NEO4J_PASSWORD"])


def read_pinned_release(compose_path: Path) -> Release:
    """Read the pinned Neo4j version and edition out of docker-compose.yml.

    The image tag is written neo4j:<version>-<edition>. Nothing else in the
    compose file is read, so the file's other settings can change freely.

    Args:
        compose_path: The docker-compose.yml to read.

    Returns:
        The pinned version and edition.

    Raises:
        ComposeFileError: The file is missing, is not YAML, or names no Neo4j image
            in the expected form.
    """
    if not compose_path.is_file():
        raise ComposeFileError(
            f"{COMPOSE_FILE} does not exist at {compose_path.parent}.\n"
            "  fix -> restore it from git; it pins the database version"
        )

    # A compose file that is not YAML, or is YAML of the wrong shape, is reported
    # as unreadable rather than crashing, so the fix is named.
    try:
        content = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
        image = content["services"][COMPOSE_SERVICE]["image"]
    except (yaml.YAMLError, KeyError, TypeError) as exc:
        raise ComposeFileError(
            f"{COMPOSE_FILE} names no image for the {COMPOSE_SERVICE} service ({exc.__class__.__name__}).\n"
            f"  fix -> restore the services.{COMPOSE_SERVICE}.image line, for example neo4j:5.26.29-community"
        ) from exc

    _, sep, tag = str(image).partition(":")
    version, dash, edition = tag.partition("-")
    if not (sep and dash and version and edition):
        raise ComposeFileError(
            f"{COMPOSE_FILE} pins the image as {image!r}, which is not in the form neo4j:<version>-<edition>.\n"
            f"  fix -> write the image line as, for example, neo4j:5.26.29-community"
        )

    return Release(version, edition)


#######################################################################################
### Ask the database ###


def ask_database(settings: Settings) -> Release:
    """Connect to the database and ask it which version and edition it is running.

    The call is kept in its own function so the checks under validation/ can stand in for it and
    never need Docker.

    Args:
        settings: The address, user and password to connect with.

    Returns:
        The version and edition the database reports for itself.

    Raises:
        neo4j.exceptions.ConfigurationError: The address is not one the driver
            accepts, so no connection was tried.
        neo4j.exceptions.ServiceUnavailable: Nothing answered at the address.
        neo4j.exceptions.AuthError: The database refused the user or password.
    """
    driver = neo4j.GraphDatabase.driver(
        settings.uri,
        auth=(settings.user, settings.password),
        connection_timeout=CONNECT_TIMEOUT_SECONDS,
    )
    # Connectivity is verified first because it fails at once when nothing
    # answers. Going straight to the query would have the driver retry for
    # some seconds, printing a warning on each attempt, before giving up.
    try:
        driver.verify_connectivity()
        result = driver.execute_query(VERSION_QUERY)
    finally:
        driver.close()

    kernel = next(row for row in result.records if row["name"] == KERNEL_COMPONENT)
    return Release(str(kernel["versions"][0]), str(kernel["edition"]))


#######################################################################################
### Command line ###


def main(argv: list[str] | None = None) -> int:
    """Read the settings and the pin, ask the database, and report whether they agree.

    Args:
        argv: The command-line arguments, or None to read the real ones.

    Returns:
        The exit code, as the header block lists them.
    """
    parser = argparse.ArgumentParser(
        description="Check that the Neo4j database is running, accepts the login in .env, and is the pinned version."
    )
    parser.add_argument(
        "--quiet", action="store_true", help="print nothing; use the exit code"
    )
    args = parser.parse_args(argv)

    def report(message: str) -> None:
        """Print a message, unless --quiet was given."""
        if not args.quiet:
            print(message)

    # The repo check runs first, so an install made outside the checkout is
    # reported as that rather than as a missing .env file.
    try:
        require_repo()
    except NotInRepoError as exc:
        report(str(exc))
        return 6

    # A missing .env and a .env with no Neo4j lines have different fixes, so each
    # gets its own exit code.
    try:
        settings = read_settings(REPO_ROOT / ENV_FILE)
    except EnvFileMissingError as exc:
        report(str(exc))
        return 27
    except SettingsMissingError as exc:
        report(str(exc))
        return 37

    # The pin is read before the database is asked, so a broken compose file is
    # reported even when the database is off.
    try:
        pinned = read_pinned_release(REPO_ROOT / COMPOSE_FILE)
    except ComposeFileError as exc:
        report(str(exc))
        return 13

    # A refused login is caught first, because it means the settings are wrong.
    # An address the driver will not accept is caught next, and before the
    # driver's general error, because it is a kind of that error and would
    # otherwise be reported as a database that is off. Anything else means
    # nothing answered at the address at all.
    try:
        running = ask_database(settings)
    except neo4j.exceptions.AuthError as exc:
        report(
            f"Neo4j at {settings.uri} rejected the login for user {settings.user!r} ({exc.__class__.__name__}).\n"
            f"  fix -> make NEO4J_USER and NEO4J_PASSWORD in {ENV_FILE} match the NEO4J_AUTH line in {COMPOSE_FILE}"
        )
        return 39
    except neo4j.exceptions.ConfigurationError as exc:
        report(
            f"the Neo4j address {settings.uri!r} in {ENV_FILE} is not a valid address ({exc.__class__.__name__}).\n"
            "  fix -> make the NEO4J_URI line in .env match .env.example, for example bolt://localhost:7687"
        )
        return 44
    except (neo4j.exceptions.ServiceUnavailable, neo4j.exceptions.DriverError) as exc:
        report(
            f"Neo4j could not be reached at {settings.uri} ({exc.__class__.__name__}).\n"
            "  fix -> start the container from the repo folder with: docker compose up -d"
        )
        return 38

    if running != pinned:
        report(
            f"the running Neo4j is {running}, but {COMPOSE_FILE} pins {pinned}.\n"
            "  fix -> stop whatever is answering at that address, then start the pinned\n"
            "         container from the repo folder with: docker compose up -d"
        )
        return 40

    report(f"Neo4j at {settings.uri} answers and is the pinned version, {running}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
