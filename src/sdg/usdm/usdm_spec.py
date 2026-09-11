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
             manifests/. A changed or swapped pin fails here rather than
             parsing and passing wrong content downstream;
             - Override is possible but should be used with caution: --allow-unpinned

             Why this file and not USDM_API.json: the API spec discards the
             target class of every relationship and every cardinality, which is
             exactly what makes the standard a graph. See DECISIONS.md, "Which
             USDM sources we hold."

Inputs:      inputs/standards/cdisc/usdm_v4/dataStructure.yml   (read-only, pinned)
             manifests/*.json                    (read-only, via sdg.pinned)

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
             3  the spec cannot be verified against manifests/, or does not
                match it; the message names which (mismatch, unreadable or
                absent manifest, malformed entry, file not recorded) and how to
                recover. A mismatch can be read anyway with --allow-unpinned
             4  the spec is present but not the shape this module expects
                (a USDM version that changed underneath us)
             5  the requested class is not found
             6  the package is not running from inside its repo (installed
                without -e); the message gives the install command

Date:        2026-09-03
Owner:       Jason Delosh
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# pyyaml is declared in environment.yml (installed there through pip).
# dataStructure.yml is YAML, so reading it is a one-call job for this library.
import yaml

# The one way to obtain a pinned file, verified against its manifest, with the
# repo root and the two integrity exceptions callers may need to catch.
from sdg.console_output import use_utf8_output
from sdg.pinned import REPO_ROOT, IntegrityError, NotInRepoError, pinned, require_repo

# Where the pinned model file is, named the way its manifest records it. The
# repo root, and the verification of the file against its manifest, come from
# sdg.pinned; nothing here locates or checks files on its own.
PINNED_LOCAL = "inputs/standards/cdisc/usdm_v4/dataStructure.yml"
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
    """Read dataStructure.yml, the pinned file or the given path, and hand back the parsed
    YAML in native form.

    The result is a dict keyed by class name, where each value is the class's own dict
    of NCI code, definition, modifier and attributes. Nothing is reshaped. Two shape
    checks run before the dict is returned: every class has Modifier and Attributes, and
    every attribute has Type, Cardinality and Relationship Type, so a structurally
    different file fails here instead of deep inside a caller.

    With verify on, the default, the file is obtained through the pinned-file check,
    which proves it against its manifest before it is read, so a changed or swapped copy
    stops here rather than flowing downstream. The command line's --allow-unpinned flag
    turns verify off for the pinned file only; it never reads another path. A path with
    verify off reads a file that is not the pinned one, such as a test fixture. With
    verify on such a file fails, since no manifest entry records it.

    Args:
        path: The file to read, or None for the pinned dataStructure.yml.
        verify: Whether to prove the file against its manifest first.

    Returns:
        The parsed YAML, a dict keyed by class name.

    Raises:
        FileNotFoundError: The pinned file is absent.
        NotInRepoError: The package is not running from inside its repo.
        IntegrityError: The file cannot be verified against its manifest, or does not
            match it.
        SpecShapeError: The file parsed but is not shaped like the USDM structure this
            module reads.
    """
    # Confirmed before the file is looked for, not inside pinned(). Installed
    # without -e, DEFAULT_SPEC sits under the wrong root and does not exist
    # there, so an existence check that ran first would report "not
    # downloaded" for a file that is downloaded, and --allow-unpinned (which
    # never reaches pinned()) would never check at all.
    require_repo()

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


def _is_ref_list(value: object) -> bool:
    """Say whether one attribute field is a non-empty list of reference dicts.

    A reference dict carries a string under '$ref'. That is the only shape _unwrap()
    reads.

    Args:
        value: The attribute field, of whatever type the YAML held.

    Returns:
        True when every item is a reference dict and there is at least one.
    """
    return (
        isinstance(value, list)
        and bool(value)
        and all(
            isinstance(item, dict) and isinstance(item.get("$ref"), str)
            for item in value
        )
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
    """List every class name in the standard.

    Args:
        spec: The loaded spec.

    Returns:
        The class names, sorted for a stable listing.
    """
    return sorted(spec)


def is_abstract(spec: dict, class_name: str) -> bool:
    """Say whether a class is abstract, from USDM's own Modifier value.

    Abstract is USDM's word for a shared parent never instantiated alone. An abstract
    class is like a blank template you never fill in directly; you only fill in its more
    specific sub-templates. For example, Identifier is abstract: you never create an
    Identifier, only a more specific one like StudyIdentifier or
    MedicalDeviceIdentifier.

    Args:
        spec: The loaded spec.
        class_name: The class to look at.

    Returns:
        True when the class is abstract, False when it is concrete.

    Raises:
        KeyError: The class is unknown. The message names it.
    """
    return spec[class_name]["Modifier"] == "Abstract"


def attributes(spec: dict, class_name: str) -> dict:
    """Give one class's attributes in file order, exactly as the standard has them.

    Inherited attributes are included because dataStructure.yml already copies them onto
    each concrete class, tagged 'Inherited From'; this does no flattening of its own.

    Args:
        spec: The loaded spec.
        class_name: The class to look at.

    Returns:
        The class's attributes, keyed by attribute name.

    Raises:
        KeyError: The class is unknown. The message names it.
    """
    return spec[class_name]["Attributes"]


def _unwrap(refs: list[dict]) -> tuple[str, ...]:
    """Take the '$ref' wrapping off a list of USDM references.

    This is the one place the wrapping is removed, so the rule lives once; both Type and
    Inherited From use this shape.

    Args:
        refs: The references, each a dict like {'$ref': '#/X'}.

    Returns:
        The names X, as a tuple.
    """
    return tuple(ref["$ref"].removeprefix("#/") for ref in refs)


def targets(attribute: dict) -> tuple[str, ...]:
    """Give the type or types one attribute references, with USDM's '#/' prefix removed.

    USDM writes every type as a list of {'$ref': '#/X'}, where X is a class name or one
    of five primitives: string, boolean, integer, float, date. Most attributes reference
    one type; four reference several, Condition.appliesToIds among them, so the result
    is always a tuple. An attribute whose Type is [{'$ref': '#/string'}] yields
    ('string',).

    Args:
        attribute: One attribute's dict.

    Returns:
        The referenced type names, as a tuple.
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
    """Print every class name, marking the abstract ones, then a count summary.

    Names go to stdout so the listing can be piped: one per line, with [abstract]
    appended to the abstract classes. The summary, for example 86 classes (80 concrete,
    6 abstract), goes to stderr so it is not mixed into piped data. The
    concrete/abstract split is the figure docs/sources_index.md records, printed here
    straight from the file.

    Args:
        spec: The loaded spec.
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
    """Print one class's attributes: name, types, cardinality, kind and, for an inherited
    attribute, the parent it comes from.

    Args:
        spec: The loaded spec.
        class_name: The class to print.

    Returns:
        0, or 5 with a guidance message when the class is unknown, so a typo yields the
            remedy rather than a traceback.
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
    """Load the spec once, run the requested listing, and give back the exit code.

    Args:
        argv: The command-line arguments, or None to read the real ones.

    Returns:
        The exit code, as the header block lists them.
    """
    # Standard text carries characters the Windows console mangles; see
    # sdg.console_output for why.
    use_utf8_output()

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
