---
paths:
  - "src/**/*.py"
  - "validation/**/*.py"
  - ".claude/hooks/**/*.py"
---

# Writing a Python file

This rule covers every Python file the project writes. Each file is one of these kinds.

- the pipeline, the package under `src/sdg/`, which holds the pipeline's workflows and steps;
- the repo tools, the package under `src/sdgtools/`, which keep the repository's own files in order and are run as commands by a person or by the pre-commit hook, whose steps are in `.pre-commit-config.yaml`;
- the validation package under `src/sdgval/`, which holds the plugins that select the checks, put them in order, skip them and write their reports, and the commands that build the inventory and run the checks;
- the checks under `validation/`, which validate the three packages, the hooks and the repo's own files, with the code they share in `validation/shared/`;
- the Claude Code hooks under `.claude/hooks/`, which run around Claude's own tool calls in a session and hold it to the repo's rules.

Where a standard convention exists, the project follows it. The conventions in use are PEP 8, the Python style guide published as Python Enhancement Proposal 8, for layout and names, the Google layout for docstrings, ruff for formatting and linting, mypy for type checking, and pytest for checks. The project departs from a convention only where this rule says so, and says why.

The test of a well-written file is that a person who reads only its header block, its docstrings and its comments comes away with an accurate picture of what the file does. `src/sdg/sources/read_manifests.py` is the worked example.

A change to the code is a change to its description. Before finishing an edit, read the file's header block, the docstrings of the functions touched and the comments around the change, and rewrite whatever the change made untrue. A new function goes into Usage, a new error into the docstring that lists errors, a new failure into the Exit codes field, and a changed rule into the comment that explained the old one. A description that lags the code is a defect, not a cleanup for later.

## The header block

Every file opens with a docstring holding eight fields, in this order:

```
Script:      filename.py
Description: what it does, and any non-obvious constraint it operates under
Inputs:      files or services read, and whether they are read-only
Outputs:     what it writes to disk, or "nothing on disk"; and, for a module that hands results back, what it returns
Usage:       one line per invocation mode, with a real example
Exit codes:  each failure it can end on, as its exit number, sub-code and what happened
Date:        YYYY-MM-DD
Owner:       Jason Delosh
```

`Date` is the day the file was first committed, and it never changes. When a file last changed is git's answer: `git log -1 --format=%cd -- <file>`.

`Owner` is who is accountable for the file and who to ask about it, not who wrote it. Who wrote a line is git's answer: `git blame <file>`. `Owner` changes only when ownership transfers.

The one exception is `__init__.py`, which carries a one-paragraph docstring naming the folder instead of a header block. The pre-commit hook refuses a commit when any other file under `src/`, `validation/` or `.claude/hooks/` lacks the block or has its fields out of order. `conftest.py` carries the block like any other file: it is read by pytest rather than run by a person, and its `Usage` lines are the pytest commands that load it.

## Exit codes

A command's exit number names a broad group of failure, such as 9, "a service did not respond". The groups are `GROUPS` in `src/sdg/exit_codes.py`, and one number means the same group in every command. A sub-code, a short name in capitals such as `NEO4J-UNREACHABLE`, names the failure itself. Two failures share a sub-code only when they share an explanation and a fix.

`docs/exit_codes.csv` is the reference a person reads. It holds one row per sub-code, with the exit number, the group, what happened and what to do. A new failure gets a new row, and its group is chosen by the separating tests in the `DECISIONS.md` entry "Exit numbers name a broad group of failure, and a sub-code names the failure itself, decided 2026-09-29". A new group is added only when no group's test fits, to `GROUPS` and to the table in the same commit.

A command reports a failure through `fail()` or `finish()` in `src/sdg/exit_codes.py`. Each problem line starts with its sub-code, and the last line names the exit number, its group and the sub-code that decided it, as in `Exit 9: a service did not respond (NEO4J-UNREACHABLE)`. The code names each failure by its number and sub-code written together, as in `fail(say, 9, "NEO4J-UNREACHABLE", message)`, or by an error class's `exit_code` and `sub_code`.

A header's `Exit codes` field lists each failure its file can end on, one entry per sub-code, written as the number, the sub-code and what happened in the table's wording, for example `12  PINNED-FILE-NOT-DOWNLOADED  a pinned file has not been downloaded`. An entry may then add a bracketed aside saying what the failure means in that file. Everything before the bracket has to match the table, so an aside can explain a failure but never redefine it. `src/sdgtools/verify_headers.py` confirms each entry against the table, confirms that every number and sub-code the code names together is a row of the table, and refuses a command's header that leaves out a sub-code its code names or a number its `main()` returns. The pre-commit hook runs it.

Project exit numbers stop at 125, because a shell gives the numbers from 126 up meanings of its own.

Codes 1 and 2 keep Python's own meanings: an unhandled error exits 1, and the argument parser exits 2 on a bad command line. Their groups are "this repo's own code failed" and "the command line is wrong", so a failure of either kind that the code catches itself takes the same number.

## Sections inside a file

A file is divided into named sections, each marked with a two-line banner: a full-width line of `#`, then `### Section name ###`. The name is a short, plain label saying what the code in the section does. Anything more than a label goes in a comment beneath the banner, where a short description of the section is welcome. When a file holds different kinds of code, for example checks that the right thing works and checks that the wrong thing is refused, each kind gets its own section.

## Names, layout and types

Layout and naming follow PEP 8: four spaces per indent, `snake_case` for functions and variables, `PascalCase` for classes, `UPPER_CASE` for constants, and imports grouped as standard library, then third party, then this project. ruff enforces all of this, so none of it is done by hand.

Every function signature carries a type hint on each argument and on the return. Checks and pytest fixtures are exempt, because their arguments are the situation pytest staged for them, and a hint on each would only repeat its name.

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

A check's docstring opens with one paragraph saying what must be true for the check to pass. `src/sdgval/build_inventory.py` copies that paragraph, and only that paragraph, into the `expected_result` column of `validation/validation_inventory.csv`, so it has to stand on its own. Anything the opening paragraph needs, put in it. A further paragraph is welcome where the check needs one, usually to say how the situation was staged, and it stays in the file rather than going into the table. It starts with a letter or a digit, never with `=`, `+`, `-` or `@`, because a spreadsheet reads a cell opening with one of those as a formula, and `src/sdgval/build_inventory.py` refuses it. Whitespace at the front of the docstring is fine, because the generator strips it before it looks at the sentence.

## Comments

Every block whose purpose is not obvious carries a comment saying why it is there. So does every `try`/`except`, saying what it absorbs and what happens instead, and every workaround or non-standard library, saying what it works around. A comment never restates the code.

All writing in a file, meaning the header block, banners, docstrings and comments, is plain English in a non-technical voice: full sentences with verbs, concise, no fragments and no label with a colon standing in for a sentence. A long list written inline becomes bullets.

Heavy commenting is not licence for clever code. A block that needs a paragraph to explain gets rewritten.

## ruff and mypy

ruff and mypy confirm a file, and both are configured in `pyproject.toml`. The commands below run them from the repo root, in the `sdg` environment.

```powershell
ruff format .          # rewrap and reindent the Python files in src/, validation/ and .claude/hooks/ to the standard layout
ruff check .           # report style and lint problems in the same files; add --fix to apply the ones ruff can fix itself
mypy                   # confirm the type hints in src/, validation/ and .claude/hooks/
```

`check_python_files` runs the same steps in that order and reports what each found. It runs `ruff format` in check mode, which reports what it would change without changing it. The pre-commit hook runs `check_python_files`, so a file that fails any of them is refused before it lands, whoever made the edit.

Line length is the formatter's job alone. A line the formatter leaves long is a string, and a message split across lines is harder to grep for, so ruff's long-line check is off.

## Checks

What a check is, and the categories, objectives and staged cases its labels name, are defined in `validation/README.md`. A check is written at the top level of its check file, never inside a class, because the inventory and a validation report name a check by its function's name alone. `src/sdgval/build_inventory.py` refuses a check inside a class. The checks live under `validation/`, and they follow everything above plus these rules.

- A check's category and objective are decided before the check is written. The category is the thing the check confirms, and whatever it is compared against is the reference. The objective is what the check confirms about it, and it decides how the check is set up, what fixes a failure and who fixes it. Every check has exactly one of each. A check found to serve two objectives is split when the two parts would have different fixes or different owners.

- Each workflow, step, repo tool, plugin and hook has its own files of checks, one per aspect of quality, at the same relative path under `validation/` as the file under `src/`. Each is named `test_`, the file's name and the aspect, so the technical checks for `src/sdg/sources/fetch_file.py` are in `validation/sdg/sources/test_fetch_file_technical.py` and its integrity checks in `test_fetch_file_integrity.py` beside it. A check file holds checks of one aspect only, and `src/sdgval/build_inventory.py` refuses one that does not. The one exception to the mirroring is the Claude Code hooks, whose checks live under `validation/claude_hooks/`, because pytest does not look inside a folder whose name starts with a dot.
- Code that checks of more than one file share lives in `validation/shared/`, one file per job, and the fixtures built on it in `validation/conftest.py`, because pytest finds a shared fixture only there.
- A check finds one discrete issue, so that a failure names one thing to fix. It may look at several things to find that issue: a refusal and the message that explains it are one issue, and so are a report's verdict and the exit status it came from. A side effect of a refusal, such as a file left untouched, is its own check, because its fix is different. Two situations staged in one check are two checks, for example a stale `docs/commands.md` and a missing one. A sentence that needs "and" to say what the check proves is a sign to look again, not a rule in itself. A situation several checks look at is staged once, in a fixture. The same check over several inputs uses `pytest.mark.parametrize`.
- A check that runs once per value says, in simple, non-technical language, in the opening paragraph of its docstring what changes from one run to the next, because that paragraph reaches a report as `expected_result` on the row of every run. Each run carries a readable name, because the name reaches a report as `parameter`. A value that is a plain word, number or path names its run by itself. A value made of several parts, such as a group of arguments, is named with `ids=`, in words that say what that run stages.
- Every check carries a `@code` marker holding its permanent id, a `@category` marker and an `@objective` marker. `validation/validation_inventory.csv` is generated from these markers. `src/sdgval/build_inventory.py` reads them by asking pytest to collect the checks, the same way a validation report reads them. A check file imports the short names for them from `src/sdgval/labels.py`. There is no aspect marker: the aspect of quality is looked up from the objective, so it cannot disagree with it. A check that stages its own situation also carries `@positive`, for a working situation where the code is expected to succeed, or `@negative`, for a broken situation where the code is expected to refuse. A check that looks at something real carries neither. The case says how the check was set up, so any objective may carry one. `src/sdgval/build_inventory.py` refuses a check whose markers break these rules.
- Before changing a check, read the `version` and `fingerprint` entries in `validation/validation_inventory_dictionary.md`, because they say when `src/sdgval/build_inventory.py` refuses a changed check whose version did not move.
- A negative check breaks exactly one thing and says which in its docstring. It asserts the error raised or the exit number for that cause. When the command prints, the check also asserts that the exit line names the cause's sub-code, because several failures share one exit number, and that the message names that cause and its remedy rather than another. Under `--quiet`, the check asserts the exit number for the cause and that nothing is printed.
- A staged check touches nothing real and never downloads. Manifests and files are staged in a temporary folder through the fixtures in `validation/conftest.py`. Anything that downloads is replaced by a fake that serves bytes, or raises, per url. A workflow is called in-process through its `main()` with an argument list, never through a subprocess.
- A check that carries no case may read the real repo, because the real files are what it validates.
- A check that reads a real pinned file names it with `@needs_pinned`. `src/sdgval/skip_rules.py` then skips the check, with the reason, when the file is not downloaded or no longer matches its manifest entry. Only the stability check for that file fails for a changed file.
- A check that reads a file in `validation/fixtures/` names it with `@needs_fixture`, written as its name inside that folder, as in `@needs_fixture("usdm_three_classes.yml")`. A validation report then records which version of that file the check read, on the check's row and nowhere else.
- A check never asserts a count that grows as the pinned files under `inputs/` grow. It asserts that the known items are present, not that they are the only ones.

## Adding a check

1. Choose the file. It is the check file for the file under test and the aspect of quality, at the mirrored path under `validation/`, as the rules above describe. A new file needs its header block.
2. Give the check the next number above the highest id in `validation/validation_inventory.csv`.
3. Write the function with its `@code`, `@category` and `@objective` markers, and `@positive` or `@negative` when it stages its own situation. The names come from `src/sdgval/labels.py`.
4. Write the docstring's first paragraph as the sentence that must be true for the check to pass. It becomes the check's `expected_result`.
5. Run Cosmic Ray on the file the check covers, and confirm the check fails when the thing its sentence states is broken. A break elsewhere in the file that the check does not state is not its job. A check that passes either way proves nothing. How to run it is in `validation/running_validation.md`, under Proving that the checks can fail.
6. Run `build_inventory` to add its row. `build_inventory --check-status` confirms the hand-kept columns alone.
7. Commit the check and `validation/validation_inventory.csv` together.
