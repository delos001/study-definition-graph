# repo_tools/

The words in brackets after each name say who runs the tool: a person, the pre-commit hook, or pytest. The rest of the line says what it reads beyond its own arguments.

- build_index.py (by hand and by the pre-commit hook): reads the header block of every script and writes repo_tools/README.md
- build_inventory.py (by hand and by the pre-commit hook): reads the checks under validation/ and writes validation_inventory.csv
- check_api_key.py (by hand): uses read_manifests, and the network
- check_facts.py (by hand): uses console_output, read_manifests, verify_pinned, usdm_spec
- check_neo4j.py (by hand): uses read_manifests, reads docker-compose.yml, and asks the local Neo4j database its version
- check_python_files.py (by hand and by the pre-commit hook): runs ruff format, ruff check and mypy
- check_sources_map.py (by hand and by pytest): uses read_manifests, and reads docs/sources_index.md
- find_unrecorded_files.py (by hand): uses read_manifests
- verify_headers.py (by hand and by the pre-commit hook): uses the header parser in build_index.py, and reads validation/exit_codes.csv
