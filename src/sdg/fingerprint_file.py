"""
Script:      fingerprint_file.py
Description: For a file, this module measures the size and sha256 and returns whether
             the file matches the manifest entry for that file.

             The file is read in pieces, so a large PDF is never held in its entirety
             in memory.

             fingerprint(path) gives the two values every manifest entry records:
               - the file's size in bytes and
               - its sha256.

             compare(path, entry) checks both values against the entry.

             Size is checked first and reported on its own, because the two failures
             mean different things: a size difference is usually a truncated or
             replaced download, while the same size with a different sha256 means
             the content changed in place, which is the case worth a closer look.

             This module reads the file it is given and nothing else. It does
             not open manifests and does not download.

Inputs:      one file   (read-only, opened only to hash)

Outputs:     Nothing on disk.
             Hands back the fingerprint (size, sha256), or the comparison result listed
             as 'matched' or which value differed and how.

Usage:       Not run directly; imported.
             from sdg.fingerprint_file import fingerprint, compare
                fingerprint(path)        -> (size, sha256)
                compare(path, entry)     -> matched, or the difference found

Exit codes:  None. Not run on its own, so no exit code. On a problem it stops
             and hands an error to the program using it, which decides what to
             do. The errors it can hand back:
             FileNotFoundError   the path does not exist

Date:        2026-09-08
Owner:       Jason Delosh
"""
