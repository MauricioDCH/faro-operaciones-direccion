"""Domain models for PDF text recovery and document classification."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from faro.provenance.models import SourceFile, SourceLocation


class DocumentType(StrEnum):
    INVOICE = "invoice"
    QUOTATION = "quotation"
    UNSUPPORTED = "unsupported"


class PageExtractionMethod(StrEnum):
    NATIVE_TEXT = "native_text"
    OCR = "ocr"
    UNSUPPORTED = "unsupported"


class ProcessingStatus(StrEnum):
    PROCESSED = "processed"
    PENDING_REVIEW = "pending_review"
    REJECTED = "rejected"
    ERROR = "error"


class RecordStatus(StrEnum):
    ACCEPTED = "accepted"
    PENDING_REVIEW = "pending_review"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class DocumentPage:
    """Recovered text and metadata for one PDF page."""

    document_page_id: str
    document_id: str
    page_number: int
    extraction_method: PageExtractionMethod
    native_text_length: int
    page_text: str
    processing_status: ProcessingStatus
    source_location: SourceLocation
    render_dpi: int | None = None
    ocr_engine: str | None = None
    ocr_engine_version: str | None = None
    ocr_language: str | None = None
    ocr_confidence: float | None = None
    error_code: str | None = None
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_page_id": self.document_page_id,
            "document_id": self.document_id,
            "page_number": self.page_number,
            "extraction_method": self.extraction_method.value,
            "native_text_length": self.native_text_length,
            "render_dpi": self.render_dpi,
            "ocr_engine": self.ocr_engine,
            "ocr_engine_version": self.ocr_engine_version,
            "ocr_language": self.ocr_language,
            "ocr_confidence": self.ocr_confidence,
            "page_text": self.page_text,
            "processing_status": self.processing_status.value,
            "source_location": self.source_location.to_dict(),
            "error_code": self.error_code,
            "error_message": self.error_message,
        }


@dataclass(frozen=True, slots=True)
class DocumentExtraction:
    """Page-level PDF extraction result with immutable provenance."""

    document_id: str
    source_file: SourceFile
    document_type: DocumentType
    page_count: int
    classification_method: str
    classification_confidence: float
    processing_status: ProcessingStatus
    record_status: RecordStatus
    pages: tuple[DocumentPage, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_id": self.document_id,
            "source_file": self.source_file.to_dict(),
            "document_type": self.document_type.value,
            "page_count": self.page_count,
            "classification_method": self.classification_method,
            "classification_confidence": self.classification_confidence,
            "processing_status": self.processing_status.value,
            "record_status": self.record_status.value,
            "pages": [page.to_dict() for page in self.pages],
        }
