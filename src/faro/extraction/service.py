"""Application service for native PDF text and OCR fallback."""

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
from faro.extraction.errors import (
    OcrRuntimeError,
    PdfRuntimeError,
    RawSourceModifiedError,
)
from faro.extraction.ocr import OcrEngine
from faro.extraction.pdf import NativeTextPolicy, PdfInspector, PdfPageReader
from faro.extraction.structured import StructuredDocumentExtractor
from faro.provenance.models import (
    EvidenceFragment,
    SourceFile,
    SourceLocation,
    sha256_file,
    stable_document_id,
    stable_location_id,
    stable_page_id,
)


class PdfExtractionService:
    """Recover page text, classify the document, and preserve provenance."""

    def __init__(
        self,
        *,
        ocr_engine: OcrEngine | None,
        ocr_enabled: bool = True,
        extraction_mode: str = "auto",
        min_ocr_confidence: float = 0.75,
        render_dpi: int = 300,
        max_pages: int = 3,
        native_text_policy: NativeTextPolicy | None = None,
        classifier: DocumentClassifier | None = None,
        inspector: PdfInspector | None = None,
        page_reader: PdfPageReader | None = None,
        structured_extractor: StructuredDocumentExtractor | None = None,
    ) -> None:
        if extraction_mode not in {"auto", "native_only", "ocr_only"}:
            raise ValueError("Unsupported PDF extraction mode.")
        self.ocr_engine = ocr_engine
        self.ocr_enabled = ocr_enabled
        self.extraction_mode = extraction_mode
        self.min_ocr_confidence = min_ocr_confidence
        self.page_reader = page_reader or PdfPageReader(render_dpi=render_dpi)
        self.inspector = inspector or PdfInspector(max_pages=max_pages)
        self.native_text_policy = native_text_policy or NativeTextPolicy()
        self.classifier = classifier or DocumentClassifier()
        self.structured_extractor = structured_extractor or StructuredDocumentExtractor()

    def extract(self, path: Path) -> DocumentExtraction:
        source_path = path.resolve()
        metadata = self.inspector.inspect(source_path)
        initial_hash = sha256_file(source_path)
        source_file = SourceFile.from_path(source_path, initial_hash)
        document_id = stable_document_id(initial_hash)

        pages = [
            self._extract_page(
                path=source_path,
                page_number=page_number,
                document_id=document_id,
                source_file=source_file,
            )
            for page_number in range(1, metadata.page_count + 1)
        ]

        final_hash = sha256_file(source_path)
        if final_hash != initial_hash:
            raise RawSourceModifiedError(
                f"Raw PDF changed during extraction: {source_path}"
            )

        combined_text = "\n".join(page.page_text for page in pages if page.page_text)
        classification = self.classifier.classify(combined_text)
        structured = self.structured_extractor.extract(
            document_id=document_id,
            document_type=classification.document_type,
            pages=tuple(pages),
            created_at=source_file.ingested_at,
        )
        processing_status, record_status = _aggregate_status(
            pages=pages,
            document_type=classification.document_type,
            structured_status=(
                structured.document.record_status if structured.document else None
            ),
        )
        return DocumentExtraction(
            document_id=document_id,
            source_file=source_file,
            document_type=classification.document_type,
            page_count=metadata.page_count,
            classification_method=classification.method,
            classification_confidence=classification.confidence,
            processing_status=processing_status,
            record_status=record_status,
            pages=tuple(pages),
            structured_document=structured.document,
            quality_findings=structured.findings,
        )

    def _extract_page(
        self,
        *,
        path: Path,
        page_number: int,
        document_id: str,
        source_file: SourceFile,
    ) -> DocumentPage:
        page_id = stable_page_id(source_file.sha256, page_number)
        location_id = stable_location_id(source_file.sha256, page_number)
        try:
            native_text = self.page_reader.native_text(path, page_number)
        except PdfRuntimeError as exc:
            return self._unsupported_page(
                page_id=page_id,
                document_id=document_id,
                page_number=page_number,
                native_text="",
                source_file=source_file,
                location_id=location_id,
                error_code=exc.code,
                error_message=str(exc),
            )

        if (
            self.extraction_mode != "ocr_only"
            and self.native_text_policy.is_sufficient(native_text)
        ):
            location = SourceLocation(
                source_location_id=location_id,
                source_file_id=source_file.source_file_id,
                page_number=page_number,
                text_excerpt=native_text[:240],
            )
            return DocumentPage(
                document_page_id=page_id,
                document_id=document_id,
                page_number=page_number,
                extraction_method=PageExtractionMethod.NATIVE_TEXT,
                native_text_length=len(native_text),
                page_text=native_text,
                processing_status=ProcessingStatus.PROCESSED,
                source_location=location,
            )

        if self.extraction_mode == "native_only" or not self.ocr_enabled:
            return self._unsupported_page(
                page_id=page_id,
                document_id=document_id,
                page_number=page_number,
                native_text=native_text,
                source_file=source_file,
                location_id=location_id,
                error_code="ocr_disabled",
                error_message="OCR is disabled and native text is insufficient.",
            )

        if self.ocr_engine is None:
            return self._unsupported_page(
                page_id=page_id,
                document_id=document_id,
                page_number=page_number,
                native_text=native_text,
                source_file=source_file,
                location_id=location_id,
                error_code="ocr_engine_missing",
                error_message="OCR is enabled but no engine was configured.",
            )

        try:
            png = self.page_reader.render_png(path, page_number)
            result = self.ocr_engine.extract_png(png)
        except (PdfRuntimeError, OcrRuntimeError) as exc:
            return self._unsupported_page(
                page_id=page_id,
                document_id=document_id,
                page_number=page_number,
                native_text=native_text,
                source_file=source_file,
                location_id=location_id,
                error_code=exc.code,
                error_message=str(exc),
                extraction_method=PageExtractionMethod.OCR,
            )

        sufficient_ocr_text = bool(result.text.strip())
        confidence_ok = (
            result.confidence is not None
            and result.confidence >= self.min_ocr_confidence
        )
        status = (
            ProcessingStatus.PROCESSED
            if sufficient_ocr_text and confidence_ok
            else ProcessingStatus.PENDING_REVIEW
        )
        error_code = None
        error_message = None
        if not sufficient_ocr_text:
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
            page_number=page_number,
            text_excerpt=result.text[:240],
            evidence=result.evidence,
        )
        return DocumentPage(
            document_page_id=page_id,
            document_id=document_id,
            page_number=page_number,
            extraction_method=PageExtractionMethod.OCR,
            native_text_length=len(native_text),
            render_dpi=self.page_reader.render_dpi,
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

    def _unsupported_page(
        self,
        *,
        page_id: str,
        document_id: str,
        page_number: int,
        native_text: str,
        source_file: SourceFile,
        location_id: str,
        error_code: str,
        error_message: str,
        extraction_method: PageExtractionMethod = PageExtractionMethod.UNSUPPORTED,
    ) -> DocumentPage:
        location = SourceLocation(
            source_location_id=location_id,
            source_file_id=source_file.source_file_id,
            page_number=page_number,
            text_excerpt=native_text[:240],
            evidence=(EvidenceFragment(text=native_text[:240]),) if native_text else (),
        )
        return DocumentPage(
            document_page_id=page_id,
            document_id=document_id,
            page_number=page_number,
            extraction_method=extraction_method,
            native_text_length=len(native_text),
            render_dpi=(
                self.page_reader.render_dpi
                if extraction_method is PageExtractionMethod.OCR
                else None
            ),
            page_text=native_text,
            processing_status=ProcessingStatus.ERROR,
            source_location=location,
            error_code=error_code,
            error_message=error_message,
        )


def _aggregate_status(
    *,
    pages: list[DocumentPage],
    document_type: DocumentType,
    structured_status: RecordStatus | None = None,
) -> tuple[ProcessingStatus, RecordStatus]:
    if document_type is DocumentType.UNSUPPORTED:
        return ProcessingStatus.REJECTED, RecordStatus.REJECTED
    if any(page.processing_status is not ProcessingStatus.PROCESSED for page in pages):
        return ProcessingStatus.PENDING_REVIEW, RecordStatus.PENDING_REVIEW
    if structured_status is RecordStatus.PENDING_REVIEW:
        return ProcessingStatus.PENDING_REVIEW, RecordStatus.PENDING_REVIEW
    return ProcessingStatus.PROCESSED, RecordStatus.ACCEPTED
