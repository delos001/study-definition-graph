# data/usdm_examples/

CDISC's three worked examples for USDM v4.0: real protocols that CDISC staff mapped into USDM by hand. Each study has its own folder holding the same three forms. Pinned to DDF-RA commit `aa303cb`; the manifest is `manifests/usdm_examples.json`.

| Form | What it is |
| --- | --- |
| `*.pdf` | The source protocol, as a person reads it. |
| `*.xlsx` | The spreadsheet a person filled in from the protocol: the manual mapping step, 25 to 35 sheets. |
| `*.json` | The USDM v4.0 output generated from that spreadsheet. |

| Study | Folder |
| --- | --- |
| The CDISC Pilot Study (LZZT) | `CDISC_Pilot/` |
| A type 2 diabetes study, NCT03421379 | `EliLilly_NCT03421379_Diabetes/` |
| A Wilson's disease study, NCT04573309 | `Alexion_NCT04573309_Wilsons/` |

These serve as the first answer keys, with a caveat: a worked example is one person's interpretation and can be wrong, so scoring must be able to flag a suspect reference rather than penalize a correct extraction that disagrees with it (`eval/README.md`).

CDISC ships two further examples in the same folder, Devices and Observational, which are not held. CDISC's own description [1]:

> In addition, two temporary examples have been included with release 3.10.2. The data contained within the example is test data and not taken from an existing protocol. These files will be replaced with a realistic example as we pass through public review for USDM v4.

Which file answers which question: `docs/sources_index.md`.

## References

[1] CDISC. "Examples" README, DDF-RA repository at commit aa303cb. https://raw.githubusercontent.com/cdisc-org/DDF-RA/aa303cb32f5d3ceecc68a16803e26720d2c1fc26/Documents/Examples/README.md (accessed 2026-08-17).
