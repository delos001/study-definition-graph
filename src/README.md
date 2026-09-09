# src/

This folder is the container the install points at. It holds the `sdg` package and nothing else.

`pip install -e .`, run once from the repo root (README.md, step 1b), tells Python to find the package here. The `-e` means editable: Python runs the files where they sit, so an edit takes effect with no reinstall, and the package can find `manifests/`, `standards/` and `data/` relative to itself. Installed without `-e`, the code would be copied into Python's own library folder and could find none of them; `require_repo()` in `sdg/sources/read_manifests.py` detects that and says so.

Code here is used in two ways. Other code imports it, for example `from sdg.sources import manifests`. Orchestrators are also run as programs, for example `python -m sdg.sources.acquire_sources`. The tools a person runs beside the pipeline live in `scripts/`, and the checks that prove this code works live in `tests/`.

| Folder | What it is |
| --- | --- |
| `sdg/` | This is the package. Its own `README.md` lists the folders inside it. |
| `sdg.egg-info/` | `pip install -e .` writes this folder. It holds a few small text files that tell Python the package is installed and where. It is not source and is not committed. It is safe to delete, because the next install recreates it. |

`docs/workflow_map_outline.md` shows the whole map: which orchestrator uses which piece.
