"""End-to-end local consolidation across Faro's implemented input adapters."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from typing import Iterable

from faro.domain.documents import DocumentExtraction, QualityFinding
from faro.extraction import NativeTextPolicy, PdfExtractionService, TesseractOcrEngine
from faro.extraction.image import ImageInspector
from faro.ingestion.delimited import (
    DelimitedIngestionService,
    DelimitedInput,
    build_profile,
)
from faro.ingestion.excel import ExcelIngestionService
from faro.ingestion.formats import InputFormat, detect_input_format
from faro.ingestion.image_document import ImageDocumentIngestionService
from faro.ingestion.json_records import (
    JsonIngestionService,
    JsonInput,
    build_json_profile,
)
from faro.ingestion.models import IngestionFinding, TabularRecord, make_finding
from faro.ingestion.ubl_xml import UblLimits, UblXmlIngestionService
from faro.normalization.consolidation import (
    RecordObservation,
    canonicalize,
    extraction_results_from_document,
    normalize_name,
    observations_from_document,
    observations_from_tabular,
    observations_from_ubl,
    stable_id,
)
from faro.persistence.sqlite_store import SQLiteOperationalStore
from faro.provenance.models import (
    DelimitedSourceLocation,
    JsonSourceLocation,
    SourceFile,
    SpreadsheetSourceLocation,
    XmlSourceLocation,
    sha256_file,
)
from faro.settings import Settings

PROFILE_BY_STEM = {
    "productos": "products",
    "products": "products",
    "clientes": "customers",
    "customers": "customers",
    "proveedores": "suppliers",
    "suppliers": "suppliers",
    "ventas": "sales",
    "sales": "sales",
    "inventario": "inventory",
    "inventory": "inventory",
    "pedidos": "orders",
    "orders": "orders",
}


@dataclass(frozen=True, slots=True)
class ConsolidationReport:
    status: str
    database_path: str
    schema_version: str
    integrity_check: str
    input_digest: str
    logical_content_hash: str
    raw_files_unchanged: bool
    adapters: dict[str, int]
    counts: dict[str, int]
    errors: int
    warnings: int

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "database_path": self.database_path,
            "schema_version": self.schema_version,
            "integrity_check": self.integrity_check,
            "input_digest": self.input_digest,
            "logical_content_hash": self.logical_content_hash,
            "raw_files_unchanged": self.raw_files_unchanged,
            "adapters": self.adapters,
            "counts": self.counts,
            "errors": self.errors,
            "warnings": self.warnings,
        }


class UnifiedConsolidationService:
    """Discover implemented sources, ingest them and atomically rebuild SQLite."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings.from_environment()
        self.consolidated_at = self.settings.consolidation_timestamp
        self.ingested_at = datetime.fromisoformat(self.consolidated_at)

    def consolidate(
        self,
        *,
        data_dir: Path | None = None,
        database_path: Path | None = None,
        include_samples: bool = True,
    ) -> ConsolidationReport:
        root = (data_dir or self.settings.data_dir).resolve()
        raw = root / "raw"
        sources: list[SourceFile] = []
        locations: list[object] = []
        observations: list[RecordObservation] = []
        findings: list[IngestionFinding] = []
        extraction_results = []
        adapters: dict[str, int] = {
            "delimited": 0,
            "image": 0,
            "json": 0,
            "pdf": 0,
            "ubl_xml": 0,
            "xlsx": 0,
        }
        raw_unchanged = True

        excel = ExcelIngestionService(ingested_at=self.ingested_at).ingest(raw)
        self._add_tabular_batch(
            excel, sources, locations, observations, findings
        )
        adapters["xlsx"] = len(excel.source_files)
        raw_unchanged &= excel.raw_files_unchanged

        delimited_inputs = self._delimited_inputs(raw / "tabular")
        if delimited_inputs:
            batch = DelimitedIngestionService(
                ingested_at=self.ingested_at,
                max_file_size_bytes=self.settings.delimited_max_file_size_mb * 1024 * 1024,
                max_records=self.settings.delimited_max_records,
                max_columns=self.settings.delimited_max_columns,
                max_field_characters=self.settings.delimited_max_field_characters,
            ).ingest(delimited_inputs, validate_references=True)
            self._add_tabular_batch(
                batch, sources, locations, observations, findings
            )
            adapters["delimited"] = len(batch.source_files)
            raw_unchanged &= batch.raw_files_unchanged

        json_inputs = self._json_inputs(raw / "imports" / "structured")
        if json_inputs:
            batch = JsonIngestionService(
                ingested_at=self.ingested_at,
                max_file_size_bytes=self.settings.json_max_file_size_mb * 1024 * 1024,
                max_records=self.settings.json_max_records,
                max_depth=self.settings.json_max_depth,
                max_fields=self.settings.json_max_fields,
                max_field_characters=self.settings.json_max_field_characters,
            ).ingest(json_inputs, validate_references=True)
            self._add_tabular_batch(
                batch, sources, locations, observations, findings
            )
            adapters["json"] = len(batch.source_files)
            raw_unchanged &= batch.raw_files_unchanged

        pdf_service = self._pdf_service()
        for path in sorted((raw / "facturas").glob("*.pdf")):
            extraction = pdf_service.extract(path)
            self._add_document(
                extraction,
                sources,
                locations,
                observations,
                findings,
                extraction_results,
            )
            adapters["pdf"] = adapters.get("pdf", 0) + 1

        image_service = self._image_service()
        image_dir = raw / "document_images"
        if image_dir.exists():
            for path in sorted(item for item in image_dir.iterdir() if item.is_file()):
                capability = detect_input_format(path)
                if capability is None or capability.adapter != "image_document":
                    continue
                extraction = image_service.extract(path)
                self._add_document(
                    extraction,
                    sources,
                    locations,
                    observations,
                    findings,
                    extraction_results,
                )
                adapters["image"] = adapters.get("image", 0) + 1

        ubl_paths = sorted((raw / "electronic_documents").glob("*.xml"))
        if include_samples:
            ubl_paths.extend(sorted((root / "samples").glob("ubl-*.xml")))
        ubl_service = UblXmlIngestionService(
            limits=UblLimits(
                max_file_size_mb=self.settings.ubl_max_file_size_mb,
                max_elements=self.settings.ubl_max_elements,
                max_depth=self.settings.ubl_max_depth,
                max_text_characters=self.settings.ubl_max_text_characters,
            )
        )
        for path in sorted(set(ubl_paths)):
            result = ubl_service.ingest(path)
            sources.append(result.source_file)
            locations.extend(result.field_locations)
            observations.extend(observations_from_ubl(result))
            findings.extend(result.findings)
            adapters["ubl_xml"] = adapters.get("ubl_xml", 0) + 1
            raw_unchanged &= result.raw_file_unchanged

        canonical = canonicalize(
            observations,
            created_at=self.consolidated_at,
        )
        findings.extend(canonical.findings)
        findings.extend(self._business_findings(canonical.canonical_records))
        input_digest = self._input_digest(sources)
        store_result = SQLiteOperationalStore(
            database_path or self.settings.database_path
        ).write(
            source_files=sources,
            source_locations=locations,
            observations=observations,
            canonical_records=canonical.canonical_records,
            findings=findings,
            transformations=canonical.transformations,
            extraction_results=extraction_results,
            consolidated_at=self.consolidated_at,
            input_digest=input_digest,
        )
        errors = sum(item.severity == "error" for item in findings)
        warnings = sum(item.severity == "warning" for item in findings)
        return ConsolidationReport(
            status="completed_with_findings" if findings else "completed",
            raw_files_unchanged=raw_unchanged,
            adapters=dict(sorted(adapters.items())),
            errors=errors,
            warnings=warnings,
            **store_result,
        )

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
            locations.append(self._row_location(record))
            locations.extend(record.field_locations)

    def _add_document(
        self,
        extraction: DocumentExtraction,
        sources: list[SourceFile],
        locations: list[object],
        observations: list[RecordObservation],
        findings: list[IngestionFinding],
        extraction_results: list[object],
    ) -> None:
        sources.append(extraction.source_file)
        locations.extend(page.source_location for page in extraction.pages)
        observations.extend(observations_from_document(extraction))
        extraction_results.extend(extraction_results_from_document(extraction))
        header_location = (
            extraction.pages[0].source_location.source_location_id
            if extraction.pages
            else None
        )
        for item in extraction.quality_findings:
            findings.append(self._document_finding(item, extraction, header_location))

    @staticmethod
    def _document_finding(
        finding: QualityFinding,
        extraction: DocumentExtraction,
        source_location_id: str | None,
    ) -> IngestionFinding:
        structured = extraction.structured_document
        entity_type = (
            structured.to_dict().get("entity_type") if structured is not None else "document"
        )
        record_id = None
        if structured is not None:
            payload = structured.to_dict()
            record_id = payload.get("invoice_id") or payload.get("quotation_id")
        return make_finding(
            rule_id=f"RULE-DOCUMENT-{finding.code.upper().replace('_', '-')}",
            code=finding.code,
            category="data_quality",
            severity=finding.severity,
            message=finding.message,
            source_location_id=source_location_id,
            entity_type=entity_type,
            record_id=record_id,
            field=finding.field,
            observed_value=finding.observed_value,
            expected_value=finding.expected_value,
        )

    @staticmethod
    def _row_location(record: TabularRecord) -> object:
        first = record.field_locations[0]
        if isinstance(first, SpreadsheetSourceLocation):
            return SpreadsheetSourceLocation(
                source_location_id=record.source_location_id,
                source_file_id=record.source_file_id,
                sheet=first.sheet,
                row=record.row_number,
                column=None,
                cell_reference=None,
                raw_value=None,
            )
        if isinstance(first, DelimitedSourceLocation):
            return DelimitedSourceLocation(
                source_location_id=record.source_location_id,
                source_file_id=record.source_file_id,
                record_number=first.record_number,
                row=record.row_number,
                column=None,
                raw_value=None,
            )
        if isinstance(first, JsonSourceLocation):
            pointer = first.json_pointer.rsplit("/", 1)[0] or "/"
            return JsonSourceLocation(
                source_location_id=record.source_location_id,
                source_file_id=record.source_file_id,
                record_number=first.record_number,
                line=first.line,
                json_pointer=pointer,
                field=None,
                raw_value=None,
            )
        raise TypeError(f"Unsupported tabular location: {type(first)!r}")

    def _pdf_service(self) -> PdfExtractionService:
        engine = (
            TesseractOcrEngine(
                command=self.settings.ocr_command,
                language=self.settings.ocr_language,
            )
            if self.settings.ocr_enabled
            else None
        )
        return PdfExtractionService(
            ocr_engine=engine,
            ocr_enabled=self.settings.ocr_enabled,
            extraction_mode=self.settings.pdf_extraction_mode,
            min_ocr_confidence=self.settings.ocr_min_confidence,
            render_dpi=self.settings.ocr_render_dpi,
            max_pages=self.settings.pdf_max_pages,
            native_text_policy=NativeTextPolicy(
                min_characters=self.settings.pdf_native_text_min_characters,
                min_words=self.settings.pdf_native_text_min_words,
            ),
        )

    def _image_service(self) -> ImageDocumentIngestionService:
        engine = (
            TesseractOcrEngine(
                command=self.settings.ocr_command,
                language=self.settings.ocr_language,
            )
            if self.settings.ocr_enabled
            else None
        )
        return ImageDocumentIngestionService(
            ocr_engine=engine,
            ocr_enabled=self.settings.ocr_enabled,
            min_ocr_confidence=self.settings.ocr_min_confidence,
            inspector=ImageInspector(
                max_file_size_mb=self.settings.image_max_file_size_mb,
                max_width=self.settings.image_max_width,
                max_height=self.settings.image_max_height,
                max_pixels=self.settings.image_max_pixels,
                min_width=self.settings.image_min_width,
                min_height=self.settings.image_min_height,
            ),
        )

    @staticmethod
    def _delimited_inputs(directory: Path) -> tuple[DelimitedInput, ...]:
        if not directory.exists():
            return ()
        result: list[DelimitedInput] = []
        for path in sorted(item for item in directory.iterdir() if item.is_file()):
            capability = detect_input_format(path)
            profile_id = PROFILE_BY_STEM.get(path.stem.casefold())
            if (
                capability is None
                or capability.format_id not in {InputFormat.CSV, InputFormat.TSV}
                or profile_id is None
            ):
                continue
            result.append(
                DelimitedInput(
                    path=path,
                    profile=build_profile(profile_id, capability.format_id),
                )
            )
        return tuple(result)

    @staticmethod
    def _json_inputs(directory: Path) -> tuple[JsonInput, ...]:
        if not directory.exists():
            return ()
        result: list[JsonInput] = []
        for path in sorted(item for item in directory.iterdir() if item.is_file()):
            capability = detect_input_format(path)
            profile_id = PROFILE_BY_STEM.get(path.stem.casefold())
            if (
                capability is None
                or capability.format_id not in {InputFormat.JSON, InputFormat.NDJSON}
                or profile_id is None
            ):
                continue
            result.append(
                JsonInput(
                    path=path,
                    profile=build_json_profile(profile_id, capability.format_id),
                )
            )
        return tuple(result)

    @staticmethod
    def _input_digest(sources: Iterable[SourceFile]) -> str:
        material = "\n".join(
            f"{item.source_file_id}|{item.file_hash}|{item.contract_version}"
            for item in sorted(
                {source.source_file_id: source for source in sources}.values(),
                key=lambda source: source.source_file_id,
            )
        )
        return sha256(material.encode("utf-8")).hexdigest()

    @staticmethod
    def _business_findings(
        canonical_records: Iterable[RecordObservation],
    ) -> list[IngestionFinding]:
        records = tuple(canonical_records)
        orders = {
            (item.payload["order_id"], item.payload["product_id"]): item
            for item in records
            if item.entity_type == "purchase_order_line"
        }
        invoices = {
            item.record_id: item
            for item in records
            if item.entity_type == "invoice"
        }
        suppliers = {
            item.payload["supplier_id"]: item
            for item in records
            if item.entity_type == "supplier"
        }
        findings: list[IngestionFinding] = []
        for line in (item for item in records if item.entity_type == "invoice_line"):
            invoice = invoices.get(line.payload["invoice_id"])
            if invoice is None or not invoice.payload.get("related_order_id"):
                continue
            order = orders.get(
                (invoice.payload["related_order_id"], line.payload.get("product_id"))
            )
            if order is None:
                continue
            if str(order.payload["ordered_quantity"]) != str(line.payload["quantity"]):
                findings.append(
                    make_finding(
                        rule_id="RULE-ORDER-INVOICE-001",
                        code="order_invoice_mismatch",
                        category="operational",
                        severity="error",
                        message="Invoice quantity differs from the related purchase order.",
                        source_location_id=line.source_location_id,
                        entity_type="invoice_line",
                        record_id=line.record_id,
                        field="quantity",
                        observed_value=line.payload["quantity"],
                        expected_value=order.payload["ordered_quantity"],
                    )
                )
        for invoice in invoices.values():
            supplier_id = invoice.payload.get("supplier_id")
            master = suppliers.get(supplier_id)
            if master is None or not invoice.payload.get("supplier_name_raw"):
                continue
            if normalize_name(invoice.payload["supplier_name_raw"]) != normalize_name(master.payload["supplier_name"]):
                findings.append(
                    make_finding(
                        rule_id="RULE-SUPPLIER-NAME-001",
                        code="inconsistent_supplier_name",
                        category="normalization",
                        severity="warning",
                        message="Invoice supplier name differs from the canonical supplier name.",
                        source_location_id=invoice.source_location_id,
                        entity_type="invoice",
                        record_id=invoice.record_id,
                        field="supplier_name_raw",
                        observed_value=invoice.payload["supplier_name_raw"],
                        expected_value=master.payload["supplier_name"],
                    )
                )
        return findings
