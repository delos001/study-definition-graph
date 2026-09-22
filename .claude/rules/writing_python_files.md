---
paths:
  - "src/**/*.py"
  - "repo_tools/**/*.py"
  - "validation/**/*.py"
  - ".claude/hooks/**/*.py"
---

# Writing a Python file

This rule covers every Python file the project writes. There are four kinds:

- the package under `src/sdg/`, which holds the pipeline's workflows and steps, the code other code imports;
- the repo tools under `repo_tools/`, which keep the repository's own files in order and are run by a person or by the pre-commit hook, `.githooks/pre-commit`;
- the checks under `validation/`, which validate the package, the scripts, the hooks and the repo's own files;
- the Claude Code hooks under `.claude/hooks/`, which run around Claude's own tool calls in a session and hold it to the repo's rules.

Where a standard convention exists, the project follows it. The conventions in use are PEP 8 for layout and names, the Google layout for docstrings, ruff for formatting and linting, mypy for type checking, and pytest for checks. The project departs from a convention only where this rule says so, and says why.

The test of a well-written file is that a person who reads only its header block, its docstrings and its comments comes away with an accurate picture of what the file does. `src/sdg/sources/read_manifests.py` is the worked example.

A change to the code is a change to its description. Before finishing an edit, read the file's header block, the docstrings of the functions touched and the comments around the change, and rewrite whatever the change made untrue. A new function goes into Usage, a new error into the docstring that lists errors, a new exit code into the Exit codes field, and a changed rule into the comment that explained the old one. A description that lags the code is a defect, not a cleanup for later.

## The header block

Every file opens with a docstring holding eight fields, in this order:

```
Script:      filename.py
Description: what it does, and any non-obvious constraint it operates under
Inputs:      files or services read, and whether they are read-only
Outputs:     what it writes to disk, or "nothing on disk"; and, for a module that hands results back, what it returns
Usage:       one line per invocation mode, with a real example
Exit codes:  each code and what causes it
Date:        YYYY-MM-DD
Owner:       Jason Delosh
```

`Date` is the day the file was first committed, and it never changes. When a file last changed is git's answer: `git log -1 --format=%cd -- <file>`.

`Owner` is who is accountable for the file and who to ask about it, not who wrote it. Who wrote a line is git's answer: `git blame <file>`. `Owner` changes only when ownership transfers.

The one exception is `__init__.py`, which carries a one-paragraph docstring naming the folder instead of a header block. The pre-commit hook refuses a commit when any other file under `src/sdg/`, `repo_tools/`, `validation/` or `.claude/hooks/` lacks the block or has its fields out of order. `conftest.py` carries the block like any other file: it is read by pytest rather than run by a person, and its `Usage` lines are the pytest commands that load it.

## Exit codes

One number means one cause across the whole repo, so a person who learns what a code means in one script knows what it means in every other. The table is `validation/exit_codes.csv`, one row per code. A header's `Exit codes` field lists only the codes that file can return, each opening with the table's wording. An entry may then add a bracketed aside saying what the cause means in that file, for example `8   a pinned file has not been downloaded (a dry run only; a real run fetches it)`. Everything before the bracket has to match the table, so an aside can explain a cause but never redefine it. `repo_tools/verify_headers.py` checks this and the pre-commit hook runs it. It also reads each file's `main()` and refuses a header that does not list a code the function returns as a plain number. A new cause takes the next unused number and is added to the table in the same commit. Two causes share a number only when they share a fix.

Codes 1 and 2 are Python's own and are never assigned to anything else: an unhandled error exits 1, and the argument parser exits 2 on a bad command line.

## Sections inside a file

A file is divided into named sections, each marked with a two-line banner: a full-width line of `#`, then `### Section name ###`. The name is a short, plain label saying what the code in the section does. Anything more than a label goes in a comment beneath the banner, where a short description of the section is welcome. When a file holds different kinds of code, for example checks that the right thing works and checks that the wrong thing is refused, each kind gets its own section.

## Names, layout and types

Layout and naming follow PEP 8: four spaces per indent, `snake_case` for functions and variables, `PascalCase` for classes, `UPPER_CASE` for constants, and imports grouped as standard library, then third party, then this project. ruff enforces all of this, so none of it is done by hand.

Every function signature carries a type hint on each argument and on the return. Checks under `validation/` are exempt, because a check's arguments are the situation pytest staged for it, and a hint on each would only repeat its name.

An `except` names the error it catches. A bare `except`, which catches everything, is never used.

## Docstrings

Every function and class has a docstring in the Google layout: one summary line, then `Args:`, `Returns:` and `Raises:` sections, each present when it applies. After the summary, a paragraph says why the function works the way it does, where that is not obvious from the code. For example:

```python
def fetch(entry: Entry, destination: Path) -> Path:
    """Download one recorded file to its temporary name.

    The file lands under a .part name, so a transfer that stops part way never
    leaves behind something that looks finished.

    Args:
        entry: The manifest entry naming the url and the file it records.
        destination: Where the finished file will live.

    Returns:
        The path of the .part file that was written.

    Raises:
        FetchError: The server answered with an error, or the transfer stopped part way.
    """
```

A check's docstring opens with one paragraph saying what must be true for the check to pass. `repo_tools/build_inventory.py` copies that paragraph, and only that paragraph, into the `expected_result` column of `validation/validation_inventory.csv`, so it has to stand on its own. Anything the opening paragraph needs, put in it. A further paragraph is welcome where the check needs one, usually to say how the situation was staged, and it stays in the file rather than going into the table. It starts with a word, never with `=`, `+`, `-` or `@`, because a spreadsheet reads a cell that starts with one of those as a formula, and `repo_tools/build_inventory.py` refuses it.

## Comments

Every block whose purpose is not obvious carries a comment saying why it is there. So does every `try`/`except`, saying what it absorbs and what happens instead, and every workaround or non-standard library, saying what it works around. A comment never restates the code.

All writing in a file, meaning the header block, banners, docstrings and comments, is plain English in a non-technical voice: full sentences with verbs, concise, no fragments and no label with a colon standing in for a sentence. A long list written inline becomes bullets.

Heavy commenting is not licence for clever code. A block that needs a paragraph to explain gets rewritten.

## ruff and mypy

Three tool runs check a file, and all three are configured in `pyproject.toml`. From the repo root, in the `sdg` environment:

```powershell
ruff format .          # rewrap and reindent every file to the standard layout
ruff check .           # report style and lint problems; add --fix to apply the ones ruff can fix itself
mypy                   # check the type hints in src/, repo_tools/, validation/ and .claude/hooks/
```

`python repo_tools/check_python_files.py` runs all three in that order and reports what each found. The pre-commit hook runs it, so a file that fails any of them is refused before it lands, whoever made the edit.

Line length is the formatter's job alone. A line the formatter leaves long is a string, and a message split across lines is harder to grep for, so ruff's long-line check is off.

## Checks

A check is one pytest function that validates one thing, for one category and one objective. The checks live under `validation/`, and they follow everything above plus these rules. The categories, the objectives and the staged cases they refer to are defined in `validation/validation_inventory_dictionary.md`.

- A check's category and objective are decided before the check is written. The category is the thing the check confirms, and whatever it is compared against is the reference. The objective is what the check confirms about it, and it decides how the check is set up, what fixes a failure and who fixes it. Every check has exactly one of each. A check found to serve two objectives is split when the two parts would have different fixes or different owners.

- Each workflow, step, hand-run script and hook has its own file of checks, at the same relative path under `validation/`, named `test_` plus the file's name. The checks for `src/sdg/sources/fetch_file.py` are in `validation/sources/test_fetch_file.py`. The one exception is the Claude Code hooks, whose checks live under `validation/claude_hooks/`, because pytest does not look inside a folder whose name starts with a dot.
- A check finds one discrete issue, so that a failure names one thing to fix. It may look at several things to find that issue: a refusal and the message that explains it are one issue, and so are a report's verdict and the exit status it came from. Two situations staged in one check are two checks, for example a stale `repo_tools/README.md` and a missing one. A sentence that needs "and" to say what the check proves is a sign to look again, not a rule in itself. A situation several checks look at is staged once, in a fixture. The same check over several inputs uses `pytest.mark.parametrize`.
- Every check carries a `@code` marker holding its permanent id from `validation/validation_inventory.csv`, a `@category` marker and an `@objective` marker. A correctness check that stages its own situation also carries `@positive`, for a working situation where the code is expected to succeed, or `@negative`, for a broken situation where the code is expected to refuse. A correctness check that looks at something real carries neither, and so does a check of any other objective. `repo_tools/build_inventory.py` refuses a check whose markers break these rules.
- A negative check breaks exactly one thing, says which in its docstring, and asserts two things: the type of error raised, and that the message names that cause and its remedy rather than another.
- A staged check touches nothing real and never downloads. Manifests and files are staged in a temporary folder through the fixtures in `validation/conftest.py`. Anything that downloads is replaced by a fake that serves bytes, or raises, per url. A workflow is called in-process through its `main()` with an argument list, never through a subprocess.
- A check that carries no case may read the real repo, because the real files are what it validates.
- A check that reads a real pinned file names it with `@needs_pinned`. `validation/conftest.py` then skips the check, with the reason, when the file is not downloaded or no longer matches its manifest entry. Only the stability check for that file fails for a changed file.
- A check never asserts a count that grows as the pinned files under `inputs/` grow. It asserts that the known items are present, not that they are the only ones.
