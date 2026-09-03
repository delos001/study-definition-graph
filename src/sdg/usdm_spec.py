"""
Script:      usdm_spec.py
Description: The single way to access the pinned USDM model. It reads
             dataStructure.yml (the USDM v4.0 UML deliverable), and answers
             questions about the standard's classes and their attributes.

             Design: The file is parsed once into its native form (the nested
             dicts and lists exactly as CDISC published them). Every function
             works off that one parse.
             - Nothing here re-models USDM into a new set of names.
             - Simple accessors hand back a slice of the parsed data unchanged;
             - Exception: USDM wraps every type in a "$ref" string and this script
             unwraps the "$ref" string using targets().

             Reading the standard anywhere in this project goes through this
             module, so there is one way to obtain any fact about USDM and no
             second representation to keep faithful.

             Cross-cutting queries the flat file cannot answer directly
             (which classes reference a given class; the whole-model edge list)
             will be added here as later phases need them, not built up front.

             Before reading the file, load() checks it against the checksum
             recorded in data/manifests/, reusing verify_manifests.py. A
             changed or swapped pin fails here rather than parsing and
             passing wrong content downstream;
             - Override is possible but should be used with caution: --allow-unpinned

             Why this file and not USDM_API.json: the API spec discards the
             target class of every relationship and every cardinality, which is
             exactly what makes the standard a graph. See DECISIONS.md, "Which
             USDM sources we hold."

Inputs:      data/raw/usdm_v4/uml/dataStructure.yml   (read-only, pinned)

Outputs:     Plain text on stdout. Writes nothing to disk.

Usage:       python -m sdg.usdm_spec --list-classes
                 print every class name in the standard, abstract ones marked
             python -m sdg.usdm_spec --attributes <class>
                 print one class's attributes: type, cardinality, kind
                 e.g.  python -m sdg.usdm_spec --attributes Activity
             python -m sdg.usdm_spec --list-classes --allow-unpinned
                 run even if the pinned file no longer matches its checksum

Exit codes:  0  success
             1  the pinned spec file is missing (run scripts/fetch_sources.py)
             2  invalid command line (argparse's own fixed code)
             3  the spec does not match its recorded checksum (a changed or
                swapped file); rerun with --allow-unpinned to read it anyway
             4  the spec is present but not the shape this module expects
                (a USDM version that changed underneath us)
             5  the requested class is not found

Date:        2026-09-02
Owner:       Jason Delosh
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# pyyaml is a conda dependency declared in environment.yml.
# dataStructure.yml is YAML, so reading it is a one-call job for this library.
import yaml

# This module lives at src/sdg/usdm_spec.py, so the repo root is three parents
# up. Resolving from __file__ keeps the path correct wherever the process is
# launched from, matching the convention in scripts/read_pdf.py.
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SPEC = REPO_ROOT / "data" / "raw" / "usdm_v4" / "uml" / "dataStructure.yml"

#######################################################################################
### Loading ###
#
# This section turns the pinned dataStructure.yml into the in-memory spec the rest of
# the module reads:
# verify the file's checksum, parse the YAML, confirm its shape, and return the
# parsed dict.
# The exceptions and message here are what that path raises when the file is changed
# or structurally wrong.

# About classes:
# Exceptions are defined as classes here so the specific kind of failure can be caught
# and reported with a specific exit code (see header for error codes) rather than
# getting a generic exception or traceback that does not distinguish between a changed
# file and a structurally different file.


class SpecShapeError(Exception):
    """The pinned spec file is parsed but is not shaped the way this module relies on.

    A USDM version whose structure changed will fail loudly and the class that broke
    the assumption is named. Raised rather than letting a later KeyError surface far
    from its cause.
    """


class IntegrityError(Exception):
    """The pinned spec file does not match the checksum recorded for it.

    Raised so a silently changed or swapped file stops here before it is
    parsed and its content flows downstream as quietly wrong output.
    Its message carries the recovery paths.
    """


# The message carried by IntegrityError: what the user sees when load()'s checksum
# check against the manifest fails, plus the paths back to a good state.
_INTEGRITY_MESSAGE = (
    "dataStructure.yml no longer matches its recorded checksum in "
    "data/manifests/raw_usdm_v4.json.\n"
    "  changed by accident   -> remove the file, then use python scripts/fetch_sources.py\n"
    "  run anyway (once)     -> re-run command, adding --allow-unpinned\n"
    "  a real new version    -> deliberate re-pin (new url, re-fetch, recompute); not a quick edit"
)


# create cached storage for verify_manifests; starts empty so the first call to
# _manifest_tools() imports it by path and stores it here so it's loaded once
# instead of re-loading each time load() runs
_manifest_module = None


def _manifest_tools():
    """Imports scripts/verify_manifests.py by path and yields that module, cached.

    verify_manifests.py owns how a manifest is located, parsed and hashed; loading
    it here once and reusing it keeps the checksum logic in one place rather than
    reimplemented.
    """
    global _manifest_module
    if _manifest_module is None:  # empty on first call, after that doesn't re-import
        import importlib.util

        path = REPO_ROOT / "scripts" / "verify_manifests.py"
        module_spec = importlib.util.spec_from_file_location("verify_manifests", path)
        module = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(module)
        _manifest_module = module
    return _manifest_module


def _verify_pinned(path: Path) -> None:
    """Takes a file path and checks it against the checksum and size recorded for it
    in the manifest; produces nothing on a match.
    Raises IntegrityError on a mismatch or if no manifest records the file.

    Reuses verify_manifests.check_entry, so it runs the same check that
    scripts/verify_manifests.py runs by hand, automatically when load() opens the file.
    """
    tools = _manifest_tools()
    manifests, _errors = tools.load_manifests("raw_usdm_v4")
    target = path.resolve()

    for _manifest_path, manifest in manifests:
        for entry in manifest.get("files", []):
            if (REPO_ROOT / entry.get("local", "")).resolve() == target:
                status, _detail = tools.check_entry(entry)
                if status != "ok":
                    raise IntegrityError(_INTEGRITY_MESSAGE)
                return

    raise IntegrityError(_INTEGRITY_MESSAGE)


def load(path: Path | None = None, verify: bool = True) -> dict:
    """Reads dataStructure.yml (the pinned file, or `path`) and produces the parsed
    YAML in native form:
    - a dict keyed by class name, where each value is the class's own dict of NCI code,
    definition, modifier and attributes.
    Nothing is reshaped.
    A check exists to confirm Modifier and Attributes are present for every class,
    so a structurally different file fails here instead of deep inside a caller.

    - Pass verify=True (the default) and the file is checked against the checksum
    recorded in data/manifests/ before it is read: a changed or swapped copy
    stops here rather than flowing downstream.
    - Pass verify=False to read a file that is not the pinned one (a test fixture),
    which the CLI exposes as --allow-unpinned.

    Raises
    - FileNotFoundError if the pinned file is absent,
    - IntegrityError if it does not match its recorded checksum,
    - SpecShapeError if it parsed but does not look like the USDM structure this module
    reads.
    """
    target = path or DEFAULT_SPEC

    if not target.exists():
        raise FileNotFoundError(target)

    # Verify the input file matches its recorded checksum in the manifest before
    # trusting the content.
    # Guards against a clean parse silently passing wrong content from a modified spec.
    if verify:
        _verify_pinned(target)

    spec = yaml.safe_load(target.read_text(encoding="utf-8"))

    if not isinstance(spec, dict) or not spec:
        raise SpecShapeError("spec is empty or not a mapping of classes")

    # Make sure Modifier and Attributes are present on all 86 classes (measured).
    for name, body in spec.items():
        if (
            not isinstance(body, dict)
            or "Modifier" not in body
            or "Attributes" not in body
        ):
            raise SpecShapeError(f"class {name!r} is missing Modifier or Attributes")
        if body["Modifier"] not in ("Concrete", "Abstract"):
            raise SpecShapeError(
                f"class {name!r} has unexpected Modifier {body['Modifier']!r}"
            )

    return spec


#######################################################################################
### Reading the standard ###
#
# Small accessors over the spec that Loading produced.
# Each takes a dict (and a class name where one is needed) and hands back a slice of
# USDM in native form. No reshaping occurs with the exception of targets(), which
# reads a single attribute and unwraps the "$ref" prefix USDM puts on every type.


def class_names(spec: dict) -> list[str]:
    """Takes the loaded spec and produces every class name in the standard, sorted
    for a stable listing."""
    return sorted(spec)


def is_abstract(spec: dict, class_name: str) -> bool:
    """Reads USDM's own Modifier value and returns True if the class is abstract,
    False if concrete.

    Abstract is USDM's word for a shared parent never instantiated alone.
    - An abstract class is like a blank template you never fill in directly.
    - You only fill in its more specific sub-templates.
        - example: 'Identifier' is abstract; you never create an Identifier, only a more
        specific one like StudyIdentifier or MedicalDeviceIdentifier.

    Raises KeyError naming the class if it is unknown.
    """
    return spec[class_name]["Modifier"] == "Abstract"


def attributes(spec: dict, class_name: str) -> dict:
    """Takes the loaded spec and a class name (one at a time) and extracts that
    class's attributes in file order, exactly as the standard has them.

    Inherited attributes are included because dataStructure.yml already copies
    them onto each concrete class (tagged 'Inherited From'); this does no
    flattening of its own. Raises KeyError naming the class if it is unknown.
    """
    if class_name not in spec:
        raise KeyError(class_name)
    return spec[class_name]["Attributes"]


def targets(attribute: dict) -> tuple[str, ...]:
    """Takes one attribute dict and produces the type(s) it references, as a tuple,
    with USDM's '#/' ref prefix removed.
    Example: an attribute whose Type is [{'$ref': '#/string'}] yields ('string',);
    Condition.appliesToIds, which lists five refs, yields those five class names.

    USDM writes every type as a list of {'$ref': '#/X'}, where X is a class name
    or one of five primitives (string, boolean, integer, float, date). Most
    attributes reference one type; four reference several (e.g. Condition.appliesToIds),
    so the result is always a tuple. This is the only place a '$ref' is unwrapped,
    so no caller has to repeat it.
    """
    return tuple(ref["$ref"].removeprefix("#/") for ref in attribute.get("Type", []))


#######################################################################################
### Command line ###
#
# The command line interface (CLI): runs when the module is invoked from a terminal,
# e.g. python -m sdg.usdm_spec --list-classes.
# main() parses the flags, loads the spec once, and dispatches to one of the two
# listings below.
# The process exit code reports the outcome.


def _print_classes(spec: dict) -> None:
    """Takes the loaded spec (main() calls load()) and prints every class name,
    marking abstract ones, then a count summary.

    Names go to stdout so the listing can be piped: every class name, one per line with
    [abstract] appended to the abstract classes.

    The summary goes to stderr (for example: 86 classes (80 concrete, 6 abstract)).
    The summary doesn't get mixed into the stdout stream so piped data isn't polluted.
    The concrete/abstract split is the figure docs/sources.md records, printed here
    straight from the file.
    """
    names = class_names(spec)
    for name in names:
        marker = "  [abstract]" if is_abstract(spec, name) else ""
        print(f"{name}{marker}")

    abstract = sum(1 for n in names if is_abstract(spec, n))
    print(
        f"\n{len(names)} classes ({len(names) - abstract} concrete, {abstract} abstract)",
        file=sys.stderr,
    )


def _print_attributes(spec: dict, class_name: str) -> int:
    """Takes the loaded spec (main() calls load()) and one class name, and
    prints that class's attributes (name, type(s), cardinality, kind, and for an
    inherited attribute, the parent it comes from).
    Produces exit code 0, or 5 with a guidance message if the class is unknown,
    so a typo yields the remedy rather than a traceback.
    """
    try:
        attrs = attributes(spec, class_name)
    except KeyError:
        print(
            f"unknown class {class_name!r}; run --list-classes to see them all",
            file=sys.stderr,
        )
        return 5

    modifier = "abstract" if is_abstract(spec, class_name) else "concrete"
    print(f"{class_name}  ({modifier})")
    definition = spec[class_name].get("Definition")
    if definition:
        print(f"  {definition}")
    print()

    for fname, attr in attrs.items():
        # Relationship Type is USDM's own Value/Ref label, always present; it is
        # carried through, not interpreted. inherited_from is shown only when
        # set, so the common own-attribute case stays uncluttered.
        inherited = attr.get("Inherited From")
        origin = (
            f"  (inherited from {inherited[0]['$ref'].removeprefix('#/')})"
            if inherited
            else ""
        )
        print(f"  {fname}")
        print(f"     type        {', '.join(targets(attr)) or '(none)'}")
        print(f"     cardinality {attr['Cardinality']}")
        print(f"     kind        {attr['Relationship Type']}{origin}")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Takes the command-line arguments, loads the spec once, runs the requested
    listing, and produces the process exit code:
    - a zero means success
    - a non-zero means failure (see script documentation at the beginning of this file).
    """
    sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        prog="python -m sdg.usdm_spec",
        description="Read the pinned USDM model (dataStructure.yml).",
    )
    # Exactly one mode per invocation; argparse reports a missing or double mode
    # as a usage error (exit 2).
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--list-classes",
        action="store_true",
        help="print every class name, abstract ones marked",
    )
    group.add_argument(
        "--attributes", metavar="CLASS", help="print one class's attributes"
    )

    # A modifier, not a mode: it works with either listing, so it sits outside
    # the mutually exclusive group.
    parser.add_argument(
        "--allow-unpinned",
        action="store_true",
        help="run even if the spec no longer matches its checksum",
    )
    args = parser.parse_args(argv)

    # A missing file, a changed one, and a structurally wrong one are three
    # different failures with three different exit codes, so a caller can tell
    # "not downloaded" from "checksum changed" from "USDM changed shape".
    try:
        spec = load(verify=not args.allow_unpinned)
    except FileNotFoundError:
        print(
            f"pinned spec not found at {DEFAULT_SPEC.relative_to(REPO_ROOT)}; "
            f"run scripts/fetch_sources.py",
            file=sys.stderr,
        )
        return 1
    except IntegrityError as exc:
        print(exc, file=sys.stderr)
        return 3
    except SpecShapeError as exc:
        print(f"spec is present but not the expected shape: {exc}", file=sys.stderr)
        return 4

    if args.list_classes:
        _print_classes(spec)
        return 0
    return _print_attributes(spec, args.attributes)


#######################################################################################
### Entry point ###
#
# __name__ equals "__main__" only when this file is run directly (python -m
# sdg.usdm_spec), not when it is imported. So main() runs here as a script, while
# importing the module for its functions does not trigger it. main()'s return value
# becomes the process exit code.


if __name__ == "__main__":
    raise SystemExit(main())
