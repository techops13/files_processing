import sys, tempfile, unittest, zipfile, tarfile, io
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import archive_extractor as a
C={'verification':{'max_members':100,'max_book_bytes':100000}}
class ArchiveTests(unittest.TestCase):
    def test_real_rar5_technical_listing(self):
        from unittest.mock import patch
        from subprocess import CompletedProcess
        listing = """Path = /Users/example/Downloads/978-3-032-24372-0.rar
Type = Rar5
Encrypted = -

----------
Path = 978-3-032-24372-0.epub
Folder = -
Size = 21967726
Attributes = A
Encrypted = -
Symbolic Link = 
Hard Link = 
Copy Link = 

Path = 978-3-032-24372-0.pdf
Folder = -
Size = 22795147
Attributes = A
Encrypted = -
Symbolic Link = 
Hard Link = 
Copy Link = 
"""
        with patch.object(a.shutil, 'which', return_value='/usr/bin/7zz'), patch.object(a.subprocess,'run',return_value=CompletedProcess([],0,listing,'')):
            members=a.list_7z(Path('books.rar'), 5)
        self.assertEqual(len(members), 2)
        self.assertTrue(all(not x.unsafe for x in members))
        self.assertEqual(a.classify(members,{'verification':{'max_members':100,'max_book_bytes':100000000}}).name,'978-3-032-24372-0.pdf')

    def test_7z_rejects_actual_links_and_unsafe_path(self):
        from unittest.mock import patch
        from subprocess import CompletedProcess
        for path, link in [('book.pdf','/etc/passwd'),('../../book.pdf','')]:
            listing=f'Path = test.rar\nType = Rar5\n\n----------\nPath = {path}\nSize = 5\nFolder = -\nSymbolic Link = {link}\n\n'
            with patch.object(a.shutil,'which',return_value='/usr/bin/7zz'), patch.object(a.subprocess,'run',return_value=CompletedProcess([],0,listing,'')):
                members=a.list_7z(Path('books.rar'),5)
            self.assertTrue(members[0].unsafe)
            with self.assertRaises(a.ArchiveIssue) as ctx:a.classify(members,C)
            self.assertEqual(ctx.exception.status,'UNSAFE_ARCHIVE')
            self.assertIn(path,ctx.exception.detail)

    def test_priority(self):
        items=[a.Member('b.djvu',10),a.Member('b.azw3',10),a.Member('b.mobi',10),a.Member('b.epub',10),a.Member('b.pdf',10)]
        self.assertEqual(a.classify(items,C).name,'b.pdf')
    def test_mixed_audio(self):
        with self.assertRaises(a.ArchiveIssue) as ctx:a.classify([a.Member('a.pdf',4),a.Member('x.mp3',2)],C)
        self.assertEqual(ctx.exception.status,'SKIPPED_MIXED_CONTENT')
    def test_unknown(self):
        with self.assertRaises(a.ArchiveIssue):a.classify([a.Member('a.pdf',4),a.Member('setup.exe',2)],C)
    def test_text_only(self):
        with self.assertRaises(a.ArchiveIssue):a.classify([a.Member('notes.txt',2)],C)
    def test_unsafe(self):
        self.assertFalse(a.safe_name('../../something.pdf'))
        self.assertFalse(a.safe_name('/tmp/file.pdf'))
        self.assertFalse(a.safe_name('C:\\Windows\\file.pdf'))
    def test_zip_stage_collision(self):
        with tempfile.TemporaryDirectory() as td:
            td=Path(td);p=td/'a.zip';out=td/'pipeline_input';out.mkdir();(out/'x.pdf').write_bytes(b'old')
            with zipfile.ZipFile(p,'w') as z:z.writestr('x.pdf',b'%PDF-1.4\nhello')
            selected=a.classify(a.list_zip(p),C)
            dest,digest=a.stage(p,selected,out,5)
            self.assertEqual(Path(dest).name,'x [dup2].pdf')
            self.assertEqual((out/'x.pdf').read_bytes(),b'old')
            self.assertEqual(len(digest),64)
    def test_reject_invalid_signature(self):
        with tempfile.TemporaryDirectory() as td:
            td=Path(td);p=td/'a.zip';out=td/'stage'
            with zipfile.ZipFile(p,'w') as z:z.writestr('fake.pdf',b'fake')
            selected=a.classify(a.list_zip(p),C)
            with self.assertRaises(a.ArchiveIssue):a.stage(p,selected,out,5)
            self.assertFalse(list(out.glob('*.pdf')))
    def test_tar_unsafe_link(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'a.tar'
            with tarfile.open(p,'w') as t:
                f=tarfile.TarInfo('x.pdf');content=b'%PDF-1.4';f.size=len(content);t.addfile(f,io.BytesIO(content))
                f=tarfile.TarInfo('lnk');f.type=tarfile.SYMTYPE;f.linkname='/tmp/wrong';t.addfile(f)
            with self.assertRaises(a.ArchiveIssue):a.classify(a.list_tar(p),C)
if __name__=='__main__':unittest.main()
