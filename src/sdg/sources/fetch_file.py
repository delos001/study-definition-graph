"""
Script:      fetch_file.py
Description: Downloads one file from one url to one destination.

             The url and destination are passed in as two values. For a pinned
             standard, they come from a manifest entry, read by read_manifests.py and
             handed over by acquire_sources.py.  For a new study, they come from the
             ClinicalTrials.gov registry response, and the entry is written after.

             A separate function fingerprints the download; acquire_sources decides
             from that whether to place or discard it. A download that fails part
             way is removed, so no half-file is left to be mistaken for a finished
             one.

             The bytes are written under a temporary name (destination plus .part).
             For example: standards/cdisc/usdm_v4/USDM-IG.pdf.part.
             The file is later renamed by the place step after the fingerprint has
             matched.

             If a server answers that the file has moved, the download follows
             the new address, since ICH and GitHub both do this for some files.

             The file is written to disk piece by piece as it arrives, so a
             large PDF never sits in memory whole.

Inputs:      one url   (network, read-only)

Outputs:     the downloaded file at <destination>.part; nothing else on disk.
             Hands back the path of that temporary file.

Usage:       Not run directly; imported.
             from sdg.fetch_file import fetch
                fetch(url, destination)   -> path of the .part file written

Exit codes:  None. Not run on its own, so no exit code. On a problem it stops
             and hands an error to the program using it, which decides what to
             do. The errors it can hand back:
             FetchError   the url could not be reached, answered with an error,
                          or the download stopped part way; the message names
                          the url and the cause

Date:        2026-09-08
Owner:       Jason Delosh
"""
