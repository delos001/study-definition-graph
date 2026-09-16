# repo_tools/

Each entry says how the tool is run and what it reads beyond its own arguments. A tool marked hook is run by the pre-commit hook as well as by hand.

- build_index.py (manual, hook): reads the header block of every script and writes repo_tools/README.md
- build_inventory.py (manual, hook): reads the checks under validation/ and writes validation_inventory.csv
- check_api_key.py (manual): uses read_manifests, and the network
- check_facts.py (manual): uses console_output, read_manifests, verify_pinned, usdm_spec
- check_neo4j.py (manual): uses read_manifests, reads docker-compose.yml, and asks the local Neo4j database its version
- check_python_files.py (manual, hook): runs ruff format, ruff check and mypy
- check_sources_map.py (manual, validation suite): uses read_manifests, and reads docs/sources_index.md
- find_unrecorded_files.py (manual): uses read_manifests
- verify_headers.py (manual, hook): uses the header parser in build_index.py, and reads validation/exit_codes.csv
