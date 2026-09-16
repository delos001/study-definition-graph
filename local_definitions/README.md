# local_definitions/

This folder holds definitions this project adds to a published standard. A definition belongs here when the project needs something a standard has no place for, and writes it down so that the pipeline and a reader can both interpret it. CDISC and the other publishers have not endorsed anything in this folder.

The files are written here and committed to git. They are not pinned, so the rules for `inputs/` do not apply to them. Codes that identify clients, therapeutic areas and document types are not definitions, and they live in `registries/`.

Everything in this folder is a draft. The structure may be realigned substantially when the prompt axes are worked out in issue #15, so no validation is built for it until the structure is stable. Issue #32 tracks that validation.

| Folder | What it holds |
| --- | --- |
| `usdm_extensions/` | The fields this project adds to USDM through the standard's extension mechanism. |
