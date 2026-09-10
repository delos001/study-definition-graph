# inputs/standards/crosswalks/

Two spreadsheets from CDISC that say how fields in other systems correspond to USDM fields. `ct-gov_mapping.xlsx` maps ClinicalTrials.gov registry fields; `m11_mapping.xlsx` maps ICH M11 protocol template elements. Both are pinned to DDF-RA commit `aa303cb`; the manifest is `manifests/crosswalks.json`.

CDISC marks them informative, not part of the standard, and describes them as provisional [1]:

> Mappings. A set of provisional mappings from M11 and CTIS to USDM. These are currently "work in progress" due to the arrival of new ICH M11 informaiton close to the release of v3.11 of the USDM. These mappings will be updted during the public review of USDM v3.12.

Spelling as in the original. That description is stale: both spreadsheets declare USDM v4.0.0 in their own Readme sheet (verified 2026-08-17), and the M11 crosswalk is aligned to the M11 Updated Step 2 Draft of 14 March 2025.

## References

[1] CDISC. "Documents" README, DDF-RA repository at commit aa303cb. https://raw.githubusercontent.com/cdisc-org/DDF-RA/aa303cb32f5d3ceecc68a16803e26720d2c1fc26/Documents/README.md (accessed 2026-08-17).
