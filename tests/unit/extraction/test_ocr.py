from __future__ import annotations

import unittest

from faro.extraction.ocr import parse_tesseract_tsv


TSV = """level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext
5\t1\t1\t1\t1\t1\t10\t20\t100\t30\t96.0\tFACTURA
5\t1\t1\t1\t1\t2\t120\t20\t50\t30\t84.0\t1001
"""


class TesseractTsvTests(unittest.TestCase):
    def test_parses_text_confidence_and_boxes(self) -> None:
        text, confidence, evidence = parse_tesseract_tsv(TSV)
        self.assertEqual(text, "FACTURA 1001")
        self.assertAlmostEqual(confidence or 0, 0.90)
        self.assertEqual(len(evidence), 2)
        self.assertEqual(evidence[0].bounding_box.width, 100)


if __name__ == "__main__":
    unittest.main()
