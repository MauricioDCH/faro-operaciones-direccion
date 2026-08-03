\
"""Secure deterministic ingestion for UBL 2.1 Invoice documents."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal, InvalidOperation
import base64
import binascii
from pathlib import Path
from typing import Any, Iterable
import xml.etree.ElementTree as ET

from faro.domain.documents import Invoice, InvoiceLine, RecordStatus
from faro.ingestion.formats import require_implemented_format
from faro.ingestion.models import IngestionFinding, make_finding
from faro.provenance.models import (
    SourceFile,
    XmlSourceLocation,
    sha256_file,
    stable_document_id,
    stable_xml_location_id,
)
from faro.quality.documents import (
    validate_document_totals,
    validate_line_totals,
    validate_required,
    validate_subtotal,
)

CONTRACT_ID = "DC-011"
CONTRACT_VERSION = "1.9.0"
DATASET_VERSION = "0.1.0"
SEED = 20260731
SUPPORTED_UBL_VERSIONS = frozenset({"2.1"})
SUPPORTED_ROOTS = frozenset({"Invoice", "AttachedDocument"})


class UblFormatError(ValueError):
    """Raised when an XML source cannot be safely interpreted as supported UBL."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        xml_xpath: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.xml_xpath = xml_xpath

    def to_dict(self) -> dict[str, str | None]:
        return {
            "code": self.code,
            "message": self.message,
            "xml_xpath": self.xml_xpath,
        }


@dataclass(frozen=True, slots=True)
class UblLimits:
    max_file_size_mb: int = 25
    max_elements: int = 50_000
    max_depth: int = 50
    max_text_characters: int = 5_000_000

    def validate(self) -> None:
        if not 1 <= self.max_file_size_mb <= 1024:
            raise ValueError("UBL max file size must be between 1 and 1024 MB.")
        if self.max_elements < 1:
            raise ValueError("UBL max elements must be positive.")
        if not 1 <= self.max_depth <= 100:
            raise ValueError("UBL max depth must be between 1 and 100.")
        if self.max_text_characters < 1:
            raise ValueError("UBL max text characters must be positive.")


@dataclass(frozen=True, slots=True)
class UblIngestionResult:
    """Canonical invoice plus XML-specific metadata and field provenance."""

    source_file: SourceFile
    document_id: str
    root_document_type: str
    ubl_version: str
    customization_id: str | None
    profile_id: str | None
    supplier: dict[str, str | None]
    customer: dict[str, str | None]
    tax_details: tuple[dict[str, str | None], ...]
    structured_document: Invoice | None
    field_locations: tuple[XmlSourceLocation, ...]
    findings: tuple[IngestionFinding, ...]
    source_hash_before: str
    source_hash_after: str
    raw_file_unchanged: bool
    status: str

    def to_dict(self, *, include_locations: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "status": self.status,
            "raw_file_unchanged": self.raw_file_unchanged,
            "source_file": self.source_file.to_dict(),
            "document_id": self.document_id,
            "root_document_type": self.root_document_type,
            "ubl_version": self.ubl_version,
            "customization_id": self.customization_id,
            "profile_id": self.profile_id,
            "supplier": self.supplier,
            "customer": self.customer,
            "tax_details": list(self.tax_details),
            "structured_document": (
                self.structured_document.to_dict()
                if self.structured_document is not None
                else None
            ),
            "findings": [item.to_dict() for item in self.findings],
            "source_hash_before": self.source_hash_before,
            "source_hash_after": self.source_hash_after,
        }
        if include_locations:
            payload["field_locations"] = [
                item.to_dict() for item in self.field_locations
            ]
        return payload


@dataclass(frozen=True, slots=True)
class _ParsedXml:
    invoice_root: ET.Element
    root_document_type: str
    embedded_source_xpath: str | None
    outer_root: ET.Element


class _Collector:
    def __init__(
        self,
        *,
        root: ET.Element,
        source_file: SourceFile,
        file_hash: str,
        embedded_prefix: str | None,
    ) -> None:
        self.root = root
        self.source_file = source_file
        self.file_hash = file_hash
        self.embedded_prefix = embedded_prefix
        self.paths = _build_logical_paths(root)
        self.locations: list[XmlSourceLocation] = []

    def location(self, element: ET.Element, field: str, raw_value: str | None) -> str:
        inner = self.paths[id(element)]
        xpath = (
            f"{self.embedded_prefix}/embedded-document{inner}"
            if self.embedded_prefix
            else inner
        )
        location_id = stable_xml_location_id(self.file_hash, xpath, field)
        self.locations.append(
            XmlSourceLocation(
                source_location_id=location_id,
                source_file_id=self.source_file.source_file_id,
                xml_xpath=xpath,
                field=field,
                raw_value=raw_value,
            )
        )
        return location_id

    def text(self, element: ET.Element | None, field: str) -> tuple[str | None, str | None]:
        if element is None:
            return None, None
        raw = (element.text or "").strip()
        location_id = self.location(element, field, raw or None)
        return raw or None, location_id


class UblXmlIngestionService:
    """Ingest one UBL 2.1 Invoice or AttachedDocument without OCR."""

    def __init__(self, *, limits: UblLimits | None = None) -> None:
        self.limits = limits or UblLimits()
        self.limits.validate()

    def ingest(self, path: Path) -> UblIngestionResult:
        source_path = path.resolve()
        if not source_path.exists():
            raise UblFormatError(
                "missing_source_file",
                f"UBL XML source does not exist: {source_path}.",
            )
        capability = require_implemented_format(source_path)
        if capability.adapter != "ubl_xml":
            raise UblFormatError(
                "unexpected_format",
                f"Expected ubl_xml input, got {capability.adapter}.",
            )
        size = source_path.stat().st_size
        limit_bytes = self.limits.max_file_size_mb * 1024 * 1024
        if size == 0:
            raise UblFormatError("empty_xml", "UBL XML source is empty.")
        if size > limit_bytes:
            raise UblFormatError(
                "xml_file_too_large",
                f"UBL XML source exceeds {self.limits.max_file_size_mb} MB.",
            )

        initial_hash = sha256_file(source_path)
        raw = source_path.read_bytes()
        outer_root = _secure_parse(raw, self.limits)
        parsed = _resolve_invoice_root(outer_root, self.limits)
        version = _read_ubl_version(parsed.invoice_root)
        if version not in SUPPORTED_UBL_VERSIONS:
            allowed = ", ".join(sorted(SUPPORTED_UBL_VERSIONS))
            raise UblFormatError(
                "unsupported_ubl_version",
                f"Unsupported UBL version {version!r}; allowed: {allowed}.",
                xml_xpath="/Invoice/UBLVersionID",
            )

        source_file = SourceFile.from_path(
            source_path,
            initial_hash,
            source_type="xml",
            contract_id=CONTRACT_ID,
            contract_version=CONTRACT_VERSION,
            dataset_version=DATASET_VERSION,
            seed=SEED,
            media_type_detected="application/xml",
            detected_format="ubl_xml",
            format_version=f"UBL-{version}",
            ingestion_adapter="ubl_xml",
            file_size_bytes=size,
            format_metadata={
                "root_document_type": parsed.root_document_type,
                "invoice_root_namespace": _namespace(parsed.invoice_root.tag),
                "embedded": parsed.embedded_source_xpath is not None,
                "security": {
                    "dtd_allowed": False,
                    "external_entities_allowed": False,
                },
            },
        )
        collector = _Collector(
            root=parsed.invoice_root,
            source_file=source_file,
            file_hash=initial_hash,
            embedded_prefix=parsed.embedded_source_xpath,
        )
        result = self._map_invoice(
            parsed=parsed,
            collector=collector,
            source_file=source_file,
            file_hash=initial_hash,
            version=version,
        )
        final_hash = sha256_file(source_path)
        unchanged = final_hash == initial_hash
        findings = list(result.findings)
        if not unchanged:
            findings.append(
                make_finding(
                    rule_id="RULE-RAW-IMMUTABLE-001",
                    code="raw_source_modified",
                    category="integrity",
                    severity="error",
                    message="Raw UBL XML changed during ingestion.",
                    source_location_id=None,
                    entity_type="invoice",
                    record_id=(
                        result.structured_document.invoice_id
                        if result.structured_document is not None
                        else None
                    ),
                    observed_value=final_hash,
                    expected_value=initial_hash,
                )
            )
        has_errors = any(item.severity == "error" for item in findings)
        status = "completed_with_findings" if has_errors else "completed"
        record_status = "pending_review" if has_errors else "accepted"
        source_file = replace(source_file, record_status=record_status)
        structured = result.structured_document
        if structured is not None and has_errors:
            structured = replace(structured, record_status=RecordStatus.PENDING_REVIEW)
        return replace(
            result,
            source_file=source_file,
            structured_document=structured,
            findings=tuple(findings),
            source_hash_after=final_hash,
            raw_file_unchanged=unchanged,
            status=status,
        )

    def _map_invoice(
        self,
        *,
        parsed: _ParsedXml,
        collector: _Collector,
        source_file: SourceFile,
        file_hash: str,
        version: str,
    ) -> UblIngestionResult:
        invoice = parsed.invoice_root
        document_id = stable_document_id(file_hash)
        findings: list[IngestionFinding] = []

        customization_id, _ = collector.text(
            _child(invoice, "CustomizationID"), "customization_id"
        )
        profile_id, _ = collector.text(_child(invoice, "ProfileID"), "profile_id")
        invoice_number, number_location = collector.text(
            _child(invoice, "ID"), "invoice_number"
        )
        issue_date_raw, issue_date_location = collector.text(
            _child(invoice, "IssueDate"), "issue_date"
        )
        issue_date = _parse_date(
            issue_date_raw,
            field="issue_date",
            location_id=issue_date_location,
            findings=findings,
        )
        currency, currency_location = collector.text(
            _child(invoice, "DocumentCurrencyCode"), "currency"
        )

        supplier_party = _path(invoice, "AccountingSupplierParty", "Party")
        customer_party = _path(invoice, "AccountingCustomerParty", "Party")
        supplier = _extract_party(
            supplier_party, collector, "supplier", findings
        )
        customer = _extract_party(
            customer_party, collector, "customer", findings
        )
        supplier_name = supplier["name"]
        supplier_id = supplier["identification_id"] or supplier["tax_id"]

        order_id, _ = collector.text(
            _path(invoice, "OrderReference", "ID"), "related_order_id"
        )
        monetary_total = _child(invoice, "LegalMonetaryTotal")
        subtotal_element = _child(monetary_total, "LineExtensionAmount")
        if subtotal_element is None:
            subtotal_element = _child(monetary_total, "TaxExclusiveAmount")
        subtotal = _decimal_from_element(
            subtotal_element,
            collector=collector,
            field="subtotal_cop",
            findings=findings,
        )
        tax_elements = [
            item
            for tax_total in _children(invoice, "TaxTotal")
            for item in [_child(tax_total, "TaxAmount")]
            if item is not None
        ]
        tax_values = [
            _decimal_from_element(
                item,
                collector=collector,
                field="tax_cop",
                findings=findings,
            )
            for item in tax_elements
        ]
        tax = (
            sum((item for item in tax_values if item is not None), Decimal("0"))
            if tax_elements
            else None
        )
        total = _decimal_from_element(
            _child(monetary_total, "PayableAmount"),
            collector=collector,
            field="total_cop",
            findings=findings,
        )

        lines: list[InvoiceLine] = []
        for index, line_element in enumerate(_children(invoice, "InvoiceLine"), start=1):
            line = _extract_line(
                line_element,
                index=index,
                document_id=document_id,
                collector=collector,
                findings=findings,
            )
            if line is not None:
                lines.append(line)

        header_location = number_location or stable_xml_location_id(
            file_hash, "/Invoice", "invoice"
        )
        internal_invoice_id = f"INV-UBL-{file_hash[:12].upper()}"
        required_values = {
            "invoice_number": invoice_number,
            "supplier_name_raw": supplier_name,
            "issue_date": issue_date,
            "currency": currency,
            "subtotal_cop": subtotal,
            "tax_cop": tax,
            "total_cop": total,
        }
        for quality in validate_required(required_values, required_values):
            findings.append(
                _quality_to_finding(
                    quality,
                    locations=collector.locations,
                    entity_type="invoice",
                    record_id=internal_invoice_id,
                )
            )
        if not lines:
            findings.append(
                make_finding(
                    rule_id="RULE-UBL-LINES-001",
                    code="missing_invoice_lines",
                    category="data_quality",
                    severity="error",
                    message="UBL invoice contains no usable InvoiceLine records.",
                    source_location_id=header_location,
                    entity_type="invoice",
                    record_id=internal_invoice_id,
                    field="lines",
                    expected_value=">=1",
                )
            )
        if currency and currency != "COP":
            findings.append(
                make_finding(
                    rule_id="RULE-UBL-CURRENCY-001",
                    code="unsupported_currency",
                    category="data_quality",
                    severity="error",
                    message="Current canonical monetary fields support COP only.",
                    source_location_id=currency_location,
                    entity_type="invoice",
                    record_id=internal_invoice_id,
                    field="currency",
                    observed_value=currency,
                    expected_value="COP",
                )
            )
        _validate_amount_currencies(
            invoice,
            document_currency=currency,
            collector=collector,
            findings=findings,
            record_id=internal_invoice_id,
        )

        provisional = Invoice(
            invoice_id=internal_invoice_id,
            document_id=document_id,
            invoice_number=invoice_number,
            supplier_name_raw=supplier_name,
            supplier_id=supplier_id,
            issue_date=issue_date,
            related_order_id=order_id,
            currency=currency,
            subtotal_cop=subtotal,
            tax_cop=tax,
            total_cop=total,
            record_status=RecordStatus.ACCEPTED,
            source_location_id=header_location,
            lines=tuple(lines),
            extraction_results=(),
        )
        for quality in (
            validate_line_totals(lines)
            + validate_subtotal(lines, subtotal)
            + validate_document_totals(subtotal=subtotal, tax=tax, total=total)
        ):
            findings.append(
                _quality_to_finding(
                    quality,
                    locations=collector.locations,
                    entity_type="invoice",
                    record_id=internal_invoice_id,
                )
            )
        if any(item.severity == "error" for item in findings):
            provisional = replace(
                provisional, record_status=RecordStatus.PENDING_REVIEW
            )

        tax_details = tuple(
            _extract_tax_subtotal(item, collector, index)
            for index, item in enumerate(_descendants(invoice, "TaxSubtotal"), start=1)
        )
        return UblIngestionResult(
            source_file=source_file,
            document_id=document_id,
            root_document_type=parsed.root_document_type,
            ubl_version=version,
            customization_id=customization_id,
            profile_id=profile_id,
            supplier=supplier,
            customer=customer,
            tax_details=tax_details,
            structured_document=provisional,
            field_locations=tuple(collector.locations),
            findings=tuple(findings),
            source_hash_before=file_hash,
            source_hash_after=file_hash,
            raw_file_unchanged=True,
            status=(
                "completed_with_findings"
                if any(item.severity == "error" for item in findings)
                else "completed"
            ),
        )


def _secure_parse(raw: bytes, limits: UblLimits) -> ET.Element:
    upper = raw.upper()
    if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
        raise UblFormatError(
            "unsafe_xml_declaration",
            "DTD and entity declarations are not allowed in UBL XML.",
        )
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise UblFormatError("invalid_xml", f"Invalid XML: {exc}.") from exc
    _validate_tree_limits(root, limits)
    return root


def _validate_tree_limits(root: ET.Element, limits: UblLimits) -> None:
    elements = 0
    text_characters = 0
    stack: list[tuple[ET.Element, int]] = [(root, 1)]
    while stack:
        element, depth = stack.pop()
        elements += 1
        text_characters += len(element.text or "") + len(element.tail or "")
        if elements > limits.max_elements:
            raise UblFormatError(
                "xml_element_limit_exceeded",
                f"XML exceeds {limits.max_elements} elements.",
            )
        if depth > limits.max_depth:
            raise UblFormatError(
                "xml_depth_limit_exceeded",
                f"XML exceeds depth {limits.max_depth}.",
            )
        if text_characters > limits.max_text_characters:
            raise UblFormatError(
                "xml_text_limit_exceeded",
                f"XML exceeds {limits.max_text_characters} text characters.",
            )
        stack.extend((child, depth + 1) for child in list(element))


def _resolve_invoice_root(root: ET.Element, limits: UblLimits) -> _ParsedXml:
    root_name = _local_name(root.tag)
    if root_name not in SUPPORTED_ROOTS:
        raise UblFormatError(
            "unsupported_ubl_document",
            f"Unsupported UBL root document: {root_name}.",
            xml_xpath=f"/{root_name}",
        )
    _validate_ubl_namespace(root, root_name)
    if root_name == "Invoice":
        return _ParsedXml(root, root_name, None, root)

    paths = _build_logical_paths(root)
    for element in root.iter():
        if _local_name(element.tag) == "Invoice":
            _validate_ubl_namespace(element, "Invoice")
            return _ParsedXml(element, root_name, paths[id(element)], root)

    candidates: list[tuple[ET.Element, bytes]] = []
    for element in root.iter():
        local = _local_name(element.tag)
        raw_text = (element.text or "").strip()
        if not raw_text:
            continue
        if local == "Description" and "<Invoice" in raw_text:
            candidates.append((element, raw_text.encode("utf-8")))
        elif local == "EmbeddedDocumentBinaryObject":
            try:
                decoded = base64.b64decode(raw_text, validate=True)
            except (ValueError, binascii.Error):
                continue
            if decoded.lstrip().startswith(b"<"):
                candidates.append((element, decoded))
    for element, payload in candidates:
        embedded = _secure_parse(payload, limits)
        if _local_name(embedded.tag) == "Invoice":
            _validate_ubl_namespace(embedded, "Invoice")
            return _ParsedXml(
                embedded,
                root_name,
                paths[id(element)],
                root,
            )
    raise UblFormatError(
        "missing_embedded_invoice",
        "AttachedDocument does not contain a supported embedded Invoice.",
        xml_xpath="/AttachedDocument",
    )



def _validate_ubl_namespace(element: ET.Element, root_name: str) -> None:
    expected = (
        "urn:oasis:names:specification:ubl:schema:xsd:"
        f"{root_name}-2"
    )
    observed = _namespace(element.tag)
    if observed != expected:
        raise UblFormatError(
            "invalid_ubl_namespace",
            f"Invalid namespace for {root_name}: {observed!r}.",
            xml_xpath=f"/{root_name}",
        )


def _read_ubl_version(root: ET.Element) -> str:
    element = _child(root, "UBLVersionID")
    raw = (element.text or "").strip() if element is not None else ""
    normalized = raw.upper().replace("UBL", "").strip()
    if normalized:
        return normalized
    raise UblFormatError(
        "missing_ubl_version",
        "UBLVersionID is required for reproducible ingestion.",
        xml_xpath="/Invoice/UBLVersionID",
    )


def _extract_party(
    party: ET.Element | None,
    collector: _Collector,
    prefix: str,
    findings: list[IngestionFinding],
) -> dict[str, str | None]:
    if party is None:
        findings.append(
            make_finding(
                rule_id="RULE-UBL-PARTY-001",
                code=f"missing_{prefix}_party",
                category="data_quality",
                severity="error",
                message=f"UBL invoice is missing {prefix} party.",
                source_location_id=None,
                entity_type="invoice",
                field=f"{prefix}_party",
            )
        )
        return {
            "name": None,
            "identification_id": None,
            "tax_id": None,
            "tax_scheme": None,
            "email": None,
        }
    name_element = _path(party, "PartyLegalEntity", "RegistrationName")
    if name_element is None:
        name_element = _path(party, "PartyName", "Name")
    name, _ = collector.text(name_element, f"{prefix}.name")
    identification, _ = collector.text(
        _path(party, "PartyIdentification", "ID"),
        f"{prefix}.identification_id",
    )
    tax_id, _ = collector.text(
        _path(party, "PartyTaxScheme", "CompanyID"), f"{prefix}.tax_id"
    )
    tax_scheme, _ = collector.text(
        _path(party, "PartyTaxScheme", "TaxScheme", "ID"),
        f"{prefix}.tax_scheme",
    )
    email, _ = collector.text(
        _path(party, "Contact", "ElectronicMail"), f"{prefix}.email"
    )
    return {
        "name": name,
        "identification_id": identification,
        "tax_id": tax_id,
        "tax_scheme": tax_scheme,
        "email": email,
    }


def _extract_line(
    element: ET.Element,
    *,
    index: int,
    document_id: str,
    collector: _Collector,
    findings: list[IngestionFinding],
) -> InvoiceLine | None:
    line_id, line_location = collector.text(
        _child(element, "ID"), f"lines[{index}].invoice_line_id"
    )
    name_element = _path(element, "Item", "Name")
    if name_element is None:
        name_element = _path(element, "Item", "Description")
    name, _ = collector.text(name_element, f"lines[{index}].product_name_raw")
    product_id, _ = collector.text(
        _path(element, "Item", "SellersItemIdentification", "ID"),
        f"lines[{index}].product_id",
    )
    quantity = _decimal_from_element(
        _child(element, "InvoicedQuantity"),
        collector=collector,
        field=f"lines[{index}].quantity",
        findings=findings,
    )
    unit_price = _decimal_from_element(
        _path(element, "Price", "PriceAmount"),
        collector=collector,
        field=f"lines[{index}].unit_price_cop",
        findings=findings,
    )
    line_total = _decimal_from_element(
        _child(element, "LineExtensionAmount"),
        collector=collector,
        field=f"lines[{index}].line_total_cop",
        findings=findings,
    )
    required = {
        "product_name_raw": name,
        "quantity": quantity,
        "unit_price_cop": unit_price,
        "line_total_cop": line_total,
    }
    missing = [key for key, value in required.items() if value is None or value == ""]
    for field in missing:
        findings.append(
            make_finding(
                rule_id="RULE-UBL-LINE-REQUIRED-001",
                code="missing_required_field",
                category="data_quality",
                severity="error",
                message=f"Required UBL invoice line field is missing: {field}.",
                source_location_id=line_location,
                entity_type="invoice_line",
                record_id=line_id or f"{document_id}-LINE-{index}",
                field=f"lines[{index}].{field}",
            )
        )
    if missing:
        return None
    assert name is not None
    assert quantity is not None and unit_price is not None and line_total is not None
    if quantity <= 0:
        findings.append(
            make_finding(
                rule_id="RULE-UBL-QUANTITY-001",
                code="invalid_quantity",
                category="data_quality",
                severity="error",
                message="UBL invoice line quantity must be greater than zero.",
                source_location_id=line_location,
                entity_type="invoice_line",
                record_id=line_id or f"{document_id}-LINE-{index}",
                field=f"lines[{index}].quantity",
                observed_value=quantity,
                expected_value=">0",
            )
        )
    return InvoiceLine(
        invoice_line_id=line_id or f"INVL-UBL-{document_id[-12:]}-{index:03d}",
        product_name_raw=name,
        product_id=product_id,
        quantity=quantity,
        unit_price_cop=unit_price,
        line_total_cop=line_total,
        record_status=(
            RecordStatus.PENDING_REVIEW if quantity <= 0 else RecordStatus.ACCEPTED
        ),
        source_location_id=line_location
        or stable_xml_location_id(collector.file_hash, f"/Invoice/InvoiceLine[{index}]", "line"),
    )


def _decimal_from_element(
    element: ET.Element | None,
    *,
    collector: _Collector,
    field: str,
    findings: list[IngestionFinding],
) -> Decimal | None:
    raw, location_id = collector.text(element, field)
    if raw is None:
        return None
    try:
        value = Decimal(raw)
    except InvalidOperation:
        findings.append(
            make_finding(
                rule_id="RULE-UBL-DECIMAL-001",
                code="invalid_decimal",
                category="data_quality",
                severity="error",
                message=f"UBL value is not a valid decimal: {field}.",
                source_location_id=location_id,
                entity_type="invoice",
                field=field,
                observed_value=raw,
                expected_value="decimal",
            )
        )
        return None
    if not value.is_finite():
        findings.append(
            make_finding(
                rule_id="RULE-UBL-DECIMAL-001",
                code="non_finite_number",
                category="data_quality",
                severity="error",
                message=f"UBL value must be finite: {field}.",
                source_location_id=location_id,
                entity_type="invoice",
                field=field,
                observed_value=raw,
                expected_value="finite decimal",
            )
        )
        return None
    return value


def _parse_date(
    raw: str | None,
    *,
    field: str,
    location_id: str | None,
    findings: list[IngestionFinding],
) -> date | None:
    if raw is None:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        findings.append(
            make_finding(
                rule_id="RULE-UBL-DATE-001",
                code="invalid_date",
                category="data_quality",
                severity="error",
                message=f"UBL value is not an ISO date: {field}.",
                source_location_id=location_id,
                entity_type="invoice",
                field=field,
                observed_value=raw,
                expected_value="YYYY-MM-DD",
            )
        )
        return None


def _extract_tax_subtotal(
    element: ET.Element,
    collector: _Collector,
    index: int,
) -> dict[str, str | None]:
    taxable, _ = collector.text(
        _child(element, "TaxableAmount"), f"tax_details[{index}].taxable_amount"
    )
    amount, _ = collector.text(
        _child(element, "TaxAmount"), f"tax_details[{index}].tax_amount"
    )
    percent, _ = collector.text(
        _path(element, "TaxCategory", "Percent"), f"tax_details[{index}].percent"
    )
    scheme_id, _ = collector.text(
        _path(element, "TaxCategory", "TaxScheme", "ID"),
        f"tax_details[{index}].scheme_id",
    )
    scheme_name, _ = collector.text(
        _path(element, "TaxCategory", "TaxScheme", "Name"),
        f"tax_details[{index}].scheme_name",
    )
    return {
        "taxable_amount": taxable,
        "tax_amount": amount,
        "percent": percent,
        "scheme_id": scheme_id,
        "scheme_name": scheme_name,
    }


def _validate_amount_currencies(
    root: ET.Element,
    *,
    document_currency: str | None,
    collector: _Collector,
    findings: list[IngestionFinding],
    record_id: str,
) -> None:
    if not document_currency:
        return
    for element in root.iter():
        if not _local_name(element.tag).endswith("Amount"):
            continue
        currency = element.attrib.get("currencyID")
        if currency and currency != document_currency:
            location_id = collector.location(
                element,
                "currencyID",
                currency,
            )
            findings.append(
                make_finding(
                    rule_id="RULE-UBL-CURRENCY-CONSISTENCY-001",
                    code="inconsistent_currency",
                    category="data_quality",
                    severity="error",
                    message="UBL monetary amount currency differs from DocumentCurrencyCode.",
                    source_location_id=location_id,
                    entity_type="invoice",
                    record_id=record_id,
                    field="currencyID",
                    observed_value=currency,
                    expected_value=document_currency,
                )
            )


def _quality_to_finding(
    quality: Any,
    *,
    locations: Iterable[XmlSourceLocation],
    entity_type: str,
    record_id: str,
) -> IngestionFinding:
    source_location_id = None
    if quality.field:
        for location in reversed(tuple(locations)):
            if location.field == quality.field:
                source_location_id = location.source_location_id
                break
    rule_by_code = {
        "missing_required_field": "RULE-UBL-REQUIRED-001",
        "line_total_mismatch": "RULE-UBL-LINE-TOTAL-001",
        "subtotal_line_sum_mismatch": "RULE-UBL-SUBTOTAL-001",
        "document_total_mismatch": "RULE-UBL-DOCUMENT-TOTAL-001",
    }
    return make_finding(
        rule_id=rule_by_code.get(quality.code, "RULE-UBL-QUALITY-001"),
        code=quality.code,
        category="data_quality",
        severity=quality.severity,
        message=quality.message,
        source_location_id=source_location_id,
        entity_type=entity_type,
        record_id=record_id,
        field=quality.field,
        observed_value=quality.observed_value,
        expected_value=quality.expected_value,
    )


def _build_logical_paths(root: ET.Element) -> dict[int, str]:
    paths: dict[int, str] = {id(root): f"/{_local_name(root.tag)}"}

    def visit(parent: ET.Element) -> None:
        children = list(parent)
        totals: dict[str, int] = {}
        for child in children:
            name = _local_name(child.tag)
            totals[name] = totals.get(name, 0) + 1
        seen: dict[str, int] = {}
        for child in children:
            name = _local_name(child.tag)
            seen[name] = seen.get(name, 0) + 1
            suffix = f"[{seen[name]}]" if totals[name] > 1 else ""
            paths[id(child)] = f"{paths[id(parent)]}/{name}{suffix}"
            visit(child)

    visit(root)
    return paths


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _namespace(tag: str) -> str | None:
    if tag.startswith("{") and "}" in tag:
        return tag[1:].split("}", 1)[0]
    return None


def _child(parent: ET.Element | None, name: str) -> ET.Element | None:
    if parent is None:
        return None
    for child in list(parent):
        if _local_name(child.tag) == name:
            return child
    return None


def _children(parent: ET.Element | None, name: str) -> list[ET.Element]:
    if parent is None:
        return []
    return [child for child in list(parent) if _local_name(child.tag) == name]


def _descendants(parent: ET.Element, name: str) -> list[ET.Element]:
    return [item for item in parent.iter() if _local_name(item.tag) == name]


def _path(parent: ET.Element | None, *names: str) -> ET.Element | None:
    current = parent
    for name in names:
        current = _child(current, name)
        if current is None:
            return None
    return current
