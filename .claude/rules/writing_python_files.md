---
paths:
  - "src/**/*.py"
  - "scripts/**/*.py"
  - "tests/**/*.py"
---

# Writing a Python file

These rules apply to every Python file the project writes. Where a standard convention exists, follow it; the project departs from a convention only where this file says so. Reading only the header, docstrings and comments must give an accurate picture of what the file does. `src/sdg/sources/read_manifests.py` is the worked example.

## Header block

Every file opens with:

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

`Date` is the day the file was first committed and never changes; when a file last changed is git's answer. `Owner` is who is accountable for the file, not who wrote it, and changes only when ownership transfers.

## Layout, names and types

- PEP 8: 4-space indents, snake_case functions and variables, PascalCase classes, UPPER_CASE constants, imports grouped as standard library, third party, local.
- Every function signature carries type hints, including the return type. Test files are exempt, since a check takes its arguments from pytest fixtures.
- Catch specific exceptions, never a bare `except`.
- Section banners group the file into named sections, two lines each: a full-width line of `#`, then `### Section name ###`. The label is short and says what the code in the section does; context goes in a comment beneath it. Each kind of code gets its own section.
- Formatting and linting are ruff's job and type checking is mypy's, not the reader's. Both are configured in `pyproject.toml`.

## Docstrings and comments

- Every function has a docstring in the Google layout: a one-line summary, then `Args:`, `Returns:` and `Raises:` sections, each present when it applies. After the summary, say why the function works the way it does where that is not obvious.
- Every non-obvious block, every `try`/`except` (what it absorbs, what happens instead) and every workaround or non-standard library carries a comment saying why. A comment never restates the code.
- All markup, meaning headers, banners, docstrings and comments, is plain English in full sentences, concise, in a non-technical voice. A long inline list becomes bullets.
- Heavy commenting is not licence for clever code. A block that needs a paragraph to explain gets rewritten.

## Test files

- One test file per code file, at the mirrored path under `tests/`, carrying the code file's name: `tests/sources/test_fetch_file.py` tests `src/sdg/sources/fetch_file.py`.
- Each check proves one promise; a claim that uses "and" one or more times is more than one check. A situation several checks look at is staged once in a fixture. Repeated cases use `parametrize`.
- Each check carries `@positive` or `@negative` and a `@code` marker holding its id from `tests/validation_inventory.csv`. Its docstring summary line is the sentence the inventory shows.
- A negative check breaks one thing and asserts the error type and that the message names the cause and its remedy.
- A check touches nothing real and never downloads: files are staged in a temporary folder through the `conftest.py` fixtures, the network is replaced by a fake, and a workflow runs in-process through its `main()`. A check that needs a pinned file skips, with that reason, when it is absent.
- No count that drifts as the corpus grows. Assert the known items are present, not that they are the only ones.
