"""Atomic deterministic SQLite persistence for canonical Faro records."""

from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3
from typing import Any, Iterable

from faro.domain.documents import ExtractionResult
from faro.ingestion.models import IngestionFinding
from faro.normalization.consolidation import (
    RecordObservation,
    TransformationEvent,
    canonical_json,
)
from faro.persistence.schema import DDL, SCHEMA_VERSION
from faro.provenance.models import (
    DelimitedSourceLocation,
    JsonSourceLocation,
    SourceFile,
    SourceLocation,
    SpreadsheetSourceLocation,
    XmlSourceLocation,
)

_LOCATION_TYPES = (
    SourceLocation,
    SpreadsheetSourceLocation,
    DelimitedSourceLocation,
    JsonSourceLocation,
    XmlSourceLocation,
)


def _json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _source_row(source: SourceFile, *, ingested_at: str) -> tuple[Any, ...]:
    return (
        source.source_file_id,
        source.file_path,
        source.file_name,
        source.source_type,
        source.contract_id,
        source.contract_version,
        source.dataset_version,
        source.seed,
        source.file_hash,
        ingested_at,
        source.record_status,
        source.media_type_declared,
        source.media_type_detected,
        source.detected_format,
        source.format_version,
        source.ingestion_adapter,
        source.file_size_bytes,
        _json(source.format_metadata or {}),
    )


def _location_row(location: object) -> tuple[Any, ...]:
    if isinstance(location, SourceLocation):
        return (
            location.source_location_id,
            location.source_file_id,
            "page",
            None,
            None,
            None,
            None,
            location.page_number,
            None,
            None,
            None,
            None,
            location.text_excerpt,
            None,
            _json([item.to_dict() for item in location.evidence]),
        )
    if isinstance(location, SpreadsheetSourceLocation):
        return (
            location.source_location_id,
            location.source_file_id,
            "spreadsheet",
            location.sheet,
            location.row,
            location.column,
            location.cell_reference,
            None,
            None,
            None,
            None,
            None,
            None,
            location.raw_value,
            "[]",
        )
    if isinstance(location, DelimitedSourceLocation):
        return (
            location.source_location_id,
            location.source_file_id,
            "delimited",
            None,
            location.row,
            location.column,
            None,
            None,
            location.record_number,
            None,
            None,
            None,
            None,
            location.raw_value,
            "[]",
        )
    if isinstance(location, JsonSourceLocation):
        return (
            location.source_location_id,
            location.source_file_id,
            "json",
            None,
            None,
            location.field,
            None,
            None,
            location.record_number,
            location.line,
            location.json_pointer,
            None,
            None,
            location.raw_value,
            "[]",
        )
    if isinstance(location, XmlSourceLocation):
        return (
            location.source_location_id,
            location.source_file_id,
            "xml",
            None,
            None,
            location.field,
            None,
            None,
            None,
            None,
            None,
            location.xml_xpath,
            None,
            location.raw_value,
            "[]",
        )
    raise TypeError(f"Unsupported source location: {type(location)!r}")


def _value(payload: dict[str, Any], key: str, default: Any = None) -> Any:
    value = payload.get(key, default)
    if isinstance(value, bool):
        return int(value)
    return value


class SQLiteOperationalStore:
    """Write a complete store to a temporary database and atomically replace it."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def write(
        self,
        *,
        source_files: Iterable[SourceFile],
        source_locations: Iterable[object],
        observations: Iterable[RecordObservation],
        canonical_records: Iterable[RecordObservation],
        findings: Iterable[IngestionFinding],
        transformations: Iterable[TransformationEvent],
        extraction_results: Iterable[ExtractionResult],
        consolidated_at: str,
        input_digest: str,
    ) -> dict[str, Any]:
        target = self.database_path.resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.unlink(missing_ok=True)
        connection = sqlite3.connect(temporary)
        try:
            connection.execute("PRAGMA page_size = 4096")
            connection.execute("PRAGMA journal_mode = DELETE")
            connection.execute("PRAGMA synchronous = FULL")
            connection.executescript(DDL)
            with connection:
                self._insert_all(
                    connection,
                    source_files=source_files,
                    source_locations=source_locations,
                    observations=observations,
                    canonical_records=canonical_records,
                    findings=findings,
                    transformations=transformations,
                    extraction_results=extraction_results,
                    consolidated_at=consolidated_at,
                    input_digest=input_digest,
                )
            integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
            if integrity != "ok":
                raise RuntimeError(f"SQLite integrity check failed: {integrity}")
            content_hash = logical_content_hash(connection)
            with connection:
                connection.execute(
                    "INSERT OR REPLACE INTO metadata(key, value) VALUES (?, ?)",
                    ("logical_content_hash", content_hash),
                )
            connection.execute("VACUUM")
            connection.close()
            os.replace(temporary, target)
        except Exception:
            connection.close()
            temporary.unlink(missing_ok=True)
            raise
        return {
            "database_path": str(self.database_path),
            "schema_version": SCHEMA_VERSION,
            "integrity_check": "ok",
            "input_digest": input_digest,
            "logical_content_hash": content_hash,
            "counts": database_counts(target),
        }

    def _insert_all(
        self,
        connection: sqlite3.Connection,
        *,
        source_files: Iterable[SourceFile],
        source_locations: Iterable[object],
        observations: Iterable[RecordObservation],
        canonical_records: Iterable[RecordObservation],
        findings: Iterable[IngestionFinding],
        transformations: Iterable[TransformationEvent],
        extraction_results: Iterable[ExtractionResult],
        consolidated_at: str,
        input_digest: str,
    ) -> None:
        metadata = {
            "schema_version": SCHEMA_VERSION,
            "consolidated_at": consolidated_at,
            "input_digest": input_digest,
            "logical_content_hash": "pending",
        }
        connection.executemany(
            "INSERT INTO metadata(key, value) VALUES (?, ?)", sorted(metadata.items())
        )
        sources = sorted({item.source_file_id: item for item in source_files}.values(), key=lambda item: item.source_file_id)
        connection.executemany(
            """INSERT INTO source_file VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            [_source_row(item, ingested_at=consolidated_at) for item in sources],
        )
        locations = {
            getattr(item, "source_location_id"): item
            for item in source_locations
            if isinstance(item, _LOCATION_TYPES)
        }
        connection.executemany(
            """INSERT INTO source_location VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            [_location_row(locations[key]) for key in sorted(locations)],
        )
        observations_sorted = sorted(observations, key=lambda item: item.observation_id)
        connection.executemany(
            """INSERT INTO record_observation VALUES (?,?,?,?,?,?,?,?,?,?)""",
            [
                (
                    item.observation_id,
                    item.entity_type,
                    item.record_id,
                    item.source_file_id,
                    item.source_location_id if item.source_location_id in locations else None,
                    item.source_format,
                    item.source_priority,
                    item.record_status,
                    item.payload_hash,
                    canonical_json(item.payload),
                )
                for item in observations_sorted
            ],
        )
        entity_order = {
            "product": 10,
            "customer": 20,
            "supplier": 30,
            "sale_line": 40,
            "inventory_snapshot": 50,
            "purchase_order_line": 60,
            "document": 70,
            "document_page": 80,
            "invoice": 90,
            "invoice_line": 100,
            "quotation": 110,
            "quotation_line": 120,
        }
        for item in sorted(
            canonical_records,
            key=lambda record: (entity_order.get(record.entity_type, 999), record.record_id),
        ):
            self._insert_canonical(connection, item, locations)
        finding_map = {item.finding_id: item for item in findings}
        connection.executemany(
            """INSERT INTO quality_finding VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            [
                (
                    item.finding_id,
                    item.rule_id,
                    item.code,
                    item.category,
                    item.severity,
                    item.message,
                    item.source_location_id if item.source_location_id in locations else None,
                    item.entity_type,
                    item.record_id,
                    item.field,
                    item.observed_value,
                    item.expected_value,
                )
                for item in sorted(finding_map.values(), key=lambda finding: finding.finding_id)
            ],
        )
        connection.executemany(
            """INSERT INTO transformation_event VALUES (?,?,?,?,?,?,?,?)""",
            [
                (
                    item.transformation_id,
                    item.entity_type,
                    item.record_id,
                    item.source_location_id if item.source_location_id in locations else None,
                    item.rule_id,
                    item.input_hash,
                    item.output_hash,
                    item.created_at,
                )
                for item in sorted(transformations, key=lambda event: event.transformation_id)
            ],
        )
        result_map = {item.extraction_id: item for item in extraction_results}
        connection.executemany(
            """INSERT INTO extraction_result VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            [
                (
                    item.extraction_id,
                    item.source_location_id if item.source_location_id in locations else None,
                    item.document_page_id,
                    item.target_entity,
                    item.target_field,
                    item.raw_value,
                    item.proposed_value,
                    item.method,
                    item.page_number,
                    item.text_excerpt,
                    item.confidence,
                    item.review_status.value,
                    consolidated_at,
                    item.ocr_engine,
                    item.ocr_engine_version,
                    item.ocr_confidence,
                )
                for item in sorted(result_map.values(), key=lambda result: result.extraction_id)
            ],
        )

    def _insert_canonical(
        self,
        connection: sqlite3.Connection,
        item: RecordObservation,
        locations: dict[str, object],
    ) -> None:
        p = item.payload
        location = item.source_location_id if item.source_location_id in locations else None
        common = (item.record_status, item.source_file_id, location)
        if item.entity_type == "product":
            connection.execute(
                "INSERT INTO product VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    p["product_id"], p["sku"], p["product_name"], p.get("product_name_raw"),
                    p["category"], p["unit"], p["unit_cost_cop"], p["sale_price_cop"],
                    int(bool(p["active"])), *common,
                ),
            )
        elif item.entity_type == "customer":
            connection.execute(
                "INSERT INTO customer VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    p["customer_id"], p["customer_name"], p["customer_type"], p.get("tax_id"),
                    p["city"], p.get("email"), p.get("phone"), int(bool(p["active"])), *common,
                ),
            )
        elif item.entity_type == "supplier":
            connection.execute(
                "INSERT INTO supplier VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    p["supplier_id"], p["supplier_name"], p.get("supplier_name_raw"), p.get("tax_id"),
                    p["city"], p.get("email"), p.get("phone"), int(bool(p["active"])), *common,
                ),
            )
        elif item.entity_type == "sale_line":
            connection.execute(
                "INSERT INTO sale_line VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    p["sale_line_id"], p["sale_id"], p["sale_date"], p["customer_id"], p["product_id"],
                    p["quantity"], p["unit_price_cop"], p["discount_cop"], p["line_total_cop"], p["channel"], *common,
                ),
            )
        elif item.entity_type == "inventory_snapshot":
            connection.execute(
                "INSERT INTO inventory_snapshot VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    p["snapshot_date"], p["product_id"], p["stock_on_hand"], p["committed_quantity"],
                    p["available_quantity"], p["reorder_point"], *common,
                ),
            )
        elif item.entity_type == "purchase_order_line":
            connection.execute(
                "INSERT INTO purchase_order_line VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    p["order_line_id"], p["order_id"], p["order_date"], p["supplier_id"], p["product_id"],
                    p["ordered_quantity"], p["expected_unit_cost_cop"], p.get("expected_delivery_date"),
                    p["status"], p.get("source_message_id"), p.get("notes"), *common,
                ),
            )
        elif item.entity_type == "document":
            connection.execute(
                "INSERT INTO document VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    p["document_id"], item.source_file_id, p["document_type"], p["page_count"],
                    p["classification_method"], p.get("classification_confidence"), p["processing_status"],
                    item.record_status, p.get("ubl_version"), p.get("root_document_type"), location,
                ),
            )
        elif item.entity_type == "document_page":
            connection.execute(
                "INSERT INTO document_page VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    p["document_page_id"], p["document_id"], p["page_number"], p["extraction_method"],
                    p["native_text_length"], p.get("render_dpi"), p.get("ocr_engine"), p.get("ocr_engine_version"),
                    p.get("ocr_language"), p.get("ocr_confidence"), p.get("page_text", ""), p["processing_status"],
                    p.get("error_code"), p.get("error_message"), item.record_status, item.source_file_id, location,
                ),
            )
        elif item.entity_type == "invoice":
            connection.execute(
                "INSERT INTO invoice VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    p["invoice_id"], p["document_id"], p.get("invoice_number"), p.get("supplier_name_raw"),
                    p.get("supplier_id"), p.get("issue_date"), p.get("related_order_id"), p.get("currency"),
                    p.get("subtotal_cop"), p.get("tax_cop"), p.get("total_cop"), *common,
                ),
            )
        elif item.entity_type == "invoice_line":
            connection.execute(
                "INSERT INTO invoice_line VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    p["invoice_line_id"], p["invoice_id"], p["product_name_raw"], p.get("product_id"),
                    p["quantity"], p["unit_price_cop"], p["line_total_cop"], *common,
                ),
            )
        elif item.entity_type == "quotation":
            connection.execute(
                "INSERT INTO quotation VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    p["quotation_id"], p["document_id"], p.get("quotation_number"), p.get("supplier_name_raw"),
                    p.get("supplier_id"), p.get("issue_date"), p.get("valid_until"), p.get("currency"),
                    p.get("subtotal_cop"), p.get("tax_cop"), p.get("total_cop"), *common,
                ),
            )
        elif item.entity_type == "quotation_line":
            connection.execute(
                "INSERT INTO quotation_line VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    p["quotation_line_id"], p["quotation_id"], p["product_name_raw"], p.get("product_id"),
                    p["quantity"], p["unit_price_cop"], p["line_total_cop"], *common,
                ),
            )


def logical_content_hash(connection: sqlite3.Connection) -> str:
    """Hash ordered logical rows, independent of SQLite file layout and OS."""

    tables = [
        row[0]
        for row in connection.execute(
            """SELECT name FROM sqlite_master
               WHERE type='table' AND name NOT IN ('metadata', 'sqlite_sequence')
               ORDER BY name"""
        )
    ]
    digest = sha256()
    for table in tables:
        columns = [row[1] for row in connection.execute(f'PRAGMA table_info("{table}")')]
        order = ",".join(f'"{name}"' for name in columns)
        rows = connection.execute(f'SELECT * FROM "{table}" ORDER BY {order}')
        digest.update(table.encode("utf-8"))
        for row in rows:
            digest.update(_json(list(row)).encode("utf-8"))
    return digest.hexdigest()


def database_counts(path: Path) -> dict[str, int]:
    connection = sqlite3.connect(path)
    try:
        return {
            row[0]: row[1]
            for row in connection.execute(
                "SELECT entity_type, record_count FROM v_entity_counts ORDER BY entity_type"
            )
        } | {
            "source_files": connection.execute("SELECT COUNT(*) FROM source_file").fetchone()[0],
            "source_locations": connection.execute("SELECT COUNT(*) FROM source_location").fetchone()[0],
            "observations": connection.execute("SELECT COUNT(*) FROM record_observation").fetchone()[0],
            "findings": connection.execute("SELECT COUNT(*) FROM quality_finding").fetchone()[0],
            "transformations": connection.execute("SELECT COUNT(*) FROM transformation_event").fetchone()[0],
        }
    finally:
        connection.close()
