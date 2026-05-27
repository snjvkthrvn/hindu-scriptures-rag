import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "rag"))

from text_normalization import build_sparse_text, lexical_aliases


class TextNormalizationTests(unittest.TestCase):
    def test_iast_aliases_include_plain_and_common_ascii(self):
        aliases = lexical_aliases("k\u1e5b\u1e63\u1e47a \u015biva mok\u1e63a \u0101tman")

        self.assertIn("krsna siva moksa atman", aliases)
        self.assertIn("krishna shiva moksha atman", aliases)

    def test_devanagari_aliases_include_iast_and_common_ascii(self):
        aliases = lexical_aliases("\u0915\u0943\u0937\u094d\u0923 \u0936\u093f\u0935")

        self.assertIn("k\u1e5b\u1e63\u1e47a \u015biva", aliases)
        self.assertIn("krsna siva", aliases)
        self.assertIn("krishna shiva", aliases)

    def test_build_sparse_text_preserves_raw_and_adds_aliases(self):
        text = build_sparse_text(["\u092e\u094b\u0915\u094d\u0937", "mok\u1e63a"])

        self.assertIn("\u092e\u094b\u0915\u094d\u0937", text)
        self.assertIn("mok\u1e63a", text)
        self.assertIn("moksa", text)
        self.assertIn("moksha", text)


if __name__ == "__main__":
    unittest.main()
