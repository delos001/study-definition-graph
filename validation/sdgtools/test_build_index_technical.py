"""
Script:      test_build_index_technical.py
Description: Automated checks for src/sdgtools/build_index.py, which generates
             docs/commands.md from the header block of each command that
             pyproject.toml installs and, under --check, is the pre-commit hook
             step that blocks a commit whose page is stale. Each check stages a
             small repo in a temporary folder, with a pyproject.toml listing one
             or more commands and the files they run, points the generator at it,
             and asserts what it writes or which exit code it returns. The run of
             --check on the real repo, the same run the pre-commit hook makes, is
             in test_build_index_integrity.py, beside this file.

Inputs:      Nothing real. Each staged repo is written to pytest's own temporary
             folder.

Outputs:     Writes nothing outside pytest's own temporary folder.

Usage:       pytest validation/sdgtools/test_build_index_technical.py
                 run these checks
             pytest validation/sdgtools/test_build_index_technical.py -v
                 one line per check with its result

Exit codes:  None of its own. It runs inside pytest.

Date:        2026-09-04
Owner:       Jason Delosh
"""

from __future__ import annotations

import pytest

from sdgtools import build_index as bi
from sdgval.labels import category, code, negative, objective, positive

# A complete header in this repo's convention: a two-line first paragraph, a
# second paragraph that must not reach the page, and a Usage whose relative
# indentation must survive.
GOOD_HEADER = '''"""
Script:      alpha.py
Description: Does the first thing,
             continued on a second line.

             A second paragraph the page must leave out.

Inputs:      nothing
Outputs:     nothing
Usage:       alpha
                 run it
             alpha --flag
                 run it with a flag
Exit codes:  0 fine
Date:        2026-09-04
Owner:       Jason Delosh
"""
'''

EXPECTED_ENTRY = """### alpha

Does the first thing, continued on a second line.

Its header block is in `src/sdgtools/alpha.py`.

```
alpha
    run it
alpha --flag
    run it with a flag
```
"""


#######################################################################################
### Helpers ###


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """Produces a function that takes {module: source}, writes each module's file
    under src/ of a temporary repo, lists each one in its pyproject.toml as a command
    named after the module's last part, and hands back the repo's folder. The
    generator is pointed at that folder."""
    monkeypatch.setattr(bi, "REPO_ROOT", tmp_path)
    (tmp_path / "docs").mkdir()

    def make(modules: dict[str, str]):
        """Write the given modules and the pyproject.toml that installs them.

        Args:
            modules: The source of each module, keyed by its dotted name, such as
                sdgtools.alpha.

        Returns:
            The staged repo's folder.
        """
        lines = ["[project.scripts]"]
        for module, source in modules.items():
            path = tmp_path / "src" / (module.replace(".", "/") + ".py")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(source, encoding="utf-8")
            lines.append(f'{module.split(".")[-1]} = "{module}:main"')
        (tmp_path / "pyproject.toml").write_text(
            "\n".join(lines) + "\n", encoding="utf-8"
        )
        return tmp_path

    return make


def page(root) -> str:
    """Read the generated page of a staged repo.

    Args:
        root: The staged repo's folder.

    Returns:
        The text of docs/commands.md.
    """
    return (root / "docs" / "commands.md").read_text(encoding="utf-8")


#######################################################################################
### Generating the page ###


@pytest.fixture
def written(repo, capsys):
    """Stage one command with a complete header, run the generator, and hand back the
    exit code, the page it wrote and what it printed."""
    root = repo({"sdgtools.alpha": GOOD_HEADER})
    exit_code = bi.main([])
    return exit_code, page(root), capsys.readouterr().out


@code("SA00241")
@category("repository")
@objective("functionality")
@positive
def test_writes_the_entry_from_the_header(written):
    """docs/commands.md holds each command under a heading of its name, with the first
    paragraph of its Description joined to one line, the file its header block is in,
    and its Usage block with the relative indentation kept."""
    _, text, _ = written
    assert EXPECTED_ENTRY in text


@code("SA00242")
@category("repository")
@objective("functionality")
@positive
def test_the_second_paragraph_is_left_out(written):
    """Only the first paragraph of a Description reaches docs/commands.md, and the
    rest stays in the header."""
    _, text, _ = written
    assert "second paragraph" not in text


@code("SA00243")
@category("repository")
@objective("functionality")
@positive
def test_the_index_opens_with_the_title_and_the_notice(written):
    """docs/commands.md opens with its title and the notice saying it is generated, so
    nobody edits it by hand."""
    _, text, _ = written
    assert text.startswith("# Commands\n\n" + bi.GENERATED_NOTICE)


@code("SA00244")
@category("repository")
@objective("functionality")
@positive
def test_the_index_ends_with_one_newline(written):
    """docs/commands.md ends with exactly one new line, so a regenerated file
    compares equal to itself and the check option does not fail on spacing."""
    _, text, _ = written
    assert text.endswith("```\n") and not text.endswith("\n\n")


@code("SA00245")
@category("repository")
@objective("functionality")
@positive
def test_the_index_is_written_with_lf_line_endings(repo):
    """docs/commands.md ends each line the same way whatever machine regenerates
    it, so the file does not change between one run and the next.

    It is read as bytes, because reading as text would hide a carriage return."""
    root = repo({"sdgtools.alpha": GOOD_HEADER})
    assert bi.main([]) == 0
    raw = (root / "docs" / "commands.md").read_bytes()
    assert b"\r" not in raw


@code("SA00246")
@category("repository")
@objective("functionality")
@positive
def test_writing_reports_the_file_and_the_count(written):
    """A run that writes docs/commands.md exits 0 and says which file it wrote and how
    many commands it holds."""
    exit_code, _, printed = written
    assert exit_code == 0
    assert "docs/commands.md written, 1 command(s)" in printed


@code("SA00247")
@category("repository")
@objective("functionality")
@positive
def test_scripts_are_listed_in_name_order(repo):
    """Two commands of one package appear in alphabetical order whatever order
    pyproject.toml lists them in, so docs/commands.md is stable between runs."""
    root = repo(
        {
            "sdgtools.zeta": GOOD_HEADER.replace("alpha", "zeta"),
            "sdgtools.alpha": GOOD_HEADER,
        }
    )
    assert bi.main([]) == 0
    text = page(root)
    assert text.index("### alpha") < text.index("### zeta")


@code("SA00632")
@category("repository")
@objective("functionality")
@positive
def test_commands_are_grouped_by_package_in_a_fixed_order(repo):
    """The commands of each package appear under that package's heading, and the
    headings run pipeline commands, then repo tools, then validation commands,
    whatever the commands' names."""
    root = repo(
        {
            "sdgval.alpha": GOOD_HEADER,
            "sdgtools.mid": GOOD_HEADER.replace("alpha", "mid"),
            "sdg.sources.zeta": GOOD_HEADER.replace("alpha", "zeta"),
        }
    )
    assert bi.main([]) == 0
    text = page(root)
    pipeline = text.index("## Pipeline commands\n\n### zeta")
    tools = text.index("## Repo tools\n\n### mid")
    validation = text.index("## Validation commands\n\n### alpha")
    assert pipeline < tools < validation


@code("SA00633")
@category("repository")
@objective("functionality")
@positive
def test_a_package_with_no_command_gets_no_heading(repo):
    """A package that installs no command has no heading on docs/commands.md."""
    root = repo({"sdgtools.alpha": GOOD_HEADER})
    assert bi.main([]) == 0
    text = page(root)
    assert "## Pipeline commands" not in text
    assert "## Validation commands" not in text


@code("SA00634")
@category("repository")
@objective("functionality")
@positive
def test_a_file_no_command_runs_is_left_out(repo):
    """A file in a package that pyproject.toml installs as no command, such as a
    pytest plugin, does not appear on docs/commands.md, even when it carries a
    complete header block.

    The plugin's header is complete, so a generator that wrongly took every file in
    the package would still write the page, and the check fails on the page naming
    the plugin rather than on an error."""
    root = repo({"sdgval.alpha": GOOD_HEADER})
    (root / "src" / "sdgval" / "plugin.py").write_text(
        GOOD_HEADER.replace("alpha", "plugin"), encoding="utf-8"
    )
    assert bi.main([]) == 0
    assert "plugin" not in page(root)


#######################################################################################
### --check, the pre-commit hook ###


@code("SA00248")
@category("repository")
@objective("functionality")
@positive
def test_check_passes_when_index_is_current(repo, capsys):
    """With the check option, the run exits 0 and writes nothing when docs/commands.md
    on disk equals what would be generated."""
    root = repo({"sdgtools.alpha": GOOD_HEADER})
    assert bi.main([]) == 0
    before = (root / "docs" / "commands.md").stat().st_mtime_ns
    assert bi.main(["--check"]) == 0
    assert (root / "docs" / "commands.md").stat().st_mtime_ns == before
    assert "is current, 1 command(s)" in capsys.readouterr().out


@code("SA00249")
@category("repository")
@objective("functionality")
@negative
def test_check_fails_when_index_is_missing(repo, capsys):
    """With the check option and no page on disk, the run exits 15, names the command
    to run, and writes nothing."""
    root = repo({"sdgtools.alpha": GOOD_HEADER})
    assert bi.main(["--check"]) == 15
    assert not (root / "docs" / "commands.md").exists()
    assert "stale. Run: build_index" in capsys.readouterr().out


@code("SA00250")
@category("repository")
@objective("functionality")
@negative
def test_check_fails_when_index_is_stale(repo, capsys):
    """With the check option and a page that no longer matches the headers, the run
    exits 15, names the command to run, and leaves the stale page as it was."""
    root = repo({"sdgtools.alpha": GOOD_HEADER})
    bi.main([])
    stale = page(root)
    repo(
        {
            "sdgtools.alpha": GOOD_HEADER.replace(
                "Does the first thing", "Does another thing"
            )
        }
    )
    capsys.readouterr()
    assert bi.main(["--check"]) == 15
    assert page(root) == stale
    assert "stale. Run: build_index" in capsys.readouterr().out


@code("SA00251")
@category("repository")
@objective("functionality")
@positive
def test_quiet_prints_nothing(repo, capsys):
    """With the quiet option, nothing is printed. The exit code is the whole report."""
    repo({"sdgtools.alpha": GOOD_HEADER})
    assert bi.main(["--quiet"]) == 0
    assert capsys.readouterr().out == ""


#######################################################################################
### Refusing a bad header, one exit code each ###


@code("SA00252")
@category("repository")
@objective("functionality")
@negative
def test_missing_field_exits_17_and_writes_nothing(repo, capsys):
    """A header missing required fields exits 17, naming the file and every missing
    field, and docs/commands.md is not written."""
    root = repo(
        {
            "sdgtools.alpha": GOOD_HEADER.replace("Outputs:     nothing\n", "").replace(
                "Owner:       Jason Delosh\n", ""
            )
        }
    )
    assert bi.main([]) == 17
    assert not (root / "docs" / "commands.md").exists()
    out = capsys.readouterr().out
    assert "src/sdgtools/alpha.py: header missing Outputs, Owner" in out
    assert "Page not written" in out


@code("SA00253")
@category("repository")
@objective("functionality")
@negative
def test_no_docstring_exits_17(repo, capsys):
    """A command's file with no docstring at the top has no header block at all, and
    the run exits 17 and says so."""
    repo({"sdgtools.alpha": "print('hello')\n"})
    assert bi.main([]) == 17
    assert "alpha.py: no module docstring" in capsys.readouterr().out


@code("SA00254")
@category("repository")
@objective("functionality")
@negative
def test_unparseable_script_exits_19_and_outranks_17(repo, capsys):
    """A command's file that is not valid Python exits 19, and 19 outranks 17 when
    another command's header is also incomplete. Both problems are still named."""
    repo({"sdgtools.alpha": "def broken(:\n", "sdgtools.beta": "print('no header')\n"})
    assert bi.main([]) == 19
    out = capsys.readouterr().out
    assert "alpha.py: cannot parse" in out
    assert "beta.py: no module docstring" in out


@code("SA00591")
@category("repository")
@objective("functionality")
@negative
def test_a_script_not_saved_as_utf8_exits_19(repo, capsys):
    """A command's file that is not saved as UTF-8 text exits 19, and the line names
    the file and says it is not saved as UTF-8 text."""
    root = repo({"sdgtools.alpha": ""})
    (root / "src" / "sdgtools" / "alpha.py").write_bytes(GOOD_HEADER.encode("utf-16"))
    assert bi.main([]) == 19
    assert "alpha.py: cannot parse, because it is not saved as UTF-8 text" in (
        capsys.readouterr().out
    )


@code("SA00255")
@category("repository")
@objective("functionality")
@negative
def test_no_scripts_exits_20(repo, capsys):
    """A pyproject.toml that installs no command exits 20 and says so."""
    repo({})
    assert bi.main([]) == 20
    assert "pyproject.toml installs no commands" in capsys.readouterr().out


#######################################################################################
### Refusing a list of commands the page cannot use ###


@code("SA00635")
@category("repository")
@objective("functionality")
@negative
def test_a_missing_pyproject_exits_13(repo, capsys):
    """With no pyproject.toml in the repo, the run exits 13, the message says the file
    cannot be read, and docs/commands.md is not written."""
    root = repo({})
    (root / "pyproject.toml").unlink()
    assert bi.main([]) == 13
    assert "pyproject.toml cannot be read" in capsys.readouterr().out
    assert not (root / "docs" / "commands.md").exists()


@code("SA00636")
@category("repository")
@objective("functionality")
@negative
def test_a_pyproject_that_cannot_be_parsed_exits_64(repo, capsys):
    """A pyproject.toml whose text is not a valid settings file exits 64, and the
    message says it cannot be parsed."""
    root = repo({})
    (root / "pyproject.toml").write_text("[project.scripts\n", encoding="utf-8")
    assert bi.main([]) == 64
    assert "pyproject.toml cannot be parsed" in capsys.readouterr().out


@code("SA00637")
@category("repository")
@objective("functionality")
@negative
def test_a_scripts_table_of_the_wrong_shape_exits_64(repo, capsys):
    """A [project.scripts] table that maps a command to something other than a
    module and function exits 64, and the message says how an entry is written."""
    root = repo({})
    (root / "pyproject.toml").write_text(
        "[project.scripts]\nalpha = 1\n", encoding="utf-8"
    )
    assert bi.main([]) == 64
    assert "must name each command with the module and function it runs" in (
        capsys.readouterr().out
    )


@code("SA00638")
@category("repository")
@objective("functionality")
@negative
def test_a_command_from_a_package_with_no_heading_exits_64(repo, capsys):
    """A command from a package that has no heading on the page exits 64, the message
    names the command and says to add the package to COMMAND_GROUPS, and
    docs/commands.md is not written."""
    root = repo({"other.alpha": GOOD_HEADER})
    assert bi.main([]) == 64
    out = capsys.readouterr().out
    assert "installs alpha from the package other" in out
    assert "Add the package to COMMAND_GROUPS" in out
    assert not (root / "docs" / "commands.md").exists()


@code("SA00639")
@category("repository")
@objective("functionality")
@negative
def test_a_command_whose_file_is_missing_exits_64(repo, capsys):
    """A command whose file does not exist exits 64, the message names the command
    and the missing file and says to correct the entry or restore the file, and
    docs/commands.md is not written."""
    root = repo({"sdgtools.alpha": GOOD_HEADER})
    (root / "src" / "sdgtools" / "alpha.py").unlink()
    assert bi.main([]) == 64
    out = capsys.readouterr().out
    assert (
        "installs alpha from sdgtools.alpha, but src/sdgtools/alpha.py does not exist"
        in out
    )
    assert "Correct the entry in pyproject.toml or restore the file" in out
    assert not (root / "docs" / "commands.md").exists()


@code("SA00640")
@category("repository")
@objective("functionality")
@negative
def test_a_wrong_command_outranks_a_broken_header(repo, capsys):
    """A command whose file is missing exits 64 when another command's file is also
    not valid Python, because the list of commands decides which headers are read.
    Both problems are still named."""
    root = repo({"sdgtools.alpha": GOOD_HEADER, "sdgtools.beta": "def broken(:\n"})
    (root / "src" / "sdgtools" / "alpha.py").unlink()
    assert bi.main([]) == 64
    out = capsys.readouterr().out
    assert "src/sdgtools/alpha.py does not exist" in out
    assert "beta.py: cannot parse" in out


#######################################################################################
### Fields written on one line, of one paragraph, or opening with a blank line ###


@code("SA00529")
@category("repository")
@objective("functionality")
@positive
def test_a_one_line_usage_is_indexed_as_written(repo, capsys):
    """A Usage field written on one line is indexed as that one line."""
    header = GOOD_HEADER.replace(
        "Usage:       alpha\n                 run it\n             alpha --flag\n"
        "                 run it with a flag\n",
        "Usage:       alpha --once\n",
    )
    root = repo({"sdgtools.alpha": header})
    assert bi.main([]) == 0
    assert "```\nalpha --once\n```" in page(root)


@code("SA00530")
@category("repository")
@objective("functionality")
@positive
def test_a_description_opening_with_a_blank_line_is_indexed(repo, capsys):
    """A Description whose text starts on the line after its label, below a blank
    line, is still indexed by its first paragraph."""
    header = GOOD_HEADER.replace(
        "Description: Does the first thing,",
        "Description:\n\n             Does the first thing,",
    )
    root = repo({"sdgtools.alpha": header})
    assert bi.main([]) == 0
    assert "Does the first thing, continued on a second line." in page(root)


@code("SA00629")
@category("repository")
@objective("functionality")
@positive
def test_a_one_paragraph_description_is_indexed_whole(repo, capsys):
    """A Description of one paragraph, with no second paragraph after it, is indexed
    whole, joined into one line."""
    header = GOOD_HEADER.replace(
        "\n\n             A second paragraph the page must leave out.\n", "\n"
    )
    root = repo({"sdgtools.alpha": header})
    assert bi.main([]) == 0
    assert "Does the first thing, continued on a second line." in page(root)
