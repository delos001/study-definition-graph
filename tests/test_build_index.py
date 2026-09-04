"""
Script:      test_build_index.py
Description: Automated checks for scripts/build_index.py, which generates
             scripts/README.md from each script's header block and, under
             --check, is the pre-commit hook that blocks a commit whose index
             is stale. Each check writes one or two small scripts to a
             temporary folder, points the generator at it, and asserts what it
             writes or which exit code it returns. One check runs --check on
             the real scripts/ folder, the same check the hook runs.

Inputs:      scripts/*.py and scripts/README.md  (read-only; the one real-folder check)

Outputs:     Writes nothing outside pytest's own temporary folder.

Usage:       pytest tests/test_build_index.py
                 run these checks
             pytest tests/test_build_index.py -v
                 one line per check with its result

Exit codes:  pytest's own: 0 all passed, 1 some failed

Date:        2026-09-04
Owner:       Jason Delosh
"""

from __future__ import annotations

import pytest

import build_index as bi

positive = pytest.mark.positive
negative = pytest.mark.negative

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
Usage:       python scripts/alpha.py
                 run it
             python scripts/alpha.py --flag
                 run it with a flag
Exit codes:  0 fine
Date:        2026-09-04
Owner:       Jason Delosh
"""
'''

EXPECTED_ENTRY = """## alpha.py

Does the first thing, continued on a second line.

```
python scripts/alpha.py
    run it
python scripts/alpha.py --flag
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
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    monkeypatch.setattr(bi, "SCRIPTS_DIR", scripts)
    monkeypatch.setattr(bi, "INDEX_PATH", scripts / "README.md")

    def make(files: dict[str, str]):
        for name, source in files.items():
            (scripts / name).write_text(source, encoding="utf-8")
        return scripts

    return make


#######################################################################################
### Generating the index ###


@positive
def test_writes_first_paragraph_and_usage_with_indent_kept(folder, capsys):
    """The index holds each script's name, the first paragraph of its
    Description joined to one line, and its Usage block with the relative
    indentation kept; the second paragraph is left out. Exit 0."""
    scripts = folder({"alpha.py": GOOD_HEADER})
    assert bi.main([]) == 0
    text = (scripts / "README.md").read_text(encoding="utf-8")
    assert text.startswith("# scripts/\n\n" + bi.GENERATED_NOTICE)
    assert EXPECTED_ENTRY in text
    assert "second paragraph" not in text
    assert text.endswith("```\n") and not text.endswith("\n\n")
    assert "scripts/README.md written, 1 script(s)" in capsys.readouterr().out


@positive
def test_scripts_are_listed_in_name_order(folder):
    """Two scripts appear in alphabetical order whatever order they were
    written, so the index is stable between runs."""
    scripts = folder({"zeta.py": GOOD_HEADER.replace("alpha", "zeta"), "alpha.py": GOOD_HEADER})
    assert bi.main([]) == 0
    text = (scripts / "README.md").read_text(encoding="utf-8")
    assert text.index("## alpha.py") < text.index("## zeta.py")


#######################################################################################
### --check, the pre-commit hook ###


@positive
def test_check_passes_when_index_is_current(folder, capsys):
    """--check exits 0 and writes nothing when the index on disk equals what
    would be generated."""
    scripts = folder({"alpha.py": GOOD_HEADER})
    assert bi.main([]) == 0
    before = (scripts / "README.md").stat().st_mtime_ns
    assert bi.main(["--check"]) == 0
    assert (scripts / "README.md").stat().st_mtime_ns == before
    assert "is current, 1 script(s)" in capsys.readouterr().out


@negative
def test_check_fails_when_index_is_stale_or_missing(folder, capsys):
    """--check exits 1, naming the command to run, when the index is missing
    or no longer matches the headers; nothing is written either way."""
    scripts = folder({"alpha.py": GOOD_HEADER})
    assert bi.main(["--check"]) == 1
    assert not (scripts / "README.md").exists()
    assert "stale. Run: python scripts/build_index.py" in capsys.readouterr().out

    bi.main([])
    folder({"alpha.py": GOOD_HEADER.replace("Does the first thing", "Does another thing")})
    assert bi.main(["--check"]) == 1


@positive
def test_quiet_prints_nothing(folder, capsys):
    """--quiet prints nothing; the exit code is the whole report."""
    folder({"alpha.py": GOOD_HEADER})
    assert bi.main(["--quiet"]) == 0
    assert capsys.readouterr().out == ""


#######################################################################################
### Refusing a bad header, one exit code each ###


@negative
def test_missing_field_exits_2_and_writes_nothing(folder, capsys):
    """A header missing required fields exits 2, naming the script and every
    missing field, and the index is not written."""
    scripts = folder({"alpha.py": GOOD_HEADER.replace("Outputs:     nothing\n", "").replace("Owner:       Jason Delosh\n", "")})
    assert bi.main([]) == 2
    assert not (scripts / "README.md").exists()
    out = capsys.readouterr().out
    assert "alpha.py: header missing Outputs, Owner" in out
    assert "Index not written" in out


@negative
def test_no_docstring_exits_2(folder, capsys):
    """A script with no module docstring has no header block at all: exit 2,
    saying so."""
    folder({"alpha.py": "print('hello')\n"})
    assert bi.main([]) == 2
    assert "alpha.py: no module docstring" in capsys.readouterr().out


@negative
def test_unparseable_script_exits_3_and_outranks_2(folder, capsys):
    """A script that is not valid Python exits 3, and 3 outranks 2 when another
    script's header is also incomplete; both problems are still named."""
    folder({"alpha.py": "def broken(:\n", "beta.py": "print('no header')\n"})
    assert bi.main([]) == 3
    out = capsys.readouterr().out
    assert "alpha.py: cannot parse" in out
    assert "beta.py: no module docstring" in out


@negative
def test_no_scripts_exits_3(folder, capsys):
    """An empty scripts folder exits 3."""
    folder({})
    assert bi.main([]) == 3
    assert "no scripts found" in capsys.readouterr().out


#######################################################################################
### The real scripts/ folder ###


@positive
def test_real_index_is_current():
    """scripts/README.md matches the headers of the real scripts, which is the
    check the pre-commit hook runs."""
    assert bi.main(["--check", "--quiet"]) == 0
