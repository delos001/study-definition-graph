"""
Script:      test_check_api_key.py
Description: Checks for repo_tools/check_api_key.py, the hand-run tool that
             confirms the Anthropic key in .env reaches the Claude API. Each
             check writes a .env file into pytest's own temporary folder, points
             the tool's repo root at it, stands in for the one function that
             calls the API, runs the tool's main() in-process, and asserts the
             exit code or the message the header promises for that state.

             No check reaches the network or reads the real .env, so none of
             them costs anything or depends on a key being present.

Inputs:      Nothing real. The .env files are written to pytest's own temporary
             folder, and the call to the Claude API is replaced by a stand-in.

Outputs:     Writes nothing to disk. Temporary files go to pytest's own folder.

Usage:       pytest validation/repo_tools/test_check_api_key.py
                 run these checks
             pytest validation/repo_tools/test_check_api_key.py -v
                 one line per check with its result

Exit codes:  pytest's own: 0 all passed, 1 some failed

Date:        2026-09-15
Owner:       Jason Delosh
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import anthropic
import httpx
import pytest

import check_api_key as script

positive = pytest.mark.positive
negative = pytest.mark.negative
# Every check carries a @code line: its short, permanent id in
# validation/validation_inventory.csv, assigned once and never reused.
code = pytest.mark.code

KEY = "sk-ant-test-key"
REPLY = "working"


#######################################################################################
### Shared staging ###
#
# One fixture builds the repo every check starts from: a temporary folder standing in
# for the repo root, with the repo check satisfied so that only the state a check
# stages can decide the outcome. The helpers write a .env file and stand in for the
# call to the API.


@dataclass(frozen=True)
class Outcome:
    """What one run of the tool produced."""

    exit_code: int
    printed: str


@pytest.fixture
def repo(tmp_path, monkeypatch) -> Path:
    """Give a check a temporary folder standing in for the repo root.

    The tool reads .env from the repo root and refuses to run outside the repo. Both
    are settled here, so each check stages only the one thing it is about.

    Returns:
        The folder standing in for the repo root.
    """
    monkeypatch.setattr(script, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(script, "require_repo", lambda: tmp_path)
    return tmp_path


def write_env(repo: Path, line: str) -> None:
    """Write a .env file holding the given line, with the other settings around it.

    Args:
        repo: The folder standing in for the repo root.
        line: The Anthropic key line to write.
    """
    (repo / ".env").write_text(
        f"# comment\n{line}\nNEO4J_USER=neo4j\n", encoding="utf-8"
    )


def answer(monkeypatch, reply: str = REPLY) -> None:
    """Stand in for the call to the API with one that replies without a network.

    Args:
        monkeypatch: pytest's patcher, which undoes this when the check ends.
        reply: What the stand-in should hand back as the model's reply.
    """
    monkeypatch.setattr(script, "call_api", lambda key: reply)


def refuse(monkeypatch, error: Exception) -> None:
    """Stand in for the call to the API with one that raises the given error.

    Args:
        monkeypatch: pytest's patcher, which undoes this when the check ends.
        error: The error the stand-in should raise.
    """

    def raise_it(key: str) -> str:
        raise error

    monkeypatch.setattr(script, "call_api", raise_it)


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
    """Stage a .env holding a key, with the API replying, and run the tool."""
    write_env(repo, f"ANTHROPIC_API_KEY={KEY}")
    answer(monkeypatch)
    return run(capsys)


#######################################################################################
### Positive checks ###
#
# The right thing works: a key that the API answers is reported as working, the key
# itself never reaches the screen, and the quiet option silences the report without
# changing the exit code.


@code("HRS0068")
@positive
def test_working_key_exits_0(working):
    """A key the API answers gives an exit code of 0."""
    assert working.exit_code == 0


@code("HRS0069")
@positive
def test_working_key_reports_the_reply(working):
    """The report names the model that answered and repeats what it replied."""
    assert script.MODEL in working.printed
    assert REPLY in working.printed


@code("HRS0070")
@positive
def test_the_key_is_never_printed(working):
    """The key itself is never printed, so it cannot end up in a terminal log."""
    assert KEY not in working.printed


@code("HRS0071")
@positive
def test_quoted_key_is_read(repo, monkeypatch, capsys):
    """A key written with quotes around it, as a person might paste it, is read
    without them."""
    write_env(repo, f'ANTHROPIC_API_KEY="{KEY}"')
    assert script.read_key(repo / ".env") == KEY


@code("HRS0072")
@positive
def test_quiet_prints_nothing(repo, monkeypatch, capsys):
    """With the quiet option, nothing at all is printed."""
    write_env(repo, "ANTHROPIC_API_KEY=")
    assert run(capsys, "--quiet").printed == ""


@code("HRS0073")
@positive
def test_quiet_keeps_the_exit_code(repo, monkeypatch, capsys):
    """With the quiet option, the exit code still reports the missing key."""
    write_env(repo, "ANTHROPIC_API_KEY=")
    assert run(capsys, "--quiet").exit_code == 28


#######################################################################################
### Negative checks ###
#
# The wrong thing is refused, and each refusal is its own exit code with a message
# that names the cause and what to do about it. One thing is broken per check.


@code("HRS0074")
@negative
def test_missing_env_file_is_refused(repo, capsys):
    """With no .env file at all, the run exits 27 and the message says to create it
    from the example."""
    outcome = run(capsys)
    assert outcome.exit_code == 27
    assert ".env does not exist" in outcome.printed
    assert "Copy-Item .env.example .env" in outcome.printed


@code("HRS0075")
@negative
def test_empty_key_is_refused(repo, capsys):
    """With a .env whose key line is empty, the run exits 28 and the message says to
    paste the key into that file."""
    write_env(repo, "ANTHROPIC_API_KEY=")
    outcome = run(capsys)
    assert outcome.exit_code == 28
    assert "no value for ANTHROPIC_API_KEY" in outcome.printed
    assert "paste your key" in outcome.printed


@code("HRS0076")
@negative
def test_rejected_key_is_reported_as_rejected(repo, monkeypatch, capsys):
    """When the API refuses the key, the run exits 29 and the message says the key
    was rejected and where to get a new one."""
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    refuse(
        monkeypatch,
        anthropic.AuthenticationError(
            "invalid x-api-key",
            response=httpx.Response(401, request=request),
            body=None,
        ),
    )
    write_env(repo, f"ANTHROPIC_API_KEY={KEY}")
    outcome = run(capsys)
    assert outcome.exit_code == 29
    assert "rejected the key" in outcome.printed
    assert "console.anthropic.com" in outcome.printed


@code("HRS0077")
@negative
def test_unreachable_api_is_reported_as_unreachable(repo, monkeypatch, capsys):
    """When the API cannot be reached at all, the run exits 30 and the message says
    to check the network rather than the key."""
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    refuse(monkeypatch, anthropic.APIConnectionError(request=request))
    write_env(repo, f"ANTHROPIC_API_KEY={KEY}")
    outcome = run(capsys)
    assert outcome.exit_code == 30
    assert "could not be reached" in outcome.printed
    assert "check the network" in outcome.printed


@code("HRS0078")
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
