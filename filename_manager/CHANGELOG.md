## [2.2.1] - 2026-10-27
- Recover unclosed publication year at filename end, such as `(2020.pdf`, without guessing author or casing.
- Add `sanitize` action for plus separators and dense hyphen-separated filename slugs.
- Mark ambiguous dense-hyphen transformations `SANITIZATION_REVIEW`; do not apply without manual refinement.
- Preserve ISBNs, manually bracketed metadata, and publisher-author separators.
- Update configuration, tests, and usage documentation.

# Changelog

## v2.1.0 — 2026-10-24

- Move complete leading bracketed metadata groups to just before the file extension, without losing their contents.
- Preserve trailing bracket groups, including `[]`, `[2026]`, and `[dup2]`.
- Remove leading/trailing underscores and other unwanted edge symbols while preserving internal underscores and punctuation.
- Continue universal cleanup across Remove, Replace, Prefix, and Suffix, with safe duplicate naming.
- Add regression tests for moved metadata, paired brackets, and symbol cleanup.


## v2.0.0 — 2026-10-24

- Enforce automatic leading and trailing symbol cleanup for **all** actions (remove, replace, prefix, suffix), including files with no matching search text.
- Preserve punctuation inside the name and preserve file extensions.
- Remove `--keep-leading-symbols` override so filename hygiene is universal; breaking change.
- Keep dry-run default and safe duplicate suffix behavior.
- Add universal-cleanup regression tests.

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

## [2.2.0] - 2026-10-26
- Added separate filename-only `normalize` action, configured by `filename_config.toml`.
- Recognizes clear year, edition, trailing `by Author`, and `Author -- Title` patterns without reading book contents.
- Preserves already fully structured filenames and manual notes; fills empty metadata bracket slots.
- Adds conservative casing review for uniformly upper/lowercase filenames, retaining questionable names during `--apply`.
- Adds filename-based potential duplicate reporting (`--action duplicates`, `--report-duplicates`). No deletion or content hashing.
- Existing remove/replace/prefix/suffix functionality remains available; normalization is opt-in.
