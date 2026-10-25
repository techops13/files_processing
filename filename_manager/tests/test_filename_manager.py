import argparse
import unittest

from filename_manager import transformed


def args(action, find=None, with_text=None, case='sensitive'):
    return argparse.Namespace(action=action, find=find, with_text=with_text,
                              case=case)


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

    def test_universal_cleanup_remove_even_if_no_match(self):
        self.assertEqual(transformed(' _-Book +_.pdf', args('remove', 'missing')), 'Book.pdf')

    def test_universal_cleanup_replace(self):
        self.assertEqual(transformed('._old_name-..zip', args('replace', 'old', 'new')), 'new_name.zip')

    def test_universal_cleanup_prefix(self):
        self.assertEqual(transformed('..Book__.epub', args('prefix', with_text='!Prefix_')), 'Prefix_..Book.epub')

    def test_universal_cleanup_suffix(self):
        self.assertEqual(transformed('_Book_.tar.gz', args('suffix', with_text='__')), 'Book.tar.gz')

    def test_replace(self):
        self.assertEqual(transformed('old_name.zip', args('replace', 'old', 'new')), 'new_name.zip')

    def test_case_insensitive(self):
        self.assertEqual(transformed('PREFIX_Book.epub', args('remove', 'prefix_', case='insensitive')), 'Book.epub')

    def test_suffix_compound_extension(self):
        self.assertEqual(transformed('backup.tar.gz', args('suffix', with_text='_v2')), 'backup_v2.tar.gz')

    def test_empty_stem_rejected(self):
        self.assertIsNone(transformed('remove.pdf', args('remove', 'remove')))

    def test_leading_bracket_year(self):
        self.assertEqual(transformed('[2026]Book.pdf', args('remove', 'missing')), 'Book [2026].pdf')

    def test_multiple_leading_groups(self):
        self.assertEqual(transformed('[2026][2nd Edition]Book.pdf', args('remove', 'missing')), 'Book [2026] [2nd Edition].pdf')

    def test_metadata_at_both_ends(self):
        self.assertEqual(transformed('[2026] Publisher -- Book [3rd Edition].pdf', args('remove', 'missing')),
                         'Publisher -- Book [3rd Edition] [2026].pdf')

    def test_underscore_around_groups(self):
        self.assertEqual(transformed('_[2026]_My_Book_.pdf', args('remove', 'missing')), 'My_Book [2026].pdf')

    def test_trailing_brackets_and_empty_pair(self):
        self.assertEqual(transformed('Book [2026] [dup2]_.pdf', args('remove', 'missing')), 'Book [2026] [dup2].pdf')
        self.assertEqual(transformed('Book [].pdf', args('remove', 'missing')), 'Book [].pdf')

    def test_no_leading_brackets_when_filename_is_valid(self):
        self.assertEqual(transformed('[dup2]Book.pdf', args('prefix', with_text='')),
                         'Book [dup2].pdf')


if __name__ == '__main__':
    unittest.main()

class DuplicateNamingTests(unittest.TestCase):
    def test_duplicate_sequence(self):
        from filename_manager import duplicate_name
        self.assertEqual(duplicate_name('1.epub', 2), '1 [dup2].epub')
        self.assertEqual(duplicate_name('backup.tar.gz', 3), 'backup [dup3].tar.gz')
