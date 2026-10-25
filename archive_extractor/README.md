# Archive Extractor v1.0

A **conservative, noninteractive** archive inventory and book stager for the `files_processing` project. It is designed as a future pipeline component, but runs independently. It never modifies original archives.

## Safety policy

1. Discover archives recursively, ignoring hidden files, symlinks, and the stage directory.
2. Inspect **every** member before selecting anything. A book alone qualifies; book + disallowed audio/video/software/unknown/nested archive means **skip the entire archive** and report why. Supporting `.txt`, `.nfo`, `.opf`, `.ncx`, `.md`, `.jpg`, `.jpeg`, `.png`, `.gif`, `.webp`, `.xml`, `.json`, `.sfv`, `.sha256` are permitted companions but never qualify an archive themselves. This allowlist is a policy choice: change it in a future reviewed release, not ad hoc.
3. Reject unsafe paths, links, encrypted entries, bad archives and unavailable extractors. Passwords are never prompted for; external commands receive closed stdin, explicit empty password, and a timeout.
4. Select **one** file per eligible archive, ranked **PDF > EPUB > MOBI > AZW3 > DJVU/DJV**. Within a format, use lexicographic member-name order; multiple distinct books in one archive are therefore not all extracted.
5. In `--stage` mode, extract the selected member only, into a temporary file, verify reported size and book signature, hash it, then publish without overwriting any existing destination (using `[dup2]`, `[dup3]`, ...). Failures leave no published partial file.

**Fail closed:** standalone gzip/bzip2/xz/zstd/lzma, CAB/ARJ/LHA/LZH, multipart archives, and ambiguous formats are *discovered and reported* but **not extracted in v1.0**. Support for these formats is planned, not falsely advertised. ZIP and TAR variants (`.tar`, `.tar.gz`, `.tgz`, `.tar.bz2`, `.tbz2`, `.tar.xz`, `.txz`) use stdlib. RAR and 7z use `7zz`/`7z` if installed. Missing extractors are reported. 7z/RAR handling must be verified on your real samples before unattended production use.

Encryption and integrity metadata may be incomplete in some archive formats. Post-extraction verification checks size and format signature; it does **not** promise semantic document validity or full antivirus scanning. Enforce a dedicated sandbox/VM for untrusted archives.

## Installation

Requires Python **3.11+**. No Python packages are needed except optional `openpyxl` for Excel inventories. Use a `venv` named exactly `venv`.

macOS (Apple Silicon):

```bash
cd ~/Projects/files_processing/archive_extractor
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
brew install 7-zip   # provides 7zz for RAR/7z; optional
python archive_extractor.py --help
```

Linux: `python3 -m venv venv && source venv/bin/activate && python -m pip install -r requirements.txt`; install a compatible 7z binary separately. Windows PowerShell: `py -3.11 -m venv venv; .\venv\Scripts\Activate.ps1; python -m pip install -r requirements.txt` and install 7-Zip CLI if RAR/7z support is needed (ensure `7z.exe` is on PATH).

## Usage

Dry-run (default, *no staging*):

```bash
python archive_extractor.py ~/Downloads/book_dump
```

Actually stage only approved books:

```bash
python archive_extractor.py ~/Downloads/book_dump --stage
```

Specify a policy config and disable ANSI colors:

```bash
python archive_extractor.py ~/Downloads/book_dump --config archive_config.toml --no-color
```

Stage output is `<input-directory>/pipeline_input/`, not the project folder. A per-run log directory is created beneath this project as `logs/YYYY-Mon-DD_HH-MM-SS/`. Each includes `archive_extractor.log`, `archive_extractor.jsonl`, `inventory.csv`, `errors.csv`, `run_summary.json`, and `inventory.xlsx` if `openpyxl` is installed. Reports include real start/end timestamps, total elapsed seconds, per-archive time and status. No ANSI codes are written to logs. Exit `0` = run finished without unhandled archive errors (including documented skips); `1` = one or more unexpected errors; `2` = invalid setup/configuration. Check inventory statuses for skipped files even on exit 0.

## Representative statuses

- `ELIGIBLE_DRY_RUN` — candidate book; no extraction performed.
- `STAGED` — safely staged and SHA-256 recorded.
- `SKIPPED_MIXED_CONTENT` — eligible book plus audio/video/software/unknown members.
- `SKIPPED_NON_BOOK` — prohibited contents, no eligible book.
- `NO_ELIGIBLE_BOOK` — only harmless side files, or empty archive.
- `PASSWORD_REQUIRED`, `CORRUPT_ARCHIVE`, `UNSAFE_ARCHIVE`, `INVALID_BOOK_FILE`, `VERIFICATION_FAILED`, `TIMEOUT`.
- `MISSING_EXTRACTOR`, `UNSUPPORTED_FORMAT`, `MULTIPART_REVIEW`, `UNREADABLE_ARCHIVE`.

**Note:** compressed ZIP/7z package member listings may include metadata; the tool never executes the contents. If tool output cannot be parsed, it refuses extraction. The `--stage` command should be run first against a **copy** of test archives.

## Verification, limitations and roadmap

Run tests using `python -m unittest discover -s tests -v`. v1.0 covers ZIP/TAR test cases, safe staging, collisions, and mixed-content exclusion. It does not yet supply an interactive CLI menu, first-class support for all requested compression types, multipart coordination, archive cryptographic attestations, or robust per-archive timeout for stdlib ZIP/TAR operations. For archives with suspect decompression ratios, handle them in a constrained VM rather than untrusted production folders.

A future pipeline should consume `run_summary.json` and `inventory.csv` rather than screen-scraping console output. Check `CHANGELOG.md` before upgrading; policy and schema changes will be documented there.

## v1.0.1 RAR5 listing fix

Some versions of 7-Zip include blank `Symbolic Link`, `Hard Link`, and `Copy Link` fields for ordinary RAR5 book files. This release treats blank fields as absent, while rejecting actual links and unsafe member paths. The archive header is not interpreted as a member. Run `python -m unittest discover -s tests -v` and then a dry run before staging.


## v1.1.0 — Phase 0 inventory and readable terminal output

Every normal run first counts files already present on disk, grouped by complete
extension (`.tar.gz` is counted separately from `.gz`). It displays directory
count, total files, bytes, categories (archive, book, audio, video, other),
per-extension counts, and scan duration **before** archive inspection. This does
not inspect archive members and does not extract anything. Existing staged
outputs, program logs, hidden entries, and symlinks are excluded.

For a statistics-only operation:

```bash
python archive_extractor.py ~/Downloads/Rapidgator --inventory-only
```

To perform the usual safe dry run or explicit staging:

```bash
python archive_extractor.py ~/Downloads/Rapidgator
python archive_extractor.py ~/Downloads/Rapidgator --stage
```

Each run records `pre_run_inventory.json` and `pre_run_inventory.csv` beside
the existing run logs, inventory, errors and summary. The inventory is also
embedded in the run summary for full processing runs.

Warnings are separated visually and include a concise indented list of up to
five disallowed members, plus a count of additional entries. The original
warning text (including **all** disallowed members) is recorded in `.log`,
`.jsonl`, and `inventory.csv`. Terminal color is enabled only when appropriate;
`--no-color` forces plain output.

The `[display]` section of `archive_config.toml` documents the intended
formatting defaults, notably `max_offending_files = 5`. This release implements
that limit and blank-line separators; remaining display keys are reserved for
future refinements.

**Safety:** Dry run is still the default, PDF > EPUB > MOBI > AZW3 > DJVU/DJV
priority is unchanged, and any archive with disallowed media is skipped in
full. This release does not add multipart extraction or change password handling.
