"""
Script:      usdm_spec.py
Description: The single path to access the pinned USDM model. It reads
             dataStructure.yml (the USDM v4.0 UML deliverable), and answers
             questions about the standard's classes and their attributes.

             Design: The file is parsed once into its native form (the nested
             dicts and lists exactly as CDISC published them).  Every function
             works off that one parse.
             - Nothing here re-models USDM into a new set of names.
             - Simple accessors hand back a slice of the parsed data unchanged;
             - Exception: USDM wraps every type in "$ref" string and this script
             unwraps the "$ref" string  using targets().

             Reading the standard anywhere in this project goes through this
             module, so there is one way to obtain any fact about USDM and no
             second representation to keep faithful.

             Cross-cutting queries the flat file cannot answer directly
             (which classes reference a given class; the whole-model edge list)
             will be added here as later phases need them, not built up front.

             Before reading the file, load() checks it against the sha256
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
                 run even if the pinned file no longer matches its fingerprint

Exit codes:  0  success
             1  the pinned spec file is missing (run scripts/fetch_sources.py)
             2  invalid command line (argparse's own fixed code)
             3  the spec does not match its recorded fingerprint (a changed or
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

# pyyaml is a conda dependency declared in environment.yml. dataStructure.yml
# is YAML, so reading it is a one-call job for this library.
import yaml

# This module lives at src/sdg/usdm_spec.py, so the repo root is three parents
# up. Resolving from __file__ keeps the path correct wherever the process is
# launched from, matching the convention in scripts/read_pdf.py.
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SPEC = REPO_ROOT / "data" / "raw" / "usdm_v4" / "uml" / "dataStructure.yml"


### Loading #####################################################################
#
# One parse, one shape check. Every other function takes the dict returned here,
# so the file is read exactly once per process.


class SpecShapeError(Exception):
    """The spec parsed but is not shaped the way this module relies on.

    Raised rather than letting a later KeyError surface far from its cause, so a
    USDM version whose structure changed fails loudly and names the class that
    broke the assumption.
    """


class IntegrityError(Exception):
    """The pinned spec file does not match the fingerprint recorded for it.

    Raised so a silently changed or swapped file stops here, before it is
    parsed and its content flows downstream as quietly wrong output. Its message
    carries the recovery paths.
    """


# The recovery paths shown when the file fails its fingerprint check. Re-pinning
# to a new version is deliberately not spelled out here: it is a multi-step act
# (new url, re-fetch, recompute) that will get its own tooling, not an edit to
# do from an error message.
_INTEGRITY_MESSAGE = (
    "dataStructure.yml no longer matches its pinned fingerprint in "
    "data/manifests/raw_usdm_v4.json.\n"
    "  changed by accident    -> remove the file, then  python scripts/fetch_sources.py\n"
    "  run anyway (once)       -> add  --allow-unpinned\n"
    "  a real new version      -> deliberate re-pin (new url, re-fetch, recompute); not a quick edit"
)

# verify_manifests.py owns how a manifest is located, parsed and hashed. Loaded
# here by path and cached, the way check_facts.py loads read_pdf.py, so the
# fingerprint rules live in one place; a second copy would be somewhere for them
# to drift, which is why fetch_sources.py imports it rather than reimplementing.
_manifest_module = None


def _manifest_tools():
    """Return the verify_manifests module, importing it by path once."""
    global _manifest_module
    if _manifest_module is None:
        import importlib.util

        path = REPO_ROOT / "scripts" / "verify_manifests.py"
        module_spec = importlib.util.spec_from_file_location("verify_manifests", path)
        module = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(module)
        _manifest_module = module
    return _manifest_module


def _verify_pinned(path: Path) -> None:
    """Confirm the file matches the sha256 and size recorded in its manifest.

    Reuses verify_manifests.check_entry, so this asks exactly the question the
    manual check asks, at the moment the file is opened. Raises IntegrityError
    with the recovery paths if the file has drifted, or if no manifest records
    it (nothing to check it against).
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
    """Read dataStructure.yml and return it in its native form.

    Returns the parsed YAML as-is: a dict keyed by class name, each value the
    class's own dict of NCI code, definition, modifier and attributes. Nothing
    is reshaped. A light check confirms the two keys every class is known to
    carry (Modifier, Attributes), so a structurally different file fails here
    with a clear message instead of deep inside a caller.

    With verify=True (the default) the file is checked against the sha256
    recorded in data/manifests/ before it is read, so a changed or swapped copy
    stops here rather than flowing downstream. Pass verify=False to read a file
    that is not the pinned one (a test fixture), which the CLI exposes as
    --allow-unpinned.

    Raises FileNotFoundError if the pinned file is absent, IntegrityError if it
    does not match its recorded fingerprint, SpecShapeError if it parsed but
    does not look like the USDM structure this module reads.
    """
    target = path or DEFAULT_SPEC

    if not target.exists():
        raise FileNotFoundError(target)

    # Verify the bytes are the pinned ones before trusting the content: a
    # silently changed file would otherwise parse cleanly and pass its wrong
    # content downstream, which is the whole failure this guards against.
    if verify:
        _verify_pinned(target)

    spec = yaml.safe_load(target.read_text(encoding="utf-8"))

    if not isinstance(spec, dict) or not spec:
        raise SpecShapeError("spec is empty or not a mapping of classes")

    # Modifier and Attributes are present on all 86 classes (measured). Checking
    # them turns a silent structural drift into an attributable error.
    for name, body in spec.items():
        if not isinstance(body, dict) or "Modifier" not in body or "Attributes" not in body:
            raise SpecShapeError(f"class {name!r} is missing Modifier or Attributes")
        if body["Modifier"] not in ("Concrete", "Abstract"):
            raise SpecShapeError(f"class {name!r} has unexpected Modifier {body['Modifier']!r}")

    return spec


### Reading the standard ########################################################
#
# Simple accessors. Each returns USDM's data in native form; the only reshaping
# is targets(), which unwraps the "$ref" prefix USDM puts on every type.


def class_names(spec: dict) -> list[str]:
    """Every class name in the standard, sorted for a stable listing."""
    return sorted(spec)


def is_abstract(spec: dict, class_name: str) -> bool:
    """True if the class is abstract: a shared parent never instantiated alone.

    Reads USDM's own Modifier value rather than inferring, so the answer is the
    standard's, not ours.
    """
    return spec[class_name]["Modifier"] == "Abstract"


def attributes(spec: dict, class_name: str) -> dict:
    """The class's attributes, in file order, exactly as the standard has them.

    Inherited attributes are included because dataStructure.yml already copies
    them onto each concrete class (tagged 'Inherited From'); this does no
    flattening of its own. Raises KeyError naming the class if it is unknown.
    """
    if class_name not in spec:
        raise KeyError(class_name)
    return spec[class_name]["Attributes"]


def targets(attribute: dict) -> tuple[str, ...]:
    """The type(s) an attribute references, with USDM's '#/' ref prefix removed.

    USDM writes every type as a list of {'$ref': '#/X'}, where X is a class name
    or one of five primitives (string, boolean, integer, float, date). Most
    attributes reference one type; four reference several (e.g.
    Condition.appliesToIds), so the return is always a tuple. This is the only
    place a '$ref' is unwrapped, so no caller has to repeat it.
    """
    return tuple(ref["$ref"].removeprefix("#/") for ref in attribute.get("Type", []))


### Command line ################################################################


def _print_classes(spec: dict) -> None:
    """Print every class name, marking abstract ones, then a count summary.

    Names go to stdout so the listing can be piped; the summary goes to stderr
    so it stays out of that stream. The concrete/abstract split is the figure
    docs/sources.md records, printed here straight from the file.
    """
    names = class_names(spec)
    for name in names:
        marker = "  [abstract]" if is_abstract(spec, name) else ""
        print(f"{name}{marker}")

    abstract = sum(1 for n in names if is_abstract(spec, n))
    print(f"\n{len(names)} classes ({len(names) - abstract} concrete, {abstract} abstract)",
          file=sys.stderr)


def _print_attributes(spec: dict, class_name: str) -> int:
    """Print one class's attributes: name, type(s), cardinality, kind.

    Returns 5 and prints guidance if the class is unknown, so a typo yields the
    remedy rather than a traceback.
    """
    try:
        attrs = attributes(spec, class_name)
    except KeyError:
        print(f"unknown class {class_name!r}; run --list-classes to see them all",
              file=sys.stderr)
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
        origin = (f"  (inherited from {inherited[0]['$ref'].removeprefix('#/')})"
                  if inherited else "")
        print(f"  {fname}")
        print(f"     type        {', '.join(targets(attr)) or '(none)'}")
        print(f"     cardinality {attr['Cardinality']}")
        print(f"     kind        {attr['Relationship Type']}{origin}")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Parse arguments, load the spec once, run the requested listing."""
    sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        prog="python -m sdg.usdm_spec",
        description="Read the pinned USDM model (dataStructure.yml).",
    )
    # Exactly one mode per invocation; argparse reports a missing or double mode
    # as a usage error (exit 2).
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--list-classes", action="store_true",
                       help="print every class name, abstract ones marked")
    group.add_argument("--attributes", metavar="CLASS",
                       help="print one class's attributes")
    # A modifier, not a mode: it works with either listing, so it sits outside
    # the mutually exclusive group.
    parser.add_argument("--allow-unpinned", action="store_true",
                        help="run even if the spec no longer matches its fingerprint")
    args = parser.parse_args(argv)

    # A missing file, a changed one, and a structurally wrong one are three
    # different failures with three different exit codes, so a caller can tell
    # "not downloaded" from "fingerprint changed" from "USDM changed shape".
    try:
        spec = load(verify=not args.allow_unpinned)
    except FileNotFoundError:
        print(f"pinned spec not found at {DEFAULT_SPEC.relative_to(REPO_ROOT)}; "
              f"run scripts/fetch_sources.py", file=sys.stderr)
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


if __name__ == "__main__":
    raise SystemExit(main())
