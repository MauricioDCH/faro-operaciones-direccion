"""Validate Faro's generated synthetic dataset against its ground truth."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from hashlib import sha256
from pathlib import Path
import json
import re
import unicodedata
import zipfile
from urllib.parse import urlparse
from typing import Any, Iterable, Mapping, Sequence
from xml.etree import ElementTree as ET

from faro.synthetic.formats import extract_pdf_text_lines

XLSX_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
COP = Decimal("0.01")


class DatasetValidationError(RuntimeError):
    """Raised when required dataset artifacts cannot be read."""


def _cell_column_index(reference: str) -> int:
    letters = "".join(character for character in reference if character.isalpha())
    index = 0
    for character in letters:
        index = index * 26 + (ord(character.upper()) - ord("A") + 1)
    return index - 1


def _excel_serial_to_iso(value: float, header: str) -> str:
    epoch = datetime(1899, 12, 30)
    converted = epoch + timedelta(days=value)
    if header.endswith("_date"):
        return converted.date().isoformat()
    return converted.isoformat()


def _read_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    try:
        root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    values: list[str] = []
    for item in root.findall(f"{{{XLSX_NS}}}si"):
        fragments = [node.text or "" for node in item.iter(f"{{{XLSX_NS}}}t")]
        values.append("".join(fragments))
    return values


def _resolve_sheet_path(archive: zipfile.ZipFile, sheet_name: str) -> str:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    relationship_targets = {
        relationship.attrib["Id"]: relationship.attrib["Target"]
        for relationship in relationships.findall(f"{{{PACKAGE_REL_NS}}}Relationship")
    }
    sheets = workbook.find(f"{{{XLSX_NS}}}sheets")
    if sheets is None:
        raise DatasetValidationError("Workbook has no sheets collection.")
    for sheet in sheets:
        if sheet.attrib.get("name") == sheet_name:
            relationship_id = sheet.attrib[f"{{{REL_NS}}}id"]
            target = relationship_targets[relationship_id]
            target = target.lstrip("/")
            return target if target.startswith("xl/") else f"xl/{target}"
    raise DatasetValidationError(f"Worksheet {sheet_name!r} was not found.")


def _read_xlsx_sheet(path: Path, sheet_name: str) -> list[dict[str, Any]]:
    with zipfile.ZipFile(path) as archive:
        shared_strings = _read_shared_strings(archive)
        sheet_path = _resolve_sheet_path(archive, sheet_name)
        root = ET.fromstring(archive.read(sheet_path))

    parsed_rows: list[dict[int, Any]] = []
    sheet_data = root.find(f"{{{XLSX_NS}}}sheetData")
    if sheet_data is None:
        return []
    for row in sheet_data.findall(f"{{{XLSX_NS}}}row"):
        parsed: dict[int, Any] = {}
        for cell in row.findall(f"{{{XLSX_NS}}}c"):
            reference = cell.attrib.get("r", "A1")
            column_index = _cell_column_index(reference)
            cell_type = cell.attrib.get("t")
            value_node = cell.find(f"{{{XLSX_NS}}}v")
            if cell_type == "inlineStr":
                text_node = cell.find(f".//{{{XLSX_NS}}}t")
                value: Any = text_node.text if text_node is not None else ""
            elif value_node is None:
                value = None
            elif cell_type == "s":
                value = shared_strings[int(value_node.text or "0")]
            elif cell_type == "b":
                value = value_node.text == "1"
            elif cell_type in {"str", "e"}:
                value = value_node.text
            else:
                raw = value_node.text or ""
                try:
                    number = float(raw)
                    value = int(number) if number.is_integer() else number
                except ValueError:
                    value = raw
            parsed[column_index] = value
        parsed_rows.append(parsed)

    if not parsed_rows:
        return []
    max_header_column = max(parsed_rows[0], default=-1)
    headers = [parsed_rows[0].get(index) for index in range(max_header_column + 1)]
    records: list[dict[str, Any]] = []
    for row_number, parsed in enumerate(parsed_rows[1:], start=2):
        record: dict[str, Any] = {"__row__": row_number}
        for index, header in enumerate(headers):
            if not header:
                continue
            value = parsed.get(index)
            if isinstance(value, (int, float)) and (str(header).endswith("_date") or str(header).endswith("_at")):
                value = _excel_serial_to_iso(float(value), str(header))
            record[str(header)] = value
        records.append(record)
    return records


def _decimal(value: Any) -> Decimal:
    if value in {None, ""}:
        return Decimal("0")
    try:
        return Decimal(str(value))
    except InvalidOperation as error:
        raise DatasetValidationError(f"Invalid decimal value: {value!r}") from error


def _normalized_name(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    ascii_text = "".join(character for character in decomposed if not unicodedata.combining(character))
    return re.sub(r"[^a-z0-9]+", "", ascii_text.lower())


def _parse_invoice(path: Path) -> dict[str, Any]:
    invoice: dict[str, Any] = {"__file__": str(path), "lines": []}
    for raw_line in extract_pdf_text_lines(path):
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("LINE|") and not line.startswith("LINE|invoice_line_id|"):
            parts = line.split("|")
            if len(parts) != 7:
                raise DatasetValidationError(f"Unexpected invoice line in {path}: {line}")
            invoice["lines"].append(
                {
                    "invoice_line_id": parts[1],
                    "product_name_raw": parts[2],
                    "product_id": parts[3],
                    "quantity": _decimal(parts[4]),
                    "unit_price_cop": _decimal(parts[5]),
                    "line_total_cop": _decimal(parts[6]),
                }
            )
            continue
        if ": " in line:
            key, value = line.split(": ", 1)
            if key in {
                "invoice_id",
                "invoice_number",
                "supplier_name_raw",
                "supplier_id",
                "issue_date",
                "related_order_id",
                "currency",
            }:
                invoice[key] = value
            elif key in {"subtotal_cop", "tax_cop", "total_cop"}:
                invoice[key] = _decimal(value)
    required = {
        "invoice_id",
        "invoice_number",
        "supplier_name_raw",
        "supplier_id",
        "issue_date",
        "related_order_id",
        "total_cop",
    }
    missing = sorted(required.difference(invoice))
    if missing:
        raise DatasetValidationError(f"Missing invoice fields in {path}: {missing}")
    return invoice


def _yaml_scalar(raw: str) -> Any:
    value = raw.strip()
    if not value:
        return ""
    if value in {"true", "false"}:
        return value == "true"
    if value in {"null", "~"}:
        return None
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value


def _load_yaml(path: Path) -> dict[str, Any]:
    """Parse Faro's controlled rule-file YAML subset without external packages."""

    result: dict[str, Any] = {}
    rules: list[dict[str, Any]] = []
    current_rule: dict[str, Any] | None = None
    current_parameters: dict[str, Any] | None = None
    current_list_key: str | None = None

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        stripped = raw_line.strip()

        if indent == 0:
            current_rule = None
            current_parameters = None
            current_list_key = None
            if stripped == "rules:":
                result["rules"] = rules
                continue
            key, raw_value = stripped.split(":", 1)
            result[key] = _yaml_scalar(raw_value)
            continue

        if indent == 2 and stripped.startswith("- id:"):
            current_rule = {"id": _yaml_scalar(stripped.split(":", 1)[1])}
            rules.append(current_rule)
            current_parameters = None
            current_list_key = None
            continue

        if current_rule is None:
            raise DatasetValidationError(f"Unsupported YAML structure in {path}: {raw_line}")

        if indent == 4:
            current_list_key = None
            if stripped == "parameters:":
                current_parameters = {}
                current_rule["parameters"] = current_parameters
                continue
            key, raw_value = stripped.split(":", 1)
            current_rule[key] = _yaml_scalar(raw_value)
            continue

        if indent == 6 and current_parameters is not None:
            key, raw_value = stripped.split(":", 1)
            if raw_value.strip():
                current_parameters[key] = _yaml_scalar(raw_value)
                current_list_key = None
            else:
                current_parameters[key] = []
                current_list_key = key
            continue

        if indent == 8 and stripped.startswith("- ") and current_parameters is not None and current_list_key:
            current_parameters[current_list_key].append(_yaml_scalar(stripped[2:]))
            continue

        raise DatasetValidationError(f"Unsupported YAML structure in {path}: {raw_line}")

    if "rules" not in result:
        result["rules"] = rules
    return result


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise DatasetValidationError(f"Expected object in {path}")
    return value


def _rule_index(rules: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {rule["id"]: rule for rule in rules.get("rules", [])}


def _finding(
    rule: Mapping[str, Any],
    source_file: str,
    source_record_ids: Sequence[str],
    source_location: Mapping[str, Any],
    details: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "rule_id": rule["id"],
        "type": rule["type"],
        "severity": rule["severity"],
        "source_file": source_file,
        "source_record_ids": list(source_record_ids),
        "source_location": dict(source_location),
        "details": dict(details or {}),
    }


def _detect_findings(root: Path, rules: Mapping[str, Any]) -> list[dict[str, Any]]:
    rule_by_id = _rule_index(rules)
    catalogs_path = root / "data/raw/catalogos.xlsx"
    sales_path = root / "data/raw/ventas.xlsx"
    inventory_path = root / "data/raw/inventario.xlsx"
    orders_path = root / "data/raw/pedidos.xlsx"
    plugin_path = root / "data/samples/plugin-email-batch.example.json"

    products = _read_xlsx_sheet(catalogs_path, "productos")
    customers = _read_xlsx_sheet(catalogs_path, "clientes")
    suppliers = _read_xlsx_sheet(catalogs_path, "proveedores")
    sales = _read_xlsx_sheet(sales_path, "ventas")
    inventory = _read_xlsx_sheet(inventory_path, "inventario")
    orders = _read_xlsx_sheet(orders_path, "pedidos")
    invoices = [
        _parse_invoice(path)
        for path in sorted((root / "data/raw/facturas").glob("factura_*.pdf"))
    ]
    plugin_batch = _load_json(plugin_path)

    product_ids = {row["product_id"] for row in products}
    customer_ids = {row["customer_id"] for row in customers}
    supplier_by_id = {row["supplier_id"]: row for row in suppliers}
    order_by_id = {row["order_id"]: row for row in orders}

    findings: list[dict[str, Any]] = []
    invalid_sale_line_ids: set[str] = set()

    duplicate_groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in sales:
        key = (
            row.get("sale_id"),
            row.get("sale_date"),
            row.get("customer_id"),
            row.get("product_id"),
            row.get("quantity"),
            row.get("unit_price_cop"),
            row.get("discount_cop"),
            row.get("line_total_cop"),
            row.get("channel"),
        )
        duplicate_groups[key].append(row)
    for rows in duplicate_groups.values():
        if len(rows) > 1:
            ordered = sorted(rows, key=lambda item: item["__row__"])
            record_ids = [str(row["sale_line_id"]) for row in ordered]
            invalid_sale_line_ids.update(record_ids[1:])
            findings.append(
                _finding(
                    rule_by_id["RULE-DUP-SALE-001"],
                    "data/raw/ventas.xlsx",
                    record_ids,
                    {"sheet": "ventas", "rows": [row["__row__"] for row in ordered]},
                )
            )

    required_fields = ["sale_id", "sale_line_id", "sale_date", "customer_id", "product_id", "quantity"]
    for row in sales:
        missing = [field for field in required_fields if row.get(field) in {None, ""}]
        if missing:
            invalid_sale_line_ids.add(str(row["sale_line_id"]))
            findings.append(
                _finding(
                    rule_by_id["RULE-REQUIRED-001"],
                    "data/raw/ventas.xlsx",
                    [str(row["sale_line_id"])],
                    {"sheet": "ventas", "row": row["__row__"], "column": missing[0]},
                    {"missing_fields": missing},
                )
            )

        sale_date = row.get("sale_date")
        try:
            parsed_date = date.fromisoformat(str(sale_date))
        except (TypeError, ValueError):
            parsed_date = None
        if parsed_date is None:
            invalid_sale_line_ids.add(str(row["sale_line_id"]))
            findings.append(
                _finding(
                    rule_by_id["RULE-DATE-001"],
                    "data/raw/ventas.xlsx",
                    [str(row["sale_line_id"])],
                    {"sheet": "ventas", "row": row["__row__"], "column": "sale_date"},
                    {"observed_value": sale_date},
                )
            )

        if _decimal(row.get("quantity")) < 0:
            invalid_sale_line_ids.add(str(row["sale_line_id"]))
            findings.append(
                _finding(
                    rule_by_id["RULE-QUANTITY-001"],
                    "data/raw/ventas.xlsx",
                    [str(row["sale_line_id"])],
                    {"sheet": "ventas", "row": row["__row__"], "column": "quantity"},
                    {"observed_value": str(row.get("quantity"))},
                )
            )

        if row.get("product_id") not in product_ids:
            invalid_sale_line_ids.add(str(row["sale_line_id"]))
            findings.append(
                _finding(
                    rule_by_id["RULE-FK-PRODUCT-001"],
                    "data/raw/ventas.xlsx",
                    [str(row["sale_line_id"])],
                    {"sheet": "ventas", "row": row["__row__"], "column": "product_id"},
                    {"observed_value": row.get("product_id")},
                )
            )

        if row.get("customer_id") not in {None, ""} and row.get("customer_id") not in customer_ids:
            raise DatasetValidationError(f"Unexpected customer reference: {row.get('customer_id')}")

    for row in inventory:
        available = _decimal(row.get("stock_on_hand")) - _decimal(row.get("committed_quantity"))
        reorder = _decimal(row.get("reorder_point"))
        if available < reorder:
            findings.append(
                _finding(
                    rule_by_id["RULE-LOW-STOCK-001"],
                    "data/raw/inventario.xlsx",
                    [str(row["product_id"])],
                    {"sheet": "inventario", "row": row["__row__"], "column": "stock_on_hand"},
                    {"available_quantity": str(available), "reorder_point": str(reorder)},
                )
            )

    for invoice in invoices:
        supplier = supplier_by_id.get(invoice["supplier_id"])
        if supplier is None:
            raise DatasetValidationError(f"Unknown invoice supplier {invoice['supplier_id']}")
        if _normalized_name(invoice["supplier_name_raw"]) != _normalized_name(supplier["supplier_name"]):
            findings.append(
                _finding(
                    rule_by_id["RULE-SUPPLIER-NAME-001"],
                    str(Path(invoice["__file__"]).relative_to(root)),
                    [str(invoice["invoice_id"]), str(invoice["supplier_id"])],
                    {"page": 1, "field": "supplier_name_raw"},
                    {
                        "observed_value": invoice["supplier_name_raw"],
                        "expected_value": supplier["supplier_name"],
                    },
                )
            )

        order = order_by_id.get(invoice["related_order_id"])
        if order is None:
            continue
        for line in invoice["lines"]:
            if line["product_id"] == order["product_id"] and line["quantity"] != _decimal(order["ordered_quantity"]):
                findings.append(
                    _finding(
                        rule_by_id["RULE-ORDER-INVOICE-001"],
                        str(Path(invoice["__file__"]).relative_to(root)),
                        [str(order["order_line_id"]), str(line["invoice_line_id"])],
                        {"page": 1, "field": "quantity"},
                        {
                            "ordered_quantity": str(order["ordered_quantity"]),
                            "invoiced_quantity": str(line["quantity"]),
                        },
                    )
                )

    invoice_groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for invoice in invoices:
        key = (invoice["supplier_id"], invoice["invoice_number"], invoice["issue_date"])
        invoice_groups[key].append(invoice)
    for group in invoice_groups.values():
        if len(group) > 1:
            ordered = sorted(group, key=lambda item: item["invoice_id"])
            findings.append(
                _finding(
                    rule_by_id["RULE-DUP-INVOICE-001"],
                    str(Path(ordered[-1]["__file__"]).relative_to(root)),
                    [str(invoice["invoice_id"]) for invoice in ordered],
                    {"page": 1, "field": "invoice_number"},
                )
            )

    for message_index, message in enumerate(plugin_batch.get("messages", []), start=1):
        if message.get("event_type") != "quantity_change":
            continue
        extracted = {
            item["field"]: item.get("proposed_value")
            for item in message.get("extractions", [])
        }
        order_id = extracted.get("order_id")
        product_id = extracted.get("product_id")
        new_quantity = extracted.get("new_quantity")
        order = order_by_id.get(order_id)
        if order and order.get("product_id") == product_id and _decimal(order.get("ordered_quantity")) != _decimal(new_quantity):
            findings.append(
                _finding(
                    rule_by_id["RULE-EMAIL-ORDER-001"],
                    "data/samples/plugin-email-batch.example.json",
                    [str(order["order_line_id"]), f"MSG-{message_index:06d}"],
                    {"source_reference": message["source_reference"], "field": "new_quantity"},
                    {
                        "ordered_quantity": str(order["ordered_quantity"]),
                        "requested_quantity": str(new_quantity),
                    },
                )
            )

    period_totals = {"2026-06": Decimal("0"), "2026-07": Decimal("0")}
    for row in sales:
        sale_line_id = str(row.get("sale_line_id"))
        if sale_line_id in invalid_sale_line_ids:
            continue
        try:
            parsed_date = date.fromisoformat(str(row.get("sale_date")))
        except ValueError:
            continue
        period = parsed_date.strftime("%Y-%m")
        if period in period_totals:
            period_totals[period] += _decimal(row.get("line_total_cop"))
    previous_total = period_totals["2026-06"]
    current_total = period_totals["2026-07"]
    decline_pct = ((current_total - previous_total) / previous_total * Decimal("100")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    threshold = Decimal(str(rule_by_id["RULE-SALES-DECLINE-001"]["parameters"]["threshold_pct"]))
    if decline_pct <= threshold:
        findings.append(
            _finding(
                rule_by_id["RULE-SALES-DECLINE-001"],
                "data/raw/ventas.xlsx",
                ["PERIOD-2026-06", "PERIOD-2026-07"],
                {"sheet": "ventas", "column": "line_total_cop"},
                {
                    "previous_total_cop": str(previous_total.quantize(COP)),
                    "current_total_cop": str(current_total.quantize(COP)),
                    "decline_pct": str(decline_pct),
                    "threshold_pct": str(threshold),
                },
            )
        )

    return findings


def _finding_key(value: Mapping[str, Any]) -> tuple[str, tuple[str, ...]]:
    rule_id = str(value.get("expected_rule_id") or value.get("rule_id"))
    record_ids = tuple(sorted(str(item) for item in value.get("source_record_ids", [])))
    return rule_id, record_ids


def _validate_manifest(root: Path, report_errors: list[str]) -> dict[str, Any]:
    manifest_path = root / "data/expected/dataset_manifest.json"
    manifest = _load_json(manifest_path)
    for relative, expected_hash in manifest.get("files", {}).items():
        path = root / relative
        if not path.is_file():
            report_errors.append(f"Manifest file missing: {relative}")
            continue
        digest = sha256(path.read_bytes()).hexdigest()
        if digest != expected_hash:
            report_errors.append(f"Hash mismatch: {relative}")
    return manifest


def _schema_type_matches(value: Any, expected_type: str) -> bool:
    if expected_type == "object":
        return isinstance(value, dict)
    if expected_type == "array":
        return isinstance(value, list)
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "null":
        return value is None
    return False


def _resolve_local_ref(root_schema: Mapping[str, Any], reference: str) -> Mapping[str, Any]:
    if not reference.startswith("#/"):
        raise DatasetValidationError(f"Only local JSON Schema references are supported: {reference}")
    current: Any = root_schema
    for part in reference[2:].split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        current = current[part]
    if not isinstance(current, Mapping):
        raise DatasetValidationError(f"JSON Schema reference does not resolve to an object: {reference}")
    return current


def _validate_schema_value(
    value: Any,
    schema: Mapping[str, Any],
    root_schema: Mapping[str, Any],
    path: tuple[str | int, ...] = (),
) -> list[str]:
    if "$ref" in schema:
        resolved = _resolve_local_ref(root_schema, str(schema["$ref"]))
        return _validate_schema_value(value, resolved, root_schema, path)

    errors: list[str] = []
    location = ".".join(str(part) for part in path) or "$"

    if "const" in schema and value != schema["const"]:
        errors.append(f"{location}: expected constant {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{location}: value {value!r} is not in the allowed enum")

    expected_types = schema.get("type")
    if isinstance(expected_types, str):
        expected_types = [expected_types]
    if expected_types is not None:
        if not any(_schema_type_matches(value, expected) for expected in expected_types):
            errors.append(f"{location}: expected type {expected_types}, got {type(value).__name__}")
            return errors

    if isinstance(value, dict):
        required = schema.get("required", [])
        for field in required:
            if field not in value:
                errors.append(f"{location}: missing required property {field!r}")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            extras = sorted(set(value) - set(properties))
            for field in extras:
                errors.append(f"{location}: unexpected property {field!r}")
        for field, child_schema in properties.items():
            if field in value:
                errors.extend(
                    _validate_schema_value(
                        value[field],
                        child_schema,
                        root_schema,
                        path + (field,),
                    )
                )

    if isinstance(value, list):
        minimum_items = schema.get("minItems")
        if minimum_items is not None and len(value) < int(minimum_items):
            errors.append(f"{location}: expected at least {minimum_items} item(s)")
        item_schema = schema.get("items")
        if isinstance(item_schema, Mapping):
            for index, item in enumerate(value):
                errors.extend(
                    _validate_schema_value(item, item_schema, root_schema, path + (index,))
                )

    if isinstance(value, str):
        if "minLength" in schema and len(value) < int(schema["minLength"]):
            errors.append(f"{location}: string is shorter than {schema['minLength']}")
        if "maxLength" in schema and len(value) > int(schema["maxLength"]):
            errors.append(f"{location}: string is longer than {schema['maxLength']}")
        if schema.get("format") == "date-time":
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    raise ValueError("timezone is required")
            except ValueError:
                errors.append(f"{location}: invalid RFC 3339 date-time")
        if schema.get("format") == "uri":
            parsed_uri = urlparse(value)
            if not parsed_uri.scheme:
                errors.append(f"{location}: invalid URI")

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{location}: value is below minimum {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{location}: value is above maximum {schema['maximum']}")

    return errors


def _validate_plugin_schema(root: Path, report_errors: list[str]) -> None:
    schema_path = root / "schemas/plugin-email-batch.schema.json"
    instance_path = root / "data/samples/plugin-email-batch.example.json"
    schema = _load_json(schema_path)
    instance = _load_json(instance_path)
    for error in _validate_schema_value(instance, schema, schema):
        report_errors.append(f"Plugin schema error at {error}")


def validate_dataset(
    root: Path,
    rules_path: Path | None = None,
    expected_path: Path | None = None,
    report_path: Path | None = None,
) -> dict[str, Any]:
    """Validate generated sources and compare findings with expected anomalies."""

    root = root.resolve()
    rules_path = rules_path or root / "config/data-quality-rules.yaml"
    expected_path = expected_path or root / "data/expected/expected_anomalies.json"
    report_path = report_path or root / "data/processed/validation_report.json"

    errors: list[str] = []
    rules = _load_yaml(rules_path)
    expected = _load_json(expected_path)
    manifest = _validate_manifest(root, errors)
    _validate_plugin_schema(root, errors)
    findings = _detect_findings(root, rules)

    expected_by_key = {_finding_key(item): item for item in expected.get("anomalies", []) if item.get("expected_detected")}
    actual_by_key = {_finding_key(item): item for item in findings}

    matched_keys = sorted(expected_by_key.keys() & actual_by_key.keys())
    missing_keys = sorted(expected_by_key.keys() - actual_by_key.keys())
    unexpected_keys = sorted(actual_by_key.keys() - expected_by_key.keys())

    for key in matched_keys:
        expected_item = expected_by_key[key]
        actual_item = actual_by_key[key]
        if expected_item.get("type") != actual_item.get("type"):
            errors.append(f"Type mismatch for {expected_item['anomaly_id']}")
        if expected_item.get("severity") != actual_item.get("severity"):
            errors.append(f"Severity mismatch for {expected_item['anomaly_id']}")
        actual_item["matched_anomaly_id"] = expected_item["anomaly_id"]

    if missing_keys:
        errors.append(f"Missing expected anomalies: {len(missing_keys)}")
    if unexpected_keys:
        errors.append(f"Unexpected findings: {len(unexpected_keys)}")

    report = {
        "schema_version": "1.0.0",
        "dataset_version": expected.get("dataset_version"),
        "seed": expected.get("seed"),
        "validated_at": "2026-07-31T04:10:00-05:00",
        "status": "passed" if not errors else "failed",
        "summary": {
            "expected": len(expected_by_key),
            "detected": len(actual_by_key),
            "matched": len(matched_keys),
            "missing": len(missing_keys),
            "unexpected": len(unexpected_keys),
        },
        "matched_anomaly_ids": [
            item["anomaly_id"]
            for item in expected.get("anomalies", [])
            if item.get("expected_detected") and _finding_key(item) in actual_by_key
        ],
        "missing": [
            {
                "rule_id": key[0],
                "source_record_ids": list(key[1]),
                "anomaly_id": expected_by_key[key]["anomaly_id"],
            }
            for key in missing_keys
        ],
        "unexpected": [actual_by_key[key] for key in unexpected_keys],
        "errors": errors,
        "findings": sorted(
            findings,
            key=lambda item: (
                item.get("matched_anomaly_id", ""),
                item["rule_id"],
                tuple(item["source_record_ids"]),
            ),
        ),
        "manifest": {
            "dataset_version": manifest.get("dataset_version"),
            "counts": manifest.get("counts", {}),
        },
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report
