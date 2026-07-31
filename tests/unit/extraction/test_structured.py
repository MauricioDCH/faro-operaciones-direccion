from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import unittest

from faro.domain.documents import (
    DocumentPage, DocumentType, PageExtractionMethod, ProcessingStatus, RecordStatus
)
from faro.extraction.structured import StructuredDocumentExtractor
from faro.provenance.models import SourceLocation


def page(text: str, *, method: PageExtractionMethod = PageExtractionMethod.NATIVE_TEXT) -> DocumentPage:
    return DocumentPage(
        document_page_id="DOCP-TEST-001", document_id="DOC-TEST", page_number=1,
        extraction_method=method, native_text_length=len(text), page_text=text,
        processing_status=ProcessingStatus.PROCESSED,
        source_location=SourceLocation("LOC-TEST-001", "SRC-TEST", 1, text[:240]),
        ocr_engine="tesseract" if method is PageExtractionMethod.OCR else None,
        ocr_engine_version="5.3.4" if method is PageExtractionMethod.OCR else None,
        ocr_language="spa" if method is PageExtractionMethod.OCR else None,
        ocr_confidence=0.91 if method is PageExtractionMethod.OCR else None,
    )


INVOICE = """FACTURA
invoice_id: INV-000001
invoice_number: FV-1001
supplier_name_raw: Distribuciones Andinas SAS
supplier_id: SUP-0001
issue_date: 2026-07-25
related_order_id: ORD-000001
currency: COP
subtotal_cop: 600000.00
tax_cop: 114000.00
total_cop: 714000.00
LINE|INVL-000001|Cafe molido 500 g|PRD-0001|50|12000.00|600000.00
"""


class StructuredDocumentExtractorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.extractor = StructuredDocumentExtractor()
        self.created_at = datetime(2026, 7, 31, tzinfo=timezone.utc).isoformat()

    def test_extracts_invoice_header_lines_and_field_evidence(self) -> None:
        result = self.extractor.extract(
            document_id="DOC-TEST", document_type=DocumentType.INVOICE,
            pages=(page(INVOICE),), created_at=self.created_at,
        )
        invoice = result.document
        self.assertIsNotNone(invoice)
        assert invoice is not None
        self.assertEqual(invoice.invoice_number, "FV-1001")
        self.assertEqual(str(invoice.total_cop), "714000.00")
        self.assertEqual(len(invoice.lines), 1)
        self.assertEqual(invoice.record_status, RecordStatus.ACCEPTED)
        self.assertFalse(result.findings)
        self.assertTrue(invoice.extraction_results)
        self.assertEqual(invoice.extraction_results[0].page_number, 1)

    def test_total_mismatch_requires_review(self) -> None:
        text = INVOICE.replace("total_cop: 714000.00", "total_cop: 700000.00")
        result = self.extractor.extract(
            document_id="DOC-TEST", document_type=DocumentType.INVOICE,
            pages=(page(text),), created_at=self.created_at,
        )
        self.assertIn("document_total_mismatch", {item.code for item in result.findings})
        assert result.document is not None
        self.assertEqual(result.document.record_status, RecordStatus.PENDING_REVIEW)

    def test_missing_required_field_requires_review(self) -> None:
        text = INVOICE.replace("invoice_number: FV-1001\n", "")
        result = self.extractor.extract(
            document_id="DOC-TEST", document_type=DocumentType.INVOICE,
            pages=(page(text),), created_at=self.created_at,
        )
        self.assertIn("missing_required_field", {item.code for item in result.findings})

    def test_invalid_quotation_validity_is_detected(self) -> None:
        text = INVOICE.replace("FACTURA", "COTIZACION").replace("invoice_id", "quotation_id").replace("INV-000001", "QUO-000001").replace("invoice_number", "quotation_number").replace("FV-1001", "COT-1001").replace("related_order_id: ORD-000001\n", "valid_until: 2026-07-20\n").replace("INVL-", "QUOL-")
        result = self.extractor.extract(
            document_id="DOC-TEST", document_type=DocumentType.QUOTATION,
            pages=(page(text),), created_at=self.created_at,
        )
        self.assertIn("invalid_valid_until", {item.code for item in result.findings})


if __name__ == "__main__":
    unittest.main()
