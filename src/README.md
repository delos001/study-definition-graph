# src/

This folder is the container the install points at. It holds the `sdg` package and nothing else.

`pip install -e .`, run once from the repo root as a step in the setup block of the root `README.md`, tells Python to find the `sdg` package here. The `-e` means editable. Python runs the files where they sit, so an edit takes effect with no reinstall, and the package can find `manifests/`, `inputs/` and `data/` relative to itself. Installed without `-e`, the code would be copied into Python's own library folder and could find none of them; `require_repo()` in `sdg/sources/read_manifests.py` detects that and says so.

Code here is used in two ways. Other code imports it, for example `from sdg.sources import manifests`. Workflows are also run as programs, for example `acquire_sources`. Three packages live here: the pipeline, `sdg/`, the repo tools a person runs beside it, `sdgtools/`, and the validation package that runs the checks, `sdgval/`. The checks that prove all three work live in `validation/`.

| Folder | What it is |
| --- | --- |
| `sdg/` | This is the `sdg` package, the pipeline. Its own `README.md` lists the folders inside it. |
| `sdgtools/` | The repo tools, each installed as a command. Its `README.md` is generated from their headers. |
| `sdgval/` | The validation package: the pytest plugins that declare the labels, select and skip the checks, and write the report. |
| `sdg.egg-info/` | `pip install -e .` writes this folder. It holds a few small text files that tell Python the packages are installed and where. It is not source and is not committed. It is safe to delete, because the next install recreates it. |

`src/sdg/sdg_file_catalog.md` lists every file in `sdg/`, folder by folder, as a workflow or a step, with what each uses.
