
"""Document-image adapter using local OCR and canonical document extraction."""

from __future__ import annotations

from pathlib import Path

from faro.domain.documents import (
    DocumentExtraction,
    DocumentPage,
    DocumentType,
    PageExtractionMethod,
    ProcessingStatus,
    RecordStatus,
)
from faro.extraction.classifier import DocumentClassifier
from faro.extraction.errors import OcrRuntimeError, RawSourceModifiedError
from faro.extraction.image import ImageInspector, ImageMetadata
from faro.extraction.ocr import OcrEngine
from faro.extraction.structured import StructuredDocumentExtractor
from faro.ingestion.formats import require_implemented_format
from faro.provenance.models import (
    SourceFile,
    SourceLocation,
    sha256_file,
    stable_document_id,
    stable_location_id,
    stable_page_id,
)


class ImageDocumentIngestionService:
    """OCR one supported document image and preserve field-level evidence."""

    def __init__(
        self,
        *,
        ocr_engine: OcrEngine | None,
        ocr_enabled: bool = True,
        min_ocr_confidence: float = 0.75,
        inspector: ImageInspector | None = None,
        classifier: DocumentClassifier | None = None,
        structured_extractor: StructuredDocumentExtractor | None = None,
    ) -> None:
        self.ocr_engine = ocr_engine
        self.ocr_enabled = ocr_enabled
        self.min_ocr_confidence = min_ocr_confidence
        self.inspector = inspector or ImageInspector()
        self.classifier = classifier or DocumentClassifier()
        self.structured_extractor = (
            structured_extractor or StructuredDocumentExtractor()
        )

    def extract(self, path: Path) -> DocumentExtraction:
        source_path = path.resolve()
        capability = require_implemented_format(source_path)
        if capability.adapter != "image_document":
            raise ValueError(
                f"Expected an image_document format, got {capability.adapter}."
            )
        metadata = self.inspector.inspect(source_path)
        initial_hash = sha256_file(source_path)
        source_file = SourceFile.from_path(
            source_path,
            initial_hash,
            source_type="image",
            contract_id="DC-012",
            contract_version="1.5.0",
            media_type_detected=metadata.media_type,
            detected_format=metadata.format_id,
            format_version="header-v1",
            ingestion_adapter="image_document",
            format_metadata=metadata.to_dict(),
        )
        document_id = stable_document_id(initial_hash)
        page = self._extract_virtual_page(
            source_path=source_path,
            source_file=source_file,
            document_id=document_id,
            metadata=metadata,
        )
        final_hash = sha256_file(source_path)
        if final_hash != initial_hash:
            raise RawSourceModifiedError(
                f"Raw image changed during extraction: {source_path}"
            )

        classification = self.classifier.classify(page.page_text)
        structured = self.structured_extractor.extract(
            document_id=document_id,
            document_type=classification.document_type,
            pages=(page,),
            created_at=source_file.ingested_at,
        )
        processing_status, record_status = _aggregate_status(
            page=page,
            document_type=classification.document_type,
            structured_status=(
                structured.document.record_status
                if structured.document is not None
                else None
            ),
        )
        return DocumentExtraction(
            document_id=document_id,
            source_file=source_file,
            document_type=classification.document_type,
            page_count=1,
            classification_method=classification.method,
            classification_confidence=classification.confidence,
            processing_status=processing_status,
            record_status=record_status,
            pages=(page,),
            structured_document=structured.document,
            quality_findings=structured.findings,
        )

    def _extract_virtual_page(
        self,
        *,
        source_path: Path,
        source_file: SourceFile,
        document_id: str,
        metadata: ImageMetadata,
    ) -> DocumentPage:
        page_number = 1
        page_id = stable_page_id(source_file.sha256, page_number)
        location_id = stable_location_id(source_file.sha256, page_number)
        if not self.ocr_enabled:
            return _error_page(
                page_id=page_id,
                document_id=document_id,
                source_file=source_file,
                error_code="ocr_disabled",
                error_message="OCR is disabled for document images.",
            )
        if self.ocr_engine is None:
            return _error_page(
                page_id=page_id,
                document_id=document_id,
                source_file=source_file,
                error_code="ocr_engine_missing",
                error_message="OCR is enabled but no engine was configured.",
            )
        try:
            result = self.ocr_engine.extract_png(source_path.read_bytes())
        except OcrRuntimeError as exc:
            return _error_page(
                page_id=page_id,
                document_id=document_id,
                source_file=source_file,
                error_code=exc.code,
                error_message=str(exc),
            )

        has_text = bool(result.text.strip())
        confidence_ok = (
            result.confidence is not None
            and result.confidence >= self.min_ocr_confidence
        )
        status = (
            ProcessingStatus.PROCESSED
            if has_text and confidence_ok
            else ProcessingStatus.PENDING_REVIEW
        )
        error_code = None
        error_message = None
        if not has_text:
            error_code = "ocr_empty_text"
            error_message = "OCR produced no usable text."
        elif not confidence_ok:
            error_code = "ocr_low_confidence"
            error_message = (
                f"OCR confidence {result.confidence!r} is below "
                f"{self.min_ocr_confidence:.2f}."
            )

        location = SourceLocation(
            source_location_id=location_id,
            source_file_id=source_file.source_file_id,
            page_number=1,
            text_excerpt=result.text[:240],
            evidence=result.evidence,
        )
        return DocumentPage(
            document_page_id=page_id,
            document_id=document_id,
            page_number=1,
            extraction_method=PageExtractionMethod.OCR,
            native_text_length=0,
            render_dpi=None,
            ocr_engine=result.engine,
            ocr_engine_version=result.engine_version,
            ocr_language=result.language,
            ocr_confidence=result.confidence,
            page_text=result.text,
            processing_status=status,
            source_location=location,
            error_code=error_code,
            error_message=error_message,
        )


def _error_page(
    *,
    page_id: str,
    document_id: str,
    source_file: SourceFile,
    error_code: str,
    error_message: str,
) -> DocumentPage:
    return DocumentPage(
        document_page_id=page_id,
        document_id=document_id,
        page_number=1,
        extraction_method=PageExtractionMethod.OCR,
        native_text_length=0,
        page_text="",
        processing_status=ProcessingStatus.ERROR,
        source_location=SourceLocation(
            source_location_id=stable_location_id(source_file.sha256, 1),
            source_file_id=source_file.source_file_id,
            page_number=1,
            text_excerpt="",
        ),
        error_code=error_code,
        error_message=error_message,
    )


def _aggregate_status(
    *,
    page: DocumentPage,
    document_type: DocumentType,
    structured_status: RecordStatus | None,
) -> tuple[ProcessingStatus, RecordStatus]:
    if document_type is DocumentType.UNSUPPORTED:
        if page.processing_status is ProcessingStatus.PENDING_REVIEW:
            return ProcessingStatus.PENDING_REVIEW, RecordStatus.PENDING_REVIEW
        return ProcessingStatus.REJECTED, RecordStatus.REJECTED
    if page.processing_status is not ProcessingStatus.PROCESSED:
        return ProcessingStatus.PENDING_REVIEW, RecordStatus.PENDING_REVIEW
    if structured_status is RecordStatus.PENDING_REVIEW:
        return ProcessingStatus.PENDING_REVIEW, RecordStatus.PENDING_REVIEW
    return ProcessingStatus.PROCESSED, RecordStatus.ACCEPTED
