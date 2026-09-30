"""
Script:      test_check_api_key_technical.py
Description: Checks for src/sdgtools/check_api_key.py, the hand-run tool that
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

Usage:       pytest validation/sdgtools/test_check_api_key_technical.py
                 run these checks
             pytest validation/sdgtools/test_check_api_key_technical.py -v
                 one line per check with its result

Exit codes:  None of its own. It runs inside pytest.

Date:        2026-09-15
Owner:       Jason Delosh
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import anthropic

# The anthropic library declares its errors with the request and response types of
# httpx2, its own HTTP library, so the fake errors are built from httpx2 to match.
import httpx2
import pytest

from sdg.exit_codes import exit_line
from sdgtools import check_api_key as script
from sdgval.labels import category, code, negative, objective, positive

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


def answer(monkeypatch: pytest.MonkeyPatch, reply: str = REPLY) -> None:
    """Stand in for the call to the API with one that replies without a network.

    Args:
        monkeypatch: pytest's patcher, which undoes this when the check ends.
        reply: What the stand-in should hand back as the model's reply.
    """
    monkeypatch.setattr(script, "call_api", lambda key: reply)


def refuse(monkeypatch: pytest.MonkeyPatch, error: Exception) -> None:
    """Stand in for the call to the API with one that raises the given error.

    Args:
        monkeypatch: pytest's patcher, which undoes this when the check ends.
        error: The error the stand-in should raise.
    """

    def raise_it(key: str) -> str:
        """Stand in for the call to the API by raising the staged error."""
        raise error

    monkeypatch.setattr(script, "call_api", raise_it)


def run(capsys: pytest.CaptureFixture[str], *argv: str) -> Outcome:
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
# itself never reaches the screen, and the quiet option silences the report.


@code("SA00257")
@category("repository")
@objective("functionality")
@positive
def test_working_key_exits_0(working):
    """A key the API answers gives an exit code of 0."""
    assert working.exit_code == 0


@code("SA00258")
@category("repository")
@objective("functionality")
@positive
def test_working_key_reports_the_reply(working):
    """The report names the model that answered and repeats what it replied."""
    assert script.MODEL in working.printed
    assert REPLY in working.printed


@code("SA00259")
@category("repository")
@objective("functionality")
@positive
def test_the_key_is_never_printed(working):
    """The key itself is never printed, so it cannot end up in a terminal log."""
    assert KEY not in working.printed


@code("SA00260")
@category("repository")
@objective("functionality")
@positive
def test_quoted_key_is_read(repo, monkeypatch, capsys):
    """A key written with quotes around it, as a person might paste it, is read
    without them."""
    write_env(repo, f'ANTHROPIC_API_KEY="{KEY}"')
    assert script.read_key(repo / ".env") == KEY


@code("SA00506")
@category("repository")
@objective("functionality")
@positive
def test_quiet_prints_nothing_when_the_key_works(repo, monkeypatch, capsys):
    """With the quiet option, a key the API answers exits 0 and nothing at all is
    printed."""
    write_env(repo, f"ANTHROPIC_API_KEY={KEY}")
    answer(monkeypatch)
    outcome = run(capsys, "--quiet")
    assert outcome.exit_code == 0
    assert outcome.printed == ""


#######################################################################################
### Negative checks ###
#
# The wrong thing is refused, and each refusal is its own exit code with a message
# that names the cause and what to do about it. One thing is broken per check.
# With the quiet option, a refusal prints nothing and its exit code still names the
# cause.


@code("SA00261")
@category("repository")
@objective("functionality")
@negative
def test_quiet_missing_key_exits_4_and_prints_nothing(repo, monkeypatch, capsys):
    """With the quiet option, a missing key still exits 4, and nothing at all is
    printed."""
    write_env(repo, "ANTHROPIC_API_KEY=")
    outcome = run(capsys, "--quiet")
    assert outcome.exit_code == 4
    assert outcome.printed == ""


@code("SA00263")
@category("repository")
@objective("functionality")
@negative
def test_missing_env_file_is_refused(repo, capsys):
    """With no .env file at all, the run exits 4 and the message says to create it
    from the example."""
    outcome = run(capsys)
    assert outcome.exit_code == 4
    assert exit_line(4, "ENV-FILE-MISSING") in outcome.printed
    assert ".env does not exist" in outcome.printed
    assert "Copy-Item .env.example .env" in outcome.printed


@code("SA00264")
@category("repository")
@objective("functionality")
@negative
def test_empty_key_is_refused(repo, capsys):
    """With a .env whose key line is empty, the run exits 4 and the message says to
    paste the key into that file."""
    write_env(repo, "ANTHROPIC_API_KEY=")
    outcome = run(capsys)
    assert outcome.exit_code == 4
    assert exit_line(4, "API-KEY-MISSING") in outcome.printed
    assert "no value for ANTHROPIC_API_KEY" in outcome.printed
    assert "paste your key" in outcome.printed


@code("SA00265")
@category("repository")
@objective("functionality")
@negative
def test_rejected_key_is_reported_as_rejected(repo, monkeypatch, capsys):
    """When the API does not recognise the key, the run exits 10 and the message says
    the key was rejected and where to get a new one."""
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    refuse(
        monkeypatch,
        anthropic.AuthenticationError(
            "invalid x-api-key",
            response=httpx2.Response(401, request=request),
            body=None,
        ),
    )
    write_env(repo, f"ANTHROPIC_API_KEY={KEY}")
    outcome = run(capsys)
    assert outcome.exit_code == 10
    assert exit_line(10, "CLAUDE-API-KEY-REJECTED") in outcome.printed
    assert "rejected the key" in outcome.printed
    assert "console.anthropic.com" in outcome.printed


@code("SA00266")
@category("repository")
@objective("functionality")
@negative
def test_key_without_access_is_reported_as_an_account_problem(
    repo, monkeypatch, capsys
):
    """When the API knows the key but will not let it use the model, the run exits 10.
    The message says the key is right and points at the account, rather than saying to
    paste the key again."""
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    refuse(
        monkeypatch,
        anthropic.PermissionDeniedError(
            "permission denied",
            response=httpx2.Response(403, request=request),
            body=None,
        ),
    )
    write_env(repo, f"ANTHROPIC_API_KEY={KEY}")
    outcome = run(capsys)
    assert outcome.exit_code == 10
    assert exit_line(10, "CLAUDE-API-ACCESS-REFUSED") in outcome.printed
    assert "refused it access" in outcome.printed
    assert "the key is right" in outcome.printed
    assert "paste it again" not in outcome.printed


@code("SA00267")
@category("repository")
@objective("functionality")
@negative
def test_unreachable_api_is_reported_as_unreachable(repo, monkeypatch, capsys):
    """When the API cannot be reached at all, the run exits 9 and the message says
    to confirm the network connection rather than the key."""
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    refuse(monkeypatch, anthropic.APIConnectionError(request=request))
    write_env(repo, f"ANTHROPIC_API_KEY={KEY}")
    outcome = run(capsys)
    assert outcome.exit_code == 9
    assert exit_line(9, "CLAUDE-API-UNREACHABLE") in outcome.printed
    assert "could not be reached" in outcome.printed
    assert "confirm the network connection" in outcome.printed


@code("SA00268")
@category("repository")
@objective("functionality")
@negative
def test_an_error_the_api_answered_with_is_reported_with_its_message(
    repo, monkeypatch, capsys
):
    """When the API answers with an error that is neither a rejected key nor a failed
    connection, such as a retired model name, the run exits 11 and prints the API's own
    message."""
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    refuse(
        monkeypatch,
        anthropic.NotFoundError(
            "model: no-such-model",
            response=httpx2.Response(404, request=request),
            body=None,
        ),
    )
    write_env(repo, f"ANTHROPIC_API_KEY={KEY}")
    outcome = run(capsys)
    assert outcome.exit_code == 11
    assert exit_line(11, "CLAUDE-API-ERROR") in outcome.printed
    assert "answered with an error" in outcome.printed
    assert "no-such-model" in outcome.printed
    assert "confirm the network connection" not in outcome.printed


@code("SA00269")
@category("repository")
@objective("functionality")
@negative
def test_outside_the_repo_is_refused(tmp_path, monkeypatch, capsys):
    """When the sdg package is installed from outside the repo, the run exits 3 before it
    looks for a .env file."""

    def not_in_repo() -> Path:
        """Stand in for the repo check with the refusal it gives outside the repo."""
        raise script.NotInRepoError("sdg is not running from inside its repo")

    monkeypatch.setattr(script, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(script, "require_repo", not_in_repo)
    outcome = run(capsys)
    assert outcome.exit_code == 3
    assert exit_line(3, "NOT-IN-REPO") in outcome.printed
    assert "not running from inside its repo" in outcome.printed


#######################################################################################
### Checks on the call to the API itself ###
#
# Every check above replaces call_api(), so the client work inside it is never
# exercised. These checks stand in for the Anthropic client instead, one level lower,
# so what the tool sends and what it makes of the reply are proven without the network.


@dataclass(frozen=True)
class FakeBlock:
    """One block of a reply, of the shape the client hands back."""

    type: str
    text: str


class FakeMessages:
    """The messages part of the client, recording what it was asked to send."""

    def __init__(self, blocks: list[FakeBlock], sent: dict[str, object]) -> None:
        self.blocks = blocks
        self.sent = sent

    def create(self, **kwargs: object) -> object:
        """Record the request, then answer with the staged blocks."""
        self.sent.update(kwargs)
        return type("FakeResponse", (), {"content": self.blocks})()


def stand_in_for_the_client(
    monkeypatch: pytest.MonkeyPatch, blocks: list[FakeBlock]
) -> dict:
    """Replace the Anthropic client with one that records what it was asked to send.

    Args:
        monkeypatch: pytest's patcher.
        blocks: The blocks the staged reply is made of.

    Returns:
        The key the client was built with and the request it was given, filled in when
            the call is made.
    """
    sent: dict = {}

    def build(api_key: str) -> object:
        """Stand in for anthropic.Anthropic and record the key it was built with."""
        sent["api_key"] = api_key
        return type("FakeClient", (), {"messages": FakeMessages(blocks, sent)})()

    monkeypatch.setattr(anthropic, "Anthropic", build)
    return sent


@code("SA00270")
@category("repository")
@objective("functionality")
@positive
def test_the_request_carries_the_key_the_pinned_model_and_the_prompt(monkeypatch):
    """The call uses the key it was given and sends the pinned model, the prompt and the
    tool's reply limit. So the answer proves that key against that model, not against
    whatever is newest."""
    sent = stand_in_for_the_client(monkeypatch, [FakeBlock("text", REPLY)])
    script.call_api(KEY)
    assert sent["api_key"] == KEY
    assert sent["model"] == script.MODEL
    assert sent["max_tokens"] == script.MAX_TOKENS
    assert sent["messages"] == [{"role": "user", "content": script.PROMPT}]


@code("SA00271")
@category("repository")
@objective("functionality")
@positive
def test_the_reply_is_the_text_with_surrounding_spaces_removed(monkeypatch):
    """The reply handed back is the text of the first text block, with surrounding
    spaces and newlines removed, so the word the tool prints is the word the model
    sent and nothing around it."""
    stand_in_for_the_client(monkeypatch, [FakeBlock("text", f"  {REPLY}\n")])
    assert script.call_api(KEY) == REPLY


@code("SA00272")
@category("repository")
@objective("functionality")
@positive
def test_a_block_that_is_not_text_is_passed_over(monkeypatch):
    """A reply whose first block is not text gives back the first text block after it,
    because a reply may carry blocks of other kinds before the words."""
    stand_in_for_the_client(
        monkeypatch, [FakeBlock("thinking", "aside"), FakeBlock("text", REPLY)]
    )
    assert script.call_api(KEY) == REPLY


@code("SA00273")
@category("repository")
@objective("functionality")
@positive
def test_a_reply_with_no_text_gives_an_empty_answer(monkeypatch):
    """A reply with no text in it gives back an empty string instead of stopping with
    a Python error."""
    stand_in_for_the_client(monkeypatch, [FakeBlock("thinking", "aside")])
    assert script.call_api(KEY) == ""


#######################################################################################
### Every refusal with the quiet option ###
#
# With the quiet option, each refusal prints nothing and still exits with its own
# code. One check runs once per refusal.

API_REQUEST = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")


def outside_the_repo(repo: Path, monkeypatch: pytest.MonkeyPatch) -> int:
    """Stage an install from outside the repo, and give the code expected."""

    def not_in_repo() -> Path:
        """Stand in for the repo check with the refusal it gives outside the repo."""
        raise script.NotInRepoError("sdg is not running from inside its repo")

    monkeypatch.setattr(script, "require_repo", not_in_repo)
    return 3


def no_env_file(repo: Path, monkeypatch: pytest.MonkeyPatch) -> int:
    """Stage a repo with no .env file, and give the code expected."""
    return 4


def rejected_key(repo: Path, monkeypatch: pytest.MonkeyPatch) -> int:
    """Stage a key the API rejects, and give the code expected."""
    write_env(repo, f"ANTHROPIC_API_KEY={KEY}")
    refuse(
        monkeypatch,
        anthropic.AuthenticationError(
            "invalid x-api-key",
            response=httpx2.Response(401, request=API_REQUEST),
            body=None,
        ),
    )
    return 10


def key_without_access(repo: Path, monkeypatch: pytest.MonkeyPatch) -> int:
    """Stage a key the API knows but will not let use the model."""
    write_env(repo, f"ANTHROPIC_API_KEY={KEY}")
    refuse(
        monkeypatch,
        anthropic.PermissionDeniedError(
            "permission denied",
            response=httpx2.Response(403, request=API_REQUEST),
            body=None,
        ),
    )
    return 10


def unreachable_api(repo: Path, monkeypatch: pytest.MonkeyPatch) -> int:
    """Stage an API that cannot be reached, and give the code expected."""
    write_env(repo, f"ANTHROPIC_API_KEY={KEY}")
    refuse(monkeypatch, anthropic.APIConnectionError(request=API_REQUEST))
    return 9


def api_error(repo: Path, monkeypatch: pytest.MonkeyPatch) -> int:
    """Stage an error the API answers with, and give the code expected."""
    write_env(repo, f"ANTHROPIC_API_KEY={KEY}")
    refuse(
        monkeypatch,
        anthropic.NotFoundError(
            "model: no-such-model",
            response=httpx2.Response(404, request=API_REQUEST),
            body=None,
        ),
    )
    return 11


@code("SA00521")
@category("repository")
@objective("functionality")
@negative
@pytest.mark.parametrize(
    "stage",
    [
        outside_the_repo,
        no_env_file,
        rejected_key,
        key_without_access,
        unreachable_api,
        api_error,
    ],
    ids=[
        "outside the repo",
        "no .env file",
        "rejected key",
        "key without access",
        "unreachable API",
        "error from the API",
    ],
)
def test_every_refusal_is_silent_under_quiet(repo, monkeypatch, capsys, stage):
    """With the quiet option, a refusal prints nothing and still exits with its own
    code. It runs once for each refusal the tool can give other than a missing key."""
    expected = stage(repo, monkeypatch)
    outcome = run(capsys, "--quiet")
    assert outcome.printed == ""
    assert outcome.exit_code == expected
