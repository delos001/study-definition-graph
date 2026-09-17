"""
Script:      check_api_key.py
Description: Confirms the Anthropic API key in .env reaches the Claude API, so a
             key that was never pasted, or was pasted wrongly, is found at setup
             rather than part way through a pipeline run.

             The check sends one very small message and reads the reply. A call
             that only asked the API which models exist would prove the key is
             a real key, but not that it can generate anything, which is what
             the pipeline needs. The message costs a fraction of a cent.

             This is the one hand-run tool that needs the network and spends
             money, so it is not part of the set of checks README.md asks a
             person to run after setup.

Inputs:      .env at the repo root   (read-only)
             The Claude API          (one message, over the network)

Outputs:     Nothing on disk. Prints whether the key works, and what to do when
             it does not. The key itself is never printed.

Usage:       python repo_tools/check_api_key.py
                 send one message and report whether the key works
             python repo_tools/check_api_key.py --quiet
                 print nothing; use the exit code

Exit codes:  0   success (the key works)
             1   unhandled error, Python's own
             2   invalid command line, the argument parser's own
             6   not running from inside the repo
             27  the .env file has not been created
             28  .env has no Anthropic API key
             29  the Claude API rejected the key
             30  the Claude API could not be reached
             41  the Claude API answered with an error (a retired model name, an
                 exhausted balance, a rate limit; the API's own message is
                 printed)
             43  the Claude API refused the key access to what was asked (the
                 key is real, and the account it belongs to is not allowed to
                 use the model)
             The numbers are the repo-wide table in
             validation/exit_codes.csv.

Date:        2026-09-15
Owner:       Jason Delosh
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import anthropic

# The repo root comes from the sdg package, so this script needs the editable
# install (pip install -e ., README.md step 5) the same as the pipeline does.
from sdg.sources.read_manifests import REPO_ROOT, NotInRepoError, require_repo

#######################################################################################
### Settings ###

# The secrets file a person creates by copying .env.example. It is gitignored,
# so it exists only on the machine it was made on.
ENV_FILE = ".env"

# The line in that file this script reads. The rest of the file is left alone.
KEY_NAME = "ANTHROPIC_API_KEY"

# The model the test message goes to, written as the exact published identifier
# rather than a name that moves to whatever is newest. Recording the identifier
# is what lets a past result be reproduced.
MODEL = "claude-opus-5"

# The smallest exchange that still proves the key can generate text. The ceiling
# is high enough that the reply is never cut off part way.
PROMPT = "Reply with the single word: working"
MAX_TOKENS = 1024


#######################################################################################
### Failures this script reports ###


class EnvFileMissingError(Exception):
    """Raised when the repo has no .env file yet."""


class KeyMissingError(Exception):
    """Raised when .env exists but carries no Anthropic key."""


#######################################################################################
### Read the key ###


def read_key(env_path: Path) -> str:
    """Take the Anthropic key out of the secrets file.

    Args:
        env_path: The .env file to read.

    Returns:
        The key, with any surrounding quotes and spaces removed.

    Raises:
        EnvFileMissingError: The file does not exist.
        KeyMissingError: The file exists but the key line is absent or empty.
    """
    if not env_path.is_file():
        raise EnvFileMissingError(
            f"{ENV_FILE} does not exist at {env_path.parent}.\n"
            "  fix -> create it from the example with: Copy-Item .env.example .env"
        )

    key = ""
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{KEY_NAME}="):
            key = line.split("=", 1)[1].strip().strip("\"'")

    if not key:
        raise KeyMissingError(
            f"{ENV_FILE} has no value for {KEY_NAME}.\n"
            f"  fix -> open {ENV_FILE} and paste your key after {KEY_NAME}="
        )

    return key


#######################################################################################
### Ask the API ###


def call_api(key: str) -> str:
    """Send one small message to the Claude API and hand back what it replied.

    The call is kept in its own function so the checks under validation/ can stand in for it and
    never touch the network.

    Args:
        key: The Anthropic API key to authenticate with.

    Returns:
        The text of the reply, with surrounding spaces removed.

    Raises:
        anthropic.APIError: The API rejected the key, or could not be reached.
    """
    client = anthropic.Anthropic(api_key=key)
    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        messages=[{"role": "user", "content": PROMPT}],
    )
    reply = next((block.text for block in response.content if block.type == "text"), "")
    return reply.strip()


#######################################################################################
### Command line ###


def main(argv: list[str] | None = None) -> int:
    """Read the key from .env, send one message, and report whether it worked.

    Args:
        argv: The command-line arguments, or None to read the real ones.

    Returns:
        The exit code, as the header block lists them.
    """
    parser = argparse.ArgumentParser(
        description="Check that the Anthropic API key in .env reaches the Claude API."
    )
    parser.add_argument(
        "--quiet", action="store_true", help="print nothing; use the exit code"
    )
    args = parser.parse_args(argv)

    # The repo check runs first, so an install made outside the checkout is
    # reported as that rather than as a missing .env file.
    try:
        require_repo()
    except NotInRepoError as exc:
        if not args.quiet:
            print(exc)
        return 6

    try:
        key = read_key(REPO_ROOT / ENV_FILE)
    except EnvFileMissingError as exc:
        if not args.quiet:
            print(exc)
        return 27
    except KeyMissingError as exc:
        if not args.quiet:
            print(exc)
        return 28

    # Four causes, four remedies. A key the API does not recognise is fixed by
    # pasting the right one. A key the API recognises but will not let use the
    # model is an account problem, and pasting again fixes nothing, so it gets
    # its own code and remedy. A connection that never reached the API is a
    # network problem. Anything else the API answered, such as a retired model
    # name, an exhausted credit balance or a rate limit, is none of those, and
    # only the API's own message says what it was, so that message is printed.
    try:
        reply = call_api(key)
    except anthropic.AuthenticationError as exc:
        if not args.quiet:
            print(
                f"the Claude API rejected the key in {ENV_FILE} ({exc.__class__.__name__}).\n"
                f"  fix -> check the key at https://console.anthropic.com/ and paste it again"
            )
        return 29
    except anthropic.PermissionDeniedError as exc:
        if not args.quiet:
            print(
                f"the Claude API knows the key in {ENV_FILE} but refused it access to {MODEL} ({exc.__class__.__name__}).\n"
                "  fix -> the key is right; check the account it belongs to at https://console.anthropic.com/"
            )
        return 43
    except anthropic.APIConnectionError as exc:
        if not args.quiet:
            print(
                f"the Claude API could not be reached ({exc.__class__.__name__}).\n"
                "  fix -> check the network, then run this again"
            )
        return 30
    except anthropic.APIError as exc:
        if not args.quiet:
            print(
                f"the Claude API answered with an error ({exc.__class__.__name__}): {exc}\n"
                "  fix -> the key reached the API and the network is fine; act on the message above"
            )
        return 41

    if not args.quiet:
        print(f"the key in {ENV_FILE} works. {MODEL} replied: {reply}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
