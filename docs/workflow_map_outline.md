

# sdg/

## sources/
### orchestrators:
- acquire_sources.py: uses read_manifests, fetch_file, fingerprint_file, finalize_file
- verify_pinned.py: uses read_manifests, fingerprint_file
- update_sources.py: uses fetch_file, fingerprint_file, finalize_file, write_manifests

### pieces:
- read_manifests.py
- fetch_file.py
- fingerprint_file.py
- finalize_file.py
- write_manifests.py - pending

## usdm/
### orchestrators:
### pieces:

-	usdm_spec.py

## locate/
### orchestrators:
### pieces:

-	pending phase 1

## classify/
### orchestrators:
### pieces:

- pending phase 2

## extract/
### orchestrators:
### pieces:

- pending phase 3

## graph/
### orchestrators:
### pieces:

- pending phase 4

# scripts/
Everything here is run by hand, so there is no orchestrator and piece split.

- adhoc extraction:
  - read_xlsx.py
  - read_pdf.py
  - pending
- upkeep:
  - build_index.py
  - verify_doc_figures.py
