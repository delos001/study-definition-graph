# eval/

This folder contains information the pipeline's output is scored against.

It holds the answer keys, and later the agreed acceptance thresholds and scoring definitions, which are fixed before testing begins. They are written here rather than downloaded, so they sit here rather than under `inputs/`.

Note: CDISC's worked examples, which serve as the first answer keys, are downloads and so sit under `inputs/worked_examples/`.

Hand-built answer sets go in their own subfolders here as they are written.

A worked example is an interpretation and can be wrong, so scoring must be able to flag a suspect reference rather than penalize a correct extraction that disagrees with it.
