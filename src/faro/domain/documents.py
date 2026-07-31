"""Domain models for PDF recovery and structured document extraction."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
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


class ReviewStatus(StrEnum):
    ACCEPTED = "accepted"
    PENDING = "pending"


@dataclass(frozen=True, slots=True)
class QualityFinding:
    code: str
    severity: str
    field: str | None
    message: str
    observed_value: str | None = None
    expected_value: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "field": self.field,
            "message": self.message,
            "observed_value": self.observed_value,
            "expected_value": self.expected_value,
        }


@dataclass(frozen=True, slots=True)
class ExtractionResult:
    extraction_id: str
    source_location_id: str
    document_page_id: str
    target_entity: str
    target_field: str
    raw_value: str
    proposed_value: str
    method: str
    page_number: int
    text_excerpt: str
    confidence: float | None
    review_status: ReviewStatus
    created_at: str
    ocr_engine: str | None = None
    ocr_engine_version: str | None = None
    ocr_confidence: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "extraction_id": self.extraction_id,
            "source_location_id": self.source_location_id,
            "document_page_id": self.document_page_id,
            "target_entity": self.target_entity,
            "target_field": self.target_field,
            "raw_value": self.raw_value,
            "proposed_value": self.proposed_value,
            "method": self.method,
            "page_number": self.page_number,
            "text_excerpt": self.text_excerpt,
            "confidence": self.confidence,
            "review_status": self.review_status.value,
            "created_at": self.created_at,
            "ocr_engine": self.ocr_engine,
            "ocr_engine_version": self.ocr_engine_version,
            "ocr_confidence": self.ocr_confidence,
        }


@dataclass(frozen=True, slots=True)
class InvoiceLine:
    invoice_line_id: str
    product_name_raw: str
    product_id: str | None
    quantity: Decimal
    unit_price_cop: Decimal
    line_total_cop: Decimal
    record_status: RecordStatus
    source_location_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "invoice_line_id": self.invoice_line_id,
            "product_name_raw": self.product_name_raw,
            "product_id": self.product_id,
            "quantity": str(self.quantity),
            "unit_price_cop": str(self.unit_price_cop),
            "line_total_cop": str(self.line_total_cop),
            "record_status": self.record_status.value,
            "source_location_id": self.source_location_id,
        }


@dataclass(frozen=True, slots=True)
class QuotationLine:
    quotation_line_id: str
    product_name_raw: str
    product_id: str | None
    quantity: Decimal
    unit_price_cop: Decimal
    line_total_cop: Decimal
    record_status: RecordStatus
    source_location_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "quotation_line_id": self.quotation_line_id,
            "product_name_raw": self.product_name_raw,
            "product_id": self.product_id,
            "quantity": str(self.quantity),
            "unit_price_cop": str(self.unit_price_cop),
            "line_total_cop": str(self.line_total_cop),
            "record_status": self.record_status.value,
            "source_location_id": self.source_location_id,
        }


@dataclass(frozen=True, slots=True)
class Invoice:
    invoice_id: str | None
    document_id: str
    invoice_number: str | None
    supplier_name_raw: str | None
    supplier_id: str | None
    issue_date: date | None
    related_order_id: str | None
    currency: str | None
    subtotal_cop: Decimal | None
    tax_cop: Decimal | None
    total_cop: Decimal | None
    record_status: RecordStatus
    source_location_id: str
    lines: tuple[InvoiceLine, ...]
    extraction_results: tuple[ExtractionResult, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_type": "invoice",
            "invoice_id": self.invoice_id,
            "document_id": self.document_id,
            "invoice_number": self.invoice_number,
            "supplier_name_raw": self.supplier_name_raw,
            "supplier_id": self.supplier_id,
            "issue_date": self.issue_date.isoformat() if self.issue_date else None,
            "related_order_id": self.related_order_id,
            "currency": self.currency,
            "subtotal_cop": str(self.subtotal_cop) if self.subtotal_cop is not None else None,
            "tax_cop": str(self.tax_cop) if self.tax_cop is not None else None,
            "total_cop": str(self.total_cop) if self.total_cop is not None else None,
            "record_status": self.record_status.value,
            "source_location_id": self.source_location_id,
            "lines": [line.to_dict() for line in self.lines],
            "extraction_results": [item.to_dict() for item in self.extraction_results],
        }


@dataclass(frozen=True, slots=True)
class Quotation:
    quotation_id: str | None
    document_id: str
    quotation_number: str | None
    supplier_name_raw: str | None
    supplier_id: str | None
    issue_date: date | None
    valid_until: date | None
    currency: str | None
    subtotal_cop: Decimal | None
    tax_cop: Decimal | None
    total_cop: Decimal | None
    record_status: RecordStatus
    source_location_id: str
    lines: tuple[QuotationLine, ...]
    extraction_results: tuple[ExtractionResult, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_type": "quotation",
            "quotation_id": self.quotation_id,
            "document_id": self.document_id,
            "quotation_number": self.quotation_number,
            "supplier_name_raw": self.supplier_name_raw,
            "supplier_id": self.supplier_id,
            "issue_date": self.issue_date.isoformat() if self.issue_date else None,
            "valid_until": self.valid_until.isoformat() if self.valid_until else None,
            "currency": self.currency,
            "subtotal_cop": str(self.subtotal_cop) if self.subtotal_cop is not None else None,
            "tax_cop": str(self.tax_cop) if self.tax_cop is not None else None,
            "total_cop": str(self.total_cop) if self.total_cop is not None else None,
            "record_status": self.record_status.value,
            "source_location_id": self.source_location_id,
            "lines": [line.to_dict() for line in self.lines],
            "extraction_results": [item.to_dict() for item in self.extraction_results],
        }


StructuredDocument = Invoice | Quotation


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
    """PDF extraction result with immutable provenance and optional structured data."""

    document_id: str
    source_file: SourceFile
    document_type: DocumentType
    page_count: int
    classification_method: str
    classification_confidence: float
    processing_status: ProcessingStatus
    record_status: RecordStatus
    pages: tuple[DocumentPage, ...]
    structured_document: StructuredDocument | None = None
    quality_findings: tuple[QualityFinding, ...] = ()

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
            "structured_document": (
                self.structured_document.to_dict() if self.structured_document else None
            ),
            "quality_findings": [item.to_dict() for item in self.quality_findings],
        }
