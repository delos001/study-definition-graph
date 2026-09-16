# local_definitions/usdm_extensions/

This folder holds the extensions this project adds to USDM. An extension is a field that USDM has no place for, attached through the standard's extension mechanism in section 6.4 of the USDM implementation guide. The extensions are treated as a standard in the same way as the pinned USDM files, but they are written here rather than published by CDISC.

An extension is scoped by the client, therapeutic area and document type codes kept in `registries/`.

The structure is a draft and may change substantially. Issue #30 tracks settling it, and validation is on hold until then under issue #32.

| File | What it holds |
| --- | --- |
| `extensions.yml` | A dummy entry that shows one possible shape of an extension. It defines no real extension. |
