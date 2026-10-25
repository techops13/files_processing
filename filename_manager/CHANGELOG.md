# Changelog

## v1.2.0 — 2026-10-24

- Trim trailing as well as leading punctuation and symbols from filename stems after remove operations.
- Preserve extensions and internal punctuation, including ISBN hyphens.
- Keep `--keep-leading-symbols` as a compatibility flag that suppresses edge cleanup.
- Add regression tests for extra periods before extensions and empty names.


## v1.1.0 — 2026-10-24

- Add automatic collision naming using `[dup2]`, `[dup3]`, etc. without overwriting existing files.
- Add `--on-conflict suffix|skip`; `suffix` is the default.
- Handle collisions with names already present or allocated during a single run.
- Update README and package metadata for v1.1.

## v1.0.0

- Interactive and noninteractive filename removal, replacement, prefix, and suffix operations.
- Recursive scanning, dry-run default, leading-symbol cleanup after removal, logging, and basic rename safeguards.
