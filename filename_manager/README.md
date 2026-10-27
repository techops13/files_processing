# Filename Manager v2.1

Offline, cross-platform Python command-line utility for recursively renaming filenames. It can **remove**, **replace**, **add a prefix**, or **add a suffix**. By default **no files are changed** (dry run).

## Requirements

- Python **3.9 or newer** (Python 3.12+ recommended).
- macOS, Windows, or Linux.
- **No third-party libraries, package downloads, or network connection** needed to run the tool.
- Read/write permission for directories you choose to modify.

`requirements.txt` is intentionally empty of installable packages. `pyproject.toml` records the Python version and dependency metadata. Run the Python script directly; no `pip install` or packaging/build tools needed.

## Setup from Git

```bash
git clone <YOUR_REPOSITORY_URL>
cd files_processing/filename_manager
```

If you don't have Git, simply download and extract the repository ZIP.

Optional project virtual environment (recommended for consistent local development):

**macOS / Linux**

```bash
python3 -m venv venv
source venv/bin/activate
python --version
python filename_manager.py --help
```

**Windows PowerShell**

```powershell
py -3 -m venv venv
.\venv\Scripts\Activate.ps1
python --version
python filename_manager.py --help
```

If PowerShell prevents activation, you can run ` .\venv\Scripts\python.exe filename_manager.py --help` directly.

On systems where Python is not installed, install Python 3.9+ from https://www.python.org/downloads/ (on Windows, enable the PATH option if offered). On macOS, `brew install python` is an alternative; on Debian/Ubuntu use `sudo apt install python3 python3-venv`.

No dependency installation is necessary. `python -m pip install -r requirements.txt` is optional and installs nothing.

## Usage

Start interactive mode:

```bash
python filename_manager.py
```

Noninteractive dry run — remove `filanem.st_` recursively:

```bash
python filename_manager.py "/path/to/books" --action remove --find "filanem.st_"
```

Apply the renames only after reviewing the preview:

```bash
python filename_manager.py "/path/to/books" --action remove --find "filanem.st_" --apply
```

Replace text:

```bash
python filename_manager.py "/path/to/books" --action replace --find "old" --with-text "new" --apply
```

Add text to a filename (without changing extensions):

```bash
python filename_manager.py "/path/to/books" --action prefix --with-text "Book_" --apply
python filename_manager.py "/path/to/books" --action suffix --with-text "_reviewed" --apply
```

On macOS / Linux, use `python3` if `python` is not mapped to Python 3. On Windows, use `py -3` in place of `python` if necessary. Quote paths containing spaces.

## Options

| Option | Meaning |
| --- | --- |
| `--action remove\|replace\|prefix\|suffix` | Operation to run |
| `--find TEXT` | String to find for remove or replace |
| `--with-text TEXT` | New text for replace/prefix/suffix |
| `--apply` | Actually rename; otherwise dry run |
| `--case sensitive\|insensitive` | Case matching (defaults to sensitive) |
| `--no-recursive` | Only process files in the selected folder |
| `--include-hidden` | Include hidden files and folders |
| `--log-dir PATH` | Save per-run logs to chosen directory (default `./logs`) |
| `--on-conflict suffix\|skip` | Automatically assign `[dup2]`, `[dup3]` (default), or skip conflicting names |
| `--help` | Show command help |

### Universal filename cleanup


### Safety and limitations

- Dry-run default; explicit `--apply` required to rename.
- Operates on **filenames**, not folders; scans child folders by default.
- Preserves filename extensions, including common compound extensions like `.tar.gz`.
- Skips hidden files/folders by default; skips symlinks.
- Will not overwrite existing destination names; automatically assigns `[dup2]`, `[dup3]`, etc. by default, or skips conflicts with `--on-conflict skip`.
- Skips invalid or empty resulting names.
- A unique timestamped log is created every run in the `logs/` directory unless configured otherwise; logs are ignored by Git.
- Renaming within the same filesystem ordinarily preserves file contents and metadata; directory timestamps may change. Back up important collections before applying bulk changes.
- Case-insensitive filename collisions may behave differently across filesystems. Test on a small sample first.

## Run tests

```bash
python -m unittest discover -s tests -v
```

## Git publishing

To add this tool to your existing **files_processing** repository (rather than creating another Git repository):

```bash
cd files_processing
# Copy this project into files_processing/filename_manager/
git add filename_manager/
git commit -m "feat(filename-manager): update to v1.1 with collision suffixes"
git push origin main
```

Make sure not to commit private book collections or log files. Verify `git status` and `git diff --cached --stat` before pushing.

## Duplicate handling (v1.1)

By default, a destination collision gets a **unique duplicate suffix** instead of being skipped or overwritten. For example, if `1.epub` exists:

- `test.st_1.epub` after removing `test.st_` becomes `1 [dup2].epub`.
- If `1 [dup2].epub` also exists, it becomes `1 [dup3].epub`.

This also accounts for *other files in the same batch* and preserves all original source filenames until their rename is evaluated. Run a dry run first to see the selected names. To keep the old behavior (skip duplicates), use `--on-conflict skip`.

```bash
python filename_manager.py /path/to/books --action remove --find 'test.st_'  # Preview
python filename_manager.py /path/to/books --action remove --find 'test.st_' --apply
python filename_manager.py /path/to/books --action remove --find 'test.st_' --on-conflict skip --apply
```

This resolves **filename collisions**, not identical content. Two files may have identical bytes; use a separate hash-based duplicate checker if you want to identify or delete truly redundant copies.

## Universal filename hygiene (v2.1)

After a **remove** operation, filename stems are trimmed on **both ends** until they begin and end with a Unicode letter or digit. The file extension is preserved and internal punctuation (including ISBN hyphens) remains unchanged.

Example: `979-8-8688-2083-0.filename.tt.pdf` with `--find filename.tt` becomes `979-8-8688-2083-0.pdf`, not `979-8-8688-2083-0..pdf`.



### Universal filename hygiene (v2.1.0)

For every file scanned, every operation trims punctuation, symbols, and whitespace **before the first letter/number and after the last letter/number of the filename stem**. This includes files where the search text is not found. Extensions remain unchanged, and internal dots, hyphens, spaces and other punctuation remain unchanged. Examples: `.._Book--.pdf` → `Book.pdf`; `979-8-8688-2083-0.filename.tt.pdf` after removing `filename.tt` → `979-8-8688-2083-0.pdf`. If cleanup empties the stem, the file is skipped. Dry run is still the default. The `--keep-leading-symbols` option is no longer supported.

## Bracket metadata convention (v2.1)

The script moves any complete leading `[metadata]` groups to the end of the
filename stem, immediately before its extension. Existing trailing bracketed
metadata, such as `[2026]`, `[2nd Edition]`, `[]`, and `[dup2]`, remains intact.
Underscores are permitted inside names but removed from the beginning and end.
This sanitation applies to every operation, including files without a search match.

Examples:

```text
[2026]Book.pdf                       -> Book [2026].pdf
[2026] Publisher -- Book [3rd Edition].pdf -> Publisher -- Book [3rd Edition] [2026].pdf
_[2026]_My_Book_.epub                -> My_Book [2026].epub
Book [2026]_.pdf                     -> Book [2026].pdf
```

Use the default dry run before `--apply`, especially on large archives.

## v2.2.0: optional filename-only normalization and duplicate review

These are distinct operations; **Remove / Replace / Prefix / Suffix still behave as before**.

```bash
# Dry-run normalization (default); no file contents are read
python filename_manager.py ~/Downloads/books --action normalize

# Apply only unambiguous proposed changes (review flags are skipped)
python filename_manager.py ~/Downloads/books --action normalize --apply

# Read-only potential duplicate groups by case-insensitive name/[dupN] suffix
python filename_manager.py ~/Downloads/books --action duplicates

# Ask for a duplicate report after an operation
python filename_manager.py ~/Downloads/books --action normalize --report-duplicates
```

Rules are in `filename_config.toml` (Python 3.11+ needed for `tomllib`). The program leaves correctly structured `Publisher -- Author - Title [Year][Edition][Notes].ext` filenames unchanged, preserving all metadata and punctuation. Normalizing other names can recognize certain years, editions and authors **only from filenames**; missing fields are kept empty and missing publisher becomes `Unknown` only when an author can be reliably parsed. Notes such as `[Must Read]`, `[Super Book]` and `[Manga Guide]` are protected from removal. The normalization output convention uses adjacent trailing groups (`[Year][Edition][Notes]`), including empty `[]` groups.

**Casing safeguard:** Uniformly upper- or lowercase filenames are flagged `CASING_REVIEW`. The script does not silently apply guessed title casing, particularly for author names and brand names. Plus-separated filenames are flagged `SEPARATOR_REVIEW`. Files flagged `CASING_REVIEW`, `SEPARATOR_REVIEW`, `MULTIPLE_NOTES_REVIEW`, or `EMPTY_TITLE` are **never renamed by `--apply`**; `AUTHOR_UNKNOWN` alone does not block adding empty brackets to preserve manual notes. Dry-run displays a proposal but does not modify files. Full casing automation needs user-approved dictionaries and further tests.

Duplicate reports are filename-based only, so they are *possible* duplicates, not proof of equal contents. Report mode never deletes files. Name normalization does not read book metadata or invoke remote AI.

## v2.2.1: sanitization and malformed year recovery

Python 3.11+ required. A virtual environment is recommended.

```bash
python filename_manager.py ~/Downloads/testing_books --action sanitize
python filename_manager.py ~/Downloads/testing_books --action normalize
python filename_manager.py ~/Downloads/testing_books --action sanitize --apply
```

All operations default to **dry run**. The `sanitize` action converts plus signs to spaces,
and proposes converting dense hyphen-separated slugs (four or more word segments) to spaces.
Dense hyphen conversions are marked `SANITIZATION_REVIEW` and **not applied** under `--apply`
because they could involve valid hyphenated names. Inspect dry-run logs and rename these
manually until a confirmed rule is added. Bracketed metadata and already structured
publisher/author/title patterns are protected. ISBN-like number patterns are preserved.

`normalize` now recognizes a dangling four-digit year at the end of the stem, e.g.
`tantra dev - mahavidyas (2020.pdf` → `tantra dev - mahavidyas [2020][][].pdf`.
`AUTHOR_UNKNOWN` and `CASING_REVIEW` still require review; normalization must not
invent authors or automatically guess capitalization.

**Operational caveat:** This tool's rename planning is conservative but not transactional;
use copies in a test directory and review logs before large-scale `--apply` runs.
