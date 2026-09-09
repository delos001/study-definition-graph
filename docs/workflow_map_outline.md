

# sdg/

## sources/
### workflows:
- acquire_sources.py: uses read_manifests, fetch_file, fingerprint_file, finalize_file
- verify_pinned.py: uses read_manifests, fingerprint_file
- update_sources.py: uses fetch_file, fingerprint_file, finalize_file, write_manifests

### steps:
- read_manifests.py
- fetch_file.py
- fingerprint_file.py
- finalize_file.py
- write_manifests.py - pending

## usdm/
### workflows:
### steps:

-	usdm_spec.py

## locate/
### workflows:
### steps:

-	pending phase 1

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

# scripts/
Everything here is run by hand, so there is no workflow and step split.

- adhoc extraction:
  - read_xlsx.py
  - read_pdf.py
  - pending
- upkeep:
  - build_index.py
  - verify_doc_figures.py
