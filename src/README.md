# src/

This folder holds the project's Python code, as the installed packages `sdg`, `sdgtools` and `sdgval`. The install looks in this folder for them, and it holds nothing else.

`pip install -e .`, run once from the repo root as a step in the setup block of the root `README.md`, tells Python to find the packages here.

The `-e` means editable. Python runs the files where they sit, so an edit takes effect with no reinstall, and the packages can find `manifests/`, `inputs/` and `data/` relative to themselves.

Installed without `-e`, the code would be copied into Python's own library folder and could find none of those folders. `require_repo()` in `sdg/sources/read_manifests.py` detects that and says so.

Code here is used in two ways.
- Other code imports it, for example `from sdg.sources import read_manifests`.
- Some files are also run as commands, for example `acquire_sources`. `docs/commands.md` lists every command.

The checks that prove the packages work live in `validation/`.

| Folder | What it is |
| --- | --- |
| `sdg/` | This is the `sdg` package, the pipeline. Its own `README.md` lists the folders inside it. |
| `sdgtools/` | This is the `sdgtools` package, the repo tools that keep the repository's own files in order. Each is installed as a command. |
| `sdgval/` | This is the `sdgval` package, the validation package. It holds the commands that build the inventory and run the checks. It also holds the pytest plugins, which declare the labels, select and skip the checks, and write the report. A pytest plugin is an extension that pytest loads on its own when it starts. |
| `sdg.egg-info/` | `pip install -e .` writes this folder. It holds a few small text files that tell Python the packages are installed and where. It is not source and is not committed. It is safe to delete, because the next install recreates it. |
