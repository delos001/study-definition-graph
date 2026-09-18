# sdg/

The words in brackets after a name say the file is run by hand; a file with no brackets is only imported. The rest of the line names the project files it imports, and any data file it reads.

- console_output.py: makes the console print the standards' characters intact on Windows

## sources/
### workflows
- acquire_sources.py (by hand): uses read_manifests, fetch_file, fingerprint_file, finalize_file
- verify_pinned.py: uses read_manifests, fingerprint_file
- update_sources.py: uses fetch_file, fingerprint_file, finalize_file, write_manifests; not yet written

### steps
- read_manifests.py
- fetch_file.py
- fingerprint_file.py: uses read_manifests
- finalize_file.py: uses fetch_file
- write_manifests.py: not yet written

## usdm/
### workflows
- usdm_spec.py (by hand): uses console_output, read_manifests, verify_pinned
### steps

## view/
### workflows
- read_pdf.py (by hand): uses console_output, read_manifests, and reads lookup_documents.yml
- read_xlsx.py (by hand): uses console_output, read_manifests
### steps
### data
- lookup_documents.yml: the documents read_pdf can open, and what to strip from their pages

## locate/
### workflows
### steps

- This folder is empty until Phase 1.

## classify/
### workflows
### steps

- This folder is empty until Phase 2.

## extract/
### workflows
### steps

- This folder is empty until Phase 3.

## graph/
### workflows
### steps

- This folder is empty until Phase 4.
