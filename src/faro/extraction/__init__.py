"""PDF text recovery, OCR fallback, and document classification."""

from faro.extraction.classifier import ClassificationResult, DocumentClassifier
from faro.extraction.errors import (
    InvalidPdfError,
    OcrRuntimeError,
    PdfExtractionError,
    PdfRuntimeError,
    RawSourceModifiedError,
    UnsupportedPdfError,
)
from faro.extraction.ocr import (
    OcrEngine,
    OcrResult,
    OcrRuntimeInfo,
    TesseractOcrEngine,
)
from faro.extraction.pdf import (
    NativeTextPolicy,
    PdfInspector,
    PdfPageReader,
    PopplerRuntime,
    PopplerRuntimeInfo,
)
from faro.extraction.service import PdfExtractionService
from faro.extraction.structured import StructuredDocumentExtractor, StructuredExtractionOutput

__all__ = [
    "ClassificationResult",
    "DocumentClassifier",
    "InvalidPdfError",
    "NativeTextPolicy",
    "OcrEngine",
    "OcrResult",
    "OcrRuntimeError",
    "OcrRuntimeInfo",
    "PdfExtractionError",
    "PdfExtractionService",
    "PdfInspector",
    "PdfPageReader",
    "PdfRuntimeError",
    "PopplerRuntime",
    "PopplerRuntimeInfo",
    "RawSourceModifiedError",
    "TesseractOcrEngine",
    "StructuredDocumentExtractor",
    "StructuredExtractionOutput",
    "UnsupportedPdfError",
]
