# registries/

This folder holds the codes the project assigns to clients, therapeutic areas and document types. Several parts of the project are scoped by these codes. The local USDM extensions in `local_definitions/usdm_extensions/` use them, and the prompt axes described in the Scope section of `PLAN.md` are expected to use them too.

The files are written here and committed to git. They are not pinned, so the rules for `inputs/` do not apply to them.

## Rules

These rules are settled.

1. An internal code is assigned here and never changes.
2. A client's internal code maps to many client codes.
3. Client codes map to many client names and many segments, such as a department or a therapeutic area, and each of those can map to many client codes.
4. No entry is edited once added. Every change is added as a new entry with the date it takes effect.
5. Anything that uses a registry refers only to the internal code.

The tables and fields in the files below are a draft. They need a real client case, and they may be realigned substantially when the prompt axes are worked out in issue #15. Issue #31 tracks settling them, and validation is on hold until then under issue #32.

## Files

| File | What it holds |
| --- | --- |
| `clients.yml` | Test clients, with their client codes and the history of each code. |
| `therapeutic_areas.yml` | Test therapeutic areas. |
| `document_types.yml` | Test document types. |
