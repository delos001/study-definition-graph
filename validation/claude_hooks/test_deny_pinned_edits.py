"""
Script:      test_deny_pinned_edits.py
Description: Checks for .claude/hooks/deny_pinned_edits.py, the Claude Code hook
             that refuses a Write or Edit to a pinned file or a hand-written
             manifest. Each check builds the message Claude Code would send,
             points the hook's repo root at pytest's own temporary folder
             through the CLAUDE_PROJECT_DIR variable, runs the hook's main()
             in-process with that message on stdin, and asserts the decision it
             printed, or that it printed nothing.

             The hook always exits 0, because its answer is the printed
             decision rather than the exit code, so these checks read what was
             printed. No check touches the real inputs/ or manifests/.

Inputs:      Nothing real. The repo root is pytest's own temporary folder, and the
             message is built in the check.

Outputs:     Writes nothing to disk.

Usage:       pytest validation/claude_hooks/test_deny_pinned_edits.py
                 run these checks
             pytest validation/claude_hooks/test_deny_pinned_edits.py -v
                 one line per check with its result

Exit codes:  pytest's own: 0 all passed, 1 some failed

Date:        2026-09-16
Owner:       Jason Delosh
"""

from __future__ import annotations

import io
import json
from dataclasses import dataclass
from pathlib import Path

import pytest

import deny_pinned_edits as hook

positive = pytest.mark.positive
negative = pytest.mark.negative
# Every check carries a @code line: its short, permanent id in
# validation/validation_inventory.csv, assigned once and never reused.
code = pytest.mark.code
# Every check carries an @objective line: what the check confirms about its target,
# one of the objectives validation/README.md defines.
objective = pytest.mark.objective
# Every check carries a @target line: what kind of thing the check confirms, one
# of the targets validation/README.md defines.
target = pytest.mark.target


#######################################################################################
### Shared staging ###
#
# One fixture stands a temporary folder in for the repo root, and one helper sends the
# hook a message and keeps what it decided. A message is what Claude Code sends before
# a Write or Edit: the tool's name, its input with the file path, and the session's
# working directory.


@dataclass(frozen=True)
class Outcome:
    """What one run of the hook produced."""

    exit_code: int
    printed: str

    @property
    def decision(self) -> dict | None:
        """The printed decision as data, or None when nothing was printed."""
        if not self.printed.strip():
            return None
        return json.loads(self.printed)["hookSpecificOutput"]

    @property
    def denied(self) -> bool:
        """Whether the hook refused the call."""
        decision = self.decision
        return decision is not None and decision["permissionDecision"] == "deny"

    @property
    def reason(self) -> str:
        """The sentence the hook gave for refusing, or an empty string."""
        decision = self.decision
        return decision["permissionDecisionReason"] if decision else ""


@pytest.fixture
def repo(tmp_path, monkeypatch) -> Path:
    """Give a check a temporary folder standing in for the repo root.

    Claude Code names the root in CLAUDE_PROJECT_DIR, and the hook reads it from
    there, so the variable is pointed at the temporary folder for the check.

    Returns:
        The folder standing in for the repo root.
    """
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    return tmp_path


def send(monkeypatch, capsys, message: str) -> Outcome:
    """Run the hook in-process with the given text on stdin.

    Args:
        monkeypatch: pytest's patcher, which undoes the stdin swap when the check ends.
        capsys: pytest's capture of what was printed.
        message: The text Claude Code would send, usually JSON.

    Returns:
        The exit code and what was printed, as an Outcome.
    """
    monkeypatch.setattr("sys.stdin", io.StringIO(message))
    exit_code = hook.main()
    return Outcome(exit_code, capsys.readouterr().out)


def edit(monkeypatch, capsys, file_path: str, cwd: str | None = None) -> Outcome:
    """Send the hook an Edit of the given path, as Claude Code would.

    Args:
        monkeypatch: pytest's patcher.
        capsys: pytest's capture of what was printed.
        file_path: The path Claude is about to edit, absolute or repo-relative.
        cwd: The session's working directory to put in the message, or None to leave
            it out.

    Returns:
        The exit code and what was printed, as an Outcome.
    """
    message: dict = {"tool_name": "Edit", "tool_input": {"file_path": file_path}}
    if cwd is not None:
        message["cwd"] = cwd
    return send(monkeypatch, capsys, json.dumps(message))


#######################################################################################
### Positive checks ###
#
# The right thing works: ordinary files, the project's own files under inputs/, the
# machine-written manifests and paths outside the repo are all allowed, the repo root
# is found the way the header says, and a malformed message never blocks work.


@code("CCH0001")
@target("repository")
@objective("correctness")
@positive
def test_an_ordinary_file_is_allowed(repo, monkeypatch, capsys):
    """A file outside inputs/ and manifests/ is allowed, and nothing is printed."""
    outcome = edit(monkeypatch, capsys, str(repo / "README.md"))
    assert outcome.exit_code == 0
    assert outcome.printed == ""


@code("CCH0002")
@target("repository")
@objective("correctness")
@positive
def test_the_inputs_readme_is_allowed(repo, monkeypatch, capsys):
    """The README.md the project writes into inputs/ itself is allowed."""
    assert not edit(monkeypatch, capsys, str(repo / "inputs" / "README.md")).denied


@code("CCH0003")
@target("repository")
@objective("correctness")
@positive
def test_a_nested_gitkeep_under_inputs_is_allowed(repo, monkeypatch, capsys):
    """A .gitkeep placeholder anywhere under inputs/ is allowed, since the project
    writes those itself."""
    path = repo / "inputs" / "study_documents" / ".gitkeep"
    assert not edit(monkeypatch, capsys, str(path)).denied


@code("CCH0004")
@target("repository")
@objective("correctness")
@positive
def test_a_study_manifest_is_allowed(repo, monkeypatch, capsys):
    """A manifest under manifests/study_documents/ is allowed, because the pipeline
    stage that downloads a study, not yet written, is meant to write those."""
    path = repo / "manifests" / "study_documents" / "NCT00000000.json"
    assert not edit(monkeypatch, capsys, str(path)).denied


@code("CCH0005")
@target("repository")
@objective("correctness")
@positive
def test_the_manifests_readme_is_allowed(repo, monkeypatch, capsys):
    """The README.md at the top of manifests/ is allowed, since only the .json
    manifests there are hand-written records."""
    assert not edit(monkeypatch, capsys, str(repo / "manifests" / "README.md")).denied


@code("CCH0006")
@target("repository")
@objective("correctness")
@positive
def test_a_path_outside_the_repo_is_allowed(
    repo, tmp_path_factory, monkeypatch, capsys
):
    """A file outside the repo is allowed, even one under a folder called inputs/,
    because the hook guards this repo's pinned files and nothing else."""
    elsewhere = tmp_path_factory.mktemp("elsewhere") / "inputs" / "x.pdf"
    assert not edit(monkeypatch, capsys, str(elsewhere)).denied


@code("CCH0007")
@target("repository")
@objective("correctness")
@positive
def test_the_project_dir_outranks_the_message_cwd(
    repo, tmp_path_factory, monkeypatch, capsys
):
    """A path under another folder's inputs/ is allowed when the session has moved
    into that folder, so the message's cwd is not what the hook takes as the repo
    root."""
    other = tmp_path_factory.mktemp("other")
    outcome = edit(monkeypatch, capsys, str(other / "inputs" / "x.pdf"), cwd=str(other))
    assert not outcome.denied


@code("CCH0008")
@target("repository")
@objective("correctness")
@positive
def test_the_message_cwd_is_used_when_the_variable_is_absent(
    tmp_path, monkeypatch, capsys
):
    """Without CLAUDE_PROJECT_DIR, the message's cwd stands in as the repo root."""
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    outcome = edit(
        monkeypatch, capsys, str(tmp_path / "inputs" / "x.pdf"), cwd=str(tmp_path)
    )
    assert outcome.denied


@code("CCH0009")
@target("repository")
@objective("correctness")
@positive
def test_a_malformed_message_is_allowed(repo, monkeypatch, capsys):
    """A message that is not the JSON Claude Code sends is allowed, with nothing
    printed, so a malformed message can never block ordinary work."""
    outcome = send(monkeypatch, capsys, "not json at all")
    assert outcome.exit_code == 0
    assert outcome.printed == ""


@code("CCH0010")
@target("repository")
@objective("correctness")
@positive
def test_a_message_without_a_path_is_allowed(repo, monkeypatch, capsys):
    """A well-formed message that names no file path is allowed, since there is
    nothing to judge."""
    outcome = send(
        monkeypatch, capsys, json.dumps({"tool_name": "Edit", "tool_input": {}})
    )
    assert outcome.exit_code == 0
    assert outcome.printed == ""


@code("CCH0011")
@target("repository")
@objective("correctness")
@positive
def test_a_refusal_is_printed_in_the_form_claude_code_reads(repo, monkeypatch, capsys):
    """A refusal is printed as the JSON Claude Code reads: a PreToolUse event with the
    decision deny and a reason, and the exit code stays 0."""
    outcome = edit(monkeypatch, capsys, str(repo / "inputs" / "x.pdf"))
    assert outcome.exit_code == 0
    assert outcome.decision is not None
    assert outcome.decision["hookEventName"] == "PreToolUse"
    assert outcome.decision["permissionDecision"] == "deny"
    assert outcome.decision["permissionDecisionReason"]


#######################################################################################
### Negative checks ###
#
# The wrong thing is refused, and the reason names the path and says where the file
# is meant to come from instead.


@code("CCH0016")
@target("repository")
@objective("correctness")
@negative
def test_a_pinned_file_is_refused_from_another_folder(
    repo, tmp_path_factory, monkeypatch, capsys
):
    """A file under the real repo's inputs/ is refused even when the message says the
    session has moved into another folder, so the root really is the project folder
    and not the current one."""
    other = tmp_path_factory.mktemp("other")
    outcome = edit(monkeypatch, capsys, str(repo / "inputs" / "x.pdf"), cwd=str(other))
    assert outcome.denied
    assert "inputs/x.pdf" in outcome.reason


@code("CCH0012")
@target("repository")
@objective("correctness")
@negative
def test_a_pinned_file_is_refused(repo, monkeypatch, capsys):
    """A file directly under inputs/ is refused, and the reason names the path and
    says such files arrive through acquire_sources."""
    outcome = edit(monkeypatch, capsys, str(repo / "inputs" / "x.pdf"))
    assert outcome.denied
    assert "inputs/x.pdf" in outcome.reason
    assert "acquire_sources" in outcome.reason


@code("CCH0013")
@target("repository")
@objective("correctness")
@negative
def test_a_nested_pinned_file_is_refused(repo, monkeypatch, capsys):
    """A file deep under inputs/ is refused the same as one at the top, because the
    rule is the folder and not a list."""
    path = repo / "inputs" / "standards" / "cdisc" / "usdm_v4" / "dataStructure.yml"
    outcome = edit(monkeypatch, capsys, str(path))
    assert outcome.denied
    assert "inputs/standards/cdisc/usdm_v4/dataStructure.yml" in outcome.reason


@code("CCH0014")
@target("repository")
@objective("correctness")
@negative
def test_a_hand_written_manifest_is_refused(repo, monkeypatch, capsys):
    """A .json manifest at the top of manifests/ is refused, and the reason says a
    re-pin is recorded in DECISIONS.md and made by a person."""
    outcome = edit(monkeypatch, capsys, str(repo / "manifests" / "cdisc_usdm_v4.json"))
    assert outcome.denied
    assert "hand-written manifest" in outcome.reason
    assert "DECISIONS.md" in outcome.reason


@code("CCH0015")
@target("repository")
@objective("correctness")
@negative
def test_a_relative_path_is_judged_against_the_repo_root(repo, monkeypatch, capsys):
    """A repo-relative path is resolved against the repo root before it is judged, so
    writing inputs/x.pdf without a folder in front is still refused."""
    outcome = edit(monkeypatch, capsys, "inputs/x.pdf")
    assert outcome.denied
    assert "inputs/x.pdf" in outcome.reason
