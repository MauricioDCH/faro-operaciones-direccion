
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from faro.domain.documents import (
    DocumentType,
    PageExtractionMethod,
    ProcessingStatus,
    RecordStatus,
)
from faro.extraction.image import ImageInspector
from faro.extraction.ocr import OcrResult, OcrRuntimeInfo
from faro.ingestion.image_document import ImageDocumentIngestionService
from faro.provenance.models import BoundingBox, EvidenceFragment, sha256_file
from tests.fixtures.images.builders import write_blank_image


@dataclass
class FakeOcr:
    text: str
    confidence: float | None = 0.95

    @property
    def runtime_info(self) -> OcrRuntimeInfo:
        return OcrRuntimeInfo(
            engine="fake",
            command="fake",
            available=True,
            version="1.0",
            languages=("spa",),
        )

    def extract_png(self, png_bytes: bytes) -> OcrResult:
        return OcrResult(
            text=self.text,
            confidence=self.confidence,
            evidence=(
                EvidenceFragment(
                    text="FACTURA",
                    confidence=self.confidence,
                    bounding_box=BoundingBox(1, 2, 30, 10),
                ),
            ),
            engine="fake",
            engine_version="1.0",
            language="spa",
        )


INVOICE_TEXT = """FACTURA DE VENTA
invoice_id: INV-IMG-001
invoice_number: FV-IMG-001
supplier_name_raw: Proveedor Imagen SAS
supplier_id: SUP-0001
issue_date: 2026-08-02
related_order_id: ORD-000001
currency: COP
subtotal_cop: 100000.00
tax_cop: 19000.00
total_cop: 119000.00
LINE|INVL-IMG-001|Cafe molido|PRD-0001|10|10000.00|100000.00
"""


class ImageDocumentIngestionServiceTests(unittest.TestCase):
    def _service(self, *, confidence: float | None = 0.95):
        return ImageDocumentIngestionService(
            ocr_engine=FakeOcr(INVOICE_TEXT, confidence),
            min_ocr_confidence=0.75,
            inspector=ImageInspector(min_width=1, min_height=1),
        )

    def test_extracts_structured_invoice_with_image_provenance(self) -> None:
        with TemporaryDirectory() as directory:
            path = write_blank_image(Path(directory) / "invoice.png", "png")
            before = sha256_file(path)
            result = self._service().extract(path)
            after = sha256_file(path)

            self.assertEqual(before, after)
            self.assertEqual(result.document_type, DocumentType.INVOICE)
            self.assertEqual(result.record_status, RecordStatus.ACCEPTED)
            self.assertEqual(
                result.pages[0].extraction_method,
                PageExtractionMethod.OCR,
            )
            self.assertEqual(result.source_file.contract_id, "DC-012")
            self.assertEqual(result.source_file.detected_format, "png")
            self.assertEqual(
                result.source_file.format_metadata["width"], 32
            )
            self.assertIsNotNone(result.structured_document)
            assert result.structured_document is not None
            self.assertEqual(
                result.structured_document.invoice_number,
                "FV-IMG-001",
            )
            self.assertTrue(result.pages[0].source_location.evidence)

    def test_low_confidence_requires_review(self) -> None:
        with TemporaryDirectory() as directory:
            path = write_blank_image(Path(directory) / "invoice.webp", "webp")
            result = self._service(confidence=0.40).extract(path)
            self.assertEqual(
                result.pages[0].processing_status,
                ProcessingStatus.PENDING_REVIEW,
            )
            self.assertEqual(result.record_status, RecordStatus.PENDING_REVIEW)
            self.assertEqual(result.pages[0].error_code, "ocr_low_confidence")

    def test_disabled_ocr_does_not_invent_text(self) -> None:
        with TemporaryDirectory() as directory:
            path = write_blank_image(Path(directory) / "invoice.tiff", "tiff")
            result = ImageDocumentIngestionService(
                ocr_engine=None,
                ocr_enabled=False,
                inspector=ImageInspector(min_width=1, min_height=1),
            ).extract(path)
            self.assertEqual(result.pages[0].page_text, "")
            self.assertEqual(result.pages[0].error_code, "ocr_disabled")
            self.assertEqual(result.record_status, RecordStatus.REJECTED)


if __name__ == "__main__":
    unittest.main()
