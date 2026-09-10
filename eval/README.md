# eval/

What the pipeline's output is scored against. Answer keys, and later the agreed acceptance thresholds and scoring definitions, which are fixed before testing begins and so live here, committed, rather than under `inputs/`.

Nothing is here yet. CDISC's three worked examples, which serve as the first answer keys, are downloads and so sit under `inputs/worked_examples/`, ignored by git and restorable from `manifests/`.

Hand-built answer sets go in their own subfolders here as they are written. A worked example is an interpretation and can be wrong, so scoring must be able to flag a suspect reference rather than penalize a correct extraction that disagrees with it.
