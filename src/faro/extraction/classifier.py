"""Deterministic classification for the supported document types."""

from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata

from faro.domain.documents import DocumentType


@dataclass(frozen=True, slots=True)
class ClassificationResult:
    document_type: DocumentType
    confidence: float
    method: str = "deterministic_keywords_v1"


class DocumentClassifier:
    """Classify invoices and quotations using transparent keyword rules."""

    _invoice_terms = (
        "factura",
        "factura de venta",
        "numero de factura",
        "nro factura",
        "invoice",
    )
    _quotation_terms = (
        "cotizacion",
        "numero de cotizacion",
        "oferta comercial",
        "quotation",
    )

    def classify(self, text: str) -> ClassificationResult:
        normalized = _normalize(text)
        invoice_hits = _count_terms(normalized, self._invoice_terms)
        quotation_hits = _count_terms(normalized, self._quotation_terms)

        if invoice_hits == 0 and quotation_hits == 0:
            return ClassificationResult(DocumentType.UNSUPPORTED, 0.0)
        if invoice_hits == quotation_hits:
            return ClassificationResult(DocumentType.UNSUPPORTED, 0.5)
        if invoice_hits > quotation_hits:
            return ClassificationResult(
                DocumentType.INVOICE,
                _classification_confidence(invoice_hits, quotation_hits),
            )
        return ClassificationResult(
            DocumentType.QUOTATION,
            _classification_confidence(quotation_hits, invoice_hits),
        )


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    without_accents = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    return re.sub(r"\s+", " ", without_accents.casefold()).strip()


def _count_terms(text: str, terms: tuple[str, ...]) -> int:
    return sum(1 for term in terms if term in text)


def _classification_confidence(primary: int, secondary: int) -> float:
    score = 0.80 + min(primary, 3) * 0.05 - min(secondary, 2) * 0.10
    return round(max(0.0, min(score, 0.99)), 4)
