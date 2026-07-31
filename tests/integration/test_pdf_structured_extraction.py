from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from faro.domain.documents import DocumentType, PageExtractionMethod, RecordStatus
from faro.extraction.ocr import TesseractOcrEngine
from faro.extraction.service import PdfExtractionService
from tests.fixtures.pdf.builders import create_native_pdf, create_scanned_pdf


INVOICE_LINES = (
    "FACTURA",
    "invoice_id: INV-000101",
    "invoice_number: FV-2101",
    "supplier_name_raw: Distribuciones Faro SAS",
    "supplier_id: SUP-0001",
    "issue_date: 2026-07-25",
    "currency: COP",
    "subtotal_cop: 600000.00",
    "tax_cop: 114000.00",
    "total_cop: 714000.00",
    "LINE|INVL-000101|Cafe molido|PRD-0001|50|12000.00|600000.00",
)

QUOTATION_LINES = (
    "COTIZACION",
    "quotation_id: QUO-000101",
    "quotation_number: COT-2101",
    "supplier_name_raw: Distribuciones Faro SAS",
    "supplier_id: SUP-0001",
    "issue_date: 2026-07-25",
    "valid_until: 2026-08-08",
    "currency: COP",
    "subtotal_cop: 600000.00",
    "tax_cop: 114000.00",
    "total_cop: 714000.00",
    "LINE|QUOL-000101|Cafe molido|PRD-0001|50|12000.00|600000.00",
)


class PdfStructuredExtractionIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = TesseractOcrEngine(language="spa")

    def test_native_invoice_is_structured_and_validated(self) -> None:
        with TemporaryDirectory() as directory:
            path=create_native_pdf(Path(directory)/"invoice.pdf", INVOICE_LINES)
            result=PdfExtractionService(ocr_engine=self.engine).extract(path)
            self.assertEqual(result.document_type, DocumentType.INVOICE)
            self.assertIsNotNone(result.structured_document)
            assert result.structured_document is not None
            self.assertEqual(result.structured_document.record_status, RecordStatus.ACCEPTED)
            self.assertEqual(len(result.structured_document.lines), 1)
            self.assertFalse(result.quality_findings)

    def test_scanned_quotation_uses_ocr_and_structures_fields(self) -> None:
        if not self.engine.runtime_info.available:
            self.skipTest(self.engine.runtime_info.error or "OCR unavailable")
        with TemporaryDirectory() as directory:
            path=create_scanned_pdf(Path(directory)/"quotation.pdf", QUOTATION_LINES)
            result=PdfExtractionService(ocr_engine=self.engine, min_ocr_confidence=0.50).extract(path)
            self.assertEqual(result.document_type, DocumentType.QUOTATION)
            self.assertEqual(result.pages[0].extraction_method, PageExtractionMethod.OCR)
            self.assertIsNotNone(result.structured_document)
            assert result.structured_document is not None
            self.assertEqual(result.structured_document.quotation_number, "COT-2101")
            self.assertEqual(len(result.structured_document.lines), 1)
            self.assertTrue(all(item.page_number == 1 for item in result.structured_document.extraction_results))


if __name__ == "__main__":
    unittest.main()
