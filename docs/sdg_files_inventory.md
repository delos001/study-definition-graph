# sdg/

- console_output.py: makes the console print the standards' characters intact on Windows

## sources/
### workflows:
- acquire_sources.py (manual): uses read_manifests, fetch_file, fingerprint_file, finalize_file
- verify_pinned.py: uses read_manifests, fingerprint_file
- update_sources.py: uses fetch_file, fingerprint_file, finalize_file, write_manifests - pending

### steps:
- read_manifests.py
- fetch_file.py
- fingerprint_file.py
- finalize_file.py
- write_manifests.py - pending

## usdm/
### workflows:
### steps:
- usdm_spec.py (manual): uses console_output, verify_pinned

## view/
### workflows:
- read_pdf.py (manual): uses read_manifests, and reads lookup_documents.yml
- read_xlsx.py (manual): uses read_manifests
### steps:
### data:
- lookup_documents.yml (the documents read_pdf can open, and what to strip from their pages)

## locate/
### workflows:
### steps:

- pending phase 1

## classify/
### workflows:
### steps:

- pending phase 2

## extract/
### workflows:
### steps:

- pending phase 3

## graph/
### workflows:
### steps:

- pending phase 4
