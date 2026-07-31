"""Deterministic structured extraction for approved synthetic PDF templates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import re
import unicodedata

from faro.domain.documents import (
    DocumentPage,
    DocumentType,
    ExtractionResult,
    Invoice,
    InvoiceLine,
    PageExtractionMethod,
    QualityFinding,
    Quotation,
    QuotationLine,
    RecordStatus,
    ReviewStatus,
    StructuredDocument,
)
from faro.quality.documents import (
    validate_document_totals,
    validate_line_totals,
    validate_quotation_dates,
    validate_required,
    validate_subtotal,
)


@dataclass(frozen=True, slots=True)
class StructuredExtractionOutput:
    document: StructuredDocument | None
    findings: tuple[QualityFinding, ...]


_LABELS: dict[str, tuple[str, ...]] = {
    "invoice_id": ("invoice_id",),
    "invoice_number": ("invoice_number", "numero de factura", "numero factura", "factura no"),
    "quotation_id": ("quotation_id",),
    "quotation_number": ("quotation_number", "numero de cotizacion", "numero cotizacion", "cotizacion no"),
    "supplier_name_raw": ("supplier_name_raw", "proveedor"),
    "supplier_id": ("supplier_id", "id sintetico"),
    "issue_date": ("issue_date", "issue date", "fecha de emision", "fecha"),
    "related_order_id": ("related_order_id", "pedido"),
    "valid_until": ("valid_until", "valida hasta", "vigencia hasta"),
    "currency": ("currency", "moneda"),
    "subtotal_cop": ("subtotal_cop", "subtotal cop", "subtotal"),
    "tax_cop": ("tax_cop", "iva cop", "iva", "impuesto"),
    "total_cop": ("total_cop", "total cop", "total"),
}


class StructuredDocumentExtractor:
    """Parse known synthetic labels and validate deterministic business constraints."""

    def extract(
        self,
        *,
        document_id: str,
        document_type: DocumentType,
        pages: tuple[DocumentPage, ...],
        created_at: str,
    ) -> StructuredExtractionOutput:
        if document_type is DocumentType.UNSUPPORTED:
            return StructuredExtractionOutput(None, ())

        values: dict[str, str] = {}
        field_pages: dict[str, DocumentPage] = {}
        line_rows: list[tuple[DocumentPage, tuple[str, ...]]] = []
        for page in pages:
            self._collect_fields(page, values, field_pages)
            line_rows.extend((page, row) for row in self._collect_lines(page.page_text))

        if document_type is DocumentType.INVOICE:
            return self._invoice(document_id, pages, values, field_pages, line_rows, created_at)
        return self._quotation(document_id, pages, values, field_pages, line_rows, created_at)

    def _invoice(self, document_id, pages, values, field_pages, line_rows, created_at):
        findings: list[QualityFinding] = []
        parsed = self._parse_common(values, findings)
        lines, line_results = self._invoice_lines(line_rows, created_at, findings)
        required = (
            "invoice_number", "supplier_name_raw", "issue_date",
            "currency", "subtotal_cop", "tax_cop", "total_cop",
        )
        findings.extend(validate_required({**values, **parsed}, required))
        findings.extend(validate_document_totals(
            subtotal=parsed["subtotal_cop"], tax=parsed["tax_cop"], total=parsed["total_cop"]
        ))
        findings.extend(validate_line_totals(lines))
        findings.extend(validate_subtotal(lines, parsed["subtotal_cop"]))
        if not lines:
            findings.append(QualityFinding(
                code="missing_document_lines", severity="error", field="lines",
                message="At least one invoice line is required."
            ))
        status = self._status(findings, pages)
        results = self._field_results(
            target_entity="invoice", values=values, field_pages=field_pages,
            created_at=created_at
        ) + line_results
        source_location_id = pages[0].source_location.source_location_id
        return StructuredExtractionOutput(
            Invoice(
                invoice_id=values.get("invoice_id") or _stable_entity_id("INV", document_id), document_id=document_id,
                invoice_number=values.get("invoice_number"),
                supplier_name_raw=values.get("supplier_name_raw"),
                supplier_id=values.get("supplier_id"), issue_date=parsed["issue_date"],
                related_order_id=values.get("related_order_id"), currency=values.get("currency"),
                subtotal_cop=parsed["subtotal_cop"], tax_cop=parsed["tax_cop"],
                total_cop=parsed["total_cop"], record_status=status,
                source_location_id=source_location_id, lines=tuple(lines),
                extraction_results=tuple(results),
            ), tuple(findings)
        )

    def _quotation(self, document_id, pages, values, field_pages, line_rows, created_at):
        findings: list[QualityFinding] = []
        parsed = self._parse_common(values, findings)
        valid_until = _parse_date(values.get("valid_until"), "valid_until", findings)
        lines, line_results = self._quotation_lines(line_rows, created_at, findings)
        required = (
            "quotation_number", "supplier_name_raw", "issue_date",
            "currency", "subtotal_cop", "tax_cop", "total_cop",
        )
        findings.extend(validate_required({**values, **parsed}, required))
        findings.extend(validate_document_totals(
            subtotal=parsed["subtotal_cop"], tax=parsed["tax_cop"], total=parsed["total_cop"]
        ))
        findings.extend(validate_line_totals(lines))
        findings.extend(validate_subtotal(lines, parsed["subtotal_cop"]))
        findings.extend(validate_quotation_dates(issue_date=parsed["issue_date"], valid_until=valid_until))
        if not lines:
            findings.append(QualityFinding(
                code="missing_document_lines", severity="error", field="lines",
                message="At least one quotation line is required."
            ))
        status = self._status(findings, pages)
        results = self._field_results(
            target_entity="quotation", values=values, field_pages=field_pages,
            created_at=created_at
        ) + line_results
        source_location_id = pages[0].source_location.source_location_id
        return StructuredExtractionOutput(
            Quotation(
                quotation_id=values.get("quotation_id") or _stable_entity_id("QUO", document_id), document_id=document_id,
                quotation_number=values.get("quotation_number"),
                supplier_name_raw=values.get("supplier_name_raw"),
                supplier_id=values.get("supplier_id"), issue_date=parsed["issue_date"],
                valid_until=valid_until, currency=values.get("currency"),
                subtotal_cop=parsed["subtotal_cop"], tax_cop=parsed["tax_cop"],
                total_cop=parsed["total_cop"], record_status=status,
                source_location_id=source_location_id, lines=tuple(lines),
                extraction_results=tuple(results),
            ), tuple(findings)
        )

    def _collect_fields(self, page, values, field_pages):
        lines = tuple(page.page_text.splitlines())
        for field, aliases in _LABELS.items():
            if field in values:
                continue
            for alias in aliases:
                alias_norm = _normalize(alias)
                for original_line in lines:
                    normalized_line = _normalize(original_line).strip()
                    match = re.match(
                        rf"^{re.escape(alias_norm)}\s*[:#-]?\s*(.+?)\s*$",
                        normalized_line,
                    )
                    if not match:
                        continue
                    if ":" in original_line:
                        raw = original_line.split(":", 1)[1].strip(" |;,")
                    else:
                        raw = original_line[len(alias):].strip(" |;,")
                    if not raw:
                        raw = match.group(1).strip(" |;,")
                    if raw:
                        values[field] = raw
                        field_pages[field] = page
                        break
                if field in values:
                    break

    def _collect_lines(self, text: str) -> list[tuple[str, ...]]:
        rows: list[tuple[str, ...]] = []
        pattern = (
            r"LINE[^\n]*?((?:INVL|QUOL)-[A-Z0-9-]+)\s*\|\s*"
            r"([^|\n]+)\|\s*(PRD-[A-Z0-9-]+)\s*\|\s*"
            r"(-?\d+(?:\.\d+)?)\s*\|\s*"
            r"(-?\d+(?:\.\d+)?)\s*[|/]\s*"
            r"(-?\d+(?:\.\d+)?)"
        )
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            rows.append(tuple(part.strip() for part in match.groups()))
        return rows

    def _parse_common(self, values, findings):
        return {
            "issue_date": _parse_date(values.get("issue_date"), "issue_date", findings),
            "subtotal_cop": _parse_decimal(values.get("subtotal_cop"), "subtotal_cop", findings),
            "tax_cop": _parse_decimal(values.get("tax_cop"), "tax_cop", findings),
            "total_cop": _parse_decimal(values.get("total_cop"), "total_cop", findings),
        }

    def _invoice_lines(self, rows, created_at, findings):
        lines=[]; results=[]
        for page, row in rows:
            line_id, name, product_id, qty_raw, unit_raw, total_raw = row
            qty=_parse_decimal(qty_raw, "quantity", findings)
            unit=_parse_decimal(unit_raw, "unit_price_cop", findings)
            total=_parse_decimal(total_raw, "line_total_cop", findings)
            if None in {qty, unit, total}:
                continue
            status = RecordStatus.ACCEPTED if page.processing_status.value == "processed" else RecordStatus.PENDING_REVIEW
            lines.append(InvoiceLine(line_id, name, product_id or None, qty, unit, total, status, page.source_location.source_location_id))
            results.extend(self._line_results("invoice_line", line_id, row, page, created_at))
        return lines, results

    def _quotation_lines(self, rows, created_at, findings):
        lines=[]; results=[]
        for page, row in rows:
            line_id, name, product_id, qty_raw, unit_raw, total_raw = row
            qty=_parse_decimal(qty_raw, "quantity", findings)
            unit=_parse_decimal(unit_raw, "unit_price_cop", findings)
            total=_parse_decimal(total_raw, "line_total_cop", findings)
            if None in {qty, unit, total}:
                continue
            status = RecordStatus.ACCEPTED if page.processing_status.value == "processed" else RecordStatus.PENDING_REVIEW
            lines.append(QuotationLine(line_id, name, product_id or None, qty, unit, total, status, page.source_location.source_location_id))
            results.extend(self._line_results("quotation_line", line_id, row, page, created_at))
        return lines, results

    def _field_results(self, *, target_entity, values, field_pages, created_at):
        results=[]
        for field, value in values.items():
            page=field_pages[field]
            results.append(_result(target_entity, field, value, page, created_at))
        return results

    def _line_results(self, target_entity, line_id, row, page, created_at):
        names=("line_id", "product_name_raw", "product_id", "quantity", "unit_price_cop", "line_total_cop")
        return [_result(target_entity, f"{line_id}.{name}", value, page, created_at) for name, value in zip(names, row)]

    def _status(self, findings, pages):
        if findings or any(page.processing_status.value != "processed" for page in pages):
            return RecordStatus.PENDING_REVIEW
        return RecordStatus.ACCEPTED



def _stable_entity_id(prefix: str, document_id: str) -> str:
    digest = sha256(f"{prefix}|{document_id}".encode("utf-8")).hexdigest()[:12].upper()
    return f"{prefix}-{digest}"

def _result(target_entity, field, value, page, created_at):
    method = "deterministic_label_parser_v1"
    confidence = 1.0 if page.extraction_method is PageExtractionMethod.NATIVE_TEXT else page.ocr_confidence
    review = ReviewStatus.ACCEPTED if page.processing_status.value == "processed" else ReviewStatus.PENDING
    key=f"{page.document_id}|{target_entity}|{field}|{value}"
    extraction_id="EXT-" + sha256(key.encode("utf-8")).hexdigest()[:16].upper()
    return ExtractionResult(
        extraction_id=extraction_id,
        source_location_id=page.source_location.source_location_id,
        document_page_id=page.document_page_id,
        target_entity=target_entity,
        target_field=field,
        raw_value=value,
        proposed_value=value,
        method=method,
        page_number=page.page_number,
        text_excerpt=value[:240],
        confidence=confidence,
        review_status=review,
        created_at=created_at,
        ocr_engine=page.ocr_engine,
        ocr_engine_version=page.ocr_engine_version,
        ocr_confidence=page.ocr_confidence,
    )


def _normalize(value: str) -> str:
    decomposed=unicodedata.normalize("NFKD", value)
    ascii_text="".join(char for char in decomposed if not unicodedata.combining(char))
    return ascii_text.lower()


def _parse_decimal(value: str | None, field: str, findings: list[QualityFinding]) -> Decimal | None:
    if value is None:
        return None
    candidate=value.strip().replace("COP", "").replace("cop", "").replace(",", "")
    match=re.search(r"-?\d+(?:\.\d+)?", candidate)
    if not match:
        findings.append(QualityFinding("invalid_decimal", "error", field, f"Invalid decimal value for {field}.", value))
        return None
    try:
        return Decimal(match.group(0))
    except InvalidOperation:
        findings.append(QualityFinding("invalid_decimal", "error", field, f"Invalid decimal value for {field}.", value))
        return None


def _parse_date(value: str | None, field: str, findings: list[QualityFinding]) -> date | None:
    if value is None:
        return None
    match=re.search(r"\d{4}-\d{2}-\d{2}", value)
    if not match:
        findings.append(QualityFinding("invalid_date", "error", field, f"Invalid ISO date for {field}.", value))
        return None
    try:
        return date.fromisoformat(match.group(0))
    except ValueError:
        findings.append(QualityFinding("invalid_date", "error", field, f"Invalid ISO date for {field}.", value))
        return None
