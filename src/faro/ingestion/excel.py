"""Deterministic ingestion and validation for Faro's approved Excel books."""

from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable

from faro.ingestion.contracts import (
    BOOLEAN,
    DATE,
    DECIMAL,
    STRING,
    FieldSpec,
    SHEET_SPECS,
    SPECS_BY_FILE,
    SheetSpec,
)
from faro.ingestion.models import (
    ExcelIngestionBatch,
    IngestionFinding,
    Scalar,
    TabularRecord,
    display_value,
    make_finding,
)
from faro.ingestion.xlsx import (
    RawCell,
    RawSheet,
    XlsxFormatError,
    XlsxWorkbook,
    column_letters,
)
from faro.quality.tabular import validate_tabular_records
from faro.provenance.models import (
    SourceFile,
    SpreadsheetSourceLocation,
    sha256_file,
    stable_spreadsheet_location_id,
)


EXCEL_EPOCH = datetime(1899, 12, 30)
CONTRACT_VERSION = "1.4.2"
DATASET_VERSION = "0.1.0"
SEED = 20260731


_display = display_value
_finding = make_finding

def _as_decimal(raw: object) -> Decimal:
    if isinstance(raw, bool):
        raise InvalidOperation
    return Decimal(str(raw).strip())


def _as_date(raw: object) -> date:
    if isinstance(raw, bool):
        raise ValueError
    text = str(raw).strip()
    try:
        serial = Decimal(text)
    except InvalidOperation:
        return date.fromisoformat(text)
    if serial < 1:
        raise ValueError
    return (EXCEL_EPOCH + timedelta(days=float(serial))).date()


def _convert(raw: object, field: FieldSpec) -> Scalar:
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return None
    if field.value_type == STRING:
        return str(raw).strip()
    if field.value_type == DECIMAL:
        return _as_decimal(raw)
    if field.value_type == DATE:
        return _as_date(raw)
    if field.value_type == BOOLEAN:
        if isinstance(raw, bool):
            return raw
        normalized = str(raw).strip().casefold()
        if normalized in {"true", "1", "yes", "sí", "si"}:
            return True
        if normalized in {"false", "0", "no"}:
            return False
        raise ValueError
    raise ValueError(f"Unsupported field type: {field.value_type}")


def _record_id(spec: SheetSpec, values: dict[str, Scalar], row: int) -> str:
    parts = [values.get(name) for name in spec.record_id_fields]
    if all(part is not None for part in parts):
        return "|".join(_display(part) or "" for part in parts)
    return f"{spec.entity_type.upper()}-ROW-{row}"


def _row_location(
    digest: str, source_file_id: str, sheet_name: str, row_number: int
) -> SpreadsheetSourceLocation:
    return SpreadsheetSourceLocation(
        source_location_id=stable_spreadsheet_location_id(
            digest, sheet_name, row_number, None
        ),
        source_file_id=source_file_id,
        sheet=sheet_name,
        row=row_number,
        column=None,
        cell_reference=None,
        raw_value=None,
    )


def _cell_location(
    *,
    digest: str,
    source_file_id: str,
    sheet_name: str,
    row_number: int,
    column_index: int,
    column_name: str,
    raw_value: object,
) -> SpreadsheetSourceLocation:
    return SpreadsheetSourceLocation(
        source_location_id=stable_spreadsheet_location_id(
            digest, sheet_name, row_number, column_name
        ),
        source_file_id=source_file_id,
        sheet=sheet_name,
        row=row_number,
        column=column_name,
        cell_reference=f"{column_letters(column_index)}{row_number}",
        raw_value=_display(raw_value),
    )


def _header_values(sheet: RawSheet) -> tuple[dict[str, int], list[str], int]:
    if not sheet.rows:
        return {}, [], 1
    header = sheet.rows[0]
    names: dict[str, int] = {}
    duplicates: list[str] = []
    for index, cell in sorted(header.cells.items()):
        name = str(cell.raw_value or "").strip()
        if not name:
            continue
        if name in names:
            duplicates.append(name)
        else:
            names[name] = index
    return names, duplicates, header.row_number


def _parse_sheet(
    sheet: RawSheet,
    spec: SheetSpec,
    source_file: SourceFile,
) -> tuple[list[TabularRecord], list[IngestionFinding]]:
    digest = source_file.sha256
    findings: list[IngestionFinding] = []
    records: list[TabularRecord] = []
    headers, duplicates, header_row = _header_values(sheet)
    workbook_location = stable_spreadsheet_location_id(
        digest, sheet.name, header_row, None
    )
    for name in duplicates:
        findings.append(
            _finding(
                rule_id="RULE-XLSX-HEADER-001",
                code="duplicate_header",
                category="structure",
                severity="error",
                message=f"Header appears more than once: {name}.",
                source_location_id=workbook_location,
                entity_type=spec.entity_type,
                field=name,
                observed_value=name,
                expected_value="unique header",
            )
        )
    missing_headers = [
        field.name for field in spec.fields if field.required and field.name not in headers
    ]
    for name in missing_headers:
        findings.append(
            _finding(
                rule_id="RULE-XLSX-HEADER-001",
                code="missing_required_header",
                category="structure",
                severity="error",
                message=f"Required header is missing: {name}.",
                source_location_id=workbook_location,
                entity_type=spec.entity_type,
                field=name,
                expected_value=name,
            )
        )
    expected = set(spec.field_names)
    for name in sorted(set(headers).difference(expected)):
        findings.append(
            _finding(
                rule_id="RULE-XLSX-HEADER-002",
                code="unexpected_header",
                category="structure",
                severity="warning",
                message=f"Header is not part of {spec.contract_id}: {name}.",
                source_location_id=workbook_location,
                entity_type=spec.entity_type,
                field=name,
                observed_value=name,
            )
        )
    if missing_headers or duplicates:
        return records, findings

    for row in sheet.rows[1:]:
        if not any(
            cell.raw_value not in (None, "") for cell in row.cells.values()
        ):
            continue
        values: dict[str, Scalar] = {}
        raw_values: dict[str, str | None] = {}
        locations: list[SpreadsheetSourceLocation] = []
        row_findings: list[IngestionFinding] = []
        for field in spec.fields:
            index = headers.get(field.name)
            assert index is not None
            raw_cell = row.cells.get(
                index,
                RawCell(
                    reference=f"{column_letters(index)}{row.row_number}",
                    raw_value=None,
                ),
            )
            location = _cell_location(
                digest=digest,
                source_file_id=source_file.source_file_id,
                sheet_name=sheet.name,
                row_number=row.row_number,
                column_index=index,
                column_name=field.name,
                raw_value=raw_cell.raw_value,
            )
            locations.append(location)
            raw_values[field.name] = _display(raw_cell.raw_value)
            if raw_cell.formula is not None:
                row_findings.append(
                    _finding(
                        rule_id="RULE-XLSX-FORMULA-001",
                        code="formula_cell_not_allowed",
                        category="structure",
                        severity="error",
                        message="Raw Excel inputs must contain values, not formulas.",
                        source_location_id=location.source_location_id,
                        entity_type=spec.entity_type,
                        field=field.name,
                        observed_value=raw_cell.formula,
                        expected_value="literal value",
                    )
                )
            try:
                value = _convert(raw_cell.raw_value, field)
            except (ValueError, InvalidOperation):
                value = None
                code = "invalid_date" if field.value_type == DATE else "invalid_type"
                rule_id = (
                    "RULE-DATE-001" if field.value_type == DATE else "RULE-XLSX-TYPE-001"
                )
                row_findings.append(
                    _finding(
                        rule_id=rule_id,
                        code=code,
                        category="data_quality",
                        severity="error",
                        message=(
                            f"Value cannot be converted to {field.value_type}: "
                            f"{field.name}."
                        ),
                        source_location_id=location.source_location_id,
                        entity_type=spec.entity_type,
                        field=field.name,
                        observed_value=raw_cell.raw_value,
                        expected_value=field.value_type,
                    )
                )
            values[field.name] = value
            raw_is_empty = raw_cell.raw_value is None or (
                isinstance(raw_cell.raw_value, str)
                and not raw_cell.raw_value.strip()
            )
            if field.required and raw_is_empty:
                row_findings.append(
                    _finding(
                        rule_id="RULE-REQUIRED-001",
                        code="missing_required_field",
                        category="data_quality",
                        severity="error",
                        message=f"Required field is missing: {field.name}.",
                        source_location_id=location.source_location_id,
                        entity_type=spec.entity_type,
                        field=field.name,
                        expected_value="non-empty value",
                    )
                )
            if isinstance(value, Decimal) and field.minimum is not None:
                if value < field.minimum:
                    row_findings.append(
                        _finding(
                            rule_id="RULE-XLSX-RANGE-001",
                            code="value_below_minimum",
                            category="data_quality",
                            severity="error",
                            message=f"Value is below the allowed minimum: {field.name}.",
                            source_location_id=location.source_location_id,
                            entity_type=spec.entity_type,
                            field=field.name,
                            observed_value=value,
                            expected_value=f">={field.minimum}",
                        )
                    )
            if isinstance(value, str) and field.allowed_values is not None:
                if value not in field.allowed_values:
                    row_findings.append(
                        _finding(
                            rule_id="RULE-XLSX-CATALOG-001",
                            code="invalid_catalog_value",
                            category="data_quality",
                            severity="error",
                            message=f"Value is not in the approved catalog: {field.name}.",
                            source_location_id=location.source_location_id,
                            entity_type=spec.entity_type,
                            field=field.name,
                            observed_value=value,
                            expected_value=", ".join(sorted(field.allowed_values)),
                        )
                    )
        record_id = _record_id(spec, values, row.row_number)
        row_findings = [replace(item, record_id=record_id) for item in row_findings]
        row_location = _row_location(
            digest, source_file.source_file_id, sheet.name, row.row_number
        )
        records.append(
            TabularRecord(
                contract_id=spec.contract_id,
                entity_type=spec.entity_type,
                record_id=record_id,
                source_file_id=source_file.source_file_id,
                source_location_id=row_location.source_location_id,
                row_number=row.row_number,
                values=values,
                raw_values=raw_values,
                field_locations=tuple(locations),
                record_status=(
                    "rejected"
                    if any(item.severity == "error" for item in row_findings)
                    else "accepted"
                ),
            )
        )
        findings.extend(row_findings)
    return records, findings



def _apply_error_statuses(
    records: list[TabularRecord], findings: Iterable[IngestionFinding]
) -> list[TabularRecord]:
    rejected = {
        item.record_id
        for item in findings
        if item.severity == "error" and item.record_id is not None
    }
    return [
        item.with_status("rejected") if item.record_id in rejected else item
        for item in records
    ]


class ExcelIngestionService:
    """Ingest all approved Excel workbooks and preserve cell provenance."""

    def __init__(self, ingested_at: datetime | None = None) -> None:
        self.ingested_at = ingested_at or datetime.now(timezone.utc)

    def ingest(self, raw_dir: Path) -> ExcelIngestionBatch:
        source_files: list[SourceFile] = []
        records: list[TabularRecord] = []
        findings: list[IngestionFinding] = []
        before: dict[str, str] = {}
        after: dict[str, str] = {}
        for file_name, specs in SPECS_BY_FILE.items():
            path = raw_dir / file_name
            if not path.is_file():
                findings.append(
                    _finding(
                        rule_id="RULE-XLSX-SOURCE-001",
                        code="missing_source_file",
                        category="structure",
                        severity="error",
                        message=f"Required Excel source is missing: {file_name}.",
                        source_location_id=None,
                        observed_value=str(path),
                        expected_value=file_name,
                    )
                )
                continue
            digest = sha256_file(path)
            before[file_name] = digest
            contract_ids = ",".join(spec.contract_id for spec in specs)
            source_file = SourceFile.from_path(
                path,
                file_hash=digest,
                ingested_at=self.ingested_at,
                source_type="xlsx",
                contract_id=contract_ids,
                contract_version=CONTRACT_VERSION,
                dataset_version=DATASET_VERSION,
                seed=SEED,
            )
            source_files.append(source_file)
            try:
                with XlsxWorkbook(path) as workbook:
                    for spec in specs:
                        if spec.sheet_name not in workbook.sheet_names:
                            findings.append(
                                _finding(
                                    rule_id="RULE-XLSX-SHEET-001",
                                    code="missing_required_sheet",
                                    category="structure",
                                    severity="error",
                                    message=(
                                        f"Required sheet is missing: {spec.sheet_name}."
                                    ),
                                    source_location_id=source_file.source_file_id,
                                    entity_type=spec.entity_type,
                                    expected_value=spec.sheet_name,
                                )
                            )
                            continue
                        parsed_records, parsed_findings = _parse_sheet(
                            workbook.read_sheet(spec.sheet_name),
                            spec,
                            source_file,
                        )
                        records.extend(parsed_records)
                        findings.extend(parsed_findings)
            except XlsxFormatError as exc:
                findings.append(
                    _finding(
                        rule_id="RULE-XLSX-FORMAT-001",
                        code=exc.code,
                        category="structure",
                        severity="error",
                        message=exc.message,
                        source_location_id=source_file.source_file_id,
                        observed_value=file_name,
                        expected_value="valid .xlsx package",
                    )
                )
            after[file_name] = sha256_file(path)
            if after[file_name] != before[file_name]:
                findings.append(
                    _finding(
                        rule_id="RULE-RAW-IMMUTABLE-001",
                        code="raw_source_modified",
                        category="integrity",
                        severity="error",
                        message="Raw source hash changed during ingestion.",
                        source_location_id=source_file.source_file_id,
                        observed_value=after[file_name],
                        expected_value=before[file_name],
                    )
                )
        cross_findings = validate_tabular_records(records)
        findings.extend(cross_findings)
        records = _apply_error_statuses(records, findings)
        unchanged = before == after and len(before) == len(SPECS_BY_FILE)
        status = (
            "failed"
            if any(
                item.severity == "error" and item.record_id is None
                for item in findings
            )
            else "completed_with_findings"
            if findings
            else "completed"
        )
        return ExcelIngestionBatch(
            source_files=tuple(source_files),
            records=tuple(records),
            findings=tuple(findings),
            source_hashes_before=before,
            source_hashes_after=after,
            raw_files_unchanged=unchanged,
            status=status,
        )
