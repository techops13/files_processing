import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from filename_normalize import is_archive_filename, load_config, normalize, sanitize
from filename_manager import main

ROOT = Path(__file__).resolve().parents[1]
CONFIG = load_config(ROOT / 'filename_config.toml')

class Version222Tests(unittest.TestCase):
    def test_spaced_metadata(self):
        name='Wiley -- Blake Rayfield - Applied Math with Python [2026] [1st Edition] [].pdf'
        expected='Wiley -- Blake Rayfield - Applied Math with Python [2026][1st Edition][].pdf'
        actual,_=normalize(name,CONFIG)
        self.assertEqual(actual,expected)
        self.assertEqual(normalize(actual,CONFIG)[0],actual)
    def test_multiple_spaces(self):
        self.assertEqual(normalize('Book [2026]  [1st Edition]  [Must Read].pdf',CONFIG)[0], 'Book [2026][1st Edition][Must Read].pdf')
    def test_adjacent_unchanged(self):
        name='Book [2026][1st Ed][].epub'
        self.assertEqual(normalize(name,CONFIG)[0],name)
    def test_archive_types(self):
        for name in ('a.rar','a.RAR','a.zip','a.7z','a.tar.gz','a.tar.xz','a.cab','a.arj','a.part1.rar','a.part00004.rar','a.7z.001','a.zip.002','a.r00','a.z01'):
            with self.subTest(name=name):
                self.assertTrue(is_archive_filename(name))
                self.assertEqual(normalize(name,CONFIG)[0],name)
                self.assertEqual(sanitize(name,CONFIG)[0],name)
    def test_non_archives(self):
        for name in ('book.pdf','book.epub','book.azw3','book.djvu'):
            self.assertFalse(is_archive_filename(name))
    def test_all_actions_skip_archives(self):
        import sys
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            archive=root/'book.part1.rar';archive.write_text('fake')
            book=root/'book.pdf';book.write_text('book')
            for action,args in [('remove',['--find','book']),('replace',['--find','book','--with-text','new']),('prefix',['--with-text','abc']),('suffix',['--with-text','abc']),('normalize',[]),('sanitize',[])]:
                with self.subTest(action=action),patch.object(sys,'argv',['filename_manager.py',str(root),'--action',action,*args,'--apply','--log-dir',str(root/'logs')]):
                    main()
                    self.assertTrue(archive.exists())
