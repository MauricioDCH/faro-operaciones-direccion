"""Deterministic JSON and NDJSON ingestion with explicit profiles."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Iterable, Sequence

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
    IngestionFinding,
    JsonIngestionBatch,
    Scalar,
    TabularRecord,
    display_value,
    make_finding,
)
from faro.provenance.models import (
    JsonSourceLocation,
    SourceFile,
    sha256_file,
    stable_json_location_id,
)
from faro.quality.tabular import validate_tabular_records


CONTRACT_VERSION = "1.7.0"
DATASET_VERSION = "0.1.0"
SEED = 20260731
SUPPORTED_SCHEMA_VERSIONS = frozenset({"1.0.0"})
_RESERVED_RECORD_KEYS = frozenset({"_schema_version", "_profile_id"})


class JsonFormatError(ValueError):
    """Raised when a JSON source violates its declared contract."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        line_number: int | None = None,
        record_number: int | None = None,
        json_pointer: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.line_number = line_number
        self.record_number = record_number
        self.json_pointer = json_pointer


@dataclass(frozen=True, slots=True)
class JsonProfile:
    """Explicit target entity and version configuration for JSON records."""

    profile_id: str
    format_id: InputFormat
    schema_version: str = "1.0.0"
    date_format: str = "%Y-%m-%d"

    def validate(self) -> None:
        if self.format_id not in {InputFormat.JSON, InputFormat.NDJSON}:
            raise ValueError("JSON profiles require json or ndjson format.")
        if self.schema_version not in SUPPORTED_SCHEMA_VERSIONS:
            allowed = ", ".join(sorted(SUPPORTED_SCHEMA_VERSIONS))
            raise ValueError(
                f"Unsupported JSON schema version {self.schema_version!r}; "
                f"allowed: {allowed}."
            )
        if not self.date_format:
            raise ValueError("Date format cannot be empty.")
        spec_for_profile(self.profile_id)

    @property
    def target_spec(self) -> SheetSpec:
        return spec_for_profile(self.profile_id)

    def to_dict(self) -> dict[str, object]:
        return {
            "profile_id": self.profile_id,
            "format_id": self.format_id.value,
            "schema_version": self.schema_version,
            "date_format": self.date_format,
            "contract_id": self.target_spec.contract_id,
            "entity_type": self.target_spec.entity_type,
        }


@dataclass(frozen=True, slots=True)
class JsonInput:
    """One JSON/NDJSON file and its explicit profile."""

    path: Path
    profile: JsonProfile


@dataclass(frozen=True, slots=True)
class _RecordCandidate:
    payload: dict[str, Any]
    record_number: int
    line_number: int | None
    pointer_prefix: str


@dataclass(frozen=True, slots=True)
class _ParsedSource:
    source_file: SourceFile
    records: tuple[TabularRecord, ...]
    findings: tuple[IngestionFinding, ...]
    profile_metadata: dict[str, object]


def build_json_profile(
    profile_id: str,
    format_id: InputFormat | str,
    *,
    schema_version: str = "1.0.0",
    date_format: str = "%Y-%m-%d",
) -> JsonProfile:
    """Build and validate a portable JSON record profile."""

    profile = JsonProfile(
        profile_id=profile_id,
        format_id=InputFormat(format_id),
        schema_version=schema_version,
        date_format=date_format,
    )
    profile.validate()
    return profile


def _reject_constant(value: str) -> None:
    raise JsonFormatError(
        "non_finite_number",
        f"Non-finite JSON number is not allowed: {value}.",
    )


def _pairs_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise JsonFormatError(
                "duplicate_json_key",
                f"Duplicate JSON object key is not allowed: {key}.",
                json_pointer=f"/{_escape_pointer(key)}",
            )
        result[key] = value
    return result


def _loads_json(text: str) -> Any:
    try:
        return json.loads(
            text,
            parse_float=Decimal,
            parse_int=Decimal,
            parse_constant=_reject_constant,
            object_pairs_hook=_pairs_without_duplicates,
        )
    except JsonFormatError:
        raise
    except json.JSONDecodeError as exc:
        raise JsonFormatError(
            "invalid_json",
            f"Invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}.",
            line_number=exc.lineno,
        ) from exc


def _escape_pointer(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def _stable_raw_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, str):
        return value
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=lambda item: str(item) if isinstance(item, Decimal) else repr(item),
    )


def _measure_depth(value: Any, depth: int = 1) -> int:
    if isinstance(value, dict):
        if not value:
            return depth
        return max(_measure_depth(item, depth + 1) for item in value.values())
    if isinstance(value, list):
        if not value:
            return depth
        return max(_measure_depth(item, depth + 1) for item in value)
    return depth


def _validate_structure_limits(
    value: Any,
    *,
    max_depth: int,
    max_fields: int,
    max_field_characters: int,
) -> None:
    if _measure_depth(value) > max_depth:
        raise JsonFormatError(
            "json_depth_limit_exceeded",
            f"JSON nesting exceeds the configured maximum depth of {max_depth}.",
        )

    def walk(item: Any, pointer: str = "") -> None:
        if isinstance(item, dict):
            if len(item) > max_fields:
                raise JsonFormatError(
                    "json_field_limit_exceeded",
                    f"JSON object exceeds the configured maximum of {max_fields} fields.",
                    json_pointer=pointer or "/",
                )
            for key, child in item.items():
                if len(key) > max_field_characters:
                    raise JsonFormatError(
                        "json_field_size_limit_exceeded",
                        "JSON key exceeds the configured character limit.",
                        json_pointer=f"{pointer}/{_escape_pointer(key)}",
                    )
                walk(child, f"{pointer}/{_escape_pointer(key)}")
        elif isinstance(item, list):
            for index, child in enumerate(item):
                walk(child, f"{pointer}/{index}")
        elif isinstance(item, str) and len(item) > max_field_characters:
            raise JsonFormatError(
                "json_field_size_limit_exceeded",
                "JSON string exceeds the configured character limit.",
                json_pointer=pointer or "/",
            )

    walk(value)


def _validate_declared_metadata(
    payload: dict[str, Any], profile: JsonProfile, *, pointer_prefix: str
) -> dict[str, Any]:
    record = dict(payload)
    declared_version = record.pop("_schema_version", None)
    declared_profile = record.pop("_profile_id", None)
    if declared_version is not None and declared_version != profile.schema_version:
        raise JsonFormatError(
            "schema_version_mismatch",
            "Record schema version does not match the declared profile.",
            json_pointer=f"{pointer_prefix}/_schema_version",
        )
    if declared_profile is not None and declared_profile != profile.profile_id:
        raise JsonFormatError(
            "profile_mismatch",
            "Record profile does not match the declared profile.",
            json_pointer=f"{pointer_prefix}/_profile_id",
        )
    return record


def _candidates_from_json(
    value: Any,
    profile: JsonProfile,
    *,
    max_records: int,
) -> tuple[_RecordCandidate, ...]:
    if isinstance(value, dict) and "records" in value:
        allowed = {"schema_version", "profile_id", "records"}
        extras = set(value) - allowed
        if extras:
            raise JsonFormatError(
                "unexpected_envelope_field",
                f"Unexpected JSON batch field(s): {', '.join(sorted(extras))}.",
            )
        if value.get("schema_version") != profile.schema_version:
            raise JsonFormatError(
                "schema_version_mismatch",
                "Batch schema_version does not match the declared profile.",
                json_pointer="/schema_version",
            )
        if value.get("profile_id") != profile.profile_id:
            raise JsonFormatError(
                "profile_mismatch",
                "Batch profile_id does not match the declared profile.",
                json_pointer="/profile_id",
            )
        records = value.get("records")
        if not isinstance(records, list):
            raise JsonFormatError(
                "invalid_records_container",
                "JSON batch records must be an array.",
                json_pointer="/records",
            )
        pointer_base = "/records"
    elif isinstance(value, list):
        records = value
        pointer_base = ""
    elif isinstance(value, dict):
        records = [value]
        pointer_base = ""
    else:
        raise JsonFormatError(
            "invalid_json_root",
            "JSON root must be an object, an array, or a versioned batch object.",
        )

    if not records:
        raise JsonFormatError(
            "empty_source",
            "JSON input does not contain any records.",
        )
    if len(records) > max_records:
        raise JsonFormatError(
            "record_limit_exceeded",
            f"JSON source exceeds the configured maximum of {max_records} records.",
        )

    candidates: list[_RecordCandidate] = []
    for index, item in enumerate(records):
        pointer = f"{pointer_base}/{index}" if pointer_base else (f"/{index}" if len(records) > 1 or isinstance(value, list) else "")
        if not isinstance(item, dict):
            raise JsonFormatError(
                "record_must_be_object",
                "Every JSON record must be an object.",
                record_number=index + 1,
                json_pointer=pointer or "/",
            )
        candidates.append(
            _RecordCandidate(
                payload=_validate_declared_metadata(item, profile, pointer_prefix=pointer),
                record_number=index + 1,
                line_number=None,
                pointer_prefix=pointer,
            )
        )
    return tuple(candidates)


def _candidates_from_ndjson(
    text: str,
    profile: JsonProfile,
    *,
    digest: str,
    source_file_id: str,
    max_records: int,
    max_depth: int,
    max_fields: int,
    max_field_characters: int,
) -> tuple[tuple[_RecordCandidate, ...], tuple[IngestionFinding, ...]]:
    candidates: list[_RecordCandidate] = []
    findings: list[IngestionFinding] = []
    record_number = 0
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        record_number += 1
        if record_number > max_records:
            findings.append(
                make_finding(
                    rule_id="RULE-JSON-LIMIT-001",
                    code="record_limit_exceeded",
                    category="structure",
                    severity="error",
                    message=(
                        f"NDJSON source exceeds the configured maximum of "
                        f"{max_records} records."
                    ),
                    source_location_id=stable_json_location_id(
                        digest, record_number, line_number, "/"
                    ),
                    record_id=f"NDJSON-RECORD-{record_number}",
                    observed_value=record_number,
                    expected_value=f"<={max_records}",
                )
            )
            break
        try:
            value = _loads_json(line)
            _validate_structure_limits(
                value,
                max_depth=max_depth,
                max_fields=max_fields,
                max_field_characters=max_field_characters,
            )
            if not isinstance(value, dict):
                raise JsonFormatError(
                    "record_must_be_object",
                    "Every NDJSON line must contain one JSON object.",
                    line_number=line_number,
                    record_number=record_number,
                    json_pointer="/",
                )
            payload = _validate_declared_metadata(value, profile, pointer_prefix="")
        except JsonFormatError as exc:
            findings.append(
                make_finding(
                    rule_id="RULE-JSON-STRUCTURE-001",
                    code=exc.code,
                    category="structure",
                    severity="error",
                    message=exc.message,
                    source_location_id=stable_json_location_id(
                        digest, record_number, line_number, exc.json_pointer or "/"
                    ),
                    entity_type=profile.target_spec.entity_type,
                    record_id=f"NDJSON-RECORD-{record_number}",
                    field=exc.json_pointer,
                    observed_value=f"line {line_number}",
                    expected_value="valid JSON object",
                )
            )
            continue
        candidates.append(
            _RecordCandidate(
                payload=payload,
                record_number=record_number,
                line_number=line_number,
                pointer_prefix="",
            )
        )
    if record_number == 0:
        findings.append(
            make_finding(
                rule_id="RULE-JSON-STRUCTURE-001",
                code="empty_source",
                category="structure",
                severity="error",
                message="NDJSON input is empty.",
                source_location_id=stable_json_location_id(digest, 0, None, "/"),
                entity_type=profile.target_spec.entity_type,
                expected_value="at least one JSON object",
            )
        )
    return tuple(candidates), tuple(findings)


def _convert(value: Any, field: FieldSpec, profile: JsonProfile) -> Scalar:
    if value is None:
        return None
    if field.value_type == STRING:
        if not isinstance(value, str):
            raise ValueError
        return value.strip()
    if field.value_type == DECIMAL:
        if isinstance(value, bool):
            raise ValueError
        if isinstance(value, Decimal):
            return value
        if isinstance(value, str):
            try:
                return Decimal(value.strip())
            except InvalidOperation as exc:
                raise ValueError from exc
        raise ValueError
    if field.value_type == DATE:
        if not isinstance(value, str):
            raise ValueError
        try:
            return datetime.strptime(value.strip(), profile.date_format).date()
        except ValueError:
            if profile.date_format == "%Y-%m-%d":
                return date.fromisoformat(value.strip())
            raise
    if field.value_type == BOOLEAN:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().casefold()
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


def _location(
    *,
    digest: str,
    source_file_id: str,
    record_number: int,
    line_number: int | None,
    json_pointer: str,
    field: str | None,
    raw_value: str | None,
) -> JsonSourceLocation:
    return JsonSourceLocation(
        source_location_id=stable_json_location_id(
            digest, record_number, line_number, json_pointer
        ),
        source_file_id=source_file_id,
        record_number=record_number,
        line=line_number,
        json_pointer=json_pointer or "/",
        field=field,
        raw_value=raw_value,
    )


def _parse_candidate(
    candidate: _RecordCandidate,
    *,
    profile: JsonProfile,
    source_file: SourceFile,
    digest: str,
) -> tuple[TabularRecord, tuple[IngestionFinding, ...]]:
    spec = profile.target_spec
    payload = candidate.payload
    record_pointer = candidate.pointer_prefix or "/"
    row_location = _location(
        digest=digest,
        source_file_id=source_file.source_file_id,
        record_number=candidate.record_number,
        line_number=candidate.line_number,
        json_pointer=record_pointer,
        field=None,
        raw_value=None,
    )
    values: dict[str, Scalar] = {}
    raw_values: dict[str, str | None] = {}
    locations: list[JsonSourceLocation] = []
    findings: list[IngestionFinding] = []

    unexpected = sorted(set(payload) - set(spec.field_names) - _RESERVED_RECORD_KEYS)
    for field_name in unexpected:
        pointer = f"{candidate.pointer_prefix}/{_escape_pointer(field_name)}"
        location = _location(
            digest=digest,
            source_file_id=source_file.source_file_id,
            record_number=candidate.record_number,
            line_number=candidate.line_number,
            json_pointer=pointer,
            field=field_name,
            raw_value=_stable_raw_value(payload[field_name]),
        )
        findings.append(
            make_finding(
                rule_id="RULE-JSON-FIELD-001",
                code="unexpected_field",
                category="structure",
                severity="error",
                message=f"Unexpected field for profile {profile.profile_id}: {field_name}.",
                source_location_id=location.source_location_id,
                entity_type=spec.entity_type,
                field=field_name,
                observed_value=payload[field_name],
                expected_value=", ".join(spec.field_names),
            )
        )

    for field in spec.fields:
        raw = payload.get(field.name)
        raw_text = _stable_raw_value(raw)
        pointer = f"{candidate.pointer_prefix}/{_escape_pointer(field.name)}"
        location = _location(
            digest=digest,
            source_file_id=source_file.source_file_id,
            record_number=candidate.record_number,
            line_number=candidate.line_number,
            json_pointer=pointer,
            field=field.name,
            raw_value=raw_text,
        )
        locations.append(location)
        raw_values[field.name] = raw_text
        value: Scalar = None
        if raw is not None:
            if isinstance(raw, (dict, list)):
                findings.append(
                    make_finding(
                        rule_id="RULE-JSON-TYPE-001",
                        code="nested_field_not_supported",
                        category="structure",
                        severity="error",
                        message=f"Operational field must be scalar: {field.name}.",
                        source_location_id=location.source_location_id,
                        entity_type=spec.entity_type,
                        field=field.name,
                        observed_value=raw_text,
                        expected_value=field.value_type,
                    )
                )
            else:
                try:
                    value = _convert(raw, field, profile)
                except (ValueError, InvalidOperation):
                    findings.append(
                        make_finding(
                            rule_id="RULE-JSON-TYPE-001",
                            code=f"invalid_{field.value_type}",
                            category="data_quality",
                            severity="error",
                            message=f"Value cannot be converted to {field.value_type}: {field.name}.",
                            source_location_id=location.source_location_id,
                            entity_type=spec.entity_type,
                            field=field.name,
                            observed_value=raw_text,
                            expected_value=field.value_type,
                        )
                    )
        values[field.name] = value
        if field.required and (raw is None or (isinstance(raw, str) and not raw.strip())):
            findings.append(
                make_finding(
                    rule_id="RULE-REQUIRED-001",
                    code="missing_required_field",
                    category="data_quality",
                    severity="error",
                    message=f"Required field is missing: {field.name}.",
                    source_location_id=location.source_location_id,
                    entity_type=spec.entity_type,
                    field=field.name,
                    expected_value="non-null value",
                )
            )
        if isinstance(value, Decimal) and field.minimum is not None and value < field.minimum:
            findings.append(
                make_finding(
                    rule_id="RULE-JSON-RANGE-001",
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
            findings.append(
                make_finding(
                    rule_id="RULE-JSON-CATALOG-001",
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

    record_id = _record_id(spec, values, candidate.record_number)
    findings = [replace(item, record_id=record_id) for item in findings]
    record = TabularRecord(
        contract_id=spec.contract_id,
        entity_type=spec.entity_type,
        record_id=record_id,
        source_file_id=source_file.source_file_id,
        source_location_id=row_location.source_location_id,
        row_number=candidate.line_number or candidate.record_number,
        values=values,
        raw_values=raw_values,
        field_locations=tuple(locations),
        record_status=(
            "rejected" if any(item.severity == "error" for item in findings) else "accepted"
        ),
    )
    return record, tuple(findings)


def _source_location_for_path(path: Path) -> str:
    digest = sha256(str(path).encode("utf-8")).hexdigest()
    return f"LOC-{digest[:16].upper()}"


def _source_finding(
    *,
    path: Path,
    code: str,
    message: str,
    entity_type: str | None,
    observed_value: object = None,
    expected_value: object = None,
) -> IngestionFinding:
    return make_finding(
        rule_id="RULE-JSON-SOURCE-001",
        code=code,
        category="structure",
        severity="error",
        message=message,
        source_location_id=_source_location_for_path(path),
        entity_type=entity_type,
        observed_value=observed_value,
        expected_value=expected_value,
    )


def _parse_source(
    source: JsonInput,
    *,
    ingested_at: datetime,
    max_file_size_bytes: int,
    max_records: int,
    max_depth: int,
    max_fields: int,
    max_field_characters: int,
) -> _ParsedSource:
    path = source.path
    profile = source.profile
    profile.validate()
    if not path.is_file():
        raise JsonFormatError(
            "missing_source_file", f"JSON source does not exist: {path}."
        )
    capability = detect_input_format(path)
    if capability is None or capability.format_id is not profile.format_id:
        raise JsonFormatError(
            "format_profile_mismatch",
            "JSON profile format does not match the file extension.",
        )
    size = path.stat().st_size
    if size > max_file_size_bytes:
        raise JsonFormatError(
            "file_size_limit_exceeded",
            f"JSON source exceeds the configured maximum of {max_file_size_bytes} bytes.",
        )
    raw = path.read_bytes()
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        raise JsonFormatError(
            "unsupported_encoding",
            "UTF-16 JSON is not supported; export the file as UTF-8.",
        )
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise JsonFormatError(
            "invalid_utf8", "JSON input must be valid UTF-8 or UTF-8 with BOM."
        ) from exc
    if "\x00" in text:
        raise JsonFormatError(
            "binary_content_detected", "JSON input contains NUL bytes."
        )

    digest = sha256_file(path)
    source_file = SourceFile.from_path(
        path,
        file_hash=digest,
        ingested_at=ingested_at,
        source_type=profile.format_id.value,
        contract_id="DC-013",
        contract_version=CONTRACT_VERSION,
        dataset_version=DATASET_VERSION,
        seed=SEED,
        media_type_detected=(
            "application/json"
            if profile.format_id is InputFormat.JSON
            else "application/x-ndjson"
        ),
        detected_format=profile.format_id.value,
        format_version=profile.schema_version,
        ingestion_adapter="json_records",
        file_size_bytes=size,
        format_metadata=profile.to_dict(),
    )

    findings: list[IngestionFinding] = []
    if profile.format_id is InputFormat.JSON:
        value = _loads_json(text)
        _validate_structure_limits(
            value,
            max_depth=max_depth,
            max_fields=max_fields,
            max_field_characters=max_field_characters,
        )
        candidates = _candidates_from_json(value, profile, max_records=max_records)
    else:
        candidates, line_findings = _candidates_from_ndjson(
            text,
            profile,
            digest=digest,
            source_file_id=source_file.source_file_id,
            max_records=max_records,
            max_depth=max_depth,
            max_fields=max_fields,
            max_field_characters=max_field_characters,
        )
        findings.extend(line_findings)

    records: list[TabularRecord] = []
    for candidate in candidates:
        record, record_findings = _parse_candidate(
            candidate,
            profile=profile,
            source_file=source_file,
            digest=digest,
        )
        records.append(record)
        findings.extend(record_findings)

    return _ParsedSource(
        source_file=source_file,
        records=tuple(records),
        findings=tuple(findings),
        profile_metadata=profile.to_dict(),
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


class JsonIngestionService:
    """Ingest profiled JSON/NDJSON sources without mutating raw files."""

    def __init__(
        self,
        *,
        ingested_at: datetime | None = None,
        max_file_size_bytes: int = 25 * 1024 * 1024,
        max_records: int = 100_000,
        max_depth: int = 20,
        max_fields: int = 200,
        max_field_characters: int = 100_000,
    ) -> None:
        if min(
            max_file_size_bytes,
            max_records,
            max_depth,
            max_fields,
            max_field_characters,
        ) < 1:
            raise ValueError("JSON ingestion limits must be positive.")
        self.ingested_at = ingested_at or datetime.now(timezone.utc)
        self.max_file_size_bytes = max_file_size_bytes
        self.max_records = max_records
        self.max_depth = max_depth
        self.max_fields = max_fields
        self.max_field_characters = max_field_characters

    def ingest_file(
        self,
        path: Path,
        profile: JsonProfile,
        *,
        validate_references: bool = False,
    ) -> JsonIngestionBatch:
        return self.ingest(
            (JsonInput(path=path, profile=profile),),
            validate_references=validate_references,
        )

    def ingest(
        self,
        sources: Iterable[JsonInput],
        *,
        validate_references: bool = True,
    ) -> JsonIngestionBatch:
        inputs = tuple(sources)
        if not inputs:
            raise ValueError("At least one JSON input is required.")

        source_files: list[SourceFile] = []
        records: list[TabularRecord] = []
        findings: list[IngestionFinding] = []
        before: dict[str, str] = {}
        after: dict[str, str] = {}
        profiles: dict[str, dict[str, object]] = {}

        for source in inputs:
            path_key = str(source.path)
            if source.path.is_file():
                before[path_key] = sha256_file(source.path)
            try:
                parsed = _parse_source(
                    source,
                    ingested_at=self.ingested_at,
                    max_file_size_bytes=self.max_file_size_bytes,
                    max_records=self.max_records,
                    max_depth=self.max_depth,
                    max_fields=self.max_fields,
                    max_field_characters=self.max_field_characters,
                )
            except (JsonFormatError, ValueError) as exc:
                try:
                    entity_type = source.profile.target_spec.entity_type
                except ValueError:
                    entity_type = None
                findings.append(
                    _source_finding(
                        path=source.path,
                        code=exc.code if isinstance(exc, JsonFormatError) else "invalid_json_profile",
                        message=exc.message if isinstance(exc, JsonFormatError) else str(exc),
                        entity_type=entity_type,
                        observed_value=str(source.path),
                        expected_value="valid profiled JSON/NDJSON source",
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
                records, validate_references=validate_references
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
        return JsonIngestionBatch(
            source_files=tuple(source_files),
            records=tuple(records),
            findings=tuple(findings),
            source_hashes_before=before,
            source_hashes_after=after,
            raw_files_unchanged=raw_unchanged,
            status=status,
            profiles=profiles,
        )
