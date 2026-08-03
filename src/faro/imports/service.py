"""Fail-safe incremental uploads that never replace the active database on error."""

from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
from typing import BinaryIO, Iterable
from uuid import uuid4

from faro.alerts import ConfigurableAlertService, load_alert_configuration
from faro.company.config import CompanyConfiguration
from faro.domain.documents import ExtractionResult, ReviewStatus
from faro.ingestion.delimited import DelimitedIngestionService, DelimitedInput, build_profile
from faro.ingestion.excel import (
    CONTRACT_VERSION as EXCEL_CONTRACT_VERSION,
    DATASET_VERSION as EXCEL_DATASET_VERSION,
    SEED as EXCEL_SEED,
    SPECS_BY_FILE,
    _parse_sheet,
)
from faro.ingestion.formats import InputFormat, detect_input_format
from faro.ingestion.json_records import JsonIngestionService, JsonInput, build_json_profile
from faro.ingestion.models import IngestionFinding, TabularRecord
from faro.ingestion.ubl_xml import UblLimits, UblXmlIngestionService
from faro.ingestion.xlsx import XlsxFormatError, XlsxWorkbook
from faro.indicators import OperationalIndicatorService, load_indicator_configuration
from faro.normalization.consolidation import (
    RecordObservation,
    TransformationEvent,
    canonicalize,
    extraction_results_from_document,
    observations_from_document,
    observations_from_tabular,
    observations_from_ubl,
)
from faro.persistence.consolidation import UnifiedConsolidationService
from faro.persistence.sqlite_store import SQLiteOperationalStore
from faro.provenance.models import (
    BoundingBox,
    DelimitedSourceLocation,
    EvidenceFragment,
    JsonSourceLocation,
    SourceFile,
    SourceLocation,
    SpreadsheetSourceLocation,
    XmlSourceLocation,
    sha256_file,
)
from faro.settings import Settings


SUPPORTED_PROFILES = {
    "products",
    "customers",
    "suppliers",
    "sales",
    "inventory",
    "orders",
}
XLSX_PROFILE_FILES = {
    "catalogs": "catalogos.xlsx",
    "sales": "ventas.xlsx",
    "inventory": "inventario.xlsx",
    "orders": "pedidos.xlsx",
}
ALLOWED_EXTENSIONS = {
    ".xlsx",
    ".csv",
    ".tsv",
    ".json",
    ".ndjson",
    ".jsonl",
    ".pdf",
    ".jpg",
    ".jpeg",
    ".png",
    ".tif",
    ".tiff",
    ".webp",
    ".xml",
}
DERIVED_RULES = {
    "RULE-CROSS-SOURCE-DUPLICATE-001",
    "RULE-CROSS-SOURCE-CONFLICT-001",
    "RULE-ORDER-INVOICE-001",
    "RULE-SUPPLIER-NAME-001",
}


class ImportValidationError(ValueError):
    """Expected client-facing validation error."""


@dataclass(frozen=True, slots=True)
class ImportRequest:
    file_name: str
    profile_id: str | None = None
    mode: str = "upsert"


@dataclass(frozen=True, slots=True)
class ImportResult:
    job_id: str
    status: str
    message: str
    records_added: int = 0
    findings_added: int = 0
    source_file_id: str | None = None
    duplicate: bool = False


@dataclass(slots=True)
class _OperationalState:
    sources: list[SourceFile]
    locations: list[object]
    observations: list[RecordObservation]
    findings: list[IngestionFinding]
    extraction_results: list[ExtractionResult]


class IncrementalImportService:
    """Ingest one uploaded source, rebuild a candidate from stored observations, and swap atomically."""

    def __init__(self, settings: Settings, company: CompanyConfiguration) -> None:
        self.settings = settings
        self.company = company
        self.consolidation = UnifiedConsolidationService(settings)

    def import_stream(
        self, stream: BinaryIO, request: ImportRequest, *, job_id: str | None = None
    ) -> ImportResult:
        job_id = job_id or f"IMP-{uuid4().hex[:16].upper()}"
        safe_name = self._safe_file_name(request.file_name)
        extension = Path(safe_name).suffix.casefold()
        if extension not in ALLOWED_EXTENSIONS:
            raise ImportValidationError(
                "Tipo de archivo no permitido. Usa Excel, CSV, TSV, JSON, PDF, imagen o XML UBL."
            )
        self._validate_profile(extension, request.profile_id)
        if request.mode not in {"append", "upsert"}:
            raise ImportValidationError("El modo debe ser append o upsert.")

        staging_dir = self.settings.import_staging_dir / job_id
        staging_dir.mkdir(parents=True, exist_ok=False)
        staged_path = staging_dir / safe_name
        try:
            file_hash = self._copy_limited(stream, staged_path)
            if self._source_hash_exists(file_hash):
                return ImportResult(
                    job_id=job_id,
                    status="duplicate",
                    message="Este archivo ya había sido procesado. No se hicieron cambios.",
                    duplicate=True,
                )
            final_path = (
                self.settings.import_archive_dir
                / datetime.now(timezone.utc).date().isoformat()
                / job_id
                / safe_name
            )
            state = self._load_operational_state()
            before_observations = len(state.observations)
            before_findings = len(state.findings)
            self._ingest_one(
                staged_path=staged_path,
                final_path=final_path,
                profile_id=request.profile_id,
                state=state,
                mode=request.mode,
            )
            result = self._commit_candidate(
                job_id=job_id,
                staged_path=staged_path,
                final_path=final_path,
                state=state,
            )
            return ImportResult(
                job_id=job_id,
                status="completed",
                message="Los datos se actualizaron correctamente. La información anterior quedó protegida.",
                records_added=max(0, len(state.observations) - before_observations),
                findings_added=max(0, len(state.findings) - before_findings),
                source_file_id=result,
            )
        finally:
            shutil.rmtree(staging_dir, ignore_errors=True)

    def _copy_limited(self, stream: BinaryIO, target: Path) -> str:
        max_bytes = self.settings.import_max_file_size_mb * 1024 * 1024
        digest = sha256()
        total = 0
        try:
            with target.open("xb") as output:
                while True:
                    chunk = stream.read(1024 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > max_bytes:
                        raise ImportValidationError(
                            f"El archivo supera el máximo permitido de {self.settings.import_max_file_size_mb} MB."
                        )
                    digest.update(chunk)
                    output.write(chunk)
                output.flush()
                os.fsync(output.fileno())
            if total == 0:
                raise ImportValidationError("El archivo está vacío.")
            return digest.hexdigest()
        except Exception:
            target.unlink(missing_ok=True)
            raise

    @staticmethod
    def _safe_file_name(value: str) -> str:
        name = Path(value or "").name.strip()
        name = re.sub(r"[^A-Za-z0-9._ -]", "_", name)
        if not name or name in {".", ".."} or len(name) > 180:
            raise ImportValidationError("El nombre del archivo no es válido.")
        return name

    @staticmethod
    def _validate_profile(extension: str, profile_id: str | None) -> None:
        if extension == ".xlsx":
            if profile_id not in XLSX_PROFILE_FILES:
                raise ImportValidationError(
                    "Para Excel selecciona: catálogos, ventas, inventario o pedidos."
                )
        elif extension in {".csv", ".tsv", ".json", ".ndjson", ".jsonl"}:
            if profile_id not in SUPPORTED_PROFILES:
                raise ImportValidationError(
                    "Selecciona qué contiene el archivo: productos, clientes, proveedores, ventas, inventario o pedidos."
                )

    def _source_hash_exists(self, digest: str) -> bool:
        if not self.settings.database_path.is_file():
            raise ImportValidationError(
                "La base operativa aún no existe. Ejecuta la consolidación inicial una sola vez."
            )
        with closing(sqlite3.connect(self.settings.database_path)) as connection:
            row = connection.execute(
                "SELECT 1 FROM source_file WHERE file_hash IN (?, ?) LIMIT 1",
                (digest, f"sha256:{digest}"),
            ).fetchone()
        return row is not None

    def _ingest_one(
        self,
        *,
        staged_path: Path,
        final_path: Path,
        profile_id: str | None,
        state: _OperationalState,
        mode: str,
    ) -> None:
        capability = detect_input_format(staged_path)
        if capability is None:
            raise ImportValidationError("No se pudo reconocer el formato real del archivo.")
        extension = staged_path.suffix.casefold()
        sources: list[SourceFile] = []
        locations: list[object] = []
        observations: list[RecordObservation] = []
        findings: list[IngestionFinding] = []
        extraction_results: list[ExtractionResult] = []

        if extension in {".csv", ".tsv"}:
            batch = DelimitedIngestionService(
                ingested_at=datetime.now(timezone.utc),
                max_file_size_bytes=self.settings.delimited_max_file_size_mb * 1024 * 1024,
                max_records=self.settings.delimited_max_records,
                max_columns=self.settings.delimited_max_columns,
                max_field_characters=self.settings.delimited_max_field_characters,
            ).ingest(
                [DelimitedInput(staged_path, build_profile(profile_id, capability.format_id))],
                validate_references=False,
            )
            self._add_tabular_batch(batch, sources, locations, observations, findings)
        elif extension in {".json", ".ndjson", ".jsonl"}:
            batch = JsonIngestionService(
                ingested_at=datetime.now(timezone.utc),
                max_file_size_bytes=self.settings.json_max_file_size_mb * 1024 * 1024,
                max_records=self.settings.json_max_records,
                max_depth=self.settings.json_max_depth,
                max_fields=self.settings.json_max_fields,
                max_field_characters=self.settings.json_max_field_characters,
            ).ingest(
                [JsonInput(staged_path, build_json_profile(profile_id, capability.format_id))],
                validate_references=False,
            )
            self._add_tabular_batch(batch, sources, locations, observations, findings)
        elif extension == ".xlsx":
            self._ingest_single_xlsx(
                staged_path, profile_id, sources, locations, observations, findings
            )
        elif extension == ".pdf":
            extraction = self.consolidation._pdf_service().extract(staged_path)
            sources.append(extraction.source_file)
            locations.extend(page.source_location for page in extraction.pages)
            observations.extend(observations_from_document(extraction))
            extraction_results.extend(extraction_results_from_document(extraction))
            header_location = extraction.pages[0].source_location.source_location_id if extraction.pages else None
            findings.extend(
                self.consolidation._document_finding(item, extraction, header_location)
                for item in extraction.quality_findings
            )
        elif extension in {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp"}:
            extraction = self.consolidation._image_service().extract(staged_path)
            sources.append(extraction.source_file)
            locations.extend(page.source_location for page in extraction.pages)
            observations.extend(observations_from_document(extraction))
            extraction_results.extend(extraction_results_from_document(extraction))
            header_location = extraction.pages[0].source_location.source_location_id if extraction.pages else None
            findings.extend(
                self.consolidation._document_finding(item, extraction, header_location)
                for item in extraction.quality_findings
            )
        elif extension == ".xml":
            result = UblXmlIngestionService(
                limits=UblLimits(
                    max_file_size_mb=self.settings.ubl_max_file_size_mb,
                    max_elements=self.settings.ubl_max_elements,
                    max_depth=self.settings.ubl_max_depth,
                    max_text_characters=self.settings.ubl_max_text_characters,
                )
            ).ingest(staged_path)
            sources.append(result.source_file)
            locations.extend(result.field_locations)
            observations.extend(observations_from_ubl(result))
            findings.extend(result.findings)
        else:
            raise ImportValidationError("Este formato todavía no admite actualización incremental.")

        if not sources:
            raise ImportValidationError("El archivo no produjo una fuente válida.")
        if any(item.severity == "error" and item.record_id is None for item in findings):
            first = next(item for item in findings if item.severity == "error" and item.record_id is None)
            raise ImportValidationError(first.message)

        patched_sources = [replace(item, file_path=str(final_path), file_name=final_path.name) for item in sources]
        # Uploaded records win over older observations of the same business key.
        boosted = [replace(item, source_priority=item.source_priority + (1000 if mode == "upsert" else 0)) for item in observations]
        state.sources.extend(patched_sources)
        state.locations.extend(locations)
        state.observations.extend(boosted)
        state.findings.extend(findings)
        state.extraction_results.extend(extraction_results)

    def _add_tabular_batch(
        self,
        batch: object,
        sources: list[SourceFile],
        locations: list[object],
        observations: list[RecordObservation],
        findings: list[IngestionFinding],
    ) -> None:
        source_files = tuple(getattr(batch, "source_files"))
        records = tuple(getattr(batch, "records"))
        sources.extend(source_files)
        findings.extend(getattr(batch, "findings"))
        observations.extend(observations_from_tabular(source_files, records))
        for record in records:
            locations.append(self.consolidation._row_location(record))
            locations.extend(record.field_locations)

    def _ingest_single_xlsx(
        self,
        path: Path,
        profile_id: str | None,
        sources: list[SourceFile],
        locations: list[object],
        observations: list[RecordObservation],
        findings: list[IngestionFinding],
    ) -> None:
        file_name = XLSX_PROFILE_FILES[profile_id]
        specs = SPECS_BY_FILE[file_name]
        digest = sha256_file(path)
        source = SourceFile.from_path(
            path,
            file_hash=digest,
            ingested_at=datetime.now(timezone.utc),
            source_type="xlsx",
            contract_id=",".join(spec.contract_id for spec in specs),
            contract_version=EXCEL_CONTRACT_VERSION,
            dataset_version=EXCEL_DATASET_VERSION,
            seed=EXCEL_SEED,
            detected_format="xlsx",
            ingestion_adapter="xlsx",
        )
        records: list[TabularRecord] = []
        try:
            with XlsxWorkbook(path) as workbook:
                for spec in specs:
                    if spec.sheet_name not in workbook.sheet_names:
                        raise ImportValidationError(
                            f"La hoja obligatoria '{spec.sheet_name}' no está en el archivo."
                        )
                    parsed, parsed_findings = _parse_sheet(
                        workbook.read_sheet(spec.sheet_name), spec, source
                    )
                    records.extend(parsed)
                    findings.extend(parsed_findings)
        except XlsxFormatError as exc:
            raise ImportValidationError(exc.message) from exc
        sources.append(source)
        observations.extend(observations_from_tabular([source], records))
        for record in records:
            locations.append(self.consolidation._row_location(record))
            locations.extend(record.field_locations)

    def _commit_candidate(
        self,
        *,
        job_id: str,
        staged_path: Path,
        final_path: Path,
        state: _OperationalState,
    ) -> str:
        timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        canonical = canonicalize(state.observations, created_at=timestamp)
        source_findings = [item for item in state.findings if item.rule_id not in DERIVED_RULES]
        findings = source_findings + list(canonical.findings)
        findings.extend(self.consolidation._business_findings(canonical.canonical_records))
        candidate = self.settings.database_path.with_suffix(
            self.settings.database_path.suffix + f".{job_id}.candidate"
        )
        candidate.unlink(missing_ok=True)
        try:
            SQLiteOperationalStore(candidate).write(
                source_files=state.sources,
                source_locations=state.locations,
                observations=state.observations,
                canonical_records=canonical.canonical_records,
                findings=findings,
                transformations=canonical.transformations,
                extraction_results=state.extraction_results,
                consolidated_at=timestamp,
                input_digest=self.consolidation._input_digest(state.sources),
            )
            indicator_configuration = load_indicator_configuration(
                self.settings.indicator_config_path
            )
            alert_configuration = load_alert_configuration(self.settings.alert_config_path)
            OperationalIndicatorService().calculate(
                database_path=candidate,
                configuration=indicator_configuration,
                preset_id=self.company.indicator_preset,
                persist=True,
            )
            ConfigurableAlertService().evaluate(
                database_path=candidate,
                alert_configuration=alert_configuration,
                indicator_configuration=indicator_configuration,
                preset_id=self.company.alert_preset,
                persist=True,
            )
            with closing(sqlite3.connect(candidate)) as connection:
                integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
                if integrity != "ok":
                    raise RuntimeError(f"Candidate integrity check failed: {integrity}")

            final_path.parent.mkdir(parents=True, exist_ok=True)
            raw_temp = final_path.with_suffix(final_path.suffix + ".tmp")
            shutil.copy2(staged_path, raw_temp)
            os.replace(raw_temp, final_path)
            backup = self.settings.database_path.with_suffix(
                self.settings.database_path.suffix + ".bak"
            )
            if self.settings.database_path.exists():
                shutil.copy2(self.settings.database_path, backup)
            try:
                os.replace(candidate, self.settings.database_path)
            except Exception:
                final_path.unlink(missing_ok=True)
                raise
            return state.sources[-1].source_file_id
        finally:
            candidate.unlink(missing_ok=True)

    def _load_operational_state(self) -> _OperationalState:
        with closing(sqlite3.connect(self.settings.database_path)) as connection:
            connection.row_factory = sqlite3.Row
            return _OperationalState(
                sources=self._load_sources(connection),
                locations=self._load_locations(connection),
                observations=self._load_observations(connection),
                findings=self._load_findings(connection),
                extraction_results=self._load_extraction_results(connection),
            )

    @staticmethod
    def _load_sources(connection: sqlite3.Connection) -> list[SourceFile]:
        result: list[SourceFile] = []
        for row in connection.execute("SELECT * FROM source_file ORDER BY source_file_id"):
            result.append(
                SourceFile(
                    source_file_id=row["source_file_id"],
                    file_path=row["file_path"],
                    file_name=row["file_name"],
                    source_type=row["source_type"],
                    contract_id=row["contract_id"],
                    contract_version=row["contract_version"],
                    dataset_version=row["dataset_version"],
                    seed=row["seed"],
                    file_hash=row["file_hash"],
                    ingested_at=row["ingested_at"],
                    record_status=row["record_status"],
                    media_type_declared=row["media_type_declared"],
                    media_type_detected=row["media_type_detected"],
                    detected_format=row["detected_format"],
                    format_version=row["format_version"],
                    ingestion_adapter=row["ingestion_adapter"],
                    file_size_bytes=row["file_size_bytes"],
                    format_metadata=json.loads(row["format_metadata_json"] or "{}"),
                )
            )
        return result

    @staticmethod
    def _load_locations(connection: sqlite3.Connection) -> list[object]:
        result: list[object] = []
        for row in connection.execute("SELECT * FROM source_location ORDER BY source_location_id"):
            common = (row["source_location_id"], row["source_file_id"])
            if row["locator_type"] == "page":
                evidence: list[EvidenceFragment] = []
                for item in json.loads(row["evidence_json"] or "[]"):
                    box = item.get("bounding_box")
                    evidence.append(
                        EvidenceFragment(
                            text=item.get("text", ""),
                            confidence=item.get("confidence"),
                            bounding_box=BoundingBox(**box) if box else None,
                        )
                    )
                result.append(
                    SourceLocation(
                        *common,
                        page_number=row["page_number"] or 1,
                        text_excerpt=row["text_excerpt"] or "",
                        evidence=tuple(evidence),
                    )
                )
            elif row["locator_type"] == "spreadsheet":
                result.append(
                    SpreadsheetSourceLocation(
                        *common,
                        sheet=row["sheet"] or "",
                        row=row["row_number"] or 1,
                        column=row["column_name"],
                        cell_reference=row["cell_reference"],
                        raw_value=row["raw_value"],
                    )
                )
            elif row["locator_type"] == "delimited":
                result.append(
                    DelimitedSourceLocation(
                        *common,
                        record_number=row["record_number"] or 1,
                        row=row["row_number"] or 1,
                        column=row["column_name"],
                        raw_value=row["raw_value"],
                    )
                )
            elif row["locator_type"] == "json":
                result.append(
                    JsonSourceLocation(
                        *common,
                        record_number=row["record_number"] or 1,
                        line=row["line_number"],
                        json_pointer=row["json_pointer"] or "/",
                        field=row["column_name"],
                        raw_value=row["raw_value"],
                    )
                )
            elif row["locator_type"] == "xml":
                result.append(
                    XmlSourceLocation(
                        *common,
                        xml_xpath=row["xml_xpath"] or "/",
                        field=row["column_name"],
                        raw_value=row["raw_value"],
                    )
                )
        return result

    @staticmethod
    def _load_observations(connection: sqlite3.Connection) -> list[RecordObservation]:
        return [
            RecordObservation(
                observation_id=row["observation_id"],
                entity_type=row["entity_type"],
                record_id=row["record_id"],
                source_file_id=row["source_file_id"],
                source_location_id=row["source_location_id"],
                source_format=row["source_format"],
                source_priority=row["source_priority"],
                record_status=row["record_status"],
                payload_hash=row["payload_hash"],
                payload=json.loads(row["payload_json"]),
            )
            for row in connection.execute(
                "SELECT * FROM record_observation ORDER BY observation_id"
            )
        ]

    @staticmethod
    def _load_findings(connection: sqlite3.Connection) -> list[IngestionFinding]:
        return [
            IngestionFinding(
                finding_id=row["finding_id"],
                rule_id=row["rule_id"],
                code=row["code"],
                category=row["category"],
                severity=row["severity"],
                message=row["message"],
                source_location_id=row["source_location_id"],
                entity_type=row["entity_type"],
                record_id=row["record_id"],
                field=row["field"],
                observed_value=row["observed_value"],
                expected_value=row["expected_value"],
            )
            for row in connection.execute("SELECT * FROM quality_finding ORDER BY finding_id")
        ]

    @staticmethod
    def _load_extraction_results(connection: sqlite3.Connection) -> list[ExtractionResult]:
        return [
            ExtractionResult(
                extraction_id=row["extraction_id"],
                source_location_id=row["source_location_id"] or "",
                document_page_id=row["document_page_id"] or "",
                target_entity=row["target_entity"],
                target_field=row["target_field"],
                raw_value=row["raw_value"] or "",
                proposed_value=row["proposed_value"] or "",
                method=row["method"],
                page_number=row["page_number"] or 1,
                text_excerpt=row["text_excerpt"] or "",
                confidence=row["confidence"],
                review_status=ReviewStatus(row["review_status"]),
                created_at=row["created_at"],
                ocr_engine=row["ocr_engine"],
                ocr_engine_version=row["ocr_engine_version"],
                ocr_confidence=row["ocr_confidence"],
            )
            for row in connection.execute("SELECT * FROM extraction_result ORDER BY extraction_id")
        ]
