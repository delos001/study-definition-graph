"""
Script:      finalize_file.py
Description: Brings a completed download to its final state: under its final
             name, or discards the download that does not match fingerprinting.

             place(partial) strips the .part suffix and renames the file into
             the expected location. It refuses if a file already exists at the final
             name and raises an error.  Pinned files are never overwritten.  A person
             must look at the existing file and decide whether to delete or move it by
             hand, then run acquire_sources again, which redoes only that file.

             discard(partial) deletes the temporary file. Called when the
             fingerprint did not match, so a wrong download never sits on
             disk under any name.

             This module moves or deletes the one file it is given. It does not
             fingerprint, does not open manifests and does not download; the
             program using it, acquire_sources, has already decided which of the
             two to do.

Inputs:      one .part file

Outputs:     place: the file under its final name; the .part name is gone.
             discard: nothing; the .part file is gone.
             Hands back the final path (place) or nothing (discard).

Usage:       Not run directly; imported.
             from sdg.finalize_file import place, discard
                place(partial)     -> final path
                discard(partial)   -> nothing

Exit codes:  None. Not run on its own, so no exit code. On a problem it stops
             and hands an error to the program using it, which decides what to
             do. The errors it can hand back:
             FileExistsError     a file is already at the final name; nothing moved
             FileNotFoundError   the .part file does not exist

Date:        2026-09-08
Owner:       Jason Delosh
"""
