"""
Script:      acquire_sources.py
Description: Acquires one or more needed source file(s) from their external location based
             on the respective manifest entry and URL.
             Only fetches files that are not yet on disk.

             Each step is a function in the sdg package. This script runs them in order:
             - read manifest
             - fetch file from URL,
             - fingerprint,
             - compare to its manifest entry,
             - place it in the correct location (only if it matches the entry).

             Files already on disk are left alone; whether they are still correct is
             verified by verify_manifests.py.

Inputs:      manifests/*.json   (read-only)
             manifests/data_raw/*.json   (read-only)
             URL for each file named (read-only)

Outputs:     The files each entry names, under standards/ or data/. Nothing
             existing is modified or deleted.

Usage:       python -m sdg.acquire_sources
                 get whatever is missing
             python -m sdg.acquire_sources --dry-run
                 list what would be fetched; no network, nothing written
             python -m sdg.acquire_sources --set cdisc_usdm_v4
                 one manifest only

Exit codes:  0  every entry's file is on disk
             1  a fetch failed, or what arrived did not match its entry
             3  no manifests found, or one could not be read
             6  the sdg package is not running from inside its repo

Date:        2026-09-08
Owner:       Jason Delosh
"""
