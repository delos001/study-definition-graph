"""
Script:      test_usdm_spec.py
Description: Checks for src/sdg/usdm/usdm_spec.py, the one module that reads
             the pinned USDM model. Each check sets up a situation, runs the
             loader, and compares what happened to what the loader's own
             documentation promises. Run them all with one command; green means
             every promise still holds, red names the one that broke.

             Two groups, two inputs:
             - Logic checks read validation/fixtures/usdm_three_classes.yml, three
               classes copied verbatim from the pinned file. Small enough to read
               whole and to break on purpose (a key deleted, a list where a dict
               should be), which the real file must never be. Broken variants are
               made in memory and written to a temporary folder pytest owns.
             - Real-file checks read the pinned dataStructure.yml itself and
               assert the measured facts about it (the class count, the attributes
               that reference several types, and that the fixture's classes are
               identical to the pinned ones). They skip, with a reason, when inputs/ is not
               downloaded, so the logic checks still run on a fresh clone.

             Every check is marked positive (the right thing works) or negative
             (the broken thing fails, and the error names the right cause).

Inputs:      validation/fixtures/usdm_three_classes.yml               (read-only)
             manifests/cdisc_usdm_v4.json                         (read-only, through
                                                                   src/sdg/sources/read_manifests.py)
             inputs/standards/cdisc/usdm_v4/dataStructure.yml     (read-only; real-file
                                                                   checks only)

Outputs:     Writes nothing to disk. Temporary files go to pytest's own folder.
             conftest.py writes validation/reports/ records when asked.

Usage:       pytest validation/usdm/test_usdm_spec.py
                 run these checks
             pytest validation/usdm/test_usdm_spec.py -v
                 one line per check with its result
             pytest --validation-report
                 also write the validation record (see conftest.py)

Exit codes:  pytest's own: 0 all passed, 1 some failed

Date:        2026-09-04
Owner:       Jason Delosh
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from sdg.usdm import usdm_spec

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "usdm_three_classes.yml"
FIXTURE_CLASSES = ("Condition", "Identifier", "StudyIdentifier")

# The real-file checks read the pinned model file. validation/conftest.py skips them
# when it is not downloaded, as on a fresh clone, or when it no longer matches its
# manifest entry, rather than fail and hide the logic checks' results.
needs_pinned_file = pytest.mark.needs_pinned(
    "inputs/standards/cdisc/usdm_v4/dataStructure.yml"
)

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

    def make(change) -> Path:
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


@code("USD0001")
@category("conversion")
@objective("correctness")
@positive
def test_lists_every_class_sorted(three):
    """A well-formed file loads, and class_names() gives every class in
    alphabetical order, so a listing is stable from run to run."""
    assert usdm_spec.class_names(three) == sorted(FIXTURE_CLASSES)


@code("USD0002")
@category("conversion")
@objective("correctness")
@positive
def test_abstract_flag_comes_from_modifier(three):
    """is_abstract() reports USDM's own Modifier, so Identifier, a parent never used
    on its own, is abstract, and StudyIdentifier, its concrete child, is not."""
    assert usdm_spec.is_abstract(three, "Identifier") is True
    assert usdm_spec.is_abstract(three, "StudyIdentifier") is False


@code("USD0003")
@category("conversion")
@objective("correctness")
@positive
def test_attributes_keep_file_order_and_inheritance(three):
    """attributes() hands back a class's attributes in the order the file lists
    them, including the ones copied down from its parent, and each inherited one
    still names that parent."""
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


@code("USD0004")
@category("conversion")
@objective("correctness")
@positive
def test_targets_unwraps_one_and_many(three):
    """targets() turns USDM's '$ref: #/X' wrapping into plain names, for an
    attribute with one target and for the five-way one (Condition.appliesToIds)."""
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


@code("USD0005")
@category("conversion")
@objective("correctness")
@negative
def test_unknown_class_raises_keyerror_naming_it(three):
    """Asking for a class that is not in the file raises KeyError carrying that
    name, so a typo is reported rather than answered with an empty result."""
    with pytest.raises(KeyError, match="Nope"):
        usdm_spec.attributes(three, "Nope")
    with pytest.raises(KeyError, match="Nope"):
        usdm_spec.is_abstract(three, "Nope")


#######################################################################################
### Refusing a wrongly shaped file (SpecShapeError, exit 4) ###
#
# Each check breaks the fixture in one described way and asserts the loader
# refuses it with a message naming the broken class or attribute, which is the
# promise SpecShapeError exists to keep.


@code("USD0006")
@category("conversion")
@objective("correctness")
@negative
def test_empty_file_is_refused(tmp_path):
    """An empty file is refused as 'empty or not a mapping' instead of being
    treated as a model with no classes."""
    empty = tmp_path / "empty.yml"
    empty.write_text("", encoding="utf-8")
    with pytest.raises(usdm_spec.SpecShapeError, match="empty or not a mapping"):
        usdm_spec.load(empty, verify=False)


@code("USD0007")
@category("conversion")
@objective("correctness")
@negative
def test_class_without_modifier_is_named(variant):
    """Deleting Modifier from one class is refused with a message naming that
    class."""
    broken = variant(lambda d: d["Condition"].pop("Modifier"))
    with pytest.raises(
        usdm_spec.SpecShapeError, match="'Condition' is missing Modifier"
    ):
        usdm_spec.load(broken, verify=False)


@code("USD0008")
@category("conversion")
@objective("correctness")
@negative
def test_unexpected_modifier_value_is_named(variant):
    """A Modifier other than Concrete or Abstract is refused, quoting the
    unexpected value, so a new USDM vocabulary cannot pass unnoticed."""
    broken = variant(lambda d: d["Identifier"].__setitem__("Modifier", "Virtual"))
    with pytest.raises(usdm_spec.SpecShapeError, match="unexpected Modifier 'Virtual'"):
        usdm_spec.load(broken, verify=False)


@code("USD0009")
@category("conversion")
@objective("correctness")
@negative
def test_attributes_not_a_mapping_is_named(variant):
    """Turning a class's Attributes into a list is refused with a message naming
    the class, before any reading function could trip over it."""
    broken = variant(lambda d: d["StudyIdentifier"].__setitem__("Attributes", []))
    with pytest.raises(
        usdm_spec.SpecShapeError, match="'StudyIdentifier': Attributes is not a mapping"
    ):
        usdm_spec.load(broken, verify=False)


@code("USD0010")
@category("conversion")
@objective("correctness")
@negative
def test_attribute_missing_a_key_is_named(variant):
    """Renaming 'Relationship Type' on one attribute is refused with a message
    naming Class.attribute and the missing key, rather than surfacing later as a
    KeyError traceback from the attribute printer in usdm_spec.py."""

    def rename(d):
        """Rename one attribute's Relationship Type key, so the expected key is gone."""
        attr = d["Condition"]["Attributes"]["name"]
        attr["Kind"] = attr.pop("Relationship Type")

    broken = variant(rename)
    with pytest.raises(
        usdm_spec.SpecShapeError, match="Condition.name is missing Relationship Type"
    ):
        usdm_spec.load(broken, verify=False)


@code("USD0011")
@category("conversion")
@objective("correctness")
@negative
def test_attribute_missing_several_keys_lists_them(variant):
    """When more than one key is missing from an attribute, the message lists all
    of them, so one read of the error shows the whole problem."""

    def drop_two(d):
        """Remove two keys from one attribute, so the error has two names to list."""
        for key in ("Type", "Cardinality"):
            d["Condition"]["Attributes"]["name"].pop(key)

    broken = variant(drop_two)
    with pytest.raises(
        usdm_spec.SpecShapeError, match="Condition.name is missing Type, Cardinality"
    ):
        usdm_spec.load(broken, verify=False)


@code("USD0012")
@category("conversion")
@objective("correctness")
@negative
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


@code("USD0013")
@category("conversion")
@objective("correctness")
@negative
def test_empty_type_list_is_refused(variant):
    """An attribute whose Type list is empty is refused with a message naming the
    attribute, because an attribute with no type is not a shape usdm_spec.py can
    answer questions about."""
    broken = variant(
        lambda d: d["Condition"]["Attributes"]["name"].__setitem__("Type", [])
    )
    with pytest.raises(
        usdm_spec.SpecShapeError, match="Condition.name: Type is not a list"
    ):
        usdm_spec.load(broken, verify=False)


@code("USD0014")
@category("conversion")
@objective("correctness")
@negative
def test_inherited_from_without_ref_is_named(variant):
    """An Inherited From entry lacking its '$ref' is refused, naming the
    attribute and the field, so the attribute printer in usdm_spec.py never indexes a missing key."""
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
### Refusing a file that cannot be trusted (exits 9 and 10) ###
#
# The per-cause messages are the pinned-file check's and are proven in
# validation/sources/test_verify_pinned.py. These prove the module is wired to it: a
# file no manifest records, and a file
# whose fingerprint differs, are refused through load() with the same messages.


@code("USD0015")
@category("conversion")
@objective("correctness")
@negative
def test_missing_file_raises_filenotfound(tmp_path):
    """A path that does not exist raises FileNotFoundError (exit 8 at the command
    line), which is a different failure from a file that fails verification."""
    with pytest.raises(FileNotFoundError) as caught:
        usdm_spec.load(tmp_path / "nope.yml")
    assert "nope.yml" in str(caught.value)


@code("USD0016")
@category("conversion")
@objective("correctness")
@negative
def test_unrecorded_file_is_refused_through_load():
    """A file no manifest entry records is refused by load() with the pinned-file
    check's message saying exactly that, not with the fingerprint-mismatch remedy."""
    with pytest.raises(usdm_spec.UnrecordedFileError) as caught:
        usdm_spec.load(FIXTURE)
    message = str(caught.value)
    assert "no manifest entry records it" in message
    assert "acquire_sources" not in message


@code("USD0017")
@category("conversion")
@objective("correctness")
@negative
def test_fingerprint_mismatch_is_refused_through_load(manifest_dir, manifest_recording):
    """A file whose recorded sha256 differs is refused by load() with both values
    and the recovery paths, including --allow-unpinned."""
    manifest_dir(manifest_recording(FIXTURE))  # sha256 is the all-zero placeholder
    with pytest.raises(usdm_spec.IntegrityError) as caught:
        usdm_spec.load(FIXTURE)
    message = str(caught.value)
    assert "manifest says 0000" in message and "--allow-unpinned" in message


#######################################################################################
### Command line exit codes ###
#
# main() takes the argument list and returns the exit code, so each documented
# code can be checked without a subprocess. The loader always reads DEFAULT_SPEC
# from the command line, so codes that need a broken input point DEFAULT_SPEC at
# a temporary file for the duration of the test.


@code("USD0018")
@category("conversion")
@objective("correctness")
@negative
def test_cli_no_mode_exits_2():
    """Running with no mode flag is a usage error: argparse prints usage and
    exits 2."""
    with pytest.raises(SystemExit) as caught:
        usdm_spec.main([])
    assert caught.value.code == 2


@code("USD0019")
@category("conversion")
@objective("correctness")
@negative
def test_cli_missing_spec_exits_8(monkeypatch, capsys):
    """When the pinned file is not downloaded, the command exits 8 and tells the
    user to run acquire_sources."""
    # A path under the repo, because the message prints it relative to the repo
    # root, as it does for the real pinned path. Nothing is written there.
    monkeypatch.setattr(usdm_spec, "DEFAULT_SPEC", FIXTURE.with_name("nope.yml"))
    assert usdm_spec.main(["--list-classes"]) == 8
    assert "acquire_sources" in capsys.readouterr().err


@code("USD0020")
@category("conversion")
@objective("correctness")
@negative
def test_cli_unrecorded_spec_exits_10(monkeypatch, capsys):
    """When the file is present but no manifest entry records it, the command
    exits 10 and prints the cause."""
    monkeypatch.setattr(usdm_spec, "DEFAULT_SPEC", FIXTURE)
    assert usdm_spec.main(["--list-classes"]) == 10
    assert "no manifest entry records it" in capsys.readouterr().err


@code("USD0032")
@category("conversion")
@objective("correctness")
@negative
def test_cli_fingerprint_mismatch_exits_9(
    manifest_dir, manifest_recording, monkeypatch, capsys
):
    """When the file is present but its sha256 differs from its manifest entry, the
    command exits 9 and prints both values and the --allow-unpinned way round."""
    manifest_dir(manifest_recording(FIXTURE))  # sha256 is the all-zero placeholder
    monkeypatch.setattr(usdm_spec, "DEFAULT_SPEC", FIXTURE)
    assert usdm_spec.main(["--list-classes"]) == 9
    err = capsys.readouterr().err
    assert "manifest says 0000" in err and "--allow-unpinned" in err


@code("USD0033")
@category("conversion")
@objective("correctness")
@negative
def test_cli_unreadable_manifest_exits_3(manifest_dir, monkeypatch, capsys):
    """When a manifest is not valid JSON, the command exits 3 and names the manifest
    as the thing that cannot be read, rather than blaming the pinned file."""
    manifest_dir("{ not json")
    monkeypatch.setattr(usdm_spec, "DEFAULT_SPEC", FIXTURE)
    assert usdm_spec.main(["--list-classes"]) == 3
    err = capsys.readouterr().err
    assert "cdisc_usdm_v4.json" in err and "cannot read" in err


@code("USD0021")
@category("conversion")
@objective("correctness")
@pytest.mark.parametrize(
    "extra", [[], ["--allow-unpinned"]], ids=["verify", "allow-unpinned"]
)
@negative
def test_cli_not_inside_repo_exits_6(monkeypatch, tmp_path, capsys, extra):
    """When the sdg package is not running from inside its repo, the command exits 6
    and prints the install command, rather than reporting the spec as missing.

    Staged as it really happens: the root the sdg package takes to be the repo is a
    folder with no repo in it, and the spec path, which follows that root, does not
    exist there. Checked with and without --allow-unpinned, since that flag bypasses
    the manifest check and must not bypass this one."""
    from sdg.sources import read_manifests

    monkeypatch.setattr(read_manifests, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(usdm_spec, "DEFAULT_SPEC", tmp_path / "inputs" / "nope.yml")
    assert usdm_spec.main(["--list-classes", *extra]) == 6
    err = capsys.readouterr().err
    assert "pip install -e ." in err and "acquire_sources" not in err


@code("USD0022")
@category("conversion")
@objective("correctness")
@negative
def test_cli_wrong_shape_exits_4(variant, monkeypatch, capsys):
    """When the file passes (or skips) verification but is not shaped like USDM,
    the command exits 4 and names the broken class."""
    broken = variant(lambda d: d["Condition"].pop("Attributes"))
    monkeypatch.setattr(usdm_spec, "DEFAULT_SPEC", broken)
    assert usdm_spec.main(["--list-classes", "--allow-unpinned"]) == 4
    assert "'Condition'" in capsys.readouterr().err


@code("USD0031")
@category("conversion")
@objective("correctness")
@negative
def test_cli_locked_file_exits_13(variant, monkeypatch, capsys):
    """When the pinned file is on disk but another program has it locked, the command
    exits 13 and says to close that program, rather than ending in a traceback."""
    monkeypatch.setattr(usdm_spec, "DEFAULT_SPEC", variant(lambda d: None))

    def locked(target):
        """Stand in for the pinned-file check with the refusal a locked file gives."""
        raise PermissionError("locked by another program")

    monkeypatch.setattr(usdm_spec, "verify_pinned", locked)
    assert usdm_spec.main(["--list-classes"]) == 13
    assert "close the program holding the file" in capsys.readouterr().err


@code("USD0023")
@category("conversion")
@objective("correctness")
@negative
def test_cli_malformed_type_exits_4_not_traceback(variant, monkeypatch, capsys):
    """A file whose Type values are not reference lists makes --attributes exit 4
    with the attribute named, not crash with a traceback while printing."""
    broken = variant(
        lambda d: d["StudyIdentifier"]["Attributes"]["scopeId"].__setitem__(
            "Type", None
        )
    )
    monkeypatch.setattr(usdm_spec, "DEFAULT_SPEC", broken)
    assert usdm_spec.main(["--attributes", "StudyIdentifier", "--allow-unpinned"]) == 4
    assert "StudyIdentifier.scopeId: Type is not a list" in capsys.readouterr().err


@code("USD0024")
@category("conversion")
@objective("correctness")
@positive
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


@code("USD0025")
@category("conversion")
@objective("correctness")
@positive
def test_cli_attributes_prints_type_cardinality_kind(monkeypatch, capsys):
    """The attributes listing prints each attribute's type, cardinality and
    kind, marks inherited ones with their parent, and exits 0."""
    monkeypatch.setattr(usdm_spec, "DEFAULT_SPEC", FIXTURE)
    assert usdm_spec.main(["--attributes", "StudyIdentifier", "--allow-unpinned"]) == 0
    out = capsys.readouterr().out
    assert "StudyIdentifier  (concrete)" in out
    assert "kind        Ref  (inherited from Identifier)" in out
    assert "cardinality 0..*" in out


@code("USD0026")
@category("conversion")
@objective("correctness")
@negative
def test_cli_unknown_class_exits_5(monkeypatch, capsys):
    """The attributes listing for a class that does not exist exits 5 and points
    at the class listing, rather than ending in a traceback."""
    monkeypatch.setattr(usdm_spec, "DEFAULT_SPEC", FIXTURE)
    assert usdm_spec.main(["--attributes", "Nope", "--allow-unpinned"]) == 5
    assert "run --list-classes" in capsys.readouterr().err


#######################################################################################
### The real pinned file ###
#
# These prove the assumptions the logic checks rely on hold for the actual
# standard, and that the fixture is a faithful sample of it. They are the only
# checks that need inputs/ downloaded.


@code("USD0027")
@category("conversion")
@objective("correctness")
@needs_pinned_file
def test_pinned_file_is_shaped_the_way_the_loader_expects():
    """The pinned dataStructure.yml passes the loader's two shape checks, so what
    src/sdg/usdm/usdm_spec.py expects of USDM v4 matches the real file. The file is
    read without the checksum step, which the stability check for it covers."""
    assert usdm_spec.load(verify=False)


@code("USD0029")
@category("conversion")
@objective("correctness")
@needs_pinned_file
def test_pinned_file_types_are_classes_or_five_primitives():
    """Every attribute type in the pinned model is a class in the model or one of
    the five primitives the docstring of targets() names, and exactly four
    attributes reference more than one type. The check compares with its own copy of
    the five and the four, not with the docstring itself."""
    spec = usdm_spec.load()
    primitives = set()
    multi = []
    for cname, body in spec.items():
        for aname, attr in body["Attributes"].items():
            refs = usdm_spec.targets(attr)
            if len(refs) > 1:
                multi.append(f"{cname}.{aname}")
            primitives.update(r for r in refs if r not in spec)
    assert primitives == {"string", "boolean", "integer", "float", "date"}
    assert sorted(multi) == [
        "Condition.appliesToIds",
        "Condition.contextIds",
        "ProductOrganizationRole.appliesToIds",
        "StudyRole.appliesToIds",
    ]


@code("USD0030")
@category("conversion")
@objective("correctness")
@needs_pinned_file
def test_fixture_classes_are_identical_to_pinned():
    """Each class in the small fixture file is identical, key for key, to the same
    class in the pinned model, so the checks that ran on the fixture ran on real
    USDM shapes and not on an approximation of them."""
    pinned = usdm_spec.load()
    sample = usdm_spec.load(FIXTURE, verify=False)
    for name in FIXTURE_CLASSES:
        assert sample[name] == pinned[name], name
