"""
Script:      test_usdm_spec.py
Description: Automated checks for src/sdg/usdm_spec.py, the one module that reads
             the pinned USDM model. Each check sets up a situation, runs the
             loader, and compares what happened to what the loader's own
             documentation promises. Run them all with one command; green means
             every promise still holds, red names the one that broke.

             Two groups, two inputs:
             - Logic checks read tests/fixtures/usdm_three_classes.yml, three
               classes copied verbatim from the pinned file. Small enough to read
               whole and to break on purpose (a key deleted, a list where a dict
               should be), which the real file must never be. Broken variants are
               made in memory and written to a temporary folder pytest owns.
             - Real-file checks read the pinned dataStructure.yml itself and
               assert the measured facts about it (86 classes, four multi-target
               attributes, and that the fixture's classes are identical to the
               pinned ones). They skip, with a reason, when data/ is not
               downloaded, so the logic checks still run on a fresh clone.

             Every check is marked positive (the right thing works) or negative
             (the broken thing fails, and the error names the right cause).

Inputs:      tests/fixtures/usdm_three_classes.yml         (read-only)
             data/manifests/raw_usdm_v4.json                (read-only)
             data/raw/usdm_v4/uml/dataStructure.yml         (read-only; real-file
                                                             checks only)
             scripts/verify_manifests.py                    (imported by the loader)

Outputs:     Writes nothing to disk. Temporary files go to pytest's own folder.
             conftest.py writes tests/validation/ records when asked.

Usage:       pytest tests/test_usdm_spec.py
                 run these checks
             pytest tests/test_usdm_spec.py -v
                 one line per check with its result
             pytest --validation-report
                 also write the validation record (see conftest.py)

Exit codes:  pytest's own: 0 all passed, 1 some failed

Date:        2026-09-04
Owner:       Jason Delosh
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from sdg import usdm_spec

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "usdm_three_classes.yml"
FIXTURE_CLASSES = ("Condition", "Identifier", "StudyIdentifier")

# The real-file checks need the pinned download. On a clone without data/ they
# skip and say why, rather than fail and hide the logic checks' results.
needs_pinned_file = pytest.mark.skipif(
    not usdm_spec.DEFAULT_SPEC.exists(),
    reason="pinned dataStructure.yml not downloaded; run scripts/fetch_sources.py",
)

positive = pytest.mark.positive
negative = pytest.mark.negative


#######################################################################################
### Helpers ###
#
# Small tools the checks share: a parsed copy of the fixture, a way to write a
# deliberately broken variant of it, and a way to point the loader at a manifest
# folder of the test's choosing.


@pytest.fixture
def three() -> dict:
    """Produces the fixture file parsed by the loader itself, with the checksum
    check off because no manifest records a test fixture."""
    return usdm_spec.load(FIXTURE, verify=False)


@pytest.fixture
def variant(tmp_path):
    """Produces a function that takes one change to apply to the fixture's parsed
    form, writes the changed copy to a temporary file, and hands back that path.
    The fixture on disk is never touched."""

    def make(change) -> Path:
        data = yaml.safe_load(FIXTURE.read_text(encoding="utf-8"))
        change(data)
        path = tmp_path / "variant.yml"
        path.write_text(yaml.safe_dump(data), encoding="utf-8")
        return path

    return make


@pytest.fixture
def manifest_dir(tmp_path, monkeypatch):
    """Produces a function that takes manifest JSON text (or None for no manifest
    at all), writes it as raw_usdm_v4.json in a temporary folder, and points the
    loader's manifest reader at that folder for the rest of the test. monkeypatch
    puts the real folder back afterwards."""
    tools = usdm_spec._manifest_tools()
    monkeypatch.setattr(tools, "MANIFEST_DIR", tmp_path)

    def make(text: str | None) -> None:
        if text is not None:
            (tmp_path / f"{usdm_spec.MANIFEST_SET}.json").write_text(text, encoding="utf-8")

    return make


def manifest_recording(path: Path, **overrides) -> str:
    """Takes a file path and produces manifest JSON with one entry for it, correct
    in size, with any field overridden (a wrong sha256, a wrong size, a missing key
    via None) so a test can stage exactly one defect."""
    entry = {
        "name": "fixture",
        "local": path.relative_to(usdm_spec.REPO_ROOT).as_posix(),
        "sha256": "0" * 64,
        "bytes": path.stat().st_size,
    }
    for key, value in overrides.items():
        if value is None:
            entry.pop(key)
        else:
            entry[key] = value
    return json.dumps({"files": [entry]})


#######################################################################################
### Reading a well-formed file ###


@positive
def test_lists_every_class_sorted(three):
    """A well-formed file loads, and class_names() gives every class in
    alphabetical order, so a listing is stable from run to run."""
    assert usdm_spec.class_names(three) == sorted(FIXTURE_CLASSES)


@positive
def test_abstract_flag_comes_from_modifier(three):
    """is_abstract() reports USDM's own Modifier: Identifier (a parent never
    instantiated alone) is abstract, StudyIdentifier (its concrete child) is not."""
    assert usdm_spec.is_abstract(three, "Identifier") is True
    assert usdm_spec.is_abstract(three, "StudyIdentifier") is False


@positive
def test_attributes_keep_file_order_and_inheritance(three):
    """attributes() hands back a class's attributes in the order the file lists
    them, including the ones copied down from its parent, and each inherited one
    still names that parent."""
    attrs = usdm_spec.attributes(three, "StudyIdentifier")
    assert list(attrs) == ["id", "text", "scopeId", "extensionAttributes", "instanceType"]
    assert attrs["id"]["Inherited From"] == [{"$ref": "#/Identifier"}]
    assert "Inherited From" not in attrs["instanceType"]


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


@negative
def test_empty_file_is_refused(tmp_path):
    """An empty file is refused as 'empty or not a mapping' instead of being
    treated as a model with no classes."""
    empty = tmp_path / "empty.yml"
    empty.write_text("", encoding="utf-8")
    with pytest.raises(usdm_spec.SpecShapeError, match="empty or not a mapping"):
        usdm_spec.load(empty, verify=False)


@negative
def test_class_without_modifier_is_named(variant):
    """Deleting Modifier from one class is refused with a message naming that
    class."""
    broken = variant(lambda d: d["Condition"].pop("Modifier"))
    with pytest.raises(usdm_spec.SpecShapeError, match="'Condition' is missing Modifier"):
        usdm_spec.load(broken, verify=False)


@negative
def test_unexpected_modifier_value_is_named(variant):
    """A Modifier other than Concrete or Abstract is refused, quoting the
    unexpected value, so a new USDM vocabulary cannot pass unnoticed."""
    broken = variant(lambda d: d["Identifier"].__setitem__("Modifier", "Virtual"))
    with pytest.raises(usdm_spec.SpecShapeError, match="unexpected Modifier 'Virtual'"):
        usdm_spec.load(broken, verify=False)


@negative
def test_attributes_not_a_mapping_is_named(variant):
    """Turning a class's Attributes into a list is refused with a message naming
    the class, before any accessor could trip over it."""
    broken = variant(lambda d: d["StudyIdentifier"].__setitem__("Attributes", []))
    with pytest.raises(
        usdm_spec.SpecShapeError, match="'StudyIdentifier': Attributes is not a mapping"
    ):
        usdm_spec.load(broken, verify=False)


@negative
def test_attribute_missing_a_key_is_named(variant):
    """Renaming 'Relationship Type' on one attribute is refused with a message
    naming Class.attribute and the missing key, rather than surfacing later as a
    KeyError traceback from the printer."""

    def rename(d):
        attr = d["Condition"]["Attributes"]["name"]
        attr["Kind"] = attr.pop("Relationship Type")

    broken = variant(rename)
    with pytest.raises(
        usdm_spec.SpecShapeError, match="Condition.name is missing Relationship Type"
    ):
        usdm_spec.load(broken, verify=False)


@negative
def test_attribute_missing_several_keys_lists_them(variant):
    """When more than one key is missing from an attribute, the message lists all
    of them, so one read of the error shows the whole problem."""

    def drop_two(d):
        for key in ("Type", "Cardinality"):
            d["Condition"]["Attributes"]["name"].pop(key)

    broken = variant(drop_two)
    with pytest.raises(
        usdm_spec.SpecShapeError, match="Condition.name is missing Type, Cardinality"
    ):
        usdm_spec.load(broken, verify=False)


@negative
def test_type_that_is_not_a_reference_list_is_named(variant):
    """A Type holding a plain word instead of a list of '$ref' entries is refused,
    naming Class.attribute and the field, rather than failing later inside the
    printer when it tries to walk the value."""
    broken = variant(lambda d: d["Condition"]["Attributes"]["name"].__setitem__("Type", "string"))
    with pytest.raises(usdm_spec.SpecShapeError, match="Condition.name: Type is not a list"):
        usdm_spec.load(broken, verify=False)


@negative
def test_empty_type_list_is_refused(variant):
    """An empty Type list is refused the same way: an attribute with no type is
    not a shape this module can answer questions about."""
    broken = variant(lambda d: d["Condition"]["Attributes"]["name"].__setitem__("Type", []))
    with pytest.raises(usdm_spec.SpecShapeError, match="Condition.name: Type is not a list"):
        usdm_spec.load(broken, verify=False)


@negative
def test_inherited_from_without_ref_is_named(variant):
    """An Inherited From entry lacking its '$ref' is refused, naming the
    attribute and the field, so the printer never indexes a missing key."""
    broken = variant(
        lambda d: d["StudyIdentifier"]["Attributes"]["id"].__setitem__("Inherited From", [{"ref": "x"}])
    )
    with pytest.raises(
        usdm_spec.SpecShapeError, match="StudyIdentifier.id: Inherited From is not a list"
    ):
        usdm_spec.load(broken, verify=False)


#######################################################################################
### Refusing a file that cannot be trusted (IntegrityError, exit 3) ###
#
# The loader checks the file against data/manifests/ before parsing. Each cause
# of failure must produce its own message with its own remedy; these checks stage
# one cause each and assert the message says that cause and not another.


@negative
def test_missing_file_raises_filenotfound(tmp_path):
    """A path that does not exist raises FileNotFoundError (exit 1 at the command
    line), which is a different failure from a file that fails verification."""
    with pytest.raises(FileNotFoundError):
        usdm_spec.load(tmp_path / "nope.yml")


@negative
def test_unrecorded_file_says_no_entry_records_it():
    """A file no manifest entry records (this fixture, with the check left on)
    is refused with a message saying exactly that and pointing at verify=False,
    not with the checksum-mismatch remedy."""
    with pytest.raises(usdm_spec.IntegrityError) as caught:
        usdm_spec.load(FIXTURE)
    message = str(caught.value)
    assert "no entry in" in message and "verify=False" in message
    assert "checksum" not in message


@negative
def test_unreadable_manifest_says_unreadable(manifest_dir):
    """A manifest that is not valid JSON is reported as unreadable, with the
    remedy pointing at the manifest, not at re-downloading the data file."""
    manifest_dir("{not json")
    with pytest.raises(usdm_spec.IntegrityError) as caught:
        usdm_spec.load(FIXTURE)
    message = str(caught.value)
    assert "is unreadable" in message and "git checkout" in message
    assert "fetch_sources" not in message


@negative
def test_absent_manifest_says_not_there(manifest_dir):
    """No manifest file at all is reported as 'not there', with the same
    restore-the-manifest remedy."""
    manifest_dir(None)
    with pytest.raises(usdm_spec.IntegrityError, match="is not there"):
        usdm_spec.load(FIXTURE)


@negative
def test_entry_without_sha256_says_malformed(manifest_dir):
    """A manifest entry for the file that carries no sha256 is reported as
    malformed, with the remedy pointing at that entry."""
    manifest_dir(manifest_recording(FIXTURE, sha256=None))
    with pytest.raises(usdm_spec.IntegrityError, match="manifest entry is malformed"):
        usdm_spec.load(FIXTURE)


@negative
def test_checksum_mismatch_shows_both_hashes_and_recovery(manifest_dir):
    """A recorded sha256 that differs from the file's is reported with both
    values and the three recovery paths, including --allow-unpinned."""
    manifest_dir(manifest_recording(FIXTURE))  # sha256 is the all-zero placeholder
    with pytest.raises(usdm_spec.IntegrityError) as caught:
        usdm_spec.load(FIXTURE)
    message = str(caught.value)
    assert "sha256" in message and "manifest says 0000" in message
    assert "--allow-unpinned" in message and "fetch_sources" in message


@negative
def test_size_mismatch_is_reported_as_size(manifest_dir):
    """A recorded byte count that differs from the file's is reported as a size
    difference (checked before the hash, since it usually means a truncated
    download), with the same recovery paths."""
    manifest_dir(manifest_recording(FIXTURE, bytes=1))
    with pytest.raises(usdm_spec.IntegrityError, match="size .* bytes, manifest says 1"):
        usdm_spec.load(FIXTURE)


#######################################################################################
### Command line exit codes ###
#
# main() takes the argument list and returns the exit code, so each documented
# code can be checked without a subprocess. The loader always reads DEFAULT_SPEC
# from the command line, so codes that need a broken input point DEFAULT_SPEC at
# a temporary file for the duration of the test.


@negative
def test_cli_no_mode_exits_2():
    """Running with no mode flag is a usage error: argparse prints usage and
    exits 2."""
    with pytest.raises(SystemExit) as caught:
        usdm_spec.main([])
    assert caught.value.code == 2


@negative
def test_cli_missing_spec_exits_1(monkeypatch, capsys):
    """When the pinned file is not downloaded, the command exits 1 and tells the
    user to run fetch_sources.py."""
    # A path under the repo, because the message prints it relative to the repo
    # root, as it does for the real pinned path. Nothing is written there.
    monkeypatch.setattr(usdm_spec, "DEFAULT_SPEC", FIXTURE.with_name("nope.yml"))
    assert usdm_spec.main(["--list-classes"]) == 1
    assert "fetch_sources" in capsys.readouterr().err


@negative
def test_cli_unverifiable_spec_exits_3(monkeypatch, capsys):
    """When the file is present but cannot be verified against the manifest, the
    command exits 3 and prints the cause."""
    monkeypatch.setattr(usdm_spec, "DEFAULT_SPEC", FIXTURE)
    assert usdm_spec.main(["--list-classes"]) == 3
    assert "no entry in" in capsys.readouterr().err


@negative
def test_cli_wrong_shape_exits_4(variant, monkeypatch, capsys):
    """When the file passes (or skips) verification but is not shaped like USDM,
    the command exits 4 and names the broken class."""
    broken = variant(lambda d: d["Condition"].pop("Attributes"))
    monkeypatch.setattr(usdm_spec, "DEFAULT_SPEC", broken)
    assert usdm_spec.main(["--list-classes", "--allow-unpinned"]) == 4
    assert "'Condition'" in capsys.readouterr().err


@negative
def test_cli_malformed_type_exits_4_not_traceback(variant, monkeypatch, capsys):
    """A file whose Type values are not reference lists makes --attributes exit 4
    with the attribute named, not crash with a traceback while printing."""
    broken = variant(lambda d: d["StudyIdentifier"]["Attributes"]["scopeId"].__setitem__("Type", None))
    monkeypatch.setattr(usdm_spec, "DEFAULT_SPEC", broken)
    assert usdm_spec.main(["--attributes", "StudyIdentifier", "--allow-unpinned"]) == 4
    assert "StudyIdentifier.scopeId: Type is not a list" in capsys.readouterr().err


@positive
def test_cli_allow_unpinned_reads_the_file(monkeypatch, capsys):
    """--allow-unpinned skips the manifest check and reads the file in place: the
    fixture (unrecorded) lists its three classes and exits 0."""
    monkeypatch.setattr(usdm_spec, "DEFAULT_SPEC", FIXTURE)
    assert usdm_spec.main(["--list-classes", "--allow-unpinned"]) == 0
    out, err = capsys.readouterr()
    assert out.splitlines() == ["Condition", "Identifier  [abstract]", "StudyIdentifier"]
    assert "3 classes (2 concrete, 1 abstract)" in err


@positive
def test_cli_attributes_prints_type_cardinality_kind(monkeypatch, capsys):
    """--attributes prints each attribute's type, cardinality and kind, and marks
    inherited ones with their parent, exiting 0."""
    monkeypatch.setattr(usdm_spec, "DEFAULT_SPEC", FIXTURE)
    assert usdm_spec.main(["--attributes", "StudyIdentifier", "--allow-unpinned"]) == 0
    out = capsys.readouterr().out
    assert "StudyIdentifier  (concrete)" in out
    assert "kind        Ref  (inherited from Identifier)" in out
    assert "cardinality 0..*" in out


@negative
def test_cli_unknown_class_exits_5(monkeypatch, capsys):
    """--attributes with a class that does not exist exits 5 and points at
    --list-classes, rather than ending in a traceback."""
    monkeypatch.setattr(usdm_spec, "DEFAULT_SPEC", FIXTURE)
    assert usdm_spec.main(["--attributes", "Nope", "--allow-unpinned"]) == 5
    assert "run --list-classes" in capsys.readouterr().err


#######################################################################################
### The real pinned file ###
#
# These prove the assumptions the logic checks rely on hold for the actual
# standard, and that the fixture is a faithful sample of it. They are the only
# checks that need data/ downloaded.


@needs_pinned_file
@positive
def test_pinned_file_verifies_and_loads():
    """The pinned dataStructure.yml matches its manifest checksum, and passes both
    shape checks, on the real thing."""
    assert usdm_spec.load()


@needs_pinned_file
@positive
def test_pinned_file_has_86_classes_80_concrete():
    """The pinned model holds 86 classes, 80 concrete and 6 abstract, the figures
    docs/sources.md records (check_facts.py re-derives the 80 as well)."""
    spec = usdm_spec.load()
    names = usdm_spec.class_names(spec)
    abstract = [n for n in names if usdm_spec.is_abstract(spec, n)]
    assert len(names) == 86
    assert len(abstract) == 6
    assert abstract == [
        "Identifier",
        "PopulationDefinition",
        "QuantityRange",
        "ScheduledInstance",
        "StudyDesign",
        "SyntaxTemplate",
    ]


@needs_pinned_file
@positive
def test_pinned_file_types_are_classes_or_five_primitives():
    """Every attribute type in the pinned model is either a class in the model or
    one of five primitives (string, boolean, integer, float, date), and exactly
    four attributes reference more than one type, as targets() documents."""
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


@needs_pinned_file
@positive
def test_fixture_classes_are_identical_to_pinned():
    """Each of the fixture's three classes is identical, key for key, to the same
    class in the pinned file, so the logic checks above ran on real USDM shapes and
    not on an approximation of them."""
    pinned = usdm_spec.load()
    sample = usdm_spec.load(FIXTURE, verify=False)
    for name in FIXTURE_CLASSES:
        assert sample[name] == pinned[name], name
