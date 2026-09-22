"""
Script:      test_read_pdf.py
Description: Checks for src/sdg/view/read_pdf.py, the command that prints part of
             a pinned PDF. They cover the list of lookup documents: that a
             well-formed list becomes the documents the command offers, that each
             path is taken from the manifest rather than from the list, and that
             every way the list can be wrong is refused with its own exit code.

             They also cover the modes that open a PDF. Those checks build a
             small document with pymupdf, one with bookmarks and one without, so
             that section, page and search modes can be exercised without a pinned
             file being present.

Inputs:      Nothing real. The list of documents, the manifests and the files are
             written to pytest's own temporary folder.

Outputs:     Writes nothing to disk. Temporary files go to pytest's own folder.

Usage:       pytest validation/view/test_read_pdf.py
                 run these checks
             pytest validation/view/test_read_pdf.py -v
                 one line per check with its result

Exit codes:  pytest's own: 0 all passed, 1 some failed

Date:        2026-09-15
Owner:       Jason Delosh
"""

from __future__ import annotations

from dataclasses import dataclass

import fitz
import pytest

from sdg.view import read_pdf
from sdg.view.read_pdf import RegistryError, UnknownFileError, load_registry

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

GUIDE = "inputs/standards/example/Example_Guide.pdf"
PLAIN = "inputs/standards/example/Plain_Document.pdf"
CONTENT = b"%PDF-1.7 not a real document\n"

# The list every check starts from. A check that stages a wrong list edits one
# line of this text, so that exactly one thing is broken.
LIST_TEXT = "\n".join(
    [
        "documents:",
        "  - key: guide",
        "    label: Example Guide v1",
        "    file: Example_Guide.pdf",
        "    boilerplate:",
        "      - '^ *Page [0-9]+ *$'",
        "  - key: plain",
        "    label: Plain Document",
        "    file: Plain_Document.pdf",
        "    boilerplate: []",
        "",
        "default: guide",
        "",
    ]
)


#######################################################################################
### Shared staging ###
#
# One fixture builds what every check starts from: a fake repo holding the two recorded
# files the list names. Another writes a list of lookup documents into a temporary
# folder. The run helper points the command at that list and calls it in-process.


@dataclass(frozen=True)
class Outcome:
    """What one run of the command produced."""

    exit_code: int
    printed: str


@pytest.fixture
def repo(fake_repo):
    """Give a check a fake repo holding the two recorded files, both on disk."""
    fake_repo.file(GUIDE, CONTENT)
    fake_repo.file(PLAIN, CONTENT)
    fake_repo.manifest("example", [fake_repo.entry(GUIDE), fake_repo.entry(PLAIN)])
    return fake_repo


@pytest.fixture
def write_list(tmp_path):
    """Give a check a function for staging the list of lookup documents.

    Returns:
        The function, which takes the file's text and hands back its path.
    """

    def make(text):
        """Write the given text as the list and give back its path."""
        path = tmp_path / "lookup_documents.yml"
        path.write_text(text, encoding="utf-8")
        return path

    return make


def run(write_list, monkeypatch, capsys, text, *argv):
    """Point the command at a staged list and run it in-process.

    Args:
        write_list: The function that writes the list.
        monkeypatch: pytest's patcher, which undoes the pointing afterwards.
        capsys: pytest's capture of what was printed.
        text: The contents of the list to stage.
        *argv: The command-line arguments to hand the command.

    Returns:
        The exit code and what was printed, as an Outcome.
    """
    monkeypatch.setattr(read_pdf, "REGISTRY_FILE", write_list(text))
    exit_code = read_pdf.main(list(argv))
    captured = capsys.readouterr()
    return Outcome(exit_code, captured.out + captured.err)


#######################################################################################
### Positive checks ###
#
# The right thing works: a well-formed list becomes the documents the command offers,
# each path comes from the manifest, and the patterns and the default are carried
# through as written.


@code("VIW0001")
@category("processing")
@objective("functionality")
@positive
def test_every_row_becomes_a_document(repo, write_list):
    """Each row in lookup_documents.yml becomes one document, keyed by the key a person types."""
    documents, _ = load_registry(write_list(LIST_TEXT))
    assert sorted(documents) == ["guide", "plain"]


@code("VIW0002")
@category("processing")
@objective("functionality")
@positive
def test_the_path_comes_from_the_manifest(repo, write_list):
    """A document's path is taken from its manifest entry, so lookup_documents.yml never states
    where a file lives."""
    documents, _ = load_registry(write_list(LIST_TEXT))
    assert documents["guide"].path == repo.root / GUIDE


@code("VIW0003")
@category("processing")
@objective("functionality")
@positive
def test_the_manifest_is_carried_for_the_missing_file_message(repo, write_list):
    """A document carries the manifest that records it, which the missing-file message
    tells a person to restore from."""
    documents, _ = load_registry(write_list(LIST_TEXT))
    assert documents["guide"].manifest == "example.json"


@code("VIW0004")
@category("processing")
@objective("functionality")
@positive
def test_boilerplate_patterns_are_compiled(repo, write_list):
    """A boilerplate pattern is compiled, and it matches the repeated header and footer
    lines it was
    written for."""
    documents, _ = load_registry(write_list(LIST_TEXT))
    assert documents["guide"].boilerplate[0].match("   Page 12  ")


@code("VIW0005")
@category("processing")
@objective("functionality")
@positive
def test_an_empty_boilerplate_list_strips_nothing(repo, write_list):
    """A document with nothing repeated on its pages carries no patterns."""
    documents, _ = load_registry(write_list(LIST_TEXT))
    assert documents["plain"].boilerplate == ()


@code("VIW0006")
@category("processing")
@objective("functionality")
@positive
def test_the_default_is_the_one_the_list_names(repo, write_list):
    """The key used when --doc is absent is the one lookup_documents.yml names as its default."""
    _, default = load_registry(write_list(LIST_TEXT))
    assert default == "guide"


@code("VIW0007")
@category("processing")
@objective("functionality")
@positive
def test_docs_names_every_document(repo, write_list, monkeypatch, capsys):
    """With every listed document on disk, --docs names each one."""
    outcome = run(write_list, monkeypatch, capsys, LIST_TEXT, "--docs")
    assert "Example Guide v1" in outcome.printed
    assert "Plain Document" in outcome.printed


@code("VIW0008")
@category("processing")
@objective("functionality")
@positive
def test_docs_exits_0_when_every_document_is_present(
    repo, write_list, monkeypatch, capsys
):
    """With every listed document on disk, --docs exits 0."""
    assert run(write_list, monkeypatch, capsys, LIST_TEXT, "--docs").exit_code == 0


#######################################################################################
### Negative checks ###
#
# The wrong thing is refused. Each check breaks one thing, and asserts the error raised
# and that its message names that cause and its remedy.


@code("VIW0009")
@category("processing")
@objective("functionality")
@negative
def test_a_missing_list_is_refused(repo, tmp_path):
    """With no list of lookup documents on disk, loading raises RegistryError naming
    the path and saying to restore it from git."""
    with pytest.raises(RegistryError) as raised:
        load_registry(tmp_path / "gone.yml")
    assert "gone.yml" in str(raised.value)
    assert "restore it from git" in str(raised.value)


@code("VIW0010")
@category("processing")
@objective("functionality")
@negative
def test_a_list_that_is_not_yaml_is_refused(repo, write_list):
    """A list that is not valid YAML raises RegistryError saying so, rather than failing
    later with a shape error."""
    with pytest.raises(RegistryError) as raised:
        load_registry(write_list("documents: [\n  - key: broken\n"))
    assert "not valid YAML" in str(raised.value)


@code("VIW0011")
@category("processing")
@objective("functionality")
@negative
def test_a_list_with_no_documents_is_refused(repo, write_list):
    """A file with no documents list raises RegistryError saying which part is
    absent."""
    with pytest.raises(RegistryError) as raised:
        load_registry(write_list("default: guide\n"))
    assert "no documents list" in str(raised.value)


@code("VIW0012")
@category("processing")
@objective("functionality")
@negative
def test_a_row_missing_a_field_is_refused(repo, write_list):
    """A row without its label raises RegistryError naming the field that is
    missing."""
    text = LIST_TEXT.replace("    label: Example Guide v1\n", "")
    with pytest.raises(RegistryError) as raised:
        load_registry(write_list(text))
    assert "label" in str(raised.value)


@code("VIW0069")
@category("processing")
@objective("functionality")
@negative
def test_a_row_that_is_not_a_set_of_fields_is_refused(repo, write_list):
    """A row that is a bare value rather than a set of fields raises RegistryError
    quoting the value, rather than crashing on the field lookup."""
    plain_row = "\n".join(
        [
            "  - key: plain",
            "    label: Plain Document",
            "    file: Plain_Document.pdf",
            "    boilerplate: []",
            "",
        ]
    )
    text = LIST_TEXT.replace(plain_row, "  - plain\n")
    with pytest.raises(RegistryError) as raised:
        load_registry(write_list(text))
    assert "plain" in str(raised.value)


@code("VIW0070")
@category("processing")
@objective("functionality")
@pytest.mark.parametrize(
    "written",
    ["'^ *Page [0-9]+ *$'", "false", "0", "''", "null"],
    ids=["one string", "false", "zero", "empty string", "null"],
)
@negative
def test_a_boilerplate_that_is_not_a_list_is_refused(repo, write_list, written):
    """A boilerplate written as anything but a list, a lone pattern string or an
    empty-looking value, raises RegistryError naming the row, rather than reading
    the string one character at a time or silently taking it as no patterns."""
    text = LIST_TEXT.replace(
        "    boilerplate:\n      - '^ *Page [0-9]+ *$'\n",
        f"    boilerplate: {written}\n",
    )
    with pytest.raises(RegistryError) as raised:
        load_registry(write_list(text))
    assert "guide" in str(raised.value) and "list" in str(raised.value)


@code("VIW0013")
@category("processing")
@objective("functionality")
@negative
def test_a_file_no_manifest_records_is_refused(repo, write_list):
    """A row naming a file that no manifest records raises UnknownFileError naming the
    file and saying to correct the name or record the file."""
    text = LIST_TEXT.replace("Example_Guide.pdf", "Nobody_Recorded_This.pdf")
    with pytest.raises(UnknownFileError) as raised:
        load_registry(write_list(text))
    assert "Nobody_Recorded_This.pdf" in str(raised.value)
    assert "record the file in manifests/" in str(raised.value)


@code("VIW0014")
@category("processing")
@objective("functionality")
@negative
def test_a_default_that_is_not_listed_is_refused(repo, write_list):
    """A default naming a key lookup_documents.yml does not hold raises RegistryError, rather than
    leaving --doc with a default it cannot accept."""
    text = LIST_TEXT.replace("default: guide", "default: nowhere")
    with pytest.raises(RegistryError) as raised:
        load_registry(write_list(text))
    assert "nowhere" in str(raised.value)


@code("VIW0015")
@category("processing")
@objective("functionality")
@negative
def test_a_missing_list_exits_31(repo, tmp_path, monkeypatch, capsys):
    """When lookup_documents.yml is missing, the command exits 31 and says where the file
    was expected and how to get it back, rather than raising."""
    monkeypatch.setattr(read_pdf, "REGISTRY_FILE", tmp_path / "gone.yml")
    assert read_pdf.main(["--docs"]) == 31
    printed = capsys.readouterr().err
    assert "is missing at" in printed and "gone.yml" in printed
    assert "restore it from git" in printed


@code("VIW0016")
@category("processing")
@objective("functionality")
@negative
def test_a_file_no_manifest_records_exits_32(repo, write_list, monkeypatch, capsys):
    """When lookup_documents.yml names a file no manifest records, the command exits 32, a
    different cause from a list that cannot be read."""
    text = LIST_TEXT.replace("Example_Guide.pdf", "Nobody_Recorded_This.pdf")
    outcome = run(write_list, monkeypatch, capsys, text, "--docs")
    assert outcome.exit_code == 32
    assert "Nobody_Recorded_This.pdf" in outcome.printed
    assert "no manifest records" in outcome.printed


@code("VIW0067")
@category("processing")
@objective("functionality")
@negative
def test_not_inside_repo_exits_6(repo, write_list, monkeypatch, tmp_path, capsys):
    """When the sdg package is not running from inside its repo, the command exits 6
    and prints the install command, because the manifests that own each document's
    path cannot be found from anywhere else."""
    from sdg.sources import read_manifests

    monkeypatch.setattr(read_manifests, "REPO_ROOT", tmp_path / "elsewhere")
    outcome = run(write_list, monkeypatch, capsys, LIST_TEXT, "--docs")
    assert outcome.exit_code == 6
    assert "pip install -e ." in outcome.printed


@code("VIW0068")
@category("processing")
@objective("functionality")
@negative
def test_an_unreadable_manifest_exits_3(repo, write_list, monkeypatch, capsys):
    """When a manifest is not valid JSON, the command exits 3 and names that manifest
    as the thing that cannot be read, rather than blaming lookup_documents.yml or a document."""
    (repo.root / "manifests" / "broken.json").write_text("{ not json", encoding="utf-8")
    outcome = run(write_list, monkeypatch, capsys, LIST_TEXT, "--docs")
    assert outcome.exit_code == 3
    assert "broken.json" in outcome.printed and "cannot read" in outcome.printed


@code("VIW0017")
@category("processing")
@objective("functionality")
@negative
def test_docs_exits_8_when_a_document_is_not_downloaded(
    fake_repo, write_list, monkeypatch, capsys
):
    """With a listed document recorded but not on disk, --docs exits 8 and says to run
    acquire_sources."""
    fake_repo.manifest(
        "example",
        [
            fake_repo.entry(GUIDE, bytes=10, sha256="0" * 64),
            fake_repo.entry(PLAIN, bytes=10, sha256="0" * 64),
        ],
    )
    outcome = run(write_list, monkeypatch, capsys, LIST_TEXT, "--docs")
    assert outcome.exit_code == 8
    assert "acquire_sources" in outcome.printed


#######################################################################################
### Staging a document to read ###
#
# The checks above never open a PDF. The ones below do, so they build a small document
# with pymupdf: two pages with bookmarks, and the same pages without, which is the
# split the command is designed around.


def build_pdf(path, with_bookmarks):
    """Write a two-page PDF, with or without the bookmarks a section lookup needs.

    Args:
        path: Where the document is written. Parent folders are created.
        with_bookmarks: Whether to give the document a table of contents.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    document = fitz.open()
    bodies = ("1 First Section\nalpha content", "2 Second Section\nbeta content")
    for number, body in enumerate(bodies, start=1):
        page = document.new_page()
        page.insert_text((72, 72), body)
        # The footer matches the boilerplate pattern the staged list carries, so
        # the stripping checks have something real to strip.
        page.insert_text((72, 700), f"Page {number}")
    if with_bookmarks:
        document.set_toc([[1, "1 First Section", 1], [1, "2 Second Section", 2]])
    document.save(str(path))
    document.close()


@pytest.fixture
def readable(fake_repo, write_list, monkeypatch):
    """Stage one document with bookmarks and one without, both recorded and on disk.

    Returns:
        The fake repo, with the command pointed at a list naming both documents.
    """
    build_pdf(fake_repo.root / GUIDE, with_bookmarks=True)
    build_pdf(fake_repo.root / PLAIN, with_bookmarks=False)
    fake_repo.manifest("example", [fake_repo.entry(GUIDE), fake_repo.entry(PLAIN)])
    monkeypatch.setattr(read_pdf, "REGISTRY_FILE", write_list(LIST_TEXT))
    return fake_repo


def read(capsys, *argv):
    """Run the command over the staged documents.

    Args:
        capsys: pytest's capture of what was printed.
        *argv: The command-line arguments to hand the command.

    Returns:
        The exit code and what was printed, as an Outcome.
    """
    exit_code = read_pdf.main(list(argv))
    captured = capsys.readouterr()
    return Outcome(exit_code, captured.out + captured.err)


def usage_mistake(capsys, *argv):
    """Run the command expecting the argument parser to refuse the command line.

    The parser ends the run itself with exit 2, so the refusal arrives as SystemExit
    rather than as a value main() hands back.

    Args:
        capsys: pytest's capture of what was printed.
        *argv: The command-line arguments to hand the command.

    Returns:
        The exit code and what was printed, as an Outcome.
    """
    with pytest.raises(SystemExit) as caught:
        read_pdf.main(list(argv))
    captured = capsys.readouterr()
    return Outcome(int(caught.value.code), captured.out + captured.err)


#######################################################################################
### Positive checks on a document ###
#
# The right thing works on a document that is present: a section is found by number,
# a page range is printed, a term is searched for, and the repeated header and footer lines are
# stripped unless it is asked for.


@code("VIW0034")
@category("processing")
@objective("functionality")
@positive
def test_a_section_is_found_by_number(readable, capsys):
    """Asking for a section by its number prints that section's text."""
    outcome = read(capsys, "1")
    assert outcome.exit_code == 0
    assert "alpha content" in outcome.printed


@code("VIW0035")
@category("processing")
@objective("functionality")
@positive
def test_a_section_is_found_by_title(readable, capsys):
    """Asking for part of a section's title prints that section."""
    assert "beta content" in read(capsys, "Second").printed


@code("VIW0036")
@category("processing")
@objective("functionality")
@positive
def test_the_section_map_lists_every_section(readable, capsys):
    """The section map names every section the document's bookmarks hold."""
    printed = read(capsys, "--list").printed
    assert "First Section" in printed
    assert "Second Section" in printed


@code("VIW0037")
@category("processing")
@objective("functionality")
@positive
def test_a_page_range_is_printed(readable, capsys):
    """A page range prints those pages, which is the mode a document without
    bookmarks is read by."""
    assert "beta content" in read(capsys, "--doc", "plain", "--pages", "2").printed


@code("VIW0044")
@category("processing")
@objective("functionality")
@positive
def test_a_two_page_range_prints_both_pages_in_order(readable, capsys):
    """A range of two pages prints both, first page first."""
    printed = read(capsys, "--doc", "plain", "--pages", "1-2").printed
    assert printed.index("alpha content") < printed.index("beta content")


@code("VIW0038")
@category("processing")
@objective("functionality")
@positive
def test_a_term_is_searched_for_across_pages(readable, capsys):
    """A search names the page that contains the term and shows the matching line,
    rather than answering that no page contains it."""
    outcome = read(capsys, "--doc", "plain", "--find", "beta")
    assert outcome.exit_code == 0
    assert "p.  2" in outcome.printed
    assert "beta content" in outcome.printed
    assert "No pages contain" not in outcome.printed


@code("VIW0039")
@category("processing")
@objective("functionality")
@positive
def test_page_furniture_is_stripped(readable, capsys):
    """A line matching the document's boilerplate pattern is left out of an extract,
    so a section reads as its own content."""
    assert "Page 1" not in read(capsys, "--pages", "1").printed


@code("VIW0040")
@category("processing")
@objective("functionality")
@positive
def test_raw_keeps_the_page_furniture(readable, capsys):
    """With --raw the boilerplate is kept, for a session that needs the page exactly
    as it is."""
    assert "Page 1" in read(capsys, "--pages", "1", "--raw").printed


#######################################################################################
### Negative checks on a document ###
#
# Each refusal the header promises, with the exit code that names its cause.


@code("VIW0041")
@category("processing")
@objective("functionality")
@negative
def test_a_section_that_does_not_exist_exits_23(readable, capsys):
    """Asking for a section the document does not hold exits 23, rather than printing
    nothing and reading as though the content were absent."""
    outcome = read(capsys, "99.99")
    assert outcome.exit_code == 23
    assert "No section matching" in outcome.printed
    assert "--list" in outcome.printed


@code("VIW0042")
@category("processing")
@objective("functionality")
@negative
def test_section_mode_on_a_document_without_bookmarks_exits_24(readable, capsys):
    """Asking for a section of a document that carries no bookmarks exits 24 and names
    the modes that do work on it."""
    outcome = read(capsys, "--doc", "plain", "--list")
    assert outcome.exit_code == 24
    assert "--find" in outcome.printed


@code("VIW0045")
@category("processing")
@objective("functionality")
@negative
def test_a_page_range_that_is_not_numbers_is_a_usage_mistake(readable, capsys):
    """A page range that is not a number, or two joined by a dash, exits 2 and shows
    the form a range takes."""
    outcome = usage_mistake(capsys, "--pages", "abc")
    assert outcome.exit_code == 2
    assert "such as 26-31" in outcome.printed


@code("VIW0049")
@category("processing")
@objective("functionality")
@negative
def test_a_page_range_with_a_trailing_dash_is_a_usage_mistake(readable, capsys):
    """A page range written with a dash and no second number exits 2, rather than being
    read as the one page before the dash."""
    outcome = usage_mistake(capsys, "--pages", "1-")
    assert outcome.exit_code == 2
    assert "such as 26-31" in outcome.printed


@code("VIW0046")
@category("processing")
@objective("functionality")
@negative
def test_a_page_range_starting_before_page_1_is_a_usage_mistake(readable, capsys):
    """A page range starting at 0 exits 2 and says so, rather than printing the last
    page under the label page 0."""
    outcome = usage_mistake(capsys, "--pages", "0")
    assert outcome.exit_code == 2
    assert "starts before page 1" in outcome.printed


@code("VIW0047")
@category("processing")
@objective("functionality")
@negative
def test_a_page_range_past_the_document_is_a_usage_mistake(readable, capsys):
    """A page range running past the last page exits 2 and says how many pages the
    document has, rather than ending in a traceback."""
    outcome = usage_mistake(capsys, "--pages", "99")
    assert outcome.exit_code == 2
    assert "which has 2 pages" in outcome.printed


@code("VIW0048")
@category("processing")
@objective("functionality")
@negative
def test_a_page_range_ending_before_it_starts_is_a_usage_mistake(readable, capsys):
    """A page range whose last page comes before its first exits 2 and says so, rather
    than printing a heading with nothing under it."""
    outcome = usage_mistake(capsys, "--pages", "2-1")
    assert outcome.exit_code == 2
    assert "ends before it starts" in outcome.printed


@code("VIW0043")
@category("processing")
@objective("functionality")
@negative
def test_a_document_not_downloaded_exits_8(fake_repo, write_list, monkeypatch, capsys):
    """Reading a document that is recorded but not on disk exits 8 and names the
    manifest to restore it from."""
    fake_repo.manifest(
        "example",
        [
            fake_repo.entry(GUIDE, bytes=10, sha256="0" * 64),
            fake_repo.entry(PLAIN, bytes=10, sha256="0" * 64),
        ],
    )
    monkeypatch.setattr(read_pdf, "REGISTRY_FILE", write_list(LIST_TEXT))
    outcome = read(capsys, "--pages", "1")
    assert outcome.exit_code == 8
    assert "example.json" in outcome.printed


#######################################################################################
### Staging a page two sections share ###
#
# A bookmark gives a section's start page and nothing else, so two sections that begin
# on one page share that page's text until the reader cuts it at their headings. This
# document puts both sections on one page so the cut at a section's start can be seen.


def build_shared_page_pdf(path):
    """Write a one-page PDF whose two bookmarked sections both begin on that page.

    Args:
        path: Where the document is written. Parent folders are created.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    document = fitz.open()
    page = document.new_page()
    page.insert_text(
        (72, 72), "1 First Section\nalpha content\n2 Second Section\nbeta content"
    )
    document.set_toc([[1, "1 First Section", 1], [1, "2 Second Section", 1]])
    document.save(str(path))
    document.close()


@pytest.fixture
def shared_page(fake_repo, write_list, monkeypatch):
    """Stage the guide as a document whose two sections share one page, recorded and
    on disk beside the plain document.

    Returns:
        The fake repo, with the command pointed at a list naming both documents.
    """
    build_shared_page_pdf(fake_repo.root / GUIDE)
    build_pdf(fake_repo.root / PLAIN, with_bookmarks=False)
    fake_repo.manifest("example", [fake_repo.entry(GUIDE), fake_repo.entry(PLAIN)])
    monkeypatch.setattr(read_pdf, "REGISTRY_FILE", write_list(LIST_TEXT))
    return fake_repo


#######################################################################################
### Checks on where a section's text is cut ###
#
# A section rarely owns a whole page at either end, so the reader cuts the first page
# at the section's own heading and the last page at the next section's heading. These
# checks prove the text on the far side of each cut is left out.


@code("VIW0051")
@category("processing")
@objective("functionality")
@positive
def test_the_previous_sections_text_is_left_out_at_the_start(shared_page, capsys):
    """When a section begins part way down a page, the text of the section before it
    on that page is left out of the extract."""
    outcome = read(capsys, "2")
    assert outcome.exit_code == 0
    assert "beta content" in outcome.printed
    assert "alpha content" not in outcome.printed


@code("VIW0066")
@category("processing")
@objective("functionality")
@positive
def test_the_next_sections_text_is_left_out_when_both_share_one_page(
    shared_page, capsys
):
    """When a section and the next both sit on one page, reading the first gives its
    own text and leaves out the next section's, so the two return different text."""
    outcome = read(capsys, "1")
    assert outcome.exit_code == 0
    assert "alpha content" in outcome.printed
    assert "beta content" not in outcome.printed


@code("VIW0052")
@category("processing")
@objective("functionality")
@positive
def test_the_next_sections_text_is_left_out_at_the_end(readable, capsys):
    """When the next section begins on a section's last page, the next section's text
    on that page is left out of the extract."""
    outcome = read(capsys, "1")
    assert outcome.exit_code == 0
    assert "beta content" not in outcome.printed


#######################################################################################
### Checks on the note about content the text leaves out ###
#
# A page that holds a picture or a table loses it in text extraction, so the reader
# adds a note saying so. These checks build one page each with pymupdf and hand it to
# the function that writes the note.


def page_with_picture():
    """Build one page holding a small picture and no table.

    Returns:
        The page, which keeps its document open for as long as it is held.
    """
    document = fitz.open()
    page = document.new_page()
    picture = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 4, 4))
    picture.set_rect(picture.irect, (255, 0, 0))
    page.insert_image(fitz.Rect(72, 100, 172, 200), pixmap=picture)
    return page


def page_with_table():
    """Build one page holding a ruled table of three rows and three columns, and no
    picture.

    Returns:
        The page, which keeps its document open for as long as it is held.
    """
    document = fitz.open()
    page = document.new_page()
    for row in range(3):
        for column in range(3):
            cell = fitz.Rect(
                72 + column * 100, 100 + row * 30, 172 + column * 100, 130 + row * 30
            )
            page.draw_rect(cell, color=(0, 0, 0), width=1)
            page.insert_text((cell.x0 + 5, cell.y0 + 20), f"r{row}c{column}")
    return page


@code("VIW0053")
@category("processing")
@objective("functionality")
@positive
def test_a_page_with_a_picture_gets_the_not_shown_note():
    """A page holding a picture gets the NOT SHOWN note counting one image, so the gap
    in the text is visible."""
    note = read_pdf.describe_lost_content(page_with_picture())
    assert "NOT SHOWN IN TEXT" in note
    assert "1 image(s)" in note


@code("VIW0054")
@category("processing")
@objective("functionality")
@positive
def test_a_page_with_a_table_gets_the_not_shown_note():
    """A page holding a ruled table gets the NOT SHOWN note counting one table."""
    note = read_pdf.describe_lost_content(page_with_table())
    assert "NOT SHOWN IN TEXT" in note
    assert "1 table(s)" in note


#######################################################################################
### Checks on finding a section and a term ###


@code("VIW0055")
@category("processing")
@objective("functionality")
@positive
def test_a_ligature_is_decomposed_for_searching():
    """The searchable form of text holding the fi ligature, a single character standing
    for the two letters f and i, spells the word with its
    plain letters, so a search for the word finds it."""
    assert "definition" in read_pdf.searchable("Deﬁnition")


@code("VIW0056")
@category("processing")
@objective("functionality")
@positive
def test_an_exact_section_number_beats_a_title_match():
    """A section whose number is exactly what was typed is chosen over an earlier
    section whose title merely contains it."""
    sections = [
        {
            "number": "1",
            "title": "1 Notes on 2",
            "start": 1,
            "end": 1,
            "next_number": "2",
        },
        {
            "number": "2",
            "title": "2 Second Section",
            "start": 1,
            "end": 1,
            "next_number": "",
        },
    ]
    assert read_pdf.find_section(sections, "2")["number"] == "2"


@code("VIW0057")
@category("processing")
@objective("functionality")
@positive
def test_a_trailing_period_on_a_section_number_is_tolerated(readable, capsys):
    """A section number typed with a trailing period finds the same section."""
    outcome = read(capsys, "1.")
    assert outcome.exit_code == 0
    assert "alpha content" in outcome.printed


@code("VIW0058")
@category("processing")
@objective("functionality")
@positive
def test_a_search_hit_names_the_section_it_falls_in(readable, capsys):
    """A search hit on a document with bookmarks names the section its page falls
    in."""
    assert "2 Second Section" in read(capsys, "--find", "beta").printed
