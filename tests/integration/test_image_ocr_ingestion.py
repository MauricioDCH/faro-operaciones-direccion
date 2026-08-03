
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from faro.domain.documents import DocumentType, PageExtractionMethod
from faro.extraction.image import ImageInspector
from faro.extraction.ocr import TesseractOcrEngine
from faro.ingestion.image_document import ImageDocumentIngestionService
from faro.provenance.models import sha256_file
from tests.fixtures.images.builders import create_document_png


class ImageOcrIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = TesseractOcrEngine(language="spa")
        cls.runtime = cls.engine.runtime_info

    def test_scanned_png_uses_real_ocr_and_preserves_raw(self) -> None:
        if not self.runtime.available:
            self.skipTest(self.runtime.error or "Tesseract unavailable")
        with TemporaryDirectory() as directory:
            path = create_document_png(
                Path(directory) / "quotation.png",
                (
                    "COTIZACION DE PROVEEDOR",
                    "quotation_number: COT-IMG-041",
                    "supplier_name_raw: Distribuciones Faro SAS",
                    "issue_date: 2026-08-02",
                    "currency: COP",
                    "subtotal_cop: 100000.00",
                    "tax_cop: 19000.00",
                    "total_cop: 119000.00",
                    "LINE|QUOL-IMG-001|Cafe molido|PRD-0001|10|10000.00|100000.00",
                ),
            )
            before = sha256_file(path)
            result = ImageDocumentIngestionService(
                ocr_engine=self.engine,
                min_ocr_confidence=0.50,
                inspector=ImageInspector(min_width=1, min_height=1),
            ).extract(path)
            after = sha256_file(path)

            self.assertEqual(before, after)
            self.assertEqual(result.document_type, DocumentType.QUOTATION)
            self.assertEqual(
                result.pages[0].extraction_method,
                PageExtractionMethod.OCR,
            )
            self.assertEqual(result.source_file.source_type, "image")
            self.assertEqual(result.source_file.detected_format, "png")
            self.assertTrue(result.pages[0].source_location.evidence)


if __name__ == "__main__":
    unittest.main()
