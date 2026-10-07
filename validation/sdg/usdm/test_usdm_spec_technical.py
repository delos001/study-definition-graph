"""
Script:      test_usdm_spec_technical.py
Description: Checks for src/sdg/usdm/usdm_spec.py, the one module that reads
             the pinned USDM model. Each check sets up a situation, runs the
             loader, and compares what happened to what the loader's own
             documentation promises. Run them all with one command; green means
             every promise still holds, red names the one that broke.

             The checks read validation/fixtures/usdm_three_classes.yml, three
             classes copied verbatim from the pinned file. It is small enough to
             read whole and to break on purpose, as by deleting a key or putting
             a list where a dict should be, which the real file must never be.
             Broken variants are made in memory and written to a temporary
             folder pytest owns. The checks that read the pinned
             dataStructure.yml itself are in test_usdm_spec_integrity.py and
             test_usdm_spec_conformance.py, beside this file.

             Every check is marked positive (the right thing works) or negative
             (the broken thing fails, and the error names the right cause).

Inputs:      validation/fixtures/usdm_three_classes.yml  (read-only)
             every manifest, read through src/sdg/sources/read_manifests.py
                                                         (read-only)

Outputs:     Writes nothing to disk. Temporary files go to pytest's own folder.
             src/sdgval/report.py writes a report to validation/reports/ when asked.

Usage:       pytest validation/sdg/usdm/test_usdm_spec_technical.py
                 run these checks
             pytest validation/sdg/usdm/test_usdm_spec_technical.py -v
                 one line per check with its result
             validate_technical --validation-report validation/sdg/usdm/test_usdm_spec_technical.py
                 run these checks and write a technical report of them

Exit codes:  None of its own. It runs inside pytest.

Date:        2026-09-04
Owner:       Jason Delosh
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from pathlib import Path
from typing import Any, NoReturn

import pytest
import yaml

from sdg.exit_codes import exit_line
from sdg.usdm import usdm_spec
from sdgval.labels import category, code, needs_fixture, negative, objective, positive
from validation.shared.usdm_model import FIXTURE, FIXTURE_CLASSES

#######################################################################################
### Helpers ###
#
# Small tools the checks share: a parsed copy of the fixture, a way to write a
# deliberately broken variant of it, and a way to point the loader at a manifest
# folder of the test's choosing.


@pytest.fixture
def three() -> dict:
    """Give a check the fixture file, parsed by the module itself.

    The manifest check is off, because no manifest records a test fixture.

    Returns:
        The parsed fixture, a dict keyed by class name.
    """
    return usdm_spec.load(FIXTURE, verify=False)


@pytest.fixture
def variant(tmp_path):
    """Give a check a function for writing a deliberately broken copy of the fixture.

    The fixture on disk is never touched; the changed copy goes to a temporary file.

    Returns:
        The function that makes a variant.
    """

    def make(change: Callable[[Any], None]) -> Path:
        """Apply one change to the fixture's parsed form and write the result.

        Args:
            change: A function that alters the parsed fixture in place.

        Returns:
            The path of the changed copy.
        """
        data = yaml.safe_load(FIXTURE.read_text(encoding="utf-8"))
        change(data)
        path = tmp_path / "variant.yml"
        path.write_text(yaml.safe_dump(data), encoding="utf-8")
        return path

    return make


#######################################################################################
### Reading a well-formed file ###


@code("SA00124")
@category("processing")
@objective("functionality")
@positive
@needs_fixture("usdm_three_classes.yml")
def test_lists_every_class_sorted(three):
    """A well-formed file loads, and its classes are listed in alphabetical order, so a
    listing is the same from run to run."""
    assert usdm_spec.class_names(three) == sorted(FIXTURE_CLASSES)


@code("SA00125")
@category("processing")
@objective("functionality")
@positive
@needs_fixture("usdm_three_classes.yml")
def test_abstract_flag_comes_from_modifier(three):
    """Whether a class is abstract comes from USDM's own Modifier field. So Identifier,
    a parent never used on its own, is abstract, and StudyIdentifier, its child, is not."""
    assert usdm_spec.is_abstract(three, "Identifier") is True
    assert usdm_spec.is_abstract(three, "StudyIdentifier") is False


@code("SA00126")
@category("processing")
@objective("functionality")
@positive
@needs_fixture("usdm_three_classes.yml")
def test_attributes_keep_file_order_and_inheritance(three):
    """A class's attributes come back in the order the file lists them, including the
    ones it takes from its parent, and each inherited one still names that parent."""
    attrs = usdm_spec.attributes(three, "StudyIdentifier")
    assert list(attrs) == [
        "id",
        "text",
        "scopeId",
        "extensionAttributes",
        "instanceType",
    ]
    assert attrs["id"]["Inherited From"] == [{"$ref": "#/Identifier"}]
    assert "Inherited From" not in attrs["instanceType"]


@code("SA00127")
@category("processing")
@objective("functionality")
@positive
@needs_fixture("usdm_three_classes.yml")
def test_targets_unwraps_one_and_many(three):
    """The types an attribute points at come back as plain class names, both for an
    attribute with one type and for the one with five."""
    single = usdm_spec.attributes(three, "StudyIdentifier")["scopeId"]
    many = usdm_spec.attributes(three, "Condition")["appliesToIds"]
    assert usdm_spec.targets(single) == ("Organization",)
    assert usdm_spec.targets(many) == (
        "BiomedicalConceptCategory",
        "Procedure",
        "Activity",
        "BiomedicalConcept",
        "BiomedicalConceptSurrogate",
    )


@code("SA00128")
@category("processing")
@objective("functionality")
@negative
@needs_fixture("usdm_three_classes.yml")
def test_unknown_class_raises_keyerror_naming_it(three):
    """Asking for a class that is not in the file is refused with an error naming it, so
    a typo is reported rather than answered with an empty result."""
    with pytest.raises(KeyError, match="Nope"):
        usdm_spec.attributes(three, "Nope")
    with pytest.raises(KeyError, match="Nope"):
        usdm_spec.is_abstract(three, "Nope")


#######################################################################################
### Refusing a wrongly shaped file (SpecShapeError, exit 15) ###
#
# Each check breaks the fixture in one described way and asserts the loader
# refuses it with a message naming the broken class or attribute, which is the
# promise SpecShapeError exists to keep.


@code("SA00129")
@category("processing")
@objective("functionality")
@negative
def test_empty_file_is_refused(tmp_path):
    """An empty file is refused as 'empty or not a mapping' instead of being
    treated as a model with no classes."""
    empty = tmp_path / "empty.yml"
    empty.write_text("", encoding="utf-8")
    with pytest.raises(usdm_spec.SpecShapeError, match="empty or not a mapping"):
        usdm_spec.load(empty, verify=False)


@code("SA00130")
@category("processing")
@objective("functionality")
@negative
@needs_fixture("usdm_three_classes.yml")
def test_class_without_modifier_is_named(variant):
    """Deleting Modifier from one class is refused with a message naming that
    class."""
    broken = variant(lambda d: d["Condition"].pop("Modifier"))
    with pytest.raises(
        usdm_spec.SpecShapeError, match="'Condition' is missing Modifier"
    ):
        usdm_spec.load(broken, verify=False)


@code("SA00131")
@category("processing")
@objective("functionality")
@negative
@needs_fixture("usdm_three_classes.yml")
def test_unexpected_modifier_value_is_named(variant):
    """A Modifier other than Concrete or Abstract is refused, and the message quotes the
    unexpected value, so a new USDM word cannot pass unnoticed."""
    broken = variant(lambda d: d["Identifier"].__setitem__("Modifier", "Virtual"))
    with pytest.raises(usdm_spec.SpecShapeError, match="unexpected Modifier 'Virtual'"):
        usdm_spec.load(broken, verify=False)


@code("SA00132")
@category("processing")
@objective("functionality")
@negative
@needs_fixture("usdm_three_classes.yml")
def test_attributes_not_a_mapping_is_named(variant):
    """Turning a class's Attributes into a list is refused with a message naming
    the class, before any reading function could trip over it."""
    broken = variant(lambda d: d["StudyIdentifier"].__setitem__("Attributes", []))
    with pytest.raises(
        usdm_spec.SpecShapeError, match="'StudyIdentifier': Attributes is not a mapping"
    ):
        usdm_spec.load(broken, verify=False)


@code("SA00133")
@category("processing")
@objective("functionality")
@negative
@needs_fixture("usdm_three_classes.yml")
def test_attribute_missing_a_key_is_named(variant):
    """An attribute missing its Relationship Type field is refused, and the message
    names the class, the attribute and the missing field."""

    def rename(d: Any) -> None:
        """Rename one attribute's Relationship Type key, so the expected key is gone."""
        attr = d["Condition"]["Attributes"]["name"]
        attr["Kind"] = attr.pop("Relationship Type")

    broken = variant(rename)
    with pytest.raises(
        usdm_spec.SpecShapeError, match="Condition.name is missing Relationship Type"
    ):
        usdm_spec.load(broken, verify=False)


@code("SA00134")
@category("processing")
@objective("functionality")
@negative
@needs_fixture("usdm_three_classes.yml")
def test_attribute_missing_several_keys_lists_them(variant):
    """When more than one key is missing from an attribute, the message lists all
    of them, so one read of the error shows the whole problem."""

    def drop_two(d: Any) -> None:
        """Remove two keys from one attribute, so the error has two names to list."""
        for key in ("Type", "Cardinality"):
            d["Condition"]["Attributes"]["name"].pop(key)

    broken = variant(drop_two)
    with pytest.raises(
        usdm_spec.SpecShapeError, match="Condition.name is missing Type, Cardinality"
    ):
        usdm_spec.load(broken, verify=False)


@code("SA00135")
@category("processing")
@objective("functionality")
@negative
@needs_fixture("usdm_three_classes.yml")
def test_type_that_is_not_a_reference_list_is_named(variant):
    """A Type holding a plain word instead of a list of '$ref' entries is refused,
    naming Class.attribute and the field, rather than failing later inside the
    printer when it tries to walk the value."""
    broken = variant(
        lambda d: d["Condition"]["Attributes"]["name"].__setitem__("Type", "string")
    )
    with pytest.raises(
        usdm_spec.SpecShapeError, match="Condition.name: Type is not a list"
    ):
        usdm_spec.load(broken, verify=False)


@code("SA00136")
@category("processing")
@objective("functionality")
@negative
@needs_fixture("usdm_three_classes.yml")
def test_empty_type_list_is_refused(variant):
    """An attribute with an empty list of types is refused, and the message names the
    attribute, because an attribute with no type cannot be described."""
    broken = variant(
        lambda d: d["Condition"]["Attributes"]["name"].__setitem__("Type", [])
    )
    with pytest.raises(
        usdm_spec.SpecShapeError, match="Condition.name: Type is not a list"
    ):
        usdm_spec.load(broken, verify=False)


@code("SA00137")
@category("processing")
@objective("functionality")
@negative
@needs_fixture("usdm_three_classes.yml")
def test_inherited_from_without_ref_is_named(variant):
    """An Inherited From entry that does not name its parent class is refused, and the
    message names the attribute and the field."""
    broken = variant(
        lambda d: d["StudyIdentifier"]["Attributes"]["id"].__setitem__(
            "Inherited From", [{"ref": "x"}]
        )
    )
    with pytest.raises(
        usdm_spec.SpecShapeError,
        match="StudyIdentifier.id: Inherited From is not a list",
    ):
        usdm_spec.load(broken, verify=False)


#######################################################################################
### Refusing a file that cannot be trusted (exit 16) ###
#
# The per-cause messages are the pinned-file check's and are proven in
# validation/sdg/sources/test_verify_pinned_technical.py. These prove the module is
# wired to it: a file no manifest records, and a file whose fingerprint differs, are
# refused through load() with the same messages.


@code("SA00138")
@category("processing")
@objective("functionality")
@negative
def test_missing_file_raises_filenotfound(tmp_path):
    """A path that does not exist is refused as a missing file, exit 12 at the command
    line, which is a different failure from a file that fails its fingerprint."""
    with pytest.raises(FileNotFoundError) as caught:
        usdm_spec.load(tmp_path / "nope.yml")
    assert "nope.yml" in str(caught.value)


@code("SA00139")
@category("processing")
@objective("functionality")
@negative
@needs_fixture("usdm_three_classes.yml")
def test_unrecorded_file_is_refused_through_load(manifest_dir):
    """A file no manifest entry records is refused when loaded, with a message saying
    exactly that rather than the remedy for a changed file.

    The manifests are staged, holding no entry, so a broken real manifest cannot make
    this check fail for a reason of its own."""
    manifest_dir('{"files": []}')
    with pytest.raises(usdm_spec.UnrecordedFileError) as caught:
        usdm_spec.load(FIXTURE)
    message = str(caught.value)
    assert "no manifest entry records it" in message
    assert "acquire_sources" not in message


@code("SA00140")
@category("processing")
@objective("functionality")
@negative
@needs_fixture("usdm_three_classes.yml")
def test_fingerprint_mismatch_is_refused_through_load(fake_repo, manifest_recording):
    """A file whose fingerprint differs from its record is refused when loaded, and the
    message shows both fingerprints and the ways to recover.

    The fixture is copied under the fake repo's inputs/, because a manifest may record
    only a location there."""
    staged = fake_repo.file(usdm_spec.PINNED_LOCAL, FIXTURE.read_bytes())
    # The recorded sha256 is the all-zero placeholder, so the fingerprint cannot match.
    fake_repo.manifest("cdisc_usdm_v4", manifest_recording(staged))
    with pytest.raises(usdm_spec.IntegrityError) as caught:
        usdm_spec.load(staged)
    message = str(caught.value)
    found = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()[:16]
    assert f"sha256 {found}" in message
    assert "manifest says 0000" in message and "--allow-unpinned" in message


#######################################################################################
### Command line exit codes ###
#
# main() takes the argument list and returns the exit code, so each documented
# code can be checked without a subprocess. The loader always reads DEFAULT_SPEC
# from the command line, so codes that need a broken input point DEFAULT_SPEC at
# a temporary file for the duration of the test.


@code("SA00141")
@category("processing")
@objective("functionality")
@negative
def test_cli_no_mode_exits_2(capsys):
    """Running with no mode option is a usage error. The usage is printed and the run
    exits 2."""
    with pytest.raises(SystemExit) as caught:
        usdm_spec.main([])
    assert caught.value.code == 2
    assert "usage:" in capsys.readouterr().err


@code("SA00142")
@category("processing")
@objective("functionality")
@negative
def test_cli_missing_spec_exits_12(monkeypatch, capsys):
    """When the pinned file is not downloaded, the command exits 12 and says to run
    acquire_sources."""
    # A path under the repo, because the message prints it relative to the repo
    # root, as it does for the real pinned path. Nothing is written there.
    monkeypatch.setattr(usdm_spec, "DEFAULT_SPEC", FIXTURE.with_name("nope.yml"))
    assert usdm_spec.main(["--list-classes"]) == 12
    err = capsys.readouterr().err
    assert exit_line(12, "PINNED-FILE-NOT-DOWNLOADED") in err
    assert "acquire_sources" in err


@code("SA00143")
@category("processing")
@objective("functionality")
@negative
@needs_fixture("usdm_three_classes.yml")
def test_cli_unrecorded_spec_exits_16(monkeypatch, capsys, manifest_dir):
    """When the file is present but no manifest entry records it, the command
    exits 16 and prints the cause.

    The manifests are staged, holding no entry, so a broken real manifest cannot make
    this check fail for a reason of its own."""
    manifest_dir('{"files": []}')
    monkeypatch.setattr(usdm_spec, "DEFAULT_SPEC", FIXTURE)
    assert usdm_spec.main(["--list-classes"]) == 16
    err = capsys.readouterr().err
    assert exit_line(16, "FILE-UNRECORDED") in err
    assert "no manifest entry records it" in err


@code("SA00144")
@category("processing")
@objective("functionality")
@negative
@needs_fixture("usdm_three_classes.yml")
def test_cli_fingerprint_mismatch_exits_16(
    fake_repo, manifest_recording, monkeypatch, capsys
):
    """When the file is present but its fingerprint differs from its manifest entry, the
    command exits 16 and prints both fingerprints and the way to proceed without the pin.

    The fixture is copied under the fake repo's inputs/, because a manifest may record
    only a location there."""
    staged = fake_repo.file(usdm_spec.PINNED_LOCAL, FIXTURE.read_bytes())
    # The recorded sha256 is the all-zero placeholder, so the fingerprint cannot match.
    fake_repo.manifest("cdisc_usdm_v4", manifest_recording(staged))
    monkeypatch.setattr(usdm_spec, "DEFAULT_SPEC", staged)
    assert usdm_spec.main(["--list-classes"]) == 16
    err = capsys.readouterr().err
    assert exit_line(16, "PINNED-FILE-CHANGED") in err
    found = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()[:16]
    assert f"sha256 {found}" in err
    assert "manifest says 0000" in err and "--allow-unpinned" in err


@code("SA00145")
@category("processing")
@objective("functionality")
@negative
@needs_fixture("usdm_three_classes.yml")
def test_cli_unparseable_manifest_exits_14(manifest_dir, monkeypatch, capsys):
    """When a manifest is not valid JSON, the command exits 14 and names the manifest as
    what is not valid, rather than blaming the pinned file."""
    manifest_dir("{ not json")
    monkeypatch.setattr(usdm_spec, "DEFAULT_SPEC", FIXTURE)
    assert usdm_spec.main(["--list-classes"]) == 14
    err = capsys.readouterr().err
    assert exit_line(14, "MANIFEST-UNPARSEABLE") in err
    assert "cdisc_usdm_v4.json" in err and "is not valid JSON" in err


@code("SA00146")
@category("processing")
@objective("functionality")
@pytest.mark.parametrize(
    "extra", [[], ["--allow-unpinned"]], ids=["verify", "allow-unpinned"]
)
@negative
def test_cli_not_inside_repo_exits_3(monkeypatch, tmp_path, capsys, extra):
    """When the sdg package is not running from inside its repo, the command exits 3 and
    prints the install command. It runs twice, with and without the option that skips
    the pinned-file record, because that option must not skip this refusal.

    Staged as it really happens: the root the sdg package takes to be the repo is a
    folder with no repo in it, and the spec path, which follows that root, does not
    exist there. Checked with and without --allow-unpinned, since that flag bypasses
    the manifest check and must not bypass this one."""
    from sdg.sources import read_manifests

    monkeypatch.setattr(read_manifests, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(usdm_spec, "DEFAULT_SPEC", tmp_path / "inputs" / "nope.yml")
    assert usdm_spec.main(["--list-classes", *extra]) == 3
    err = capsys.readouterr().err
    assert exit_line(3, "NOT-IN-REPO") in err
    assert "pip install -e ." in err and "acquire_sources" not in err


@code("SA00147")
@category("processing")
@objective("functionality")
@negative
@needs_fixture("usdm_three_classes.yml")
def test_cli_wrong_shape_exits_15(variant, monkeypatch, capsys):
    """When the file loads but is not shaped like USDM, the command exits 15 and names
    the broken class."""
    broken = variant(lambda d: d["Condition"].pop("Attributes"))
    monkeypatch.setattr(usdm_spec, "DEFAULT_SPEC", broken)
    assert usdm_spec.main(["--list-classes", "--allow-unpinned"]) == 15
    err = capsys.readouterr().err
    assert exit_line(15, "USDM-MODEL-WRONG-SHAPE") in err
    assert "'Condition'" in err


@code("SA00148")
@category("processing")
@objective("functionality")
@negative
@needs_fixture("usdm_three_classes.yml")
def test_cli_locked_file_exits_13(variant, monkeypatch, capsys):
    """When the pinned file is on disk but another program has it locked, the command
    exits 13 and says to close that program, rather than ending in a traceback."""
    monkeypatch.setattr(usdm_spec, "DEFAULT_SPEC", variant(lambda d: None))

    def locked(target: str | Path) -> NoReturn:
        """Stand in for the pinned-file check with the refusal a locked file gives."""
        raise PermissionError("locked by another program")

    monkeypatch.setattr(usdm_spec, "verify_file", locked)
    assert usdm_spec.main(["--list-classes"]) == 13
    err = capsys.readouterr().err
    assert exit_line(13, "PINNED-FILE-UNREADABLE") in err
    assert "close the program holding the file" in err


@code("SA00149")
@category("processing")
@objective("functionality")
@negative
@needs_fixture("usdm_three_classes.yml")
def test_cli_malformed_type_exits_15_not_traceback(variant, monkeypatch, capsys):
    """A file whose type values are not lists of references makes the attributes option
    exit 15 and name the attribute, rather than failing with a Python error while
    printing."""
    broken = variant(
        lambda d: d["StudyIdentifier"]["Attributes"]["scopeId"].__setitem__(
            "Type", None
        )
    )
    monkeypatch.setattr(usdm_spec, "DEFAULT_SPEC", broken)
    assert usdm_spec.main(["--attributes", "StudyIdentifier", "--allow-unpinned"]) == 15
    err = capsys.readouterr().err
    assert exit_line(15, "USDM-MODEL-WRONG-SHAPE") in err
    assert "StudyIdentifier.scopeId: Type is not a list" in err


@code("SA00150")
@category("processing")
@objective("functionality")
@positive
@needs_fixture("usdm_three_classes.yml")
def test_cli_allow_unpinned_reads_the_file(monkeypatch, capsys):
    """With the allow-unpinned option, the manifest check is skipped and a file no
    manifest records is read in place, listing its classes and exiting 0."""
    monkeypatch.setattr(usdm_spec, "DEFAULT_SPEC", FIXTURE)
    assert usdm_spec.main(["--list-classes", "--allow-unpinned"]) == 0
    out, err = capsys.readouterr()
    assert out.splitlines() == [
        "Condition",
        "Identifier  [abstract]",
        "StudyIdentifier",
    ]
    assert "3 classes (2 concrete, 1 abstract)" in err


@code("SA00151")
@category("processing")
@objective("functionality")
@positive
@needs_fixture("usdm_three_classes.yml")
def test_cli_attributes_prints_type_cardinality_kind(monkeypatch, capsys):
    """The attributes listing prints each attribute's type, cardinality and
    kind, marks inherited ones with their parent, and exits 0."""
    monkeypatch.setattr(usdm_spec, "DEFAULT_SPEC", FIXTURE)
    assert usdm_spec.main(["--attributes", "StudyIdentifier", "--allow-unpinned"]) == 0
    out = capsys.readouterr().out
    assert "StudyIdentifier  (concrete)" in out
    assert "type        Organization" in out
    assert "kind        Ref  (inherited from Identifier)" in out
    assert "cardinality 0..*" in out


@code("SA00152")
@category("processing")
@objective("functionality")
@negative
@needs_fixture("usdm_three_classes.yml")
def test_cli_unknown_class_exits_17(monkeypatch, capsys):
    """The attributes listing for a class that does not exist exits 17 and points
    at the class listing, rather than ending in a traceback."""
    monkeypatch.setattr(usdm_spec, "DEFAULT_SPEC", FIXTURE)
    assert usdm_spec.main(["--attributes", "Nope", "--allow-unpinned"]) == 17
    err = capsys.readouterr().err
    assert exit_line(17, "USDM-CLASS-NOT-FOUND") in err
    assert "run --list-classes" in err


#######################################################################################
### A class with no definition ###


@code("SA00533")
@category("processing")
@objective("functionality")
@positive
@needs_fixture("usdm_three_classes.yml")
def test_a_class_with_no_definition_is_listed_without_one(variant, monkeypatch, capsys):
    """Asking for the attributes of a class that has no Definition prints the class
    and its attributes, with no definition line, rather than failing."""
    bare = variant(lambda d: d["Condition"].pop("Definition"))
    monkeypatch.setattr(usdm_spec, "DEFAULT_SPEC", bare)
    assert usdm_spec.main(["--attributes", "Condition", "--allow-unpinned"]) == 0
    printed = capsys.readouterr().out
    assert "Condition  (concrete)" in printed
    assert "A state of being." not in printed


#######################################################################################
### A manifest location outside inputs/ and a file that is not YAML ###


@code("SA00610")
@category("processing")
@objective("functionality")
@negative
@needs_fixture("usdm_three_classes.yml")
def test_cli_manifest_location_outside_inputs_exits_15(fake_repo, monkeypatch, capsys):
    """When a manifest records a location that does not stay under inputs/, the
    command exits 15 and quotes the location, rather than reporting an unreadable
    manifest."""
    staged = fake_repo.file(usdm_spec.PINNED_LOCAL, FIXTURE.read_bytes())
    fake_repo.manifest(
        "stray", [fake_repo.entry("inputs/../elsewhere.txt", bytes=1, sha256="0" * 64)]
    )
    monkeypatch.setattr(usdm_spec, "DEFAULT_SPEC", staged)
    assert usdm_spec.main(["--list-classes"]) == 15
    err = capsys.readouterr().err
    assert exit_line(15, "MANIFEST-LOCATION-OUTSIDE-INPUTS") in err
    assert "does not stay under inputs/" in err


@code("SA00615")
@category("processing")
@objective("functionality")
@negative
def test_cli_a_file_that_is_not_yaml_exits_14(tmp_path, monkeypatch, capsys):
    """When the model file is not valid YAML and the pinned-file record is skipped, the
    command exits 14 and says the file is not valid YAML, rather than stopping on a
    traceback."""
    broken = tmp_path / "broken.yml"
    broken.write_text("Activity: [unclosed\n", encoding="utf-8")
    monkeypatch.setattr(usdm_spec, "DEFAULT_SPEC", broken)
    assert usdm_spec.main(["--list-classes", "--allow-unpinned"]) == 14
    err = capsys.readouterr().err
    assert exit_line(14, "USDM-MODEL-UNPARSEABLE") in err
    assert "broken.yml is not valid YAML" in err
