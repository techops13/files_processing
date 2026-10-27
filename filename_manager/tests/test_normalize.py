import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from filename_normalize import normalize, load_config, duplicate_groups

CFG = load_config(Path(__file__).resolve().parents[1] / 'filename_config.toml')

class NormalizationTests(unittest.TestCase):
    def test_valid_full_name_unchanged(self):
        s='Published independently -- Colett, Maverick - Mastering Claude AI [2026][1st Ed][].pdf'
        self.assertEqual(normalize(s, CFG)[0], s)
    def test_author_year_edition(self):
        s='Rebel Code Linux and the Open Source Revolution (1st Edition) by Glyn Moody (2002).epub'
        self.assertEqual(normalize(s, CFG)[0], 'Unknown -- Glyn Moody - Rebel Code Linux and the Open Source Revolution[2002][1st Edition][].epub')
    def test_notes_preserved(self):
        self.assertEqual(normalize('Recursion Mathematics and Python [Must Refer].pdf', CFG)[0], 'Recursion Mathematics and Python[][][Must Refer].pdf')
    def test_author_title_and_notes(self):
        s='Patricia B. McConnell -- The Other End of the Leash[2003][Must Read Book].epub'
        self.assertEqual(normalize(s, CFG)[0], 'Unknown -- Patricia B. McConnell - The Other End of the Leash[2003][][Must Read Book].epub')
    def test_plus_review(self):
        result, issues = normalize('Polyamorous+Advice+You+Won+t.epub', CFG)
        self.assertIn('SEPARATOR_REVIEW', issues)
        self.assertIn('Polyamorous Advice', result)
    def test_uppercase_review(self):
        result, flags = normalize('MACHINE LEARNING WITH PYTHON.epub', CFG)
        self.assertIn('CASING_REVIEW', flags)
        self.assertEqual(result, 'MACHINE LEARNING WITH PYTHON[][][].epub')
    def test_duplicates(self):
        with TemporaryDirectory() as d:
            files=[Path(d)/'Book.pdf',Path(d)/'book [dup2].pdf']
            self.assertEqual(len(duplicate_groups(files)), 1)

if __name__ == '__main__': unittest.main()
