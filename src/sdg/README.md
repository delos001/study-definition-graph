# src/sdg/

This is the `sdg` package. It holds the pipeline, as code other code imports, and the commands a person runs on the project's inputs, which `docs/commands.md` lists. It has one folder per group of work, in the order the pipeline runs. A folder gets a `README.md` listing its files once it has files to list; each file's header block is the full account of that file. Nothing is described at more than one level.

| Folder | What it does |
| --- | --- |
| `sources/` | It gets and keeps the pipeline's inputs. It acquires recorded files, updates a source to a new version, and proves a file is the pinned one before any stage reads it. |
| `usdm/` | It reads the USDM standard, so the pipeline knows what a class is, what it holds, and what it points at. |
| `view/` | It shows a person what is inside a pinned document, such as a PDF section or a workbook sheet. |
| `locate/` | In phase 1, it takes a study document and finds where its content lives, such as its section boundaries and the schedule grid, with no AI. |
| `classify/` | In phase 2, it says what kind of document a study document is and what each located section is about. |
| `extract/` | In phase 3, it turns classified content into USDM-shaped structures, each carrying where it came from. |
| `graph/` | In phase 4, it loads the structures into Neo4j, links across documents, and answers questions that span them. |

A file used by several stages goes in the root of `sdg/`. Today two files sit there. `console_output.py` makes the console print the standards' characters intact on Windows. `exit_codes.py` holds the groups of failure a command exits with, and prints the lines a failing command shows. When two or more such files are about the same thing, they move into a folder named for that thing. Nothing gets a folder before it has earned one.

A file does one job. When a file also does a piece of work that comes before or after its job, and another file could use that piece too, that piece belongs in a file of its own.

Every folder holds two kinds of file. A workflow runs steps in order and decides what happens at each one. It holds the policy, and it turns errors into an outcome. A step does one thing, decides nothing, and belongs to no workflow, so any workflow can use it. A step may use another step, for example the fingerprint step takes the entry the manifest step read.

The package is installed once with `pip install -e .`, which is a step in the setup block of the root `README.md`. The tools that keep the repository's own files in order are in `src/sdgtools/`, and the checks that prove this code works are in `validation/sdg/`.
