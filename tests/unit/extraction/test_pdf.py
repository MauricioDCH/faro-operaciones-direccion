from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from faro.extraction.errors import UnsupportedPdfError
from faro.extraction.pdf import NativeTextPolicy, PdfInspector, PdfPageReader
from tests.fixtures.pdf.builders import create_multi_page_pdf, create_native_pdf


class NativeTextPolicyTests(unittest.TestCase):
    def test_requires_words_and_alphanumeric_characters(self) -> None:
        policy = NativeTextPolicy(min_characters=20, min_words=4)
        self.assertTrue(policy.is_sufficient("FACTURA FV 1001 TOTAL 50000 COP"))
        self.assertFalse(policy.is_sufficient("FACTURA"))


class PdfInspectorTests(unittest.TestCase):
    def test_rejects_document_above_page_limit(self) -> None:
        with TemporaryDirectory() as directory:
            path = create_multi_page_pdf(Path(directory) / "long.pdf", 4)
            with self.assertRaises(UnsupportedPdfError):
                PdfInspector(max_pages=3).inspect(path)

    def test_reads_native_text_from_one_page_pdf(self) -> None:
        with TemporaryDirectory() as directory:
            path = create_native_pdf(
                Path(directory) / "invoice.pdf",
                ("FACTURA DE VENTA", "Numero FV-1001", "TOTAL 100000 COP"),
            )
            metadata = PdfInspector(max_pages=3).inspect(path)
            text = PdfPageReader().native_text(path, 1)
            self.assertEqual(metadata.page_count, 1)
            self.assertIn("FACTURA DE VENTA", text)


if __name__ == "__main__":
    unittest.main()
