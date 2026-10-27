import unittest
from filename_normalize import load_config, normalize, sanitize
from pathlib import Path
CFG = load_config(Path(__file__).resolve().parents[1] / 'filename_config.toml')

class Version221Tests(unittest.TestCase):
    def test_unclosed_year(self):
        name, review = normalize('tantra dev - mahavidyas (2020.pdf', CFG)
        self.assertEqual(name, 'tantra dev - mahavidyas [2020][][].pdf')
        self.assertIn('AUTHOR_UNKNOWN', review)
        self.assertIn('CASING_REVIEW', review)
    def test_slug_proposed_not_safe_to_apply(self):
        name, review = sanitize('devops-for-trustworthy-smart-iot-systems.pdf', CFG)
        self.assertEqual(name, 'devops for trustworthy smart iot systems.pdf')
        self.assertIn('SANITIZATION_REVIEW', review)
    def test_plus(self):
        self.assertEqual(sanitize('Python+Programming+Guide.epub', CFG), ('Python Programming Guide.epub', []))
    def test_curated(self):
        x = 'Red Wheel Weiser -- Author - Book [2026][][].pdf'
        self.assertEqual(sanitize(x, CFG), (x, []))
    def test_isbn(self):
        self.assertEqual(sanitize('978-3-032-24372-0.pdf', CFG)[0], '978-3-032-24372-0.pdf')
    def test_hyphen_name(self):
        self.assertEqual(sanitize('Jean-Paul Sartre.pdf', CFG)[0], 'Jean-Paul Sartre.pdf')

if __name__ == '__main__': unittest.main()
