# src/sdg/

The `sdg` package: the project's pipeline code, as modules other code imports. Each module opens with a header block (what it does, inputs, outputs, usage, exit codes) that is the full account; this file is the index. Kept by hand.

## Obtaining sources

| Module | What it does |
| --- | --- |
| `pinned.py` | The one way to obtain a pinned file (a downloaded standard or example whose version never moves). `pinned(<path>)` finds the file's entry in `data/manifests/`, checks its size and sha256 fingerprint, and returns the file with its identity (fingerprint and the url it was fetched from). Every way the check can fail has its own message and remedy. Also holds the repo location, the "am I running from inside the repo" check, and the manifest-reading and hashing code that `scripts/verify_manifests.py` and `scripts/fetch_sources.py` share, so the check run by hand is the check run automatically. If a source ever comes from an API instead of a manifest, the inside of `pinned()` changes and its callers do not. |

## Reading the USDM standard

| Module | What it does |
| --- | --- |
| `usdm_spec.py` | The one way to read the pinned USDM model (`dataStructure.yml`). Obtains the file through `pinned.py`, checks the parsed content is shaped the way USDM v4.0 is (every class has its Modifier and Attributes, every attribute its Type, Cardinality and Relationship Type), and answers questions about it: list the classes, is one abstract, list a class's attributes, what does an attribute point at. Nothing is reshaped or renamed; the answers are CDISC's own structures. Also a command line for the Phase 0 check: `python -m sdg.usdm_spec --list-classes` and `--attributes <class>`. |

## Package plumbing

| File | What it does |
| --- | --- |
| `__init__.py` | Marks the folder as a package so `import sdg` works. One docstring, no code. |

Which module calls which, and what reads `data/`: `docs/code_map.md`. The checks for each module: `tests/README.md`.
