#!/usr/bin/env python3
"""Safely remove, replace, prefix, or suffix filename text recursively.

Python 3.9+, standard library only. Dry-run is the default.
"""
import argparse
import datetime as dt
import logging
import os
from pathlib import Path


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument('directory', nargs='?', help='Directory to scan')
    p.add_argument('--action', choices=['remove', 'replace', 'prefix', 'suffix'])
    p.add_argument('--find', help='Text to remove or replace')
    p.add_argument('--with-text', default=None, help='Replacement text, or text to prepend/append')
    p.add_argument('--case', choices=['sensitive', 'insensitive'], default=None)
    p.add_argument('--apply', action='store_true', help='Actually rename files (otherwise dry run)')
    p.add_argument('--keep-leading-symbols', action='store_true', help='Disable automatic removal of leading symbols after a remove operation')
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
        print('1) Remove string  2) Replace string  3) Add prefix  4) Add suffix')
        args.action = {'1': 'remove', '2': 'replace', '3': 'prefix', '4': 'suffix'}[ask_choice('Choose [1-4]: ', {'1','2','3','4'})]
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


def trim_leading_symbols(value):
    """Discard leading punctuation, symbols, whitespace and control characters.

    Unicode letters and numbers remain intact.
    """
    return value[next((i for i, ch in enumerate(value) if ch.isalnum()), len(value)):]


def transformed(name, args):
    # Work on the filename stem, never alter extension(s) from operations.
    # pathlib treats .tar.gz as .gz, so explicitly protect well-known compound extensions.
    compound = ('.tar.gz', '.tar.bz2', '.tar.xz', '.tar.zst')
    ext = next((name[-len(e):] for e in compound if name.lower().endswith(e)), None)
    if ext is None:
        ext = Path(name).suffix
    stem = name[:-len(ext)] if ext else name
    if args.action == 'remove':
        stem = replace_text(stem, args.find, '', args.case == 'insensitive')
        if not args.keep_leading_symbols:
            stem = trim_leading_symbols(stem)
    elif args.action == 'replace':
        stem = replace_text(stem, args.find, args.with_text, args.case == 'insensitive')
    elif args.action == 'prefix':
        stem = args.with_text + stem
    elif args.action == 'suffix':
        stem = stem + args.with_text
    return stem + ext if stem else None


def main():
    args = parse_args()
    # Fully specified automated calls never prompt.
    if not (args.directory and args.action and (args.action not in ('remove','replace') or args.find is not None)
            and (args.action not in ('replace','prefix','suffix') or args.with_text is not None)):
        args = interactive(args)
    if args.case is None:
        args.case = 'sensitive'
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
    logging.info('Directory=%s action=%s apply=%s case=%s recursive=%s trim_leading=%s', root, args.action, args.apply, args.case, not args.no_recursive, not args.keep_leading_symbols)
    files = []
    for current, dirs, names in os.walk(root, followlinks=False):
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
            files.append(source)
    files.sort()
    print(f'Mode: {"APPLY" if args.apply else "DRY RUN"} | Scanning: {root} | Files: {len(files)}')
    changed = skipped = conflicts = errors = 0
    # Reserve destinations across batch (including unchanged source names) to avoid clashes.
    source_paths = set(files)
    planned_destinations = set()
    for src in files:
        updated = transformed(src.name, args)
        if updated is None or updated in {'.', '..'} or '/' in updated or '\\' in updated or '\x00' in updated:
            skipped += 1
            logging.warning('INVALID_TARGET %s', src)
            continue
        if updated == src.name:
            skipped += 1
            continue
        dst = src.with_name(updated)
        if dst.exists() or dst in planned_destinations or (dst in source_paths):
            conflicts += 1
            print(f'CONFLICT: {src.name} -> {updated}')
            logging.warning('CONFLICT %s -> %s', src, dst)
            continue
        planned_destinations.add(dst)
        print(f'{"RENAME" if args.apply else "WOULD RENAME"}: {src} -> {updated}')
        logging.info('%s %s -> %s', 'RENAME' if args.apply else 'DRY_RUN', src, dst)
        if args.apply:
            try:
                src.rename(dst)
            except OSError as exc:
                errors += 1
                logging.exception('FAILED %s -> %s', src, dst)
                print(f'ERROR: {exc}')
                continue
        changed += 1
    summary = f'Files scanned={len(files)}; {"renamed" if args.apply else "proposed"}={changed}; unchanged/skipped={skipped}; conflicts={conflicts}; errors={errors}'
    logging.info(summary)
    print(summary)
    print(f'Logfile: {log_path}')
    if conflicts or errors:
        raise SystemExit(2)


if __name__ == '__main__':
    main()
