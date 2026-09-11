---
paths:
  - "src/**/*.py"
  - "scripts/**/*.py"
  - "tests/**/*.py"
---

# Writing a Python file

This rule covers every Python file the project writes. There are three kinds:

- the package under `src/sdg/`, which holds the pipeline's workflows and steps, the code other code imports;
- the hand-run scripts under `scripts/`, which a person runs from a terminal;
- the checks under `tests/`, which prove the package and the scripts do what they say.

Where a standard convention exists, the project follows it. The conventions in use are PEP 8 for layout and names, the Google layout for docstrings, ruff for formatting and linting, mypy for type checking, and pytest for checks. The project departs from a convention only where this rule says so, and says why.

The test of a well-written file is that a person who reads only its header block, its docstrings and its comments comes away with an accurate picture of what the file does. `src/sdg/sources/read_manifests.py` is the worked example.

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

The one exception is `__init__.py`, which carries a one-paragraph docstring naming the folder instead of a header block. The pre-commit hook refuses a commit when any other file under `src/sdg/` or `scripts/` lacks the block or has its fields out of order.

## Sections inside a file

A file is divided into named sections, each marked with a two-line banner: a full-width line of `#`, then `### Section name ###`. The name is a short, plain label saying what the code in the section does. Anything more than a label goes in a comment beneath the banner, where a short description of the section is welcome. When a file holds different kinds of code, for example checks that the right thing works and checks that the wrong thing is refused, each kind gets its own section.

## Names, layout and types

Layout and naming follow PEP 8: four spaces per indent, `snake_case` for functions and variables, `PascalCase` for classes, `UPPER_CASE` for constants, and imports grouped as standard library, then third party, then this project. ruff enforces all of this, so none of it is done by hand.

Every function signature carries a type hint on each argument and on the return. Checks under `tests/` are exempt, because a check's arguments are the situation pytest staged for it, and a hint on each would only repeat its name.

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

A check's docstring is the summary line alone: one plain sentence saying what the check proves. That sentence is copied into `tests/validation_inventory.csv`, so it has to stand on its own.

## Comments

Every block whose purpose is not obvious carries a comment saying why it is there. So does every `try`/`except`, saying what it absorbs and what happens instead, and every workaround or non-standard library, saying what it works around. A comment never restates the code.

All writing in a file, meaning the header block, banners, docstrings and comments, is plain English in a non-technical voice: full sentences with verbs, concise, no fragments and no label with a colon standing in for a sentence. A long list written inline becomes bullets.

Heavy commenting is not licence for clever code. A block that needs a paragraph to explain gets rewritten.

## ruff and mypy

Three tool runs check a file, and all three are configured in `pyproject.toml`. From the repo root, in the `sdg` environment:

```powershell
ruff format .          # rewrap and reindent every file to the standard layout
ruff check .           # report style and lint problems; add --fix to apply the ones ruff can fix itself
mypy                   # check the type hints in src/, scripts/ and tests/
```

`python scripts/check_python_files.py` runs all three in that order and reports what each found. The pre-commit hook runs it, so a file that fails any of them is refused before it lands, whoever made the edit.

Line length is the formatter's job alone. A line the formatter leaves long is a string, and a message split across lines is harder to grep for, so ruff's long-line check is off.

## Checks

A check is one pytest function that proves one promise the code makes. The checks live under `tests/`, and they follow everything above plus these rules.

- Each workflow, step and hand-run script has its own file of checks, at the same relative path under `tests/`, named `test_` plus the file's name. The checks for `src/sdg/sources/fetch_file.py` are in `tests/sources/test_fetch_file.py`.
- A check proves one promise. If the sentence saying what it proves uses "and", it is more than one check. A situation several checks look at is staged once, in a fixture, and each check asserts one thing about it. The same check over several inputs uses `pytest.mark.parametrize`.
- Every check carries `@positive`, meaning the right thing works, or `@negative`, meaning the wrong thing is refused, and a `@code` marker holding its permanent id from `tests/validation_inventory.csv`.
- A negative check breaks exactly one thing, says which in its docstring, and asserts two things: the type of error raised, and that the message names that cause and its remedy rather than another.
- A check touches nothing real and never downloads. Manifests and files are staged in a temporary folder through the fixtures in `tests/conftest.py`. Anything that downloads is replaced by a fake that serves bytes, or raises, per url. A workflow is called in-process through its `main()` with an argument list, never through a subprocess. A check that needs a pinned file skips, with that reason, when the file is absent.
- A check never asserts a count that grows as the corpus grows. It asserts that the known items are present, not that they are the only ones.
