"""
Script:      write_manifests.py
Description: Writes one manifest entry, or updates one that exists.

             DRAFT. Nothing uses this yet. Its first users will be the Phase 1
             study fetcher, which records each downloaded study document under
             manifests/study_documents/, and the update command from issue #18, which
             moves a source to a new version. The shape of what it writes is
             settled when the first of those is built.

             What is known now:
             - it writes the same fields read_manifests.py requires: name, url,
               local, bytes and sha256,
             - it never overwrites an existing entry unless told to, because a
               manifest entry is the record of what was pinned,
             - it writes the whole manifest file back in the same layout it was
               read in, so a diff shows only the entry that changed.

Inputs:      one manifest file   (read, then rewritten)
             one entry's fields

Outputs:     the manifest file with the entry added or replaced.

Usage:       Not run directly; imported.
             from sdg.sources import write_entry
                write_entry(manifest, entry)   -> to be settled

Exit codes:  None. Not run on its own, so no exit code. On a problem it stops
             and hands an error to the program using it, which decides what to
             do. The errors it can hand back:
             ManifestError   the manifest cannot be read or written, or the entry
                             already exists and replacing it was not asked for

Date:        2026-09-09
Owner:       Jason Delosh
"""
