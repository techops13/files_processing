"""Conservative, filename-only normalizer and duplicate reviewer; no file content reads."""
import re
import tomllib
from collections import defaultdict
from pathlib import Path

YEAR = re.compile(r'^(?:18|19|20)\d{2}$')
YEAR_AND_TEXT = re.compile(r'^((?:18|19|20)\d{2})(?:,\s*(.+))?$')
EDITION = re.compile(r'^\d+(?:st|nd|rd|th)\s+(?:ed|edition)$|^revised edition$', re.I)
BRACKET_END = re.compile(r'(?:\[[^\[\]]*\])+$')
BRACKET = re.compile(r'\[([^\[\]]*)\]')
PAREN = re.compile(r'\(([^()]*)\)')
BY_AUTHOR = re.compile(r'^(.*?)\s+by\s+([^()\[\]]+?)\s*$', re.I)


def load_config(path):
    with open(path, 'rb') as f:
        return tomllib.load(f)


def split_name(name):
    ext = Path(name).suffix
    return (name[:-len(ext)] if ext else name), ext


def tidy(s):
    return re.sub(r'\s+', ' ', s).strip(' _.-')


def smart_case(s, cfg):
    """Only normalize uniformly uppercase/lowercase text; flag uncertain proper nouns."""
    words = re.findall(r'[A-Za-z]+', s)
    if len(words) < 2 or not (all(w.isupper() for w in words) or all(w.islower() for w in words)):
        return s, []
    acronyms = {x.casefold(): x for x in cfg['casing']['acronyms']}
    special = {x.casefold(): x for x in cfg['casing']['special_terms']}
    minor = {'and', 'or', 'of', 'the', 'to', 'for', 'in', 'with', 'a', 'an', 'on', 'by', 'from', 'at'}
    def fix(m):
        w = m.group()
        low = w.casefold()
        if low in acronyms: return acronyms[low]
        if low in special: return special[low]
        if low in minor and m.start() != 0: return low
        return w.capitalize()
    proposed = re.sub(r'[A-Za-z]+', fix, s)
    return proposed, ['CASING_REVIEW'] if cfg['casing'].get('review_unknown_proper_names', True) else []


def normalize(name, cfg):
    """Return (proposed filename, review codes). Existing fully formatted names remain byte-identical."""
    stem, ext = split_name(name)
    # Complete convention, including empty [] fields, always takes priority.
    full = re.match(r'^.+? -- .+? - .+?\[[^\[\]]*\]\[[^\[\]]*\]\[[^\[\]]*\]$', stem)
    if full or (BRACKET_END.search(stem) and len(BRACKET.findall(BRACKET_END.search(stem).group())) == 3):
        return name, []
    review = []
    if cfg['normalization'].get('convert_plus_separators') and '+' in stem:
        stem = stem.replace('+', ' ')
        review.append('SEPARATOR_REVIEW')
    # Collect trailing bracket groups, keeping any notes verbatim.
    m = BRACKET_END.search(stem)
    trailing = BRACKET.findall(m.group()) if m else []
    body = stem[:m.start()] if m else stem
    year = edition = None
    notes = []
    for b in trailing:
        if YEAR.fullmatch(b) and year is None: year = b
        elif EDITION.fullmatch(b) and edition is None: edition = b
        else: notes.append(b)
    # Consume parenthesized year/edition. Keep other parentheses in title.
    def convert(match):
        nonlocal year, edition
        val = match.group(1).strip()
        y = YEAR_AND_TEXT.fullmatch(val)
        if y and year is None:
            year = y.group(1)
            if y.group(2): notes.append(y.group(2))
            return ' '
        if EDITION.fullmatch(val) and edition is None:
            edition = val
            return ' '
        return match.group()
    body = PAREN.sub(convert, body)
    body = tidy(body)
    # Detect author expressed as trailing 'by NAME', or 'Author -- Title'.
    publisher = author = None
    title = body
    if ' -- ' in body:
        left, right = body.split(' -- ', 1)
        if ' - ' in right:
            publisher, other = left, right
            author, title = other.split(' - ', 1)
        else:
            author, title = left, right
    else:
        mb = BY_AUTHOR.fullmatch(body)
        if mb:
            title, author = mb.groups()
    if author:
        author = tidy(author)
        title = tidy(title)
        publisher = tidy(publisher) if publisher else cfg['normalization'].get('missing_publisher', 'Unknown')
        # Don't guess the capitalization of an author/publisher.
        title_case, flags = smart_case(title, cfg) if cfg['casing'].get('enabled') else (title, [])
        if flags:
            review.extend(flags)
            # Do not automatically apply uncertain case changes.
        else:
            title = title_case
        body = f'{publisher} -- {author} - {title}'
    else:
        if cfg['normalization'].get('review_missing_author', True): review.append('AUTHOR_UNKNOWN')
        candidate, flags = smart_case(body, cfg) if cfg['casing'].get('enabled') else (body, [])
        review.extend(flags)  # keep original casing if uncertain
    if len(notes) > 1:
        review.append('MULTIPLE_NOTES_REVIEW')
        # Do not destroy extra tags or collapse them into a guessed single notes field.
        return name, sorted(set(review))
    if not body: return name, ['EMPTY_TITLE']
    # If only notes supplied, fill year and edition slots without changing the notes.
    result = f'{body}[{year or ""}][{edition or ""}][{notes[0] if notes else ""}]{ext}'
    return result, sorted(set(review))


def duplicate_groups(paths):
    """Group filename-only potential duplicates without touching contents."""
    groups = defaultdict(list)
    for p in paths:
        key = re.sub(r'\s*\[dup\d+\](?=\.[^.]+$)', '', p.name, flags=re.I).casefold()
        groups[key].append(p)
    return {key: entries for key, entries in groups.items() if len(entries) > 1}
