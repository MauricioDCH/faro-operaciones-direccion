"""Structured exceptions for PDF extraction."""

from __future__ import annotations


class PdfExtractionError(RuntimeError):
    """Base error for document extraction failures."""

    code = "pdf_extraction_error"


class InvalidPdfError(PdfExtractionError):
    code = "invalid_pdf"


class UnsupportedPdfError(PdfExtractionError):
    code = "unsupported_pdf"


class PdfRuntimeError(PdfExtractionError):
    code = "pdf_runtime_error"


class OcrRuntimeError(PdfExtractionError):
    code = "ocr_runtime_error"


class RawSourceModifiedError(PdfExtractionError):
    code = "raw_source_modified"
