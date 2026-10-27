#!/usr/bin/env python3
"""Safely remove, replace, prefix, or suffix filename text recursively.

Python 3.9+, standard library only. Dry-run is the default.
"""
import argparse
import datetime as dt
import logging
import os
import re
from filename_normalize import load_config, normalize, duplicate_groups, sanitize, is_archive_filename
from pathlib import Path


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument('directory', nargs='?', help='Directory to scan')
    p.add_argument('--action', choices=['remove', 'replace', 'prefix', 'suffix', 'normalize', 'duplicates', 'sanitize'])
    p.add_argument('--config', help='Filename normalization TOML (defaults beside script)')
    p.add_argument('--report-duplicates', action='store_true', help='Report potential filename duplicates after processing')
    p.add_argument('--find', help='Text to remove or replace')
    p.add_argument('--with-text', default=None, help='Replacement text, or text to prepend/append')
    p.add_argument('--case', choices=['sensitive', 'insensitive'], default=None)
    p.add_argument('--apply', action='store_true', help='Actually rename files (otherwise dry run)')
    p.add_argument('--on-conflict', choices=['suffix', 'skip'], default='suffix',
                   help='If target exists, add [dup2], [dup3], etc. or skip')
    p.add_argument('--no-recursive', action='store_true', help='Only scan selected directory')
    p.add_argument('--include-hidden', action='store_true', help='Include hidden files and directories')
    p.add_argument('--log-dir', help='Where to store the logfile (default: current working directory/logs)')
    return p.parse_args()


def ask_choice(prompt, choices):
    while True:
        answer = input(prompt).strip().lower()
        if answer in choices:
            return answer
        print('Choose: ' + ', '.join(choices))


def interactive(args):
    if not args.directory:
        args.directory = input('Directory to scan: ').strip().strip('"')
    if not args.action:
        print('1) Remove  2) Replace  3) Prefix  4) Suffix  5) Normalize  6) Duplicates  7) Sanitize')
        args.action = {'1': 'remove', '2': 'replace', '3': 'prefix', '4': 'suffix', '5': 'normalize', '6': 'duplicates', '7': 'sanitize'}[ask_choice('Choose [1-7]: ', {'1','2','3','4','5','6','7'})]
    if args.action in ('remove', 'replace') and args.find is None:
        args.find = input('Text to find: ')
    if args.action in ('replace', 'prefix', 'suffix') and args.with_text is None:
        args.with_text = input('New text: ')
    if args.case is None:
        args.case = {'s':'sensitive', 'i':'insensitive'}[ask_choice('Case matching [s]ensitive/[i]nsensitive: ', {'s','i'})]
    return args


def replace_text(name, old, new, insensitive):
    if not insensitive:
        return name.replace(old, new)
    import re
    return re.sub(re.escape(old), lambda match: new, name, flags=re.IGNORECASE)


def trim_edge_symbols(value):
    """Clean name edges while moving leading [...] metadata to the end.

    Underscores are valid inside the name but not at its edges. Complete
    bracket groups at the end are preserved (including empty [] groups).
    """
    leading_groups = []
    rest = value
    # Ignore leading edge punctuation, but retain bracket groups for moving.
    while True:
        rest = rest.lstrip()  # leading spaces
        while rest and not rest[0].isalnum() and rest[0] != '[':
            rest = rest[1:]
        match = re.match(r'^\[([^\[\]]*)\]', rest)
        if not match:
            break
        leading_groups.append(match.group(0))
        rest = rest[match.end():]

    # Strip edge noise after a closing bracket without stripping that bracket.
    while rest and not rest[-1].isalnum() and rest[-1] != ']':
        rest = rest[:-1]
    # Preserve complete bracket groups already at the end of the stem.
    trailing = re.search(r'(?:\s*\[[^\[\]]*\])+$', rest)
    ending_groups = re.findall(r'\[[^\[\]]*\]', trailing.group(0)) if trailing else []
    core = rest[:trailing.start()] if trailing else rest
    first = next((i for i, ch in enumerate(core) if ch.isalnum()), len(core))
    if first == len(core):
        return ''  # avoid metadata-only filenames with no base title
    last = next(i for i in range(len(core) - 1, first - 1, -1) if core[i].isalnum())
    core = core[first:last + 1]
    return core + ''.join(' ' + group for group in ending_groups + leading_groups)


def transformed(name, args, cfg=None):
    if args.action == 'normalize':
        return normalize(name, cfg)[0]
    if args.action == 'sanitize':
        return sanitize(name, cfg)[0]
    if args.action == 'duplicates':
        return name
    # Work on the filename stem, never alter extension(s) from operations.
    # pathlib treats .tar.gz as .gz, so explicitly protect well-known compound extensions.
    compound = ('.tar.gz', '.tar.bz2', '.tar.xz', '.tar.zst')
    ext = next((name[-len(e):] for e in compound if name.lower().endswith(e)), None)
    if ext is None:
        ext = Path(name).suffix
    stem = name[:-len(ext)] if ext else name
    if args.action == 'remove':
        stem = replace_text(stem, args.find, '', args.case == 'insensitive')
    elif args.action == 'replace':
        stem = replace_text(stem, args.find, args.with_text, args.case == 'insensitive')
    elif args.action == 'prefix':
        stem = args.with_text + stem
    elif args.action == 'suffix':
        stem = stem + args.with_text
    # Universal filename hygiene, even if the requested search text is absent.
    stem = trim_edge_symbols(stem)
    return stem + ext if stem else None


def duplicate_name(name, number):
    """Insert a duplicate marker before the final or known compound extension."""
    compound = ('.tar.gz', '.tar.bz2', '.tar.xz', '.tar.zst')
    ext = next((name[-len(e):] for e in compound if name.lower().endswith(e)), None)
    if ext is None:
        ext = Path(name).suffix
    stem = name[:-len(ext)] if ext else name
    # Avoid producing a second duplicate marker if the cleaned filename already has one.
    stem = re.sub(r' \[dup\d+\]$', '', stem, flags=re.IGNORECASE)
    return f'{stem} [dup{number}]{ext}'


def destination_taken(dst, reserved):
    """Case-folding also protects likely cross-platform / macOS case-insensitive clashes."""
    return dst.exists() or str(dst).casefold() in reserved


def main():
    args = parse_args()
    # Fully specified automated calls never prompt.
    if not (args.directory and args.action and (args.action not in ('remove','replace') or args.find is not None)
            and (args.action not in ('replace','prefix','suffix') or args.with_text is not None)):
        args = interactive(args)
    if args.case is None:
        args.case = 'sensitive'
    cfg_path = Path(args.config).expanduser() if args.config else Path(__file__).with_name('filename_config.toml')
    cfg = load_config(cfg_path) if args.action in ('normalize', 'sanitize') else None
    if args.action in ('remove','replace') and not args.find:
        raise SystemExit('ERROR: --find must not be empty.')
    if args.action in ('replace','prefix','suffix') and args.with_text is None:
        raise SystemExit('ERROR: --with-text is required.')
    if args.action in ('prefix','suffix') and not args.with_text:
        raise SystemExit('ERROR: text to add must not be empty.')
    root = Path(args.directory).expanduser().resolve()
    if not root.is_dir():
        raise SystemExit(f'ERROR: Not a directory: {root}')
    log_dir = Path(args.log_dir).expanduser().resolve() if args.log_dir else Path.cwd() / 'logs'
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime('%Y-%b-%d_%H%M%S_%f')
    log_path = log_dir / f'filename_manager_{stamp}.log'
    logging.basicConfig(filename=log_path, level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s', encoding='utf-8')
    logging.info('Directory=%s action=%s apply=%s case=%s recursive=%s universal_edge_cleanup=True', root, args.action, args.apply, args.case, not args.no_recursive)
    files = []
    for current, dirs, names in os.walk(root, followlinks=False):
        # Never process generated logs, even if logs live under the input tree.
        dirs[:] = [d for d in dirs if (Path(current) / d).resolve() != log_dir and log_dir not in (Path(current) / d).resolve().parents]
        if not args.include_hidden:
            dirs[:] = [d for d in dirs if not d.startswith('.')]
        if args.no_recursive:
            dirs[:] = []
        for name in names:
            if not args.include_hidden and name.startswith('.'):
                continue
            source = Path(current) / name
            if source.is_symlink() or not source.is_file():
                continue
            if is_archive_filename(source.name):
                continue
            files.append(source)
    files.sort()
    print(f'Mode: {"APPLY" if args.apply else "DRY RUN"} | Scanning: {root} | Files: {len(files)}')
    if args.action == 'duplicates':
        groups = duplicate_groups(files)
        print(f'Potential duplicate groups: {len(groups)}')
        for key, entries in sorted(groups.items()):
            print(f'\n  GROUP: {key} ({len(entries)} files)')
            for entry in entries: print(f'    {entry}')
        logging.info('Duplicate groups=%s details=%s', len(groups), {k: [str(p) for p in v] for k,v in groups.items()})
        return
    changed = skipped = conflicts = errors = 0
    # Reserve every original name even if it is unchanged or processed later.
    # This prevents a planned rename from taking another file's original path.
    reserved = {str(src).casefold() for src in files}
    duplicates = 0
    for src in files:
        updated = transformed(src.name, args, cfg)
        if args.action in ('normalize', 'sanitize'):
            updated, review = (normalize(src.name, cfg) if args.action == 'normalize' else sanitize(src.name, cfg))
            if review:
                logging.warning('REVIEW_REQUIRED %s reasons=%s proposed=%s', src, review, updated)
                print(f'\nREVIEW REQUIRED: {src.name} | {", ".join(review)}\n  Proposed: {updated}')
                # A review flag is informational during dry run; never auto-apply.
                if args.apply and any(code in {'CASING_REVIEW', 'SEPARATOR_REVIEW', 'SANITIZATION_REVIEW', 'MULTIPLE_NOTES_REVIEW', 'EMPTY_TITLE'} for code in review):
                    skipped += 1
                    continue
        if updated is None or updated in {'.', '..'} or '/' in updated or '\\' in updated or '\x00' in updated:
            skipped += 1
            logging.warning('INVALID_TARGET %s', src)
            continue
        if updated == src.name:
            skipped += 1
            continue
        dst = src.with_name(updated)
        original_target = dst
        if destination_taken(dst, reserved):
            if args.on_conflict == 'skip':
                conflicts += 1
                print(f'CONFLICT SKIPPED: {src.name} -> {updated}')
                logging.warning('CONFLICT_SKIPPED %s -> %s', src, dst)
                continue
            number = 2
            while True:
                alternative = src.with_name(duplicate_name(updated, number))
                if not destination_taken(alternative, reserved):
                    dst = alternative
                    break
                number += 1
            duplicates += 1
            print(f'DUPLICATE: {src.name} -> {dst.name} (requested: {original_target.name})')
            logging.info('DUPLICATE_RESOLVED %s -> %s; original_target=%s', src, dst, original_target)
        reserved.add(str(dst).casefold())
        print(f'{"RENAME" if args.apply else "WOULD RENAME"}: {src} -> {dst.name}')
        logging.info('%s %s -> %s', 'RENAME' if args.apply else 'DRY_RUN', src, dst)
        if args.apply:
            try:
                # Defensive second check before renaming; never intentionally overwrite.
                if dst.exists():
                    raise FileExistsError(f'Target appeared after planning: {dst}')
                src.rename(dst)
            except OSError as exc:
                errors += 1
                logging.exception('FAILED %s -> %s', src, dst)
                print(f'ERROR: {exc}')
                continue
        changed += 1
    summary = f'Files scanned={len(files)}; {"renamed" if args.apply else "proposed"}={changed}; unchanged/skipped={skipped}; duplicates_resolved={duplicates}; conflicts_skipped={conflicts}; errors={errors}'
    logging.info(summary)
    print(summary)
    print(f'Logfile: {log_path}')
    if args.report_duplicates:
        effective = [p for p in root.rglob('*') if p.is_file() and not p.is_symlink()] if args.apply else files
        groups = duplicate_groups(effective)
        print(f'\nPOTENTIAL DUPLICATE GROUPS: {len(groups)}')
        for key, entries in sorted(groups.items()):
            print(f'\n  {key} ({len(entries)})')
            for entry in entries[:10]: print(f'    {entry}')
            if len(entries) > 10: print(f'    ... and {len(entries)-10} more')
        logging.info('DUPLICATE_GROUPS %s %s', len(groups), {k: [str(x) for x in v] for k,v in groups.items()})
    if conflicts or errors:
        raise SystemExit(2)


if __name__ == '__main__':
    main()
