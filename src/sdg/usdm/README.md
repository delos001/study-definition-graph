# src/sdg/usdm/

Read the USDM standard so the pipeline knows what a class is, what it holds, and what it points at.

| File | What it does |
| --- | --- |
| `usdm_spec.py` | Reads the pinned model file, checks it is shaped the way USDM v4.0 is, and answers questions about it: the classes, whether one is abstract, a class's attributes, what an attribute points at. Also a command line: `usdm_spec --list-classes`. It is a step, as `docs/sdg_files_inventory.md` lists it. |
