# Changelog

## v1.1.0 — 2026-10-24

- Add automatic collision naming using `[dup2]`, `[dup3]`, etc. without overwriting existing files.
- Add `--on-conflict suffix|skip`; `suffix` is the default.
- Handle collisions with names already present or allocated during a single run.
- Update README and package metadata for v1.1.

## v1.0.0

- Interactive and noninteractive filename removal, replacement, prefix, and suffix operations.
- Recursive scanning, dry-run default, leading-symbol cleanup after removal, logging, and basic rename safeguards.
