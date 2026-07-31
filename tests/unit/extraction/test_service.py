from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from faro.domain.documents import (
    DocumentType,
    PageExtractionMethod,
    ProcessingStatus,
)
from faro.extraction.ocr import OcrResult, OcrRuntimeInfo
from faro.extraction.service import PdfExtractionService
from faro.provenance.models import BoundingBox, EvidenceFragment, sha256_file
from tests.fixtures.pdf.builders import create_native_pdf, create_scanned_pdf


class FakeOcrEngine:
    @property
    def runtime_info(self) -> OcrRuntimeInfo:
        return OcrRuntimeInfo(
            engine="fake-ocr",
            command="fake",
            available=True,
            version="1.0",
            languages=("spa",),
        )

    def extract_png(self, png_bytes: bytes) -> OcrResult:
        self.last_png = png_bytes
        return OcrResult(
            text="COTIZACION COT-2026-041 TOTAL 743750 COP",
            confidence=0.95,
            evidence=(
                EvidenceFragment(
                    text="COTIZACION",
                    confidence=0.95,
                    bounding_box=BoundingBox(1, 2, 3, 4),
                ),
            ),
            engine="fake-ocr",
            engine_version="1.0",
            language="spa",
        )


class PdfExtractionServiceTests(unittest.TestCase):
    def test_uses_native_text_before_ocr(self) -> None:
        with TemporaryDirectory() as directory:
            path = create_native_pdf(
                Path(directory) / "invoice.pdf",
                (
                    "FACTURA DE VENTA",
                    "Numero de factura FV-1001",
                    "Proveedor Distribuciones Faro SAS",
                    "TOTAL 743750 COP",
                ),
            )
            before = sha256_file(path)
            result = PdfExtractionService(ocr_engine=FakeOcrEngine()).extract(path)
            after = sha256_file(path)

            self.assertEqual(result.document_type, DocumentType.INVOICE)
            self.assertEqual(
                result.pages[0].extraction_method,
                PageExtractionMethod.NATIVE_TEXT,
            )
            self.assertEqual(before, after)

    def test_uses_ocr_for_scanned_page(self) -> None:
        with TemporaryDirectory() as directory:
            path = create_scanned_pdf(
                Path(directory) / "quotation.pdf",
                ("COTIZACION", "Numero COT-2026-041", "TOTAL 743750 COP"),
            )
            result = PdfExtractionService(ocr_engine=FakeOcrEngine()).extract(path)

            self.assertEqual(result.document_type, DocumentType.QUOTATION)
            self.assertEqual(result.processing_status, ProcessingStatus.PENDING_REVIEW)
            self.assertIsNotNone(result.structured_document)
            self.assertEqual(result.pages[0].extraction_method, PageExtractionMethod.OCR)
            self.assertEqual(result.pages[0].ocr_engine_version, "1.0")
            self.assertTrue(result.pages[0].source_location.evidence)

    def test_degrades_safely_when_ocr_is_disabled(self) -> None:
        with TemporaryDirectory() as directory:
            path = create_scanned_pdf(
                Path(directory) / "scan.pdf",
                ("FACTURA", "Numero FV-1001", "TOTAL 100000 COP"),
            )
            result = PdfExtractionService(
                ocr_engine=None,
                ocr_enabled=False,
            ).extract(path)

            self.assertEqual(result.pages[0].processing_status, ProcessingStatus.ERROR)
            self.assertEqual(result.pages[0].error_code, "ocr_disabled")
            self.assertEqual(result.document_type, DocumentType.UNSUPPORTED)


if __name__ == "__main__":
    unittest.main()
