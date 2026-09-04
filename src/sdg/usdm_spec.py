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
             - Exception: USDM wraps every reference in a "$ref" string and this
             script takes that wrapping off, in one helper (_unwrap()).

             Reading the standard anywhere in this project goes through this
             module, so there is one way to obtain any fact about USDM and no
             second representation to keep faithful.

             Cross-cutting queries the flat file cannot answer directly
             (which classes reference a given class; the whole-model edge list)
             will be added here as later phases need them, not built up front.

             Before reading the file, load() obtains it through sdg.pinned,
             which checks it against the fingerprint recorded in
             data/manifests/. A changed or swapped pin fails here rather than
             parsing and passing wrong content downstream;
             - Override is possible but should be used with caution: --allow-unpinned

             Why this file and not USDM_API.json: the API spec discards the
             target class of every relationship and every cardinality, which is
             exactly what makes the standard a graph. See DECISIONS.md, "Which
             USDM sources we hold."

Inputs:      data/raw/usdm_v4/uml/dataStructure.yml   (read-only, pinned)
             data/manifests/*.json                    (read-only, via sdg.pinned)

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
             3  the spec cannot be verified against data/manifests/, or does not
                match it; the message names which (mismatch, unreadable or
                absent manifest, malformed entry, file not recorded) and how to
                recover. A mismatch can be read anyway with --allow-unpinned
             4  the spec is present but not the shape this module expects
                (a USDM version that changed underneath us)
             5  the requested class is not found
             6  the package is not running from inside its repo (installed
                without -e); the message gives the install command

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

# The one way to obtain a pinned file, verified against its manifest, with the
# repo root and the two integrity exceptions callers may need to catch.
from sdg.pinned import REPO_ROOT, IntegrityError, NotInRepoError, pinned

# Where the pinned model file is, named the way its manifest records it. The
# repo root, and the verification of the file against its manifest, come from
# sdg.pinned; nothing here locates or checks files on its own.
PINNED_LOCAL = "data/raw/usdm_v4/uml/dataStructure.yml"
DEFAULT_SPEC = REPO_ROOT / PINNED_LOCAL

#######################################################################################
### Loading ###
#
# This section turns the pinned dataStructure.yml into the in-memory spec the rest of
# the module reads: obtain the verified file through sdg.pinned, parse the YAML,
# confirm its shape, and return the parsed dict.
#
# Exceptions are classes so the specific kind of failure can be caught and reported
# with a specific exit code (see header) rather than a generic traceback. The shape
# failure is this module's own. The integrity failures (a changed or unverifiable
# file, a package not running from its repo) are sdg.pinned's, imported above so
# callers can catch them from here as well.


class SpecShapeError(Exception):
    """The pinned spec file is parsed but is not shaped the way this module relies on.

    A USDM version whose structure changed will fail loudly and the class that broke
    the assumption is named. Raised rather than letting a later KeyError surface far
    from its cause.
    """


def load(path: Path | None = None, verify: bool = True) -> dict:
    """Reads dataStructure.yml (the pinned file, or `path`) and produces the parsed
    YAML in native form:
    - a dict keyed by class name, where each value is the class's own dict of NCI code,
    definition, modifier and attributes.
    Nothing is reshaped.
    Two shape checks run before the dict is returned: every class has Modifier and
    Attributes, and every attribute has Type, Cardinality and Relationship Type,
    so a structurally different file fails here instead of deep inside a caller.

    - Pass verify=True (the default) and the file is obtained through
    sdg.pinned, which checks it against its manifest before it is read: a changed
    or swapped copy stops here rather than flowing downstream. The CLI's
    --allow-unpinned flag sets verify=False for the pinned file only; it never
    reads another path.
    - Pass `path` with verify=False to read a file that is not the pinned one (a
    test fixture). With verify=True such a file fails, since no manifest entry
    records it.

    Raises
    - FileNotFoundError if the pinned file is absent,
    - NotInRepoError if the package is not running from inside its repo,
    - IntegrityError if the file cannot be verified against its manifest or does
    not match it,
    - SpecShapeError if it parsed but does not look like the USDM structure this module
    reads.
    """
    target = path or DEFAULT_SPEC

    if not target.exists():
        raise FileNotFoundError(target)

    # Obtain the file through sdg.pinned (manifest entry, size, fingerprint) before
    # trusting the content. Guards against a clean parse silently passing wrong
    # content from a modified spec.
    if verify:
        text = pinned(target).read_text()
    else:
        text = target.read_text(encoding="utf-8")

    spec = yaml.safe_load(text)

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

    # Make sure every attribute carries the three keys the accessors and the
    # printer index directly (all 833 attributes do, measured), so a renamed key
    # in a future USDM is named here rather than surfacing as a KeyError traceback.
    # The two reference-valued keys, Type (always) and Inherited From (when
    # present), must also hold a list of {'$ref': '#/X'} entries, since _unwrap()
    # walks them; an empty or misshapen value would otherwise fail there instead.
    for name, body in spec.items():
        if not isinstance(body["Attributes"], dict):
            raise SpecShapeError(f"class {name!r}: Attributes is not a mapping")
        for attr_name, attr in body["Attributes"].items():
            missing = [
                key
                for key in ("Type", "Cardinality", "Relationship Type")
                if not isinstance(attr, dict) or key not in attr
            ]
            if missing:
                raise SpecShapeError(
                    f"attribute {name}.{attr_name} is missing {', '.join(missing)}"
                )
            for key in ("Type", "Inherited From"):
                if key in attr and not _is_ref_list(attr[key]):
                    raise SpecShapeError(
                        f"attribute {name}.{attr_name}: {key} is not a list of "
                        "{'$ref': '#/...'} entries"
                    )

    return spec


def _is_ref_list(value) -> bool:
    """Takes one attribute field and reports whether it is a non-empty list whose
    every item is a dict carrying a string '$ref', the only shape _unwrap() reads."""
    return (
        isinstance(value, list)
        and bool(value)
        and all(isinstance(item, dict) and isinstance(item.get("$ref"), str) for item in value)
    )


#######################################################################################
### Reading the standard ###
#
# Small accessors over the spec that Loading produced.
# Each takes a dict (and a class name where one is needed) and hands back a slice of
# USDM in native form. No reshaping occurs with the exception of _unwrap(), which
# takes the "$ref" wrapping off a list of references; targets() and the printer
# both go through it.


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
    return spec[class_name]["Attributes"]


def _unwrap(refs: list[dict]) -> tuple[str, ...]:
    """Takes a list of USDM references, each {'$ref': '#/X'}, and produces the
    names X as a tuple. The one place the '$ref' wrapping is taken off, so the
    rule lives once; both Type and Inherited From use this shape."""
    return tuple(ref["$ref"].removeprefix("#/") for ref in refs)


def targets(attribute: dict) -> tuple[str, ...]:
    """Takes one attribute dict and produces the type(s) it references, as a tuple,
    with USDM's '#/' ref prefix removed.
    Example: an attribute whose Type is [{'$ref': '#/string'}] yields ('string',);
    Condition.appliesToIds, which lists five refs, yields those five class names.

    USDM writes every type as a list of {'$ref': '#/X'}, where X is a class name
    or one of five primitives (string, boolean, integer, float, date). Most
    attributes reference one type; four reference several (e.g. Condition.appliesToIds),
    so the result is always a tuple.
    """
    return _unwrap(attribute.get("Type", []))


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
        inherited = _unwrap(attr.get("Inherited From", []))
        origin = f"  (inherited from {', '.join(inherited)})" if inherited else ""
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

    # A missing file, a changed one, a structurally wrong one, and a package not
    # running from its repo are four different failures with four different exit
    # codes, so a caller can tell "not downloaded" from "checksum changed" from
    # "USDM changed shape" from "installed the wrong way".
    try:
        spec = load(verify=not args.allow_unpinned)
    except FileNotFoundError:
        print(
            f"pinned spec not found at {DEFAULT_SPEC.relative_to(REPO_ROOT)}; "
            f"run scripts/fetch_sources.py",
            file=sys.stderr,
        )
        return 1
    except NotInRepoError as exc:
        print(exc, file=sys.stderr)
        return 6
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
