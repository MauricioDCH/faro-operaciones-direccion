"""Canonical observations and cross-source selection for Faro consolidation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from hashlib import sha256
import json
import re
from typing import Any, Iterable

from faro.domain.documents import DocumentExtraction, ExtractionResult, Invoice, Quotation
from faro.ingestion.models import IngestionFinding, TabularRecord, make_finding
from faro.ingestion.ubl_xml import UblIngestionResult
from faro.provenance.models import SourceFile

SOURCE_PRIORITIES = {
    "ubl_xml": 100,
    "xlsx": 90,
    "pdf": 85,
    "image": 80,
    "json": 70,
    "ndjson": 70,
    "csv": 60,
    "tsv": 60,
}


def _json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, tuple):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if hasattr(value, "value"):
        return value.value
    return value


def canonical_json(payload: dict[str, Any]) -> str:
    """Return stable JSON for hashes and SQLite payloads."""

    return json.dumps(
        _json_value(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def payload_hash(payload: dict[str, Any]) -> str:
    return sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def stable_id(prefix: str, *parts: object) -> str:
    material = "|".join("" if part is None else str(part) for part in parts)
    return f"{prefix}-{sha256(material.encode('utf-8')).hexdigest()[:16].upper()}"


def normalize_name(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def source_format(source_file: SourceFile) -> str:
    return (
        source_file.detected_format
        or source_file.source_type
        or source_file.ingestion_adapter
        or "unknown"
    ).casefold()


@dataclass(frozen=True, slots=True)
class RecordObservation:
    observation_id: str
    entity_type: str
    record_id: str
    source_file_id: str
    source_location_id: str | None
    source_format: str
    source_priority: int
    record_status: str
    payload: dict[str, Any]
    payload_hash: str


@dataclass(frozen=True, slots=True)
class TransformationEvent:
    transformation_id: str
    entity_type: str
    record_id: str
    source_location_id: str | None
    rule_id: str
    input_hash: str
    output_hash: str
    created_at: str


@dataclass(frozen=True, slots=True)
class CanonicalizationResult:
    canonical_records: tuple[RecordObservation, ...]
    findings: tuple[IngestionFinding, ...]
    transformations: tuple[TransformationEvent, ...]


def observation(
    *,
    entity_type: str,
    record_id: str,
    source_file: SourceFile,
    source_location_id: str | None,
    record_status: str,
    payload: dict[str, Any],
) -> RecordObservation:
    fmt = source_format(source_file)
    digest = payload_hash(payload)
    return RecordObservation(
        observation_id=stable_id(
            "OBS",
            entity_type,
            record_id,
            source_file.source_file_id,
            source_location_id,
            digest,
        ),
        entity_type=entity_type,
        record_id=record_id,
        source_file_id=source_file.source_file_id,
        source_location_id=source_location_id,
        source_format=fmt,
        source_priority=SOURCE_PRIORITIES.get(fmt, 50),
        record_status=record_status,
        payload=_json_value(payload),
        payload_hash=digest,
    )


def observations_from_tabular(
    source_files: Iterable[SourceFile], records: Iterable[TabularRecord]
) -> tuple[RecordObservation, ...]:
    sources = {item.source_file_id: item for item in source_files}
    result: list[RecordObservation] = []
    for record in records:
        source = sources[record.source_file_id]
        payload = dict(record.values)
        if record.entity_type == "inventory_snapshot":
            payload["available_quantity"] = (
                payload.get("stock_on_hand", Decimal("0"))
                - payload.get("committed_quantity", Decimal("0"))
            )
        payload["record_status"] = record.record_status
        payload["source_location_id"] = record.source_location_id
        result.append(
            observation(
                entity_type=record.entity_type,
                record_id=record.record_id,
                source_file=source,
                source_location_id=record.source_location_id,
                record_status=record.record_status,
                payload=payload,
            )
        )
    return tuple(result)


def _invoice_key(invoice: Invoice) -> str:
    supplier = invoice.supplier_id or normalize_name(invoice.supplier_name_raw)
    return stable_id(
        "INV",
        supplier,
        invoice.invoice_number or invoice.invoice_id,
        invoice.issue_date,
    )


def _quotation_key(quotation: Quotation) -> str:
    supplier = quotation.supplier_id or normalize_name(quotation.supplier_name_raw)
    return stable_id(
        "QUO",
        supplier,
        quotation.quotation_number or quotation.quotation_id,
        quotation.issue_date,
    )


def observations_from_document(
    extraction: DocumentExtraction,
) -> tuple[RecordObservation, ...]:
    source = extraction.source_file
    status = extraction.record_status.value
    result: list[RecordObservation] = [
        observation(
            entity_type="document",
            record_id=extraction.document_id,
            source_file=source,
            source_location_id=(
                extraction.pages[0].source_location.source_location_id
                if extraction.pages
                else None
            ),
            record_status=status,
            payload={
                "document_id": extraction.document_id,
                "source_file_id": source.source_file_id,
                "document_type": extraction.document_type.value,
                "page_count": extraction.page_count,
                "classification_method": extraction.classification_method,
                "classification_confidence": extraction.classification_confidence,
                "processing_status": extraction.processing_status.value,
                "record_status": status,
            },
        )
    ]
    for page in extraction.pages:
        result.append(
            observation(
                entity_type="document_page",
                record_id=page.document_page_id,
                source_file=source,
                source_location_id=page.source_location.source_location_id,
                record_status=(
                    "accepted"
                    if status == "accepted" and page.processing_status.value == "processed"
                    else "pending_review"
                ),
                payload=page.to_dict(),
            )
        )
    structured = extraction.structured_document
    if isinstance(structured, Invoice):
        invoice_id = _invoice_key(structured)
        payload = structured.to_dict()
        payload.pop("lines", None)
        payload.pop("extraction_results", None)
        payload["source_invoice_id"] = structured.invoice_id
        payload["invoice_id"] = invoice_id
        result.append(
            observation(
                entity_type="invoice",
                record_id=invoice_id,
                source_file=source,
                source_location_id=structured.source_location_id,
                record_status=(
                    "accepted"
                    if status == "accepted" and structured.record_status.value == "accepted"
                    else "pending_review"
                ),
                payload=payload,
            )
        )
        for index, line in enumerate(structured.lines, start=1):
            line_id = stable_id(
                "INVL",
                invoice_id,
                line.product_id or normalize_name(line.product_name_raw),
                index,
            )
            line_payload = line.to_dict()
            line_payload["source_invoice_line_id"] = line.invoice_line_id
            line_payload["invoice_line_id"] = line_id
            line_payload["invoice_id"] = invoice_id
            result.append(
                observation(
                    entity_type="invoice_line",
                    record_id=line_id,
                    source_file=source,
                    source_location_id=line.source_location_id,
                    record_status=(
                        "accepted"
                        if status == "accepted" and line.record_status.value == "accepted"
                        else "pending_review"
                    ),
                    payload=line_payload,
                )
            )
    elif isinstance(structured, Quotation):
        quotation_id = _quotation_key(structured)
        payload = structured.to_dict()
        payload.pop("lines", None)
        payload.pop("extraction_results", None)
        payload["source_quotation_id"] = structured.quotation_id
        payload["quotation_id"] = quotation_id
        result.append(
            observation(
                entity_type="quotation",
                record_id=quotation_id,
                source_file=source,
                source_location_id=structured.source_location_id,
                record_status=(
                    "accepted"
                    if status == "accepted" and structured.record_status.value == "accepted"
                    else "pending_review"
                ),
                payload=payload,
            )
        )
        for index, line in enumerate(structured.lines, start=1):
            line_id = stable_id(
                "QUOL",
                quotation_id,
                line.product_id or normalize_name(line.product_name_raw),
                index,
            )
            line_payload = line.to_dict()
            line_payload["source_quotation_line_id"] = line.quotation_line_id
            line_payload["quotation_line_id"] = line_id
            line_payload["quotation_id"] = quotation_id
            result.append(
                observation(
                    entity_type="quotation_line",
                    record_id=line_id,
                    source_file=source,
                    source_location_id=line.source_location_id,
                    record_status=(
                        "accepted"
                        if status == "accepted" and line.record_status.value == "accepted"
                        else "pending_review"
                    ),
                    payload=line_payload,
                )
            )
    return tuple(result)


def observations_from_ubl(result: UblIngestionResult) -> tuple[RecordObservation, ...]:
    source = result.source_file
    status = "accepted" if result.status == "completed" else "pending_review"
    observations: list[RecordObservation] = [
        observation(
            entity_type="document",
            record_id=result.document_id,
            source_file=source,
            source_location_id=(
                result.field_locations[0].source_location_id
                if result.field_locations
                else None
            ),
            record_status=status,
            payload={
                "document_id": result.document_id,
                "source_file_id": source.source_file_id,
                "document_type": "invoice",
                "page_count": 1,
                "classification_method": "ubl_root_v1",
                "classification_confidence": 1.0,
                "processing_status": (
                    "processed" if status == "accepted" else "pending_review"
                ),
                "record_status": status,
                "ubl_version": result.ubl_version,
                "root_document_type": result.root_document_type,
            },
        )
    ]
    if result.structured_document is not None:
        invoice = result.structured_document
        invoice_id = _invoice_key(invoice)
        payload = invoice.to_dict()
        payload.pop("lines", None)
        payload.pop("extraction_results", None)
        payload["source_invoice_id"] = invoice.invoice_id
        payload["invoice_id"] = invoice_id
        observations.append(
            observation(
                entity_type="invoice",
                record_id=invoice_id,
                source_file=source,
                source_location_id=invoice.source_location_id,
                record_status=invoice.record_status.value,
                payload=payload,
            )
        )
        for index, line in enumerate(invoice.lines, start=1):
            line_id = stable_id(
                "INVL",
                invoice_id,
                line.product_id or normalize_name(line.product_name_raw),
                index,
            )
            line_payload = line.to_dict()
            line_payload["source_invoice_line_id"] = line.invoice_line_id
            line_payload["invoice_line_id"] = line_id
            line_payload["invoice_id"] = invoice_id
            observations.append(
                observation(
                    entity_type="invoice_line",
                    record_id=line_id,
                    source_file=source,
                    source_location_id=line.source_location_id,
                    record_status=line.record_status.value,
                    payload=line_payload,
                )
            )
    return tuple(observations)


def canonicalize(
    observations: Iterable[RecordObservation],
    *,
    created_at: str,
) -> CanonicalizationResult:
    """Select one accepted canonical record per business identifier."""

    groups: dict[tuple[str, str], list[RecordObservation]] = {}
    for item in observations:
        groups.setdefault((item.entity_type, item.record_id), []).append(item)

    canonical: list[RecordObservation] = []
    findings: list[IngestionFinding] = []
    transformations: list[TransformationEvent] = []
    for (entity_type, record_id), items in sorted(groups.items()):
        accepted = [item for item in items if item.record_status == "accepted"]
        if not accepted:
            continue
        accepted.sort(
            key=lambda item: (
                -item.source_priority,
                item.source_file_id,
                item.source_location_id or "",
                item.observation_id,
            )
        )
        selected = accepted[0]
        canonical.append(selected)
        distinct_hashes = {item.payload_hash for item in accepted}
        if len(accepted) > 1:
            exact = len(distinct_hashes) == 1
            findings.append(
                make_finding(
                    rule_id=(
                        "RULE-CROSS-SOURCE-DUPLICATE-001"
                        if exact
                        else "RULE-CROSS-SOURCE-CONFLICT-001"
                    ),
                    code=(
                        "duplicate_cross_source"
                        if exact
                        else "cross_source_conflict"
                    ),
                    category="consolidation",
                    severity="warning" if exact else "error",
                    message=(
                        "Equivalent accepted records were observed in multiple sources."
                        if exact
                        else "Accepted sources disagree; the configured priority selected the canonical record."
                    ),
                    source_location_id=selected.source_location_id,
                    entity_type=entity_type,
                    record_id=record_id,
                    observed_value=",".join(item.source_file_id for item in accepted),
                    expected_value=selected.source_file_id,
                )
            )
        transformations.append(
            TransformationEvent(
                transformation_id=stable_id(
                    "TRF", entity_type, record_id, selected.observation_id
                ),
                entity_type=entity_type,
                record_id=record_id,
                source_location_id=selected.source_location_id,
                rule_id="select_canonical_source_v1",
                input_hash=selected.payload_hash,
                output_hash=selected.payload_hash,
                created_at=created_at,
            )
        )
    return CanonicalizationResult(
        canonical_records=tuple(canonical),
        findings=tuple(findings),
        transformations=tuple(transformations),
    )


def extraction_results_from_document(
    extraction: DocumentExtraction,
) -> tuple[ExtractionResult, ...]:
    structured = extraction.structured_document
    return structured.extraction_results if structured is not None else ()
