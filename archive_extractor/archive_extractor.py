#!/usr/bin/env python3
"""Conservative book-only archive inventory and staging utility. Python >=3.11."""
from __future__ import annotations
import argparse, csv, hashlib, json, logging, os, re, shutil, subprocess, sys, tarfile, time, zipfile
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath
import tomllib

ROOT=Path(__file__).resolve().parent
BOOK={'.pdf':0,'.epub':1,'.mobi':2,'.azw3':3,'.djvu':4,'.djv':4}
AUDIO={'.mp3','.m4b','.m4a','.aac','.flac','.ogg','.wav','.wma','.opus','.aiff'}
VIDEO={'.mp4','.mkv','.avi','.mov','.wmv','.webm','.mpeg','.mpg','.m4v','.ts'}
ALLOWED_SIDE={'.txt','.nfo','.md','.opf','.ncx','.jpg','.jpeg','.png','.gif','.webp','.xml','.json','.sfv','.sha256'}
ARCHIVE_SUFFIXES=('.tar.gz','.tar.bz2','.tar.xz','.tar.zst','.tar.lzma','.tgz','.tbz2','.txz','.zip','.rar','.7z','.tar','.gz','.bz2','.xz','.zst','.lzma','.cab','.arj','.lha','.lzh')
MULTIPART_RE=re.compile(r'(?i)(\.part\d+\.rar|\.7z\.\d{3}|\.zip\.\d{3}|\.r\d{2})$')
DISPLAY={'INFO':'\033[34m','SUCCESS':'\033[32m','WARNING':'\033[33m','ERROR':'\033[31m','SHOWSTOPPER':'\033[1;31m','DEBUG':'\033[90m'}

class ArchiveIssue(Exception):
    def __init__(self,status,detail=''):
        super().__init__(detail); self.status=status; self.detail=detail

@dataclass
class Member:
    name:str
    size:int
    encrypted:bool=False
    unsafe:bool=False
    is_dir:bool=False


def archive_type(path:Path):
    n=path.name.lower()
    if MULTIPART_RE.search(n): return 'MULTIPART'
    for ext in ARCHIVE_SUFFIXES:
        if n.endswith(ext):
            if ext in ('.zip','.rar','.7z'): return ext[1:]
            if ext in ('.tar','.tgz','.tbz2','.txz') or ext.startswith('.tar.'): return 'tar'
            return 'other'
    return None

def safe_name(name):
    p=PurePosixPath(name.replace('\\','/'))
    return not (p.is_absolute() or '..' in p.parts or not p.name or '\x00' in name or re.match(r'^[A-Za-z]:',name))

def list_zip(p):
    try:
        with zipfile.ZipFile(p) as z:
            return [Member(x.filename,x.file_size,bool(x.flag_bits & 1),not safe_name(x.filename),x.is_dir()) for x in z.infolist()]
    except (zipfile.BadZipFile,OSError,EOFError) as e: raise ArchiveIssue('CORRUPT_ARCHIVE',str(e)) from e

def list_tar(p):
    try:
        with tarfile.open(p,'r:*') as t:
            return [Member(m.name,m.size,False,not safe_name(m.name) or not (m.isfile() or m.isdir()),m.isdir()) for m in t.getmembers()]
    except (tarfile.TarError,OSError,EOFError) as e: raise ArchiveIssue('CORRUPT_ARCHIVE',str(e)) from e

def list_7z(p,timeout):
    exe=shutil.which('7zz') or shutil.which('7z')
    if not exe: raise ArchiveIssue('MISSING_EXTRACTOR','Install 7zz / 7z for RAR and 7z archives')
    try:
        cp=subprocess.run([exe,'l','-slt','-p-','--',str(p)],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=timeout)
    except subprocess.TimeoutExpired: raise ArchiveIssue('TIMEOUT','Archive listing timed out')
    out=cp.stdout+'\n'+cp.stderr
    if cp.returncode:
        s='PASSWORD_REQUIRED' if re.search('password|encrypted|wrong password',out,re.I) else 'UNREADABLE_ARCHIVE'
        raise ArchiveIssue(s,out[-450:])
    # 7z technical listing contains a header record before the member records.
    if '----------' not in out:
        raise ArchiveIssue('UNREADABLE_ARCHIVE','Missing member separator in 7-Zip listing')
    segments=out.split('----------',1)[1].split('\n\n')
    members=[]
    for seg in segments:
        d={}
        for line in seg.splitlines():
            if ' = ' in line:
                k,v=line.split(' = ',1);d[k.strip()]=v.strip()
        if 'Path' not in d: continue
        name=d['Path']; size=int(d.get('Size','0') or '0')
        directory=d.get('Folder','-')=='+'
        # 7-Zip prints link keys even for regular files, with empty values.
        # Only nonempty link targets indicate actual link members.
        link=any(d.get(k, '').strip() for k in ('Symbolic Link','Hard Link','Copy Link'))
        # Windows reparse entries and other special types are never eligible.
        attrs=d.get('Attributes','')
        special=bool(re.search(r'\bReparse Point\b', attrs, re.I))
        members.append(Member(name,size,d.get('Encrypted','-')=='+',
                              not safe_name(name) or bool(link) or special,directory))
    if not members: raise ArchiveIssue('UNREADABLE_ARCHIVE','No parseable entries in technical listing')
    return members

def inspect(p,timeout):
    kind=archive_type(p)
    if kind=='zip': return list_zip(p)
    if kind=='tar': return list_tar(p)
    if kind in ('rar','7z'): return list_7z(p,timeout)
    if kind=='MULTIPART': raise ArchiveIssue('MULTIPART_REVIEW','Multipart sets require manual review in v1.0')
    raise ArchiveIssue('UNSUPPORTED_FORMAT','No validated read-only backend for this archive format')

def classify(members,config):
    files=[m for m in members if not m.is_dir]
    if not files: raise ArchiveIssue('NO_ELIGIBLE_BOOK','Archive contains no files')
    unsafe=next((m for m in members if m.unsafe),None)
    if unsafe: raise ArchiveIssue('UNSAFE_ARCHIVE',f'Unsafe path, symbolic link, or special member: {unsafe.name!r}')
    if any(m.encrypted for m in members): raise ArchiveIssue('PASSWORD_REQUIRED','Encrypted member detected')
    books=[];others=[];nonbook=[]
    for m in files:
        ext=Path(m.name).suffix.lower()
        if ext in BOOK: books.append(m)
        elif ext in AUDIO or ext in VIDEO: others.append(m.name)
        elif ext in ALLOWED_SIDE: nonbook.append(m.name)
        else: others.append(m.name)
    if others:
        raise ArchiveIssue('SKIPPED_MIXED_CONTENT' if books else 'SKIPPED_NON_BOOK', 'Disallowed members: '+', '.join(others))
    if not books: raise ArchiveIssue('NO_ELIGIBLE_BOOK','Text/supporting files alone do not qualify')
    maxfiles=config['verification']['max_members']
    if len(members)>maxfiles: raise ArchiveIssue('LIMIT_EXCEEDED',f'{len(members)} members > {maxfiles}')
    maxsize=config['verification']['max_book_bytes']
    if any(m.size>maxsize for m in books): raise ArchiveIssue('LIMIT_EXCEEDED','Book exceeds configured size limit')
    return min(books,key=lambda m:(BOOK[Path(m.name).suffix.lower()],m.name.casefold()))

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

def extract_to(p,member,dest,timeout):
    kind=archive_type(p)
    if kind=='zip':
        with zipfile.ZipFile(p) as z, z.open(member.name,'r') as inp, dest.open('xb') as out: shutil.copyfileobj(inp,out)
    elif kind=='tar':
        with tarfile.open(p,'r:*') as t:
            m=t.getmember(member.name)
            if not m.isfile(): raise ArchiveIssue('UNSAFE_ARCHIVE','Not a regular file')
            inp=t.extractfile(m)
            if inp is None: raise ArchiveIssue('EXTRACTION_FAILED','Cannot open member')
            with inp, dest.open('xb') as out: shutil.copyfileobj(inp,out)
    else:
        exe=shutil.which('7zz') or shutil.which('7z')
        if not exe: raise ArchiveIssue('MISSING_EXTRACTOR','7zz not installed')
        # Stream only the selected member; noninteractive stdin and password disabled.
        with dest.open('xb') as f:
            try:
                cp=subprocess.run([exe,'x','-so','-p-','--',str(p),member.name],stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.PIPE,timeout=timeout)
            except subprocess.TimeoutExpired: raise ArchiveIssue('TIMEOUT','Extraction timed out')
        if cp.returncode: raise ArchiveIssue('EXTRACTION_FAILED',cp.stderr.decode(errors='replace')[-450:])

def check_signature(path):
    ext=path.suffix.lower()
    with path.open('rb') as f:head=f.read(32)
    if ext=='.pdf':return head.startswith(b'%PDF-')
    if ext=='.epub':return zipfile.is_zipfile(path) and 'mimetype' in zipfile.ZipFile(path).namelist()
    if ext in ('.djvu','.djv'):return head.startswith(b'AT&TFORM')
    # MOBI/AZW3 signatures occur deeper; validate minimum size; no false claim of full format validation.
    if ext in ('.mobi','.azw3'):return path.stat().st_size>=80
    return False

def stage(p,member,out,timeout):
    out.mkdir(parents=True,exist_ok=True)
    stem=Path(member.name).stem;ext=Path(member.name).suffix.lower()
    if not stem or stem in ('.','..'):raise ArchiveIssue('INVALID_MEMBER_NAME','Invalid selected name')
    # Never trust path components from the archive: use basename only.
    stem=Path(member.name).stem
    name=f'{stem}{ext}'; i=2
    while (out/name).exists(): name=f'{stem} [dup{i}]{ext}';i+=1
    temp=out/(f'.archive-stage-{os.getpid()}-{time.time_ns()}.part')
    try:
        extract_to(p,member,temp,timeout)
        if temp.stat().st_size!=member.size: raise ArchiveIssue('VERIFICATION_FAILED',f'Size mismatch: expected {member.size}, got {temp.stat().st_size}')
        # Signature validated against bytes of the temp file, using expected extension.
        if not check_signature_as(temp,ext): raise ArchiveIssue('INVALID_BOOK_FILE','Invalid or unsupported book file signature')
        digest=sha(temp)
        # No-clobber final publishing (hardlink), works within output directory.
        target=out/name
        while True:
            try: os.link(temp,target);break
            except FileExistsError:
                name=f'{stem} [dup{i}]{ext}';i+=1;target=out/name
        return str(target),digest
    finally:
        temp.unlink(missing_ok=True)

def check_signature_as(path,ext):
    with path.open('rb') as f:
        head=f.read(80)
    if ext=='.pdf':return head.startswith(b'%PDF-')
    if ext=='.epub':
        try:
            with zipfile.ZipFile(path) as z:return z.read('mimetype')==b'application/epub+zip'
        except (zipfile.BadZipFile,KeyError,RuntimeError):return False
    if ext in ('.djv','.djvu'):return head.startswith(b'AT&TFORM')
    if ext in ('.mobi','.azw3'):
        with path.open('rb') as f:
            f.seek(60);return f.read(8) in (b'BOOKMOBI',b'TEXtREAd')
    return False

def extension_of(path):
    """Use compound archive suffixes as a single extension for inventory."""
    name=path.name.lower()
    for suffix in sorted(ARCHIVE_SUFFIXES,key=len,reverse=True):
        if name.endswith(suffix): return suffix
    if MULTIPART_RE.search(name):
        return '.multipart'
    return path.suffix.lower() or '[no extension]'


def pre_run_inventory(directory, out, logs_dir):
    """Read-only count of directory entries, excluding staging and project logs."""
    exts=Counter(); groups=Counter(); bytes_total=0; dirs_total=0; files_total=0
    for root, dirs, files in os.walk(directory):
        dirs[:]=[d for d in dirs if not d.startswith('.') and not (Path(root)/d).is_symlink()
                 and (Path(root)/d).resolve() not in (out,logs_dir)]
        dirs_total+=len(dirs)
        for name in files:
            if name.startswith('.'): continue
            p=Path(root)/name
            if p.is_symlink() or not p.is_file():continue
            try: size=p.stat().st_size
            except OSError:continue
            files_total+=1;bytes_total+=size
            ext=extension_of(p);exts[ext]+=1
            if archive_type(p):group='archives'
            elif p.suffix.lower() in BOOK:group='books'
            elif p.suffix.lower() in AUDIO:group='audio'
            elif p.suffix.lower() in VIDEO:group='video'
            else:group='other'
            groups[group]+=1
    return {'directories':dirs_total,'total_files':files_total,'total_bytes':bytes_total,
            'categories':dict(groups),'extensions':dict(sorted(exts.items()))}


def format_pre_run_dashboard(inventory, directory, mode, color=False):
    """Readable, width-stable pre-run inventory; optional ANSI only for terminals."""
    codes={'title':'\033[1;96m','heading':'\033[1;94m','archive':'\033[94m',
           'book':'\033[92m','warn':'\033[93m','label':'\033[2m'}
    def styled(value, kind):
        return f"{codes[kind]}{value}\033[0m" if color else value
    def line():return '─'*60
    def metric(label,value):return f"  {label:<24} {value:>18}"
    groups=inventory['categories']; extensions=inventory['extensions']
    archive_exts=[];book_exts=[];other_exts=[]
    for ext,count in extensions.items():
        if ext in ARCHIVE_SUFFIXES or ext=='.multipart': archive_exts.append((ext,count))
        elif ext in BOOK:book_exts.append((ext,count))
        else:other_exts.append((ext,count))
    result=['',styled('  ARCHIVE EXTRACTOR  |  PHASE 0 — PRE-RUN INVENTORY','title'),
            styled('  '+line(),'label'),f'  Directory : {directory}',f'  Mode      : {mode}',
            '',styled('  OVERVIEW','heading'),
            metric('Total files',f"{inventory['total_files']:,}"),
            metric('Directories',f"{inventory['directories']:,}"),
            metric('Archive files',f"{groups.get('archives',0):,}"),
            metric('Book files (on disk)',f"{groups.get('books',0):,}"),
            metric('Other files',f"{sum(v for k,v in groups.items() if k not in ('books','archives')):,}"),
            metric('Total size',f"{inventory['total_bytes']/1024**3:,.2f} GiB"),
            metric('Scan time',f"{inventory['scan_duration_seconds']:.3f} s")]
    for title,rows,kind in [('ARCHIVE FORMATS',archive_exts,'archive'),
                             ('BOOK FORMATS',book_exts,'book'),
                             ('OTHER FILE TYPES',other_exts,'warn')]:
        if not rows:continue
        result.extend(['',styled('  '+title,'heading'),styled('  '+line(),'label')])
        for ext,count in sorted(rows,key=lambda row:(-row[1],row[0])):
            result.append(f"  {styled(ext,kind):<0}"+f"{' ' * max(1,26-len(ext))}{count:>12,}")
    result.extend(['',styled('  '+line(),'label'),
                   styled('  Inventory complete • counts exclude archive contents','book'), ''])
    return '\n'.join(result)


def write_pre_inventory(data,logs):
    (logs/'pre_run_inventory.json').write_text(json.dumps(data,indent=2)+'\n',encoding='utf8')
    with (logs/'pre_run_inventory.csv').open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.writer(f);writer.writerow(['extension','file_count'])
        writer.writerows(sorted(data['extensions'].items()))


def format_issue(detail, max_files=5):
    """Summarize huge disallowed-member lists without truncating the persisted log."""
    prefix='Disallowed members: '
    if not detail.startswith(prefix):return detail
    names=detail[len(prefix):].split(', ')
    shown=names[:max_files]
    suffix=f'\n    ... and {len(names)-len(shown)} more (full list in logs)' if len(names)>len(shown) else ''
    return f'{len(names)} disallowed member(s):\n'+''.join(f'    - {name}\n' for name in shown).rstrip('\n')+suffix


def log_line(logfile,jsonfile,level,msg,context,color,console_message=None):
    ts=datetime.now().astimezone().isoformat(timespec='seconds')
    record={'timestamp':ts,'level':level,'message':msg,**context}
    with logfile.open('a',encoding='utf8') as f:f.write(f'{ts} [{level}] {msg}\n')
    with jsonfile.open('a',encoding='utf8') as f:f.write(json.dumps(record,ensure_ascii=False)+'\n')
    prefix=DISPLAY.get(level,'') if color else ''
    print(f'{prefix}[{level}] {console_message if console_message is not None else msg}{chr(27)+"[0m" if prefix else ""}')

def run(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('directory',type=Path,help='Directory to recursively scan')
    ap.add_argument('--config',type=Path,default=ROOT/'archive_config.toml')
    ap.add_argument('--stage',action='store_true',help='Actually stage eligible books (default is dry run)')
    ap.add_argument('--no-color',action='store_true')
    ap.add_argument('--verbose',action='store_true')
    ap.add_argument('--inventory-only',action='store_true',help='Count files without archive inspection or staging')
    args=ap.parse_args(argv)
    start=datetime.now().astimezone();tick=time.monotonic()
    runid=start.strftime('%Y-%b-%d_%H-%M-%S')
    try:
        with args.config.open('rb') as f:config=tomllib.load(f)
        assert config['books']['priority']==['pdf','epub','mobi','azw3','djvu'], 'Book format priority is invalid'
        assert config['filtering']['skip_mixed_content'] is True
        directory=args.directory.expanduser().resolve(strict=True)
        assert directory.is_dir()
    except (OSError,ValueError,KeyError,AssertionError) as e:
        print(f'[SHOWSTOPPER] Configuration or input invalid: {e}',file=sys.stderr);return 2
    logs=ROOT/'logs'/runid
    try:logs.mkdir(parents=True,exist_ok=False)
    except FileExistsError:logs=ROOT/'logs'/(runid+f'-{os.getpid()}');logs.mkdir(parents=True)
    logfile=logs/'archive_extractor.log';jsonfile=logs/'archive_extractor.jsonl'
    emit=lambda level,msg,console_message=None,**ctx:log_line(logfile,jsonfile,level,msg,ctx,not args.no_color and 'NO_COLOR' not in os.environ and config.get('logging',{}).get('console_colors',True) and sys.stdout.isatty(),console_message)
    timeout=config['verification']['timeout_seconds']
    out=(directory/config['general']['stage_directory']).resolve()
    if not out.is_relative_to(directory) or out==directory:
        emit('SHOWSTOPPER','Unsafe stage_directory configuration');return 2
    mode='INVENTORY_ONLY' if args.inventory_only else ('STAGE' if args.stage else 'DRY_RUN')
    emit('INFO',f'Run {runid} started {start.isoformat()}, mode={mode}')
    inv_start=time.monotonic()
    inventory=pre_run_inventory(directory,out,ROOT/'logs')
    inventory['scan_duration_seconds']=round(time.monotonic()-inv_start,3)
    write_pre_inventory(inventory,logs)
    console_color=(not args.no_color and 'NO_COLOR' not in os.environ
                   and config.get('logging',{}).get('console_colors',True)
                   and sys.stdout.isatty())
    print(format_pre_run_dashboard(inventory,directory,mode,color=console_color))
    emit('INFO','Pre-run inventory complete', inventory=inventory)
    if args.inventory_only:
        end=datetime.now().astimezone();elapsed=round(time.monotonic()-tick,3)
        summary={'run_id':runid,'mode':mode,'start':start.isoformat(),'end':end.isoformat(),
                 'elapsed_seconds':elapsed,'inventory':inventory,'logs':str(logs)}
        (logs/'run_summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf8')
        emit('INFO',f'Inventory-only complete | elapsed {elapsed:.3f}s | Reports: {logs}')
        return 0
    rows=[];counts=Counter()
    paths=[]
    for root,dirs,files in os.walk(directory):
        dirs[:]=[d for d in dirs if not d.startswith('.') and (Path(root)/d).resolve()!=out and (Path(root)/d).resolve()!=ROOT/'logs']
        for name in files:
            if name.startswith('.'):continue
            p=Path(root)/name
            if p.is_symlink():continue
            if archive_type(p):paths.append(p)
    for idx,p in enumerate(sorted(paths),1):
        t0=time.monotonic()
        row={'archive':str(p),'status':'','reason':'','selected_member':'','output':'','sha256':'','duration_s':'','member_count':0}
        try:
            members=inspect(p,timeout);row['member_count']=len(members)
            selected=classify(members,config);row['selected_member']=selected.name
            if args.stage:
                result,digest=stage(p,selected,out,timeout)
                row['output']=result;row['sha256']=digest;status='STAGED'
            else:status='ELIGIBLE_DRY_RUN'
            print()
            emit('SUCCESS',f'{idx}/{len(paths)} {p.name}: {status}: {selected.name}')
        except ArchiveIssue as e:
            status=e.status;row['reason']=e.detail
            print()
            emit('WARNING',f'{idx}/{len(paths)} {p.name}: {status}: {e.detail}', console_message=f'{idx}/{len(paths)} {p.name}\n  Status: {status}\n  Reason: {format_issue(e.detail, config.get("display",{}).get("max_offending_files",5))}\n  Action: Skipped; original unchanged')
        except (OSError,zipfile.BadZipFile,tarfile.TarError,RuntimeError,subprocess.SubprocessError) as e:
            status='ERROR';row['reason']=str(e);print();emit('ERROR',f'{idx}/{len(paths)} {p.name}: {str(e)}')
        row['status']=status;row['duration_s']=round(time.monotonic()-t0,3);counts[status]+=1;rows.append(row)
    fields=['archive','status','reason','selected_member','output','sha256','duration_s','member_count']
    with (logs/'inventory.csv').open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(rows)
    with (logs/'errors.csv').open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(r for r in rows if r['status'] not in ('STAGED','ELIGIBLE_DRY_RUN'))
    try:
        from openpyxl import Workbook
        wb=Workbook();ws=wb.active;ws.title='Inventory';ws.append(fields)
        for r in rows:ws.append([r[k] for k in fields])
        wb.save(logs/'inventory.xlsx')
    except ImportError:emit('WARNING','Excel output unavailable; install openpyxl (CSV always generated)')
    end=datetime.now().astimezone();elapsed=round(time.monotonic()-tick,3)
    summary={'run_id':runid,'mode':'STAGE' if args.stage else 'DRY_RUN','start':start.isoformat(),'end':end.isoformat(),'elapsed_seconds':elapsed,'archive_count':len(paths),'pre_run_inventory':inventory,'counts':dict(counts),'logs':str(logs),'config':str(args.config)}
    (logs/'run_summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf8')
    emit('INFO',f'Finished {end.isoformat()} | elapsed {elapsed:.3f}s | archives {len(paths)} | results {dict(counts)}')
    emit('INFO',f'Reports: {logs}')
    return 1 if counts['ERROR'] else 0

if __name__=='__main__':sys.exit(run())
