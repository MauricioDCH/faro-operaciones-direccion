"""Typed results for deterministic Excel ingestion."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import date
from decimal import Decimal
from hashlib import sha256
from typing import Any

from faro.provenance.models import SourceFile, SpreadsheetSourceLocation


Scalar = str | bool | int | Decimal | date | None


def display_value(value: object) -> str | None:
    """Return a stable textual representation for evidence and findings."""

    if value is None:
        return None
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, tuple):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    if hasattr(value, "to_dict"):
        return value.to_dict()
    return value


@dataclass(frozen=True, slots=True)
class IngestionFinding:
    """Structured Excel ingestion or data-quality finding."""

    finding_id: str
    rule_id: str
    code: str
    category: str
    severity: str
    message: str
    source_location_id: str | None
    entity_type: str | None = None
    record_id: str | None = None
    field: str | None = None
    observed_value: str | None = None
    expected_value: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def make_finding(
    *,
    rule_id: str,
    code: str,
    category: str,
    severity: str,
    message: str,
    source_location_id: str | None,
    entity_type: str | None = None,
    record_id: str | None = None,
    field: str | None = None,
    observed_value: object = None,
    expected_value: object = None,
) -> IngestionFinding:
    """Build a deterministic structured finding."""

    material = "|".join(
        item or ""
        for item in (code, source_location_id, record_id, field)
    )
    finding_id = f"FND-{sha256(material.encode('utf-8')).hexdigest()[:16].upper()}"
    return IngestionFinding(
        finding_id=finding_id,
        rule_id=rule_id,
        code=code,
        category=category,
        severity=severity,
        message=message,
        source_location_id=source_location_id,
        entity_type=entity_type,
        record_id=record_id,
        field=field,
        observed_value=display_value(observed_value),
        expected_value=display_value(expected_value),
    )


@dataclass(frozen=True, slots=True)
class TabularRecord:
    """A typed row with row- and field-level provenance."""

    contract_id: str
    entity_type: str
    record_id: str
    source_file_id: str
    source_location_id: str
    row_number: int
    values: dict[str, Scalar]
    raw_values: dict[str, str | None]
    field_locations: tuple[SpreadsheetSourceLocation, ...]
    record_status: str = "accepted"

    def with_status(self, status: str) -> "TabularRecord":
        return replace(self, record_status=status)

    def location_for(self, field: str) -> SpreadsheetSourceLocation:
        for location in self.field_locations:
            if location.column == field:
                return location
        raise KeyError(field)

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_id": self.contract_id,
            "entity_type": self.entity_type,
            "record_id": self.record_id,
            "source_file_id": self.source_file_id,
            "source_location_id": self.source_location_id,
            "row_number": self.row_number,
            "values": _json_value(self.values),
            "raw_values": self.raw_values,
            "field_locations": [item.to_dict() for item in self.field_locations],
            "record_status": self.record_status,
        }


@dataclass(frozen=True, slots=True)
class ExcelIngestionBatch:
    """Complete deterministic result for the approved Excel sources."""

    source_files: tuple[SourceFile, ...]
    records: tuple[TabularRecord, ...]
    findings: tuple[IngestionFinding, ...]
    source_hashes_before: dict[str, str]
    source_hashes_after: dict[str, str]
    raw_files_unchanged: bool
    status: str

    @property
    def accepted_records(self) -> tuple[TabularRecord, ...]:
        return tuple(item for item in self.records if item.record_status == "accepted")

    @property
    def rejected_records(self) -> tuple[TabularRecord, ...]:
        return tuple(item for item in self.records if item.record_status == "rejected")

    def records_for(self, entity_type: str) -> tuple[TabularRecord, ...]:
        return tuple(item for item in self.records if item.entity_type == entity_type)

    def to_dict(self, include_records: bool = True) -> dict[str, Any]:
        counts_by_entity: dict[str, int] = {}
        for record in self.records:
            counts_by_entity[record.entity_type] = (
                counts_by_entity.get(record.entity_type, 0) + 1
            )
        payload: dict[str, Any] = {
            "status": self.status,
            "raw_files_unchanged": self.raw_files_unchanged,
            "counts": {
                "source_files": len(self.source_files),
                "records": len(self.records),
                "accepted_records": len(self.accepted_records),
                "rejected_records": len(self.rejected_records),
                "findings": len(self.findings),
                "errors": sum(
                    item.severity == "error" for item in self.findings
                ),
                "warnings": sum(
                    item.severity == "warning" for item in self.findings
                ),
                "by_entity": counts_by_entity,
            },
            "source_files": [item.to_dict() for item in self.source_files],
            "source_hashes_before": self.source_hashes_before,
            "source_hashes_after": self.source_hashes_after,
            "findings": [item.to_dict() for item in self.findings],
        }
        if include_records:
            payload["records"] = [item.to_dict() for item in self.records]
        return payload
