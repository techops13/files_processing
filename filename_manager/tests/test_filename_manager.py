import argparse
import unittest

from filename_manager import transformed


def args(action, find=None, with_text=None, case='sensitive', keep_leading_symbols=False):
    return argparse.Namespace(action=action, find=find, with_text=with_text,
                              case=case, keep_leading_symbols=keep_leading_symbols)


class FilenameManagerTests(unittest.TestCase):
    def test_remove_and_trim(self):
        self.assertEqual(transformed('filanem.st_978-3-032-24372-0.rar', args('remove', 'filanem.st')),
                         '978-3-032-24372-0.rar')

    def test_trailing_dots_after_remove(self):
        self.assertEqual(transformed('979-8-8688-2083-0.filename.tt.pdf', args('remove', 'filename.tt')),
                         '979-8-8688-2083-0.pdf')

    def test_edges_preserve_internal_hyphens(self):
        self.assertEqual(transformed('_.A-B+_.pdf', args('remove', 'not-found')),
                         'A-B.pdf')

    def test_all_symbols_empty_stem(self):
        self.assertIsNone(transformed('...__.pdf', args('remove', 'not-found')))

    def test_keep_symbols(self):
        self.assertEqual(transformed('filanem.st_ABC.pdf', args('remove', 'filanem.st', keep_leading_symbols=True)),
                         '_ABC.pdf')

    def test_replace(self):
        self.assertEqual(transformed('old_name.zip', args('replace', 'old', 'new')), 'new_name.zip')

    def test_case_insensitive(self):
        self.assertEqual(transformed('PREFIX_Book.epub', args('remove', 'prefix_', case='insensitive')), 'Book.epub')

    def test_suffix_compound_extension(self):
        self.assertEqual(transformed('backup.tar.gz', args('suffix', with_text='_v2')), 'backup_v2.tar.gz')

    def test_empty_stem_rejected(self):
        self.assertIsNone(transformed('remove.pdf', args('remove', 'remove')))


if __name__ == '__main__':
    unittest.main()

class DuplicateNamingTests(unittest.TestCase):
    def test_duplicate_sequence(self):
        from filename_manager import duplicate_name
        self.assertEqual(duplicate_name('1.epub', 2), '1 [dup2].epub')
        self.assertEqual(duplicate_name('backup.tar.gz', 3), 'backup [dup3].tar.gz')
