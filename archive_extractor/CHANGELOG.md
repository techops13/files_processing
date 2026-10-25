# Changelog

## [1.0.1] - 2026-10-25

### Fixed
- RAR5/7z technical-listing parser now ignores archive-level metadata and recognizes empty link fields as absent.
- Flags nonempty symbolic/hard/copy links as unsafe, preserves path traversal protections.
- Unsafe archive errors now include the offending member name.
- Added RAR5 listing regression tests for real-world safe entries and malicious paths/links.


## [1.0.0] - 2026-10-25

### Added
- Self-contained Archive Extractor foundation and TOML configuration.
- Recursive archive inventory and dry run by default; explicit `--stage`.
- Book priority PDF > EPUB > MOBI > AZW3 > DJVU/DJV.
- Strict whole-archive rejection for mixed media, executables, nested archives, unknown types, encrypted items and unsafe paths.
- ZIP/TAR built-in reader; optional 7z CLI backend for 7z and RAR; unsupported formats are inventoried and skipped.
- Atomic-style no-overwrite staging, collision suffixes, temporary file cleanup, size/signature verification and SHA-256 output hash.
- Run start/end timestamps, monotonic elapsed timing, color-coded terminal levels, human/JSONL logs, CSV and optional XLSX inventory.
- Regression tests for safe staging and filtering.

### Limitations
- Standalone compressed streams, miscellaneous legacy archive formats and multipart sets are reported but not extracted.
- CLI is flag-based, not interactive; ZIP/TAR operations do not have a hard interruption timeout.
- External 7z/RAR backend depends on installed 7zz/7z and should be tested with representative real-world archives.
