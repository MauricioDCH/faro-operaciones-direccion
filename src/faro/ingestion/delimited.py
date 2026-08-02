"""Deterministic CSV and TSV ingestion with explicit profiles."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable, Sequence
import csv
import io

from faro.ingestion.contracts import (
    BOOLEAN,
    DATE,
    DECIMAL,
    STRING,
    FieldSpec,
    SheetSpec,
    spec_for_profile,
)
from faro.ingestion.formats import InputFormat, detect_input_format
from faro.ingestion.models import (
    DelimitedIngestionBatch,
    IngestionFinding,
    Scalar,
    TabularRecord,
    display_value,
    make_finding,
)
from faro.provenance.models import (
    DelimitedSourceLocation,
    SourceFile,
    sha256_file,
    stable_delimited_location_id,
)
from faro.quality.tabular import validate_tabular_records


ALLOWED_DELIMITERS = (",", ";", "\t", "|")
SUPPORTED_ENCODINGS = frozenset({"utf-8", "utf-8-sig"})
CONTRACT_VERSION = "1.6.0"
DATASET_VERSION = "0.1.0"
SEED = 20260731


class DelimitedFormatError(ValueError):
    """Raised when a delimited source violates its declared profile."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        record_number: int | None = None,
        row_number: int | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.record_number = record_number
        self.row_number = row_number


@dataclass(frozen=True, slots=True)
class DelimitedProfile:
    """Explicit parsing and target-entity configuration for one source."""

    profile_id: str
    format_id: InputFormat
    delimiter: str = "auto"
    encoding: str = "utf-8-sig"
    decimal_separator: str = "."
    thousands_separator: str | None = None
    date_format: str = "%Y-%m-%d"
    has_header: bool = True

    def validate(self) -> None:
        if self.format_id not in {InputFormat.CSV, InputFormat.TSV}:
            raise ValueError("Delimited profiles require csv or tsv format.")
        if self.delimiter != "auto" and self.delimiter not in ALLOWED_DELIMITERS:
            raise ValueError("Delimiter must be auto, comma, semicolon, tab, or pipe.")
        if self.encoding not in SUPPORTED_ENCODINGS:
            raise ValueError("Encoding must be utf-8 or utf-8-sig.")
        if self.decimal_separator not in {".", ","}:
            raise ValueError("Decimal separator must be '.' or ','.")
        if self.thousands_separator not in {None, ".", ",", " ", "'"}:
            raise ValueError("Unsupported thousands separator.")
        if self.thousands_separator == self.decimal_separator:
            raise ValueError("Thousands and decimal separators must differ.")
        if not self.date_format:
            raise ValueError("Date format cannot be empty.")
        if not self.has_header:
            raise ValueError("Headerless delimited files are not supported.")
        spec_for_profile(self.profile_id)

    @property
    def target_spec(self) -> SheetSpec:
        return spec_for_profile(self.profile_id)

    def to_dict(self, *, resolved_delimiter: str | None = None) -> dict[str, object]:
        return {
            "profile_id": self.profile_id,
            "format_id": self.format_id.value,
            "delimiter": resolved_delimiter or self.delimiter,
            "encoding": self.encoding,
            "decimal_separator": self.decimal_separator,
            "thousands_separator": self.thousands_separator,
            "date_format": self.date_format,
            "has_header": self.has_header,
            "contract_id": self.target_spec.contract_id,
            "entity_type": self.target_spec.entity_type,
        }


@dataclass(frozen=True, slots=True)
class DelimitedInput:
    """One file and the explicit profile used to ingest it."""

    path: Path
    profile: DelimitedProfile


@dataclass(frozen=True, slots=True)
class _DecodedSource:
    text: str
    encoding: str
    had_utf8_bom: bool


@dataclass(frozen=True, slots=True)
class _ParsedSource:
    source_file: SourceFile
    records: tuple[TabularRecord, ...]
    findings: tuple[IngestionFinding, ...]
    profile_metadata: dict[str, object]


def build_profile(
    profile_id: str,
    format_id: InputFormat | str,
    *,
    delimiter: str | None = None,
    encoding: str = "utf-8-sig",
    decimal_separator: str = ".",
    thousands_separator: str | None = None,
    date_format: str = "%Y-%m-%d",
) -> DelimitedProfile:
    """Build and validate a profile with portable defaults."""

    normalized_format = InputFormat(format_id)
    default_delimiter = "\t" if normalized_format is InputFormat.TSV else "auto"
    profile = DelimitedProfile(
        profile_id=profile_id,
        format_id=normalized_format,
        delimiter=default_delimiter if delimiter is None else delimiter,
        encoding=encoding,
        decimal_separator=decimal_separator,
        thousands_separator=thousands_separator,
        date_format=date_format,
    )
    profile.validate()
    return profile


def _decode_source(raw: bytes, profile: DelimitedProfile) -> _DecodedSource:
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        raise DelimitedFormatError(
            "unsupported_encoding",
            "UTF-16 input is not supported; export the file as UTF-8.",
        )
    had_bom = raw.startswith(b"\xef\xbb\xbf")
    codec = "utf-8-sig" if had_bom or profile.encoding == "utf-8-sig" else "utf-8"
    try:
        text = raw.decode(codec)
    except UnicodeDecodeError as exc:
        raise DelimitedFormatError(
            "invalid_utf8",
            "Delimited input must be valid UTF-8 or UTF-8 with BOM.",
        ) from exc
    if "\x00" in text:
        raise DelimitedFormatError(
            "binary_content_detected",
            "Delimited input contains NUL bytes and is not accepted as text.",
        )
    return _DecodedSource(
        text=text,
        encoding="utf-8-sig" if had_bom else "utf-8",
        had_utf8_bom=had_bom,
    )


def detect_delimiter(text: str) -> str:
    """Detect one allowed delimiter from the header or reject ambiguity."""

    sample = text[:65536]
    nonempty_lines = [line for line in sample.splitlines() if line.strip()]
    if not nonempty_lines:
        raise DelimitedFormatError("empty_source", "Delimited input is empty.")
    header_line = nonempty_lines[0]
    candidates: list[tuple[int, str]] = []
    for delimiter in ALLOWED_DELIMITERS:
        try:
            header = next(
                csv.reader([header_line], delimiter=delimiter, strict=True)
            )
        except (csv.Error, StopIteration):
            continue
        if len(header) >= 2:
            candidates.append((len(header), delimiter))
    if not candidates:
        raise DelimitedFormatError(
            "delimiter_not_detected",
            "Delimiter could not be determined; declare it explicitly.",
        )
    best_width = max(width for width, _delimiter in candidates)
    best = [delimiter for width, delimiter in candidates if width == best_width]
    if len(best) != 1:
        raise DelimitedFormatError(
            "ambiguous_delimiter",
            "Multiple delimiters are plausible; declare one explicitly.",
        )
    return best[0]


def _parse_decimal(raw: str, profile: DelimitedProfile) -> Decimal:
    normalized = raw.strip().replace("\u00a0", " ")
    if profile.thousands_separator:
        normalized = normalized.replace(profile.thousands_separator, "")
    if profile.decimal_separator == ",":
        normalized = normalized.replace(",", ".")
    if not normalized:
        raise InvalidOperation
    return Decimal(normalized)


def _convert(raw: str | None, field: FieldSpec, profile: DelimitedProfile) -> Scalar:
    if raw is None or not raw.strip():
        return None
    text = raw.strip()
    if field.value_type == STRING:
        return text
    if field.value_type == DECIMAL:
        return _parse_decimal(text, profile)
    if field.value_type == DATE:
        try:
            return datetime.strptime(text, profile.date_format).date()
        except ValueError:
            if profile.date_format == "%Y-%m-%d":
                return date.fromisoformat(text)
            raise
    if field.value_type == BOOLEAN:
        normalized = text.casefold()
        if normalized in {"true", "1", "yes", "sí", "si"}:
            return True
        if normalized in {"false", "0", "no"}:
            return False
        raise ValueError
    raise ValueError(f"Unsupported field type: {field.value_type}")


def _record_id(spec: SheetSpec, values: dict[str, Scalar], record_number: int) -> str:
    parts = [values.get(name) for name in spec.record_id_fields]
    if all(part is not None for part in parts):
        return "|".join(display_value(part) or "" for part in parts)
    return f"{spec.entity_type.upper()}-RECORD-{record_number}"


def _row_location(
    *,
    digest: str,
    source_file_id: str,
    record_number: int,
    row_number: int,
) -> DelimitedSourceLocation:
    return DelimitedSourceLocation(
        source_location_id=stable_delimited_location_id(
            digest, record_number, None
        ),
        source_file_id=source_file_id,
        record_number=record_number,
        row=row_number,
        column=None,
        raw_value=None,
    )


def _field_location(
    *,
    digest: str,
    source_file_id: str,
    record_number: int,
    row_number: int,
    column: str,
    raw_value: str | None,
) -> DelimitedSourceLocation:
    return DelimitedSourceLocation(
        source_location_id=stable_delimited_location_id(
            digest, record_number, column
        ),
        source_file_id=source_file_id,
        record_number=record_number,
        row=row_number,
        column=column,
        raw_value=raw_value,
    )


def _source_finding(
    *,
    source_file: SourceFile | None,
    code: str,
    message: str,
    observed_value: object = None,
    expected_value: object = None,
    entity_type: str | None = None,
) -> IngestionFinding:
    return make_finding(
        rule_id="RULE-DELIMITED-SOURCE-001",
        code=code,
        category="structure",
        severity="error",
        message=message,
        source_location_id=(source_file.source_file_id if source_file else None),
        entity_type=entity_type,
        observed_value=observed_value,
        expected_value=expected_value,
    )


def _validate_headers(
    headers: Sequence[str],
    *,
    spec: SheetSpec,
    source_file: SourceFile,
    digest: str,
) -> tuple[dict[str, int], list[IngestionFinding]]:
    normalized = [item.strip() for item in headers]
    header_location = stable_delimited_location_id(digest, 0, None)
    findings: list[IngestionFinding] = []
    positions: dict[str, int] = {}
    duplicates: set[str] = set()
    for index, name in enumerate(normalized):
        if not name:
            findings.append(
                make_finding(
                    rule_id="RULE-DELIMITED-HEADER-001",
                    code="empty_header",
                    category="structure",
                    severity="error",
                    message="Header names cannot be empty.",
                    source_location_id=header_location,
                    entity_type=spec.entity_type,
                    observed_value=index + 1,
                    expected_value="non-empty header",
                )
            )
            continue
        if name in positions:
            duplicates.add(name)
        else:
            positions[name] = index
    for name in sorted(duplicates):
        findings.append(
            make_finding(
                rule_id="RULE-DELIMITED-HEADER-001",
                code="duplicate_header",
                category="structure",
                severity="error",
                message=f"Header appears more than once: {name}.",
                source_location_id=header_location,
                entity_type=spec.entity_type,
                field=name,
                observed_value=name,
                expected_value="unique header",
            )
        )
    for field in spec.fields:
        if field.required and field.name not in positions:
            findings.append(
                make_finding(
                    rule_id="RULE-DELIMITED-HEADER-001",
                    code="missing_required_header",
                    category="structure",
                    severity="error",
                    message=f"Required header is missing: {field.name}.",
                    source_location_id=header_location,
                    entity_type=spec.entity_type,
                    field=field.name,
                    expected_value=field.name,
                )
            )
    expected = set(spec.field_names)
    for name in sorted(set(positions).difference(expected)):
        findings.append(
            make_finding(
                rule_id="RULE-DELIMITED-HEADER-002",
                code="unexpected_header",
                category="structure",
                severity="warning",
                message=f"Header is not part of {spec.contract_id}: {name}.",
                source_location_id=header_location,
                entity_type=spec.entity_type,
                field=name,
                observed_value=name,
            )
        )
    return positions, findings


def _parse_source(
    source: DelimitedInput,
    *,
    ingested_at: datetime,
    max_file_size_bytes: int,
    max_records: int,
    max_columns: int,
    max_field_characters: int,
) -> _ParsedSource:
    path = source.path
    profile = source.profile
    profile.validate()
    capability = detect_input_format(path)
    if capability is None or capability.format_id not in {InputFormat.CSV, InputFormat.TSV}:
        raise DelimitedFormatError(
            "unsupported_delimited_extension",
            f"Expected .csv or .tsv input: {path.name}.",
        )
    if capability.format_id is not profile.format_id:
        raise DelimitedFormatError(
            "format_profile_mismatch",
            f"Profile expects {profile.format_id.value}, but file is {capability.format_id.value}.",
        )
    if not path.is_file():
        raise DelimitedFormatError(
            "missing_source_file", f"Delimited source does not exist: {path}."
        )
    size = path.stat().st_size
    if size > max_file_size_bytes:
        raise DelimitedFormatError(
            "file_size_limit_exceeded",
            f"Delimited source exceeds {max_file_size_bytes} bytes.",
        )
    digest = sha256_file(path)
    decoded = _decode_source(path.read_bytes(), profile)
    delimiter = detect_delimiter(decoded.text) if profile.delimiter == "auto" else profile.delimiter
    media_type = "text/csv" if profile.format_id is InputFormat.CSV else "text/tab-separated-values"
    source_file = SourceFile.from_path(
        path,
        file_hash=digest,
        ingested_at=ingested_at,
        source_type=profile.format_id.value,
        contract_id=profile.target_spec.contract_id,
        contract_version=CONTRACT_VERSION,
        dataset_version=DATASET_VERSION,
        seed=SEED,
        media_type_declared=media_type,
        media_type_detected=media_type,
        detected_format=profile.format_id.value,
        ingestion_adapter="delimited",
        file_size_bytes=size,
        format_metadata={
            "profile_id": profile.profile_id,
            "encoding": decoded.encoding,
            "utf8_bom": decoded.had_utf8_bom,
            "delimiter": delimiter,
            "decimal_separator": profile.decimal_separator,
            "thousands_separator": profile.thousands_separator,
            "date_format": profile.date_format,
        },
    )

    reader = csv.reader(
        io.StringIO(decoded.text, newline=""),
        delimiter=delimiter,
        quotechar='"',
        doublequote=True,
        strict=True,
    )
    try:
        headers = next(reader)
    except StopIteration as exc:
        raise DelimitedFormatError("empty_source", "Delimited input is empty.") from exc
    except csv.Error as exc:
        raise DelimitedFormatError("invalid_header", str(exc), row_number=1) from exc
    if len(headers) > max_columns:
        raise DelimitedFormatError(
            "column_limit_exceeded",
            f"Delimited source exceeds {max_columns} columns.",
            row_number=1,
        )

    spec = profile.target_spec
    positions, findings = _validate_headers(
        headers, spec=spec, source_file=source_file, digest=digest
    )
    if any(item.severity == "error" for item in findings):
        return _ParsedSource(
            source_file=source_file,
            records=(),
            findings=tuple(findings),
            profile_metadata=profile.to_dict(resolved_delimiter=delimiter),
        )

    records: list[TabularRecord] = []
    try:
        for record_number, row in enumerate(reader, start=1):
            row_number = reader.line_num
            if record_number > max_records:
                findings.append(
                    _source_finding(
                        source_file=source_file,
                        code="record_limit_exceeded",
                        message=f"Delimited source exceeds {max_records} records.",
                        observed_value=record_number,
                        expected_value=f"<={max_records}",
                        entity_type=spec.entity_type,
                    )
                )
                break
            if not any(value.strip() for value in row):
                continue
            row_findings: list[IngestionFinding] = []
            row_location = _row_location(
                digest=digest,
                source_file_id=source_file.source_file_id,
                record_number=record_number,
                row_number=row_number,
            )
            if len(row) != len(headers):
                row_findings.append(
                    make_finding(
                        rule_id="RULE-DELIMITED-ROW-001",
                        code="malformed_row_width",
                        category="structure",
                        severity="error",
                        message="Record column count does not match the header.",
                        source_location_id=row_location.source_location_id,
                        entity_type=spec.entity_type,
                        observed_value=len(row),
                        expected_value=len(headers),
                    )
                )
            values: dict[str, Scalar] = {}
            raw_values: dict[str, str | None] = {}
            locations: list[DelimitedSourceLocation] = []
            for field in spec.fields:
                index = positions.get(field.name)
                assert index is not None
                raw_value = row[index] if index < len(row) else None
                if raw_value is not None and len(raw_value) > max_field_characters:
                    row_findings.append(
                        make_finding(
                            rule_id="RULE-DELIMITED-FIELD-001",
                            code="field_size_limit_exceeded",
                            category="structure",
                            severity="error",
                            message=f"Field exceeds {max_field_characters} characters.",
                            source_location_id=row_location.source_location_id,
                            entity_type=spec.entity_type,
                            field=field.name,
                            observed_value=len(raw_value),
                            expected_value=f"<={max_field_characters}",
                        )
                    )
                location = _field_location(
                    digest=digest,
                    source_file_id=source_file.source_file_id,
                    record_number=record_number,
                    row_number=row_number,
                    column=field.name,
                    raw_value=raw_value,
                )
                locations.append(location)
                raw_values[field.name] = raw_value
                try:
                    value = _convert(raw_value, field, profile)
                except (ValueError, InvalidOperation):
                    value = None
                    code = "invalid_date" if field.value_type == DATE else "invalid_type"
                    rule_id = "RULE-DATE-001" if field.value_type == DATE else "RULE-DELIMITED-TYPE-001"
                    row_findings.append(
                        make_finding(
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
                            observed_value=raw_value,
                            expected_value=field.value_type,
                        )
                    )
                values[field.name] = value
                if field.required and (raw_value is None or not raw_value.strip()):
                    row_findings.append(
                        make_finding(
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
                if isinstance(value, Decimal) and field.minimum is not None and value < field.minimum:
                    row_findings.append(
                        make_finding(
                            rule_id="RULE-DELIMITED-RANGE-001",
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
                if isinstance(value, str) and field.allowed_values is not None and value not in field.allowed_values:
                    row_findings.append(
                        make_finding(
                            rule_id="RULE-DELIMITED-CATALOG-001",
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
            record_id = _record_id(spec, values, record_number)
            row_findings = [replace(item, record_id=record_id) for item in row_findings]
            records.append(
                TabularRecord(
                    contract_id=spec.contract_id,
                    entity_type=spec.entity_type,
                    record_id=record_id,
                    source_file_id=source_file.source_file_id,
                    source_location_id=row_location.source_location_id,
                    row_number=row_number,
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
    except csv.Error as exc:
        findings.append(
            _source_finding(
                source_file=source_file,
                code="malformed_delimited_text",
                message=str(exc),
                observed_value=reader.line_num,
                expected_value="valid quoted delimited text",
                entity_type=spec.entity_type,
            )
        )

    return _ParsedSource(
        source_file=source_file,
        records=tuple(records),
        findings=tuple(findings),
        profile_metadata=profile.to_dict(resolved_delimiter=delimiter),
    )


def _apply_error_statuses(
    records: Sequence[TabularRecord], findings: Iterable[IngestionFinding]
) -> tuple[TabularRecord, ...]:
    rejected = {
        item.record_id
        for item in findings
        if item.severity == "error" and item.record_id is not None
    }
    return tuple(
        item.with_status("rejected") if item.record_id in rejected else item
        for item in records
    )


class DelimitedIngestionService:
    """Ingest profiled CSV/TSV sources without mutating raw files."""

    def __init__(
        self,
        *,
        ingested_at: datetime | None = None,
        max_file_size_bytes: int = 25 * 1024 * 1024,
        max_records: int = 100_000,
        max_columns: int = 100,
        max_field_characters: int = 100_000,
    ) -> None:
        if max_file_size_bytes < 1:
            raise ValueError("max_file_size_bytes must be positive.")
        if max_records < 1 or max_columns < 1 or max_field_characters < 1:
            raise ValueError("Delimited limits must be positive.")
        self.ingested_at = ingested_at or datetime.now(timezone.utc)
        self.max_file_size_bytes = max_file_size_bytes
        self.max_records = max_records
        self.max_columns = max_columns
        self.max_field_characters = max_field_characters

    def ingest_file(
        self,
        path: Path,
        profile: DelimitedProfile,
        *,
        validate_references: bool = False,
    ) -> DelimitedIngestionBatch:
        return self.ingest(
            (DelimitedInput(path=path, profile=profile),),
            validate_references=validate_references,
        )

    def ingest(
        self,
        sources: Iterable[DelimitedInput],
        *,
        validate_references: bool = True,
    ) -> DelimitedIngestionBatch:
        source_files: list[SourceFile] = []
        records: list[TabularRecord] = []
        findings: list[IngestionFinding] = []
        before: dict[str, str] = {}
        after: dict[str, str] = {}
        profiles: dict[str, dict[str, object]] = {}

        inputs = tuple(sources)
        if not inputs:
            raise ValueError("At least one delimited input is required.")

        for source in inputs:
            path_key = str(source.path)
            try:
                if source.path.is_file():
                    before[path_key] = sha256_file(source.path)
                parsed = _parse_source(
                    source,
                    ingested_at=self.ingested_at,
                    max_file_size_bytes=self.max_file_size_bytes,
                    max_records=self.max_records,
                    max_columns=self.max_columns,
                    max_field_characters=self.max_field_characters,
                )
            except (DelimitedFormatError, ValueError) as exc:
                try:
                    entity_type = source.profile.target_spec.entity_type
                except ValueError:
                    entity_type = None
                findings.append(
                    _source_finding(
                        source_file=None,
                        code=(
                            exc.code
                            if isinstance(exc, DelimitedFormatError)
                            else "invalid_delimited_profile"
                        ),
                        message=(
                            exc.message
                            if isinstance(exc, DelimitedFormatError)
                            else str(exc)
                        ),
                        observed_value=str(source.path),
                        expected_value="valid profiled CSV/TSV source",
                        entity_type=entity_type,
                    )
                )
                if source.path.is_file():
                    after[path_key] = sha256_file(source.path)
                continue
            source_files.append(parsed.source_file)
            records.extend(parsed.records)
            findings.extend(parsed.findings)
            profiles[parsed.source_file.source_file_id] = parsed.profile_metadata
            after[path_key] = sha256_file(source.path)
            if after[path_key] != before[path_key]:
                findings.append(
                    make_finding(
                        rule_id="RULE-RAW-IMMUTABLE-001",
                        code="raw_source_modified",
                        category="integrity",
                        severity="error",
                        message="Raw source hash changed during ingestion.",
                        source_location_id=parsed.source_file.source_file_id,
                        observed_value=after[path_key],
                        expected_value=before[path_key],
                    )
                )

        if records:
            cross_findings = validate_tabular_records(
                records,
                validate_references=validate_references,
            )
            findings.extend(cross_findings)
            records = list(_apply_error_statuses(records, findings))

        raw_unchanged = before == after and len(before) == len(inputs)
        has_source_error = any(
            item.severity == "error" and item.record_id is None
            for item in findings
        )
        status = (
            "failed"
            if has_source_error
            else "completed_with_findings"
            if findings
            else "completed"
        )
        return DelimitedIngestionBatch(
            source_files=tuple(source_files),
            records=tuple(records),
            findings=tuple(findings),
            source_hashes_before=before,
            source_hashes_after=after,
            raw_files_unchanged=raw_unchanged,
            status=status,
            profiles=profiles,
        )
