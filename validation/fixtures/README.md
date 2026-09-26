# validation/fixtures/

A fixture here is a small file on disk that stands in for a real file a check should not read directly, such as a pinned file under `inputs/`.

A check needs one when the real file must never be altered, may not be present, or is too large to read whole. A check reads the fixture, or a broken copy of it made in memory, in place of the real file.

The pytest fixtures in `validation/conftest.py` are also called fixtures, but they are setups that a check asks for by name.

A check that reads a file here names it with the `needs_fixture` label, written as the file's name inside this folder, as in `@needs_fixture("usdm_three_classes.yml")`. A validation report then records which version of the file the check read.

## In this folder

- `usdm_three_classes.yml`: Holds three classes from the pinned USDM model, read by the checks of the model loader `src/sdg/usdm/usdm_spec.py`.
