"""
Script:      test_build_index.py
Description: Automated checks for src/sdgtools/build_index.py, which generates
             src/sdgtools/README.md from each script's header block and, under
             --check, is the pre-commit hook that blocks a commit whose index
             is stale. Each check writes one or two small scripts to a
             temporary folder, points the generator at it, and asserts what it
             writes or which exit code it returns. One check runs --check on
             the real src/sdgtools/ folder, the same check the pre-commit hook, .githooks/pre-commit, runs.

Inputs:      src/sdgtools/*.py and src/sdgtools/README.md  (read-only; the one real-folder check)

Outputs:     Writes nothing outside pytest's own temporary folder.

Usage:       pytest validation/sdgtools/test_build_index.py
                 run these checks
             pytest validation/sdgtools/test_build_index.py -v
                 one line per check with its result

Exit codes:  pytest's own: 0 all passed, 1 some failed

Date:        2026-09-04
Owner:       Jason Delosh
"""

from __future__ import annotations

import pytest

from sdgtools import build_index as bi

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

# A complete header in this repo's convention: a two-line first paragraph, a
# second paragraph that must not reach the index, and a Usage whose relative
# indentation must survive.
GOOD_HEADER = '''"""
Script:      alpha.py
Description: Does the first thing,
             continued on a second line.

             A second paragraph the index must leave out.

Inputs:      nothing
Outputs:     nothing
Usage:       python repo_tools/alpha.py
                 run it
             python repo_tools/alpha.py --flag
                 run it with a flag
Exit codes:  0 fine
Date:        2026-09-04
Owner:       Jason Delosh
"""
'''

EXPECTED_ENTRY = """## alpha.py

Does the first thing, continued on a second line.

```
python repo_tools/alpha.py
    run it
python repo_tools/alpha.py --flag
    run it with a flag
```
"""


#######################################################################################
### Helpers ###


@pytest.fixture
def folder(tmp_path, monkeypatch):
    """Produces a function that takes {filename: source} and writes those
    scripts to a temporary folder the generator is pointed at, with the index
    path beside them, and hands back that folder."""
    scripts = tmp_path / "repo_tools"
    scripts.mkdir()
    monkeypatch.setattr(bi, "SCRIPTS_DIR", scripts)
    monkeypatch.setattr(bi, "INDEX_PATH", scripts / "README.md")

    def make(files: dict[str, str]):
        """Write the given scripts into the folder and hand the folder back.

        Args:
            files: The scripts to write, source text keyed by file name.

        Returns:
            The folder the generator is pointed at.
        """
        for name, source in files.items():
            (scripts / name).write_text(source, encoding="utf-8")
        return scripts

    return make


#######################################################################################
### Generating the index ###


@pytest.fixture
def written(folder, capsys):
    """Stage one script with a complete header, run the generator, and hand back the
    exit code, the index it wrote and what it printed."""
    scripts = folder({"alpha.py": GOOD_HEADER})
    exit_code = bi.main([])
    text = (scripts / "README.md").read_text(encoding="utf-8")
    return exit_code, text, capsys.readouterr().out


@code("SA00241")
@category("repository")
@objective("functionality")
@positive
def test_writes_the_entry_from_the_header(written):
    """src/sdgtools/README.md holds each script's name, the first paragraph of its Description
    joined to one line, and its Usage block with the relative indentation kept."""
    _, text, _ = written
    assert EXPECTED_ENTRY in text


@code("SA00242")
@category("repository")
@objective("functionality")
@positive
def test_the_second_paragraph_is_left_out(written):
    """Only the first paragraph of a Description reaches src/sdgtools/README.md; the rest stays in
    the header."""
    _, text, _ = written
    assert "second paragraph" not in text


@code("SA00243")
@category("repository")
@objective("functionality")
@positive
def test_the_index_opens_with_the_title_and_the_notice(written):
    """src/sdgtools/README.md opens with its title and the notice saying it is generated, so
    nobody edits it by hand."""
    _, text, _ = written
    assert text.startswith("# src/sdgtools/\n\n" + bi.GENERATED_NOTICE)


@code("SA00244")
@category("repository")
@objective("functionality")
@positive
def test_the_index_ends_with_one_newline(written):
    """src/sdgtools/README.md ends with exactly one newline, so a regenerated file compares equal
    to itself and --check does not fail on whitespace."""
    _, text, _ = written
    assert text.endswith("```\n") and not text.endswith("\n\n")


@code("SA00245")
@category("repository")
@objective("functionality")
@positive
def test_the_index_is_written_with_lf_line_endings(folder):
    """src/sdgtools/README.md is written with a bare line feed (LF) ending each line
    whatever machine regenerates it, so the file does not flip endings between one
    run and the next.

    It is read as bytes, because reading as text would hide a carriage return."""
    scripts = folder({"alpha.py": GOOD_HEADER})
    assert bi.main([]) == 0
    raw = (scripts / "README.md").read_bytes()
    assert b"\r" not in raw


@code("SA00246")
@category("repository")
@objective("functionality")
@positive
def test_writing_reports_the_file_and_the_count(written):
    """A run that writes src/sdgtools/README.md exits 0 and says which file it wrote and how many
    scripts it holds."""
    exit_code, _, printed = written
    assert exit_code == 0
    assert "src/sdgtools/README.md written, 1 script(s)" in printed


@code("SA00247")
@category("repository")
@objective("functionality")
@positive
def test_scripts_are_listed_in_name_order(folder):
    """Two scripts appear in alphabetical order whatever order they were
    written, so src/sdgtools/README.md is stable between runs."""
    scripts = folder(
        {"zeta.py": GOOD_HEADER.replace("alpha", "zeta"), "alpha.py": GOOD_HEADER}
    )
    assert bi.main([]) == 0
    text = (scripts / "README.md").read_text(encoding="utf-8")
    assert text.index("## alpha.py") < text.index("## zeta.py")


#######################################################################################
### --check, the pre-commit hook ###


@code("SA00248")
@category("repository")
@objective("functionality")
@positive
def test_check_passes_when_index_is_current(folder, capsys):
    """With the check option, the run exits 0 and writes nothing when src/sdgtools/README.md
    on disk equals what would be generated."""
    scripts = folder({"alpha.py": GOOD_HEADER})
    assert bi.main([]) == 0
    before = (scripts / "README.md").stat().st_mtime_ns
    assert bi.main(["--check"]) == 0
    assert (scripts / "README.md").stat().st_mtime_ns == before
    assert "is current, 1 script(s)" in capsys.readouterr().out


@code("SA00249")
@category("repository")
@objective("functionality")
@negative
def test_check_fails_when_index_is_missing(folder, capsys):
    """With the check option and no index on disk, the run exits 15, names the command
    to run, and writes nothing."""
    scripts = folder({"alpha.py": GOOD_HEADER})
    assert bi.main(["--check"]) == 15
    assert not (scripts / "README.md").exists()
    assert "stale. Run: build_index" in capsys.readouterr().out


@code("SA00250")
@category("repository")
@objective("functionality")
@negative
def test_check_fails_when_index_is_stale(folder, capsys):
    """With the check option and an index that no longer matches the headers, the run
    exits 15, names the command to run, and leaves the stale index as it was."""
    scripts = folder({"alpha.py": GOOD_HEADER})
    bi.main([])
    stale = (scripts / "README.md").read_text(encoding="utf-8")
    folder(
        {"alpha.py": GOOD_HEADER.replace("Does the first thing", "Does another thing")}
    )
    capsys.readouterr()
    assert bi.main(["--check"]) == 15
    assert (scripts / "README.md").read_text(encoding="utf-8") == stale
    assert "stale. Run: build_index" in capsys.readouterr().out


@code("SA00251")
@category("repository")
@objective("functionality")
@positive
def test_quiet_prints_nothing(folder, capsys):
    """With the quiet option, nothing is printed; the exit code is the whole
    report."""
    folder({"alpha.py": GOOD_HEADER})
    assert bi.main(["--quiet"]) == 0
    assert capsys.readouterr().out == ""


#######################################################################################
### Refusing a bad header, one exit code each ###


@code("SA00252")
@category("repository")
@objective("functionality")
@negative
def test_missing_field_exits_17_and_writes_nothing(folder, capsys):
    """A header missing required fields exits 17, naming the script and every
    missing field, and src/sdgtools/README.md is not written."""
    scripts = folder(
        {
            "alpha.py": GOOD_HEADER.replace("Outputs:     nothing\n", "").replace(
                "Owner:       Jason Delosh\n", ""
            )
        }
    )
    assert bi.main([]) == 17
    assert not (scripts / "README.md").exists()
    out = capsys.readouterr().out
    assert "alpha.py: header missing Outputs, Owner" in out
    assert "Index not written" in out


@code("SA00253")
@category("repository")
@objective("functionality")
@negative
def test_no_docstring_exits_17(folder, capsys):
    """A script with no module docstring has no header block at all: exit 17,
    saying so."""
    folder({"alpha.py": "print('hello')\n"})
    assert bi.main([]) == 17
    assert "alpha.py: no module docstring" in capsys.readouterr().out


@code("SA00254")
@category("repository")
@objective("functionality")
@negative
def test_unparseable_script_exits_19_and_outranks_17(folder, capsys):
    """A script that is not valid Python exits 19, and 19 outranks 17 when another
    script's header is also incomplete; both problems are still named."""
    folder({"alpha.py": "def broken(:\n", "beta.py": "print('no header')\n"})
    assert bi.main([]) == 19
    out = capsys.readouterr().out
    assert "alpha.py: cannot parse" in out
    assert "beta.py: no module docstring" in out


@code("SA00255")
@category("repository")
@objective("functionality")
@negative
def test_no_scripts_exits_20(folder, capsys):
    """An empty scripts folder exits 20."""
    folder({})
    assert bi.main([]) == 20
    assert "no scripts found" in capsys.readouterr().out


#######################################################################################
### The real src/sdgtools/ folder ###


@code("SA00256")
@category("repository")
@objective("correctness")
def test_real_index_is_current():
    """src/sdgtools/README.md matches the headers of the real scripts, which is the
    check the pre-commit hook runs."""
    assert bi.main(["--check", "--quiet"]) == 0
