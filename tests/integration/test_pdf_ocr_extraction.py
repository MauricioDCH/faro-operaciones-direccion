from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from faro.domain.documents import (
    DocumentType,
    PageExtractionMethod,
    ProcessingStatus,
)
from faro.extraction.ocr import TesseractOcrEngine
from faro.extraction.service import PdfExtractionService
from faro.provenance.models import sha256_file
from tests.fixtures.pdf.builders import create_mixed_pdf, create_scanned_pdf


class PdfOcrIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = TesseractOcrEngine(language="spa")
        cls.runtime = cls.engine.runtime_info

    def test_missing_tesseract_is_reported_without_invented_text(self) -> None:
        with TemporaryDirectory() as directory:
            path = create_scanned_pdf(
                Path(directory) / "invoice.pdf",
                (
                    "FACTURA DE VENTA",
                    "Numero de factura FV-1001",
                    "TOTAL 743750 COP",
                ),
            )
            missing = TesseractOcrEngine(command="missing-faro-tesseract")
            result = PdfExtractionService(ocr_engine=missing).extract(path)

            self.assertEqual(result.pages[0].processing_status, ProcessingStatus.ERROR)
            self.assertEqual(result.pages[0].error_code, "ocr_runtime_error")
            self.assertEqual(result.pages[0].page_text, "")
            self.assertEqual(result.document_type, DocumentType.UNSUPPORTED)

    def test_scanned_quotation_uses_real_ocr(self) -> None:
        if not self.runtime.available:
            self.skipTest(self.runtime.error or "Tesseract spa runtime unavailable")

        with TemporaryDirectory() as directory:
            path = create_scanned_pdf(
                Path(directory) / "quotation.pdf",
                (
                    "COTIZACION DE PROVEEDOR",
                    "Numero de cotizacion COT-2026-041",
                    "Proveedor Distribuciones Faro SAS",
                    "TOTAL 743750 COP",
                ),
            )
            before = sha256_file(path)
            result = PdfExtractionService(
                ocr_engine=self.engine,
                min_ocr_confidence=0.60,
            ).extract(path)
            after = sha256_file(path)

            self.assertEqual(before, after)
            self.assertEqual(result.document_type, DocumentType.QUOTATION)
            self.assertEqual(result.pages[0].extraction_method, PageExtractionMethod.OCR)
            self.assertEqual(result.pages[0].ocr_engine, "tesseract")
            self.assertEqual(result.pages[0].ocr_language, "spa")
            self.assertIsNotNone(result.pages[0].ocr_engine_version)
            self.assertIn("COTIZACION", result.pages[0].page_text.upper())
            self.assertTrue(result.pages[0].source_location.evidence)

    def test_mixed_pdf_selects_method_per_page(self) -> None:
        if not self.runtime.available:
            self.skipTest(self.runtime.error or "Tesseract spa runtime unavailable")

        with TemporaryDirectory() as directory:
            path = create_mixed_pdf(
                Path(directory) / "mixed.pdf",
                (
                    "FACTURA DE VENTA",
                    "Numero de factura FV-2001",
                    "Proveedor Distribuciones Faro SAS",
                    "Pagina uno con texto nativo suficiente",
                ),
                (
                    "DETALLE FACTURA FV-2001",
                    "Producto Cafe Molido",
                    "Cantidad 20",
                    "TOTAL 250000 COP",
                ),
            )
            result = PdfExtractionService(
                ocr_engine=self.engine,
                min_ocr_confidence=0.55,
            ).extract(path)

            self.assertEqual(result.document_type, DocumentType.INVOICE)
            self.assertEqual(
                [page.extraction_method for page in result.pages],
                [PageExtractionMethod.NATIVE_TEXT, PageExtractionMethod.OCR],
            )
            self.assertEqual(result.page_count, 2)


if __name__ == "__main__":
    unittest.main()
