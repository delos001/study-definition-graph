# searches/

This folder holds a record of each search run to find candidate studies. There is one subfolder per source searched, and one file per run.

The records are committed, because a source such as ClinicalTrials.gov changes daily and a later run cannot show what an earlier run found.

| Folder | What it holds |
| --- | --- |
| `ctgov/` | One JSON file per run of `find_ctgov_studies`, named by the date and time the run started. Each file holds the search as sent, the filters as they were set, how many studies were left after each filter, and the details of each candidate study. |
