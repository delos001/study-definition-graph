"""
Script:      read_manifests.py
Description: Reads the manifests and provides three pieces of information:
             1 which manifests exist:
                - all of them, or
                - one, by name
             2 which entry describes a given file, if any,
             3 an entry's details as named fields rather than JSON keys
                - its url,
                - local path,
                - size,
                - fingerprint

             Manifests under manifests/data_raw/ are read alongside the top-level
             manifests.
             This module never downloads, hashes or checks a file against disk.

Inputs:      manifests/*.json, manifests/data_raw/*.json   (read-only)

Outputs:     Nothing on disk.
             Hands back, in memory: the manifests found, one entry, or an entry's fields.

Usage:       Not run directly; imported.
             from sdg.read_manifests import manifests, entry_for
                manifests()                  -> every manifest
                manifests("cdisc_usdm_v4")   -> one manifest, by name
                entry_for("standards/cdisc/usdm_v4/dataStructure.yml") -> that file's
                  entry, or None

Exit codes:  None. Not run on its own, so no exit code. On a problem it stops
             and hands an error to the program using it, which decides what to
             do. The errors it can hand back:
             NotInRepoError   the package is not running from inside its repo
             ManifestError    a manifest cannot be read, or an entry lacks a required field

Date:        2026-09-08
Owner:       Jason Delosh
"""
