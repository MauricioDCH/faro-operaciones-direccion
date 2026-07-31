"""Generate Faro's deterministic synthetic operational dataset.

The generator creates related Excel workbooks, text-extractable PDF invoices,
a plugin-email fixture, expected anomaly ground truth, and a hash manifest.
Raw artifacts are never overwritten unless ``force=True`` is explicitly supplied.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from hashlib import sha256
from pathlib import Path
import json
import random
import shutil
from typing import Any, Mapping, Sequence

from faro.synthetic.formats import write_invoice_pdf, write_xlsx

DEFAULT_SEED = 20260731
DATASET_VERSION = "0.1.0"
SCHEMA_VERSION = "1.0.0"
CONTRACT_VERSION = "1.3.0"
FIXED_GENERATED_AT = "2026-07-31T04:00:00-05:00"
COP = Decimal("0.01")

GENERATED_RELATIVE_PATHS = (
    Path("data/raw/catalogos.xlsx"),
    Path("data/raw/ventas.xlsx"),
    Path("data/raw/inventario.xlsx"),
    Path("data/raw/pedidos.xlsx"),
    Path("data/samples/plugin-email-batch.example.json"),
    Path("data/expected/expected_anomalies.json"),
    Path("data/expected/dataset_manifest.json"),
)


@dataclass(frozen=True)
class DatasetBuild:
    """In-memory deterministic records used to write every source."""

    products: list[dict[str, Any]]
    customers: list[dict[str, Any]]
    suppliers: list[dict[str, Any]]
    sales: list[dict[str, Any]]
    inventory: list[dict[str, Any]]
    orders: list[dict[str, Any]]
    invoices: list[dict[str, Any]]
    plugin_batch: dict[str, Any]
    expected_anomalies: dict[str, Any]


def _money(value: Decimal | int | str) -> Decimal:
    return Decimal(value).quantize(COP, rounding=ROUND_HALF_UP)


def _line_total(quantity: Decimal | int, unit_price: Decimal, discount: Decimal = Decimal("0")) -> Decimal:
    return _money(Decimal(quantity) * unit_price - discount)


def _tax(subtotal: Decimal) -> Decimal:
    return _money(subtotal * Decimal("0.19"))


def _iso_date(year: int, month: int, day: int) -> date:
    return date(year, month, day)


def _build_products() -> list[dict[str, Any]]:
    rows = [
        ("PRD-0001", "CAF-500", "Café molido 500 g", "Bebidas", "unit", "12000", "16800"),
        ("PRD-0002", "AZU-1000", "Azúcar 1 kg", "Abarrotes", "unit", "3200", "4800"),
        ("PRD-0003", "ARR-1000", "Arroz 1 kg", "Abarrotes", "unit", "4000", "5800"),
        ("PRD-0004", "ACE-1000", "Aceite vegetal 1 L", "Abarrotes", "unit", "8500", "11500"),
        ("PRD-0005", "DET-1000", "Detergente líquido 1 L", "Aseo", "unit", "9000", "13500"),
        ("PRD-0006", "LAV-500", "Jabón lavaplatos 500 ml", "Aseo", "unit", "5200", "7800"),
        ("PRD-0007", "PAP-004", "Papel higiénico x4", "Aseo", "unit", "7800", "11000"),
        ("PRD-0008", "GAL-012", "Galletas surtidas x12", "Abarrotes", "box", "9500", "14000"),
        ("PRD-0009", "LEC-1000", "Leche UHT 1 L", "Bebidas", "unit", "3600", "5200"),
        ("PRD-0010", "CHO-500", "Chocolate de mesa 500 g", "Bebidas", "unit", "8500", "12200"),
        ("PRD-0011", "DES-1000", "Desinfectante 1 L", "Aseo", "unit", "7200", "10800"),
        ("PRD-0012", "BOL-020", "Bolsas de basura x20", "Aseo", "unit", "6800", "9900"),
    ]
    return [
        {
            "product_id": product_id,
            "sku": sku,
            "product_name": name,
            "category": category,
            "unit": unit,
            "unit_cost_cop": _money(cost),
            "sale_price_cop": _money(price),
            "active": True,
        }
        for product_id, sku, name, category, unit, cost, price in rows
    ]


def _build_customers() -> list[dict[str, Any]]:
    names = [
        "Tienda Laureles",
        "Mercado Belén",
        "Autoservicio Boston",
        "Minimercado Robledo",
        "Comercial San Javier",
        "Tienda El Poblado",
    ]
    rows: list[dict[str, Any]] = []
    for index, name in enumerate(names, start=1):
        rows.append(
            {
                "customer_id": f"CUS-{index:04d}",
                "customer_name": name,
                "customer_type": "business",
                "tax_id": f"SYN-CUS-{index:04d}",
                "city": "Medellín",
                "email": f"compras{index}@cliente.example",
                "phone": f"300000{index:04d}",
                "active": True,
            }
        )
    return rows


def _build_suppliers() -> list[dict[str, Any]]:
    names = [
        "Distribuciones Andinas SAS",
        "Abastecimientos Medellín SAS",
        "Comercializadora del Valle SAS",
        "Suministros Antioquia SAS",
    ]
    rows: list[dict[str, Any]] = []
    for index, name in enumerate(names, start=1):
        rows.append(
            {
                "supplier_id": f"SUP-{index:04d}",
                "supplier_name": name,
                "tax_id": f"SYN-SUP-{index:04d}",
                "city": "Medellín",
                "email": f"ventas{index}@proveedor.example",
                "phone": f"604000{index:04d}",
                "active": True,
            }
        )
    return rows


def _build_sales(
    rng: random.Random,
    products: Sequence[Mapping[str, Any]],
    customers: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    product_by_id = {row["product_id"]: row for row in products}
    product_ids = list(product_by_id)
    customer_ids = [row["customer_id"] for row in customers]
    channels = ["store", "phone", "email", "whatsapp"]
    rows: list[dict[str, Any]] = []

    def append_clean_line(period_start: date, period_days: int, quantity_range: tuple[int, int]) -> None:
        line_number = len(rows) + 1
        product_id = rng.choice(product_ids)
        product = product_by_id[product_id]
        quantity = Decimal(rng.randint(*quantity_range))
        discount = _money("500") if rng.random() < 0.15 else _money("0")
        unit_price = product["sale_price_cop"]
        sale_date = period_start + timedelta(days=rng.randrange(period_days))
        rows.append(
            {
                "sale_id": f"SAL-{line_number:06d}",
                "sale_line_id": f"SALL-{line_number:06d}",
                "sale_date": sale_date,
                "customer_id": rng.choice(customer_ids),
                "product_id": product_id,
                "quantity": quantity,
                "unit_price_cop": unit_price,
                "discount_cop": discount,
                "line_total_cop": _line_total(quantity, unit_price, discount),
                "channel": rng.choice(channels),
            }
        )

    for _ in range(30):
        append_clean_line(_iso_date(2026, 6, 1), 30, (8, 14))
    for _ in range(12):
        append_clean_line(_iso_date(2026, 7, 1), 31, (2, 5))

    original_duplicate = rows[30].copy()  # Excel row 32.
    duplicate = original_duplicate.copy()
    duplicate["sale_line_id"] = "SALL-000043"
    rows.append(duplicate)  # Excel row 44.

    rows.append(
        {
            "sale_id": "SAL-000044",
            "sale_line_id": "SALL-000044",
            "sale_date": _iso_date(2026, 7, 18),
            "customer_id": None,
            "product_id": "PRD-0002",
            "quantity": Decimal("2"),
            "unit_price_cop": product_by_id["PRD-0002"]["sale_price_cop"],
            "discount_cop": _money("0"),
            "line_total_cop": _line_total(2, product_by_id["PRD-0002"]["sale_price_cop"]),
            "channel": "store",
        }
    )
    rows.append(
        {
            "sale_id": "SAL-000045",
            "sale_line_id": "SALL-000045",
            "sale_date": "2026-02-30",
            "customer_id": "CUS-0002",
            "product_id": "PRD-0003",
            "quantity": Decimal("3"),
            "unit_price_cop": product_by_id["PRD-0003"]["sale_price_cop"],
            "discount_cop": _money("0"),
            "line_total_cop": _line_total(3, product_by_id["PRD-0003"]["sale_price_cop"]),
            "channel": "phone",
        }
    )
    rows.append(
        {
            "sale_id": "SAL-000046",
            "sale_line_id": "SALL-000046",
            "sale_date": _iso_date(2026, 7, 20),
            "customer_id": "CUS-0003",
            "product_id": "PRD-0004",
            "quantity": Decimal("-2"),
            "unit_price_cop": product_by_id["PRD-0004"]["sale_price_cop"],
            "discount_cop": _money("0"),
            "line_total_cop": _line_total(-2, product_by_id["PRD-0004"]["sale_price_cop"]),
            "channel": "email",
        }
    )
    rows.append(
        {
            "sale_id": "SAL-000047",
            "sale_line_id": "SALL-000047",
            "sale_date": _iso_date(2026, 7, 22),
            "customer_id": "CUS-0004",
            "product_id": "PRD-9999",
            "quantity": Decimal("4"),
            "unit_price_cop": _money("7000"),
            "discount_cop": _money("0"),
            "line_total_cop": _money("28000"),
            "channel": "whatsapp",
        }
    )

    clean_rows = rows[:42]
    june_total = sum(
        (row["line_total_cop"] for row in clean_rows if row["sale_date"].month == 6),
        Decimal("0"),
    )
    july_total = sum(
        (row["line_total_cop"] for row in clean_rows if row["sale_date"].month == 7),
        Decimal("0"),
    )
    decline_pct = ((july_total - june_total) / june_total * Decimal("100")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    if decline_pct > Decimal("-30"):
        raise AssertionError(f"Seeded sales decline is insufficient: {decline_pct}%")

    metrics = {
        "previous_period": "2026-06",
        "current_period": "2026-07",
        "previous_total_cop": str(_money(june_total)),
        "current_total_cop": str(_money(july_total)),
        "decline_pct": str(decline_pct),
    }
    return rows, metrics


def _build_inventory(products: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, product in enumerate(products, start=1):
        if product["product_id"] == "PRD-0005":
            stock, committed, reorder = Decimal("8"), Decimal("3"), Decimal("10")
        else:
            reorder = Decimal(10 + (index % 4) * 5)
            committed = Decimal(index % 3)
            stock = reorder + committed + Decimal(8 + index)
        rows.append(
            {
                "snapshot_date": _iso_date(2026, 7, 31),
                "product_id": product["product_id"],
                "stock_on_hand": stock,
                "committed_quantity": committed,
                "reorder_point": reorder,
            }
        )
    return rows


def _build_orders() -> list[dict[str, Any]]:
    definitions = [
        ("ORD-000001", "SUP-0001", "PRD-0001", "50", "12000", "2026-07-20", "2026-07-25", "received"),
        ("ORD-000002", "SUP-0002", "PRD-0005", "30", "9000", "2026-07-21", "2026-07-27", "confirmed"),
        ("ORD-000003", "SUP-0003", "PRD-0008", "40", "9500", "2026-07-22", "2026-07-28", "received"),
        ("ORD-000004", "SUP-0001", "PRD-0009", "60", "3600", "2026-07-23", "2026-07-29", "received"),
        ("ORD-000005", "SUP-0004", "PRD-0011", "25", "7200", "2026-07-24", "2026-07-30", "confirmed"),
    ]
    rows: list[dict[str, Any]] = []
    for index, definition in enumerate(definitions, start=1):
        order_id, supplier_id, product_id, quantity, cost, order_date, delivery, status = definition
        rows.append(
            {
                "order_id": order_id,
                "order_line_id": f"ORDL-{index:06d}",
                "order_date": date.fromisoformat(order_date),
                "supplier_id": supplier_id,
                "product_id": product_id,
                "ordered_quantity": Decimal(quantity),
                "expected_unit_cost_cop": _money(cost),
                "expected_delivery_date": date.fromisoformat(delivery),
                "status": status,
                "source_message_id": "MSG-000001" if order_id == "ORD-000002" else None,
                "notes": "Pedido sintético para la demostración de Faro.",
            }
        )
    return rows


def _build_invoices(
    products: Sequence[Mapping[str, Any]],
    suppliers: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    product_by_id = {row["product_id"]: row for row in products}
    supplier_by_id = {row["supplier_id"]: row for row in suppliers}
    definitions = [
        ("INV-000001", "FV-1001", "SUP-0001", "ORD-000001", "PRD-0001", "50", "12000", "2026-07-25"),
        ("INV-000002", "FV-2001", "SUP-0002", "ORD-000002", "PRD-0005", "30", "9000", "2026-07-27"),
        ("INV-000003", "FV-3001", "SUP-0003", "ORD-000003", "PRD-0008", "35", "9500", "2026-07-28"),
        ("INV-000004", "FV-1002", "SUP-0001", "ORD-000004", "PRD-0009", "60", "3600", "2026-07-29"),
        ("INV-000005", "FV-4001", "SUP-0004", "ORD-000005", "PRD-0011", "25", "7200", "2026-07-30"),
        ("INV-000006", "FV-1002", "SUP-0001", "ORD-000004", "PRD-0009", "60", "3600", "2026-07-29"),
    ]
    invoices: list[dict[str, Any]] = []
    for index, definition in enumerate(definitions, start=1):
        invoice_id, number, supplier_id, order_id, product_id, quantity, unit_price, issue_date = definition
        supplier_name = supplier_by_id[supplier_id]["supplier_name"]
        if invoice_id == "INV-000003":
            supplier_name = "Comercializadora Valle S.A.S."
        product_name = product_by_id[product_id]["product_name"]
        subtotal = _line_total(Decimal(quantity), _money(unit_price))
        tax_value = _tax(subtotal)
        invoices.append(
            {
                "invoice_id": invoice_id,
                "invoice_number": number,
                "supplier_name_raw": supplier_name,
                "supplier_id": supplier_id,
                "issue_date": date.fromisoformat(issue_date),
                "related_order_id": order_id,
                "currency": "COP",
                "subtotal_cop": subtotal,
                "tax_cop": tax_value,
                "total_cop": _money(subtotal + tax_value),
                "lines": [
                    {
                        "invoice_line_id": f"INVL-{index:06d}",
                        "product_name_raw": product_name,
                        "product_id": product_id,
                        "quantity": Decimal(quantity),
                        "unit_price_cop": _money(unit_price),
                        "line_total_cop": subtotal,
                    }
                ],
            }
        )
    return invoices


def _build_plugin_batch() -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "batch_id": "PLGMAIL-20260731-001",
        "platform": "chatgpt",
        "plugin_name": "gmail",
        "source_app": "gmail",
        "account_label": "faro-demo-synthetic",
        "query": "after:2026/07/01 before:2026/08/01 label:faro-demo",
        "prompt_version": "1.0.0",
        "generated_at": FIXED_GENERATED_AT,
        "messages": [
            {
                "provider_message_id": "synthetic-message-001",
                "thread_id": "synthetic-thread-001",
                "source_reference": "gmail-citation:synthetic-message-001",
                "source_url": None,
                "from_address": "ventas2@proveedor.example",
                "to_addresses": ["compras@faro-demo.example"],
                "subject": "Cambio pedido ORD-000002",
                "sent_at": "2026-07-26T10:30:00-05:00",
                "body_excerpt": "Del pedido ORD-000002 envíen solamente 20 unidades del producto PRD-0005.",
                "event_type": "quantity_change",
                "extractions": [
                    {
                        "field": "order_id",
                        "raw_value": "ORD-000002",
                        "proposed_value": "ORD-000002",
                        "confidence": 1.0,
                        "evidence_excerpt": "pedido ORD-000002",
                        "review_status": "accepted",
                    },
                    {
                        "field": "product_id",
                        "raw_value": "PRD-0005",
                        "proposed_value": "PRD-0005",
                        "confidence": 1.0,
                        "evidence_excerpt": "producto PRD-0005",
                        "review_status": "accepted",
                    },
                    {
                        "field": "new_quantity",
                        "raw_value": 20,
                        "proposed_value": 20,
                        "confidence": 0.99,
                        "evidence_excerpt": "solamente 20 unidades",
                        "review_status": "accepted",
                    },
                ],
            },
            {
                "provider_message_id": "synthetic-message-002",
                "thread_id": "synthetic-thread-002",
                "source_reference": "gmail-citation:synthetic-message-002",
                "source_url": None,
                "from_address": "ventas4@proveedor.example",
                "to_addresses": ["compras@faro-demo.example"],
                "subject": "Novedad de entrega ORD-000005",
                "sent_at": "2026-07-29T15:00:00-05:00",
                "body_excerpt": "La entrega del pedido ORD-000005 se mantiene para el 30 de julio de 2026.",
                "event_type": "delivery_update",
                "extractions": [
                    {
                        "field": "order_id",
                        "raw_value": "ORD-000005",
                        "proposed_value": "ORD-000005",
                        "confidence": 1.0,
                        "evidence_excerpt": "pedido ORD-000005",
                        "review_status": "accepted",
                    },
                    {
                        "field": "expected_delivery_date",
                        "raw_value": "30 de julio de 2026",
                        "proposed_value": "2026-07-30",
                        "confidence": 0.97,
                        "evidence_excerpt": "30 de julio de 2026",
                        "review_status": "accepted",
                    },
                ],
            },
        ],
        "limitations": [
            "Fixture reproducible; no representa una conexión activa durante esta ejecución."
        ],
    }


def _build_expected_anomalies(sales_metrics: Mapping[str, Any]) -> dict[str, Any]:
    anomalies = [
        {
            "anomaly_id": "ANOM-001",
            "type": "duplicate_sale_line",
            "severity": "error",
            "source_file": "data/raw/ventas.xlsx",
            "source_location": {"sheet": "ventas", "rows": [32, 44]},
            "source_record_ids": ["SALL-000031", "SALL-000043"],
            "expected_rule_id": "RULE-DUP-SALE-001",
            "expected_detected": True,
            "description": "Dos líneas representan la misma venta con identificadores de línea diferentes.",
        },
        {
            "anomaly_id": "ANOM-002",
            "type": "missing_required_field",
            "severity": "error",
            "source_file": "data/raw/ventas.xlsx",
            "source_location": {"sheet": "ventas", "row": 45, "column": "customer_id"},
            "source_record_ids": ["SALL-000044"],
            "expected_rule_id": "RULE-REQUIRED-001",
            "expected_detected": True,
            "description": "La línea de venta no contiene customer_id.",
        },
        {
            "anomaly_id": "ANOM-003",
            "type": "invalid_date",
            "severity": "error",
            "source_file": "data/raw/ventas.xlsx",
            "source_location": {"sheet": "ventas", "row": 46, "column": "sale_date"},
            "source_record_ids": ["SALL-000045"],
            "expected_rule_id": "RULE-DATE-001",
            "expected_detected": True,
            "description": "La fecha 2026-02-30 no existe.",
        },
        {
            "anomaly_id": "ANOM-004",
            "type": "negative_quantity",
            "severity": "error",
            "source_file": "data/raw/ventas.xlsx",
            "source_location": {"sheet": "ventas", "row": 47, "column": "quantity"},
            "source_record_ids": ["SALL-000046"],
            "expected_rule_id": "RULE-QUANTITY-001",
            "expected_detected": True,
            "description": "La cantidad vendida es negativa.",
        },
        {
            "anomaly_id": "ANOM-005",
            "type": "unknown_product",
            "severity": "error",
            "source_file": "data/raw/ventas.xlsx",
            "source_location": {"sheet": "ventas", "row": 48, "column": "product_id"},
            "source_record_ids": ["SALL-000047"],
            "expected_rule_id": "RULE-FK-PRODUCT-001",
            "expected_detected": True,
            "description": "La venta referencia PRD-9999, que no existe en el catálogo.",
        },
        {
            "anomaly_id": "ANOM-006",
            "type": "inconsistent_supplier_name",
            "severity": "warning",
            "source_file": "data/raw/facturas/factura_003.pdf",
            "source_location": {"page": 1, "field": "supplier_name_raw"},
            "source_record_ids": ["INV-000003", "SUP-0003"],
            "expected_rule_id": "RULE-SUPPLIER-NAME-001",
            "expected_detected": True,
            "description": "El nombre del proveedor en la factura no coincide con el catálogo.",
        },
        {
            "anomaly_id": "ANOM-007",
            "type": "low_inventory",
            "severity": "warning",
            "source_file": "data/raw/inventario.xlsx",
            "source_location": {"sheet": "inventario", "row": 6, "column": "stock_on_hand"},
            "source_record_ids": ["PRD-0005"],
            "expected_rule_id": "RULE-LOW-STOCK-001",
            "expected_detected": True,
            "description": "La cantidad disponible está por debajo del punto de reposición.",
        },
        {
            "anomaly_id": "ANOM-008",
            "type": "order_invoice_mismatch",
            "severity": "warning",
            "source_file": "data/raw/facturas/factura_003.pdf",
            "source_location": {"page": 1, "field": "quantity"},
            "source_record_ids": ["ORDL-000003", "INVL-000003"],
            "expected_rule_id": "RULE-ORDER-INVOICE-001",
            "expected_detected": True,
            "description": "El pedido solicita 40 unidades y la factura registra 35.",
        },
        {
            "anomaly_id": "ANOM-009",
            "type": "duplicate_invoice",
            "severity": "error",
            "source_file": "data/raw/facturas/factura_006.pdf",
            "source_location": {"page": 1, "field": "invoice_number"},
            "source_record_ids": ["INV-000004", "INV-000006"],
            "expected_rule_id": "RULE-DUP-INVOICE-001",
            "expected_detected": True,
            "description": "Dos documentos comparten proveedor, número y fecha de factura.",
        },
        {
            "anomaly_id": "ANOM-010",
            "type": "email_order_conflict",
            "severity": "warning",
            "source_file": "data/samples/plugin-email-batch.example.json",
            "source_location": {
                "source_reference": "gmail-citation:synthetic-message-001",
                "field": "new_quantity",
            },
            "source_record_ids": ["ORDL-000002", "MSG-000001"],
            "expected_rule_id": "RULE-EMAIL-ORDER-001",
            "expected_detected": True,
            "description": "El correo solicita 20 unidades y el pedido conserva 30.",
        },
        {
            "anomaly_id": "ANOM-011",
            "type": "abnormal_sales_decline",
            "severity": "warning",
            "source_file": "data/raw/ventas.xlsx",
            "source_location": {"sheet": "ventas", "column": "line_total_cop"},
            "source_record_ids": ["PERIOD-2026-06", "PERIOD-2026-07"],
            "expected_rule_id": "RULE-SALES-DECLINE-001",
            "expected_detected": True,
            "description": "Las ventas válidas de julio caen más del 30 % frente a junio.",
            "expected_details": dict(sales_metrics),
        },
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "dataset_version": DATASET_VERSION,
        "contract_version": CONTRACT_VERSION,
        "seed": DEFAULT_SEED,
        "status": "implemented",
        "anomalies": anomalies,
    }


def build_dataset(seed: int = DEFAULT_SEED) -> DatasetBuild:
    """Build all records in memory before writing any artifact."""

    rng = random.Random(seed)
    products = _build_products()
    customers = _build_customers()
    suppliers = _build_suppliers()
    sales, sales_metrics = _build_sales(rng, products, customers)
    inventory = _build_inventory(products)
    orders = _build_orders()
    invoices = _build_invoices(products, suppliers)
    plugin_batch = _build_plugin_batch()
    expected_anomalies = _build_expected_anomalies(sales_metrics)
    expected_anomalies["seed"] = seed
    return DatasetBuild(
        products=products,
        customers=customers,
        suppliers=suppliers,
        sales=sales,
        inventory=inventory,
        orders=orders,
        invoices=invoices,
        plugin_batch=plugin_batch,
        expected_anomalies=expected_anomalies,
    )


def _json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False, default=_json_value) + "\n",
        encoding="utf-8",
    )


def _write_workbooks(root: Path, build: DatasetBuild) -> list[Path]:
    generated: list[Path] = []

    catalog_path = root / "data/raw/catalogos.xlsx"
    write_xlsx(
        catalog_path,
        [
            (
                "productos",
                [
                    "product_id",
                    "sku",
                    "product_name",
                    "category",
                    "unit",
                    "unit_cost_cop",
                    "sale_price_cop",
                    "active",
                ],
                build.products,
            ),
            (
                "clientes",
                [
                    "customer_id",
                    "customer_name",
                    "customer_type",
                    "tax_id",
                    "city",
                    "email",
                    "phone",
                    "active",
                ],
                build.customers,
            ),
            (
                "proveedores",
                [
                    "supplier_id",
                    "supplier_name",
                    "tax_id",
                    "city",
                    "email",
                    "phone",
                    "active",
                ],
                build.suppliers,
            ),
        ],
        title="Faro - catálogos sintéticos",
        subject="Productos, clientes y proveedores sintéticos.",
    )
    generated.append(catalog_path)

    sales_path = root / "data/raw/ventas.xlsx"
    write_xlsx(
        sales_path,
        [
            (
                "ventas",
                [
                    "sale_id",
                    "sale_line_id",
                    "sale_date",
                    "customer_id",
                    "product_id",
                    "quantity",
                    "unit_price_cop",
                    "discount_cop",
                    "line_total_cop",
                    "channel",
                ],
                build.sales,
            )
        ],
        title="Faro - ventas sintéticas",
        subject="Líneas de venta sintéticas con anomalías controladas.",
    )
    generated.append(sales_path)

    inventory_path = root / "data/raw/inventario.xlsx"
    write_xlsx(
        inventory_path,
        [
            (
                "inventario",
                [
                    "snapshot_date",
                    "product_id",
                    "stock_on_hand",
                    "committed_quantity",
                    "reorder_point",
                ],
                build.inventory,
            )
        ],
        title="Faro - inventario sintético",
        subject="Inventario sintético para reglas operativas.",
    )
    generated.append(inventory_path)

    orders_path = root / "data/raw/pedidos.xlsx"
    write_xlsx(
        orders_path,
        [
            (
                "pedidos",
                [
                    "order_id",
                    "order_line_id",
                    "order_date",
                    "supplier_id",
                    "product_id",
                    "ordered_quantity",
                    "expected_unit_cost_cop",
                    "expected_delivery_date",
                    "status",
                    "source_message_id",
                    "notes",
                ],
                build.orders,
            )
        ],
        title="Faro - pedidos sintéticos",
        subject="Pedidos a proveedores sintéticos.",
    )
    generated.append(orders_path)
    return generated


def _write_invoices(root: Path, invoices: Sequence[Mapping[str, Any]]) -> list[Path]:
    directory = root / "data/raw/facturas"
    directory.mkdir(parents=True, exist_ok=True)
    generated: list[Path] = []
    for index, invoice in enumerate(invoices, start=1):
        path = directory / f"factura_{index:03d}.pdf"
        write_invoice_pdf(path, invoice)
        generated.append(path)
    return generated

def _sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _remove_generated_outputs(root: Path) -> None:
    for relative in GENERATED_RELATIVE_PATHS:
        path = root / relative
        if path.is_file():
            path.unlink()
    invoices = root / "data/raw/facturas"
    if invoices.exists():
        shutil.rmtree(invoices)


def _prepare_generation(root: Path, force: bool) -> dict[str, Any] | None:
    manifest_path = root / "data/expected/dataset_manifest.json"
    if force:
        _remove_generated_outputs(root)
        return None
    if not manifest_path.exists():
        return None

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    mismatches: list[str] = []
    for relative, expected_hash in manifest.get("files", {}).items():
        path = root / relative
        if not path.is_file():
            mismatches.append(f"missing {relative}")
        elif _sha256(path) != expected_hash:
            mismatches.append(f"modified {relative}")
    if mismatches:
        details = ", ".join(mismatches[:5])
        raise FileExistsError(
            "A prior generated dataset differs from its manifest "
            f"({details}). Use --force only after approving replacement."
        )
    return manifest


def generate_dataset(root: Path, seed: int = DEFAULT_SEED, force: bool = False) -> dict[str, Any]:
    """Generate the complete synthetic baseline below ``root``.

    Args:
        root: Repository-like root containing ``data/``.
        seed: Fixed deterministic seed.
        force: Explicitly replace a prior generated run.

    Returns:
        The generated manifest.
    """

    root = root.resolve()
    existing_manifest = _prepare_generation(root, force)
    if existing_manifest is not None:
        return existing_manifest
    build = build_dataset(seed)

    generated_paths = _write_workbooks(root, build)
    generated_paths.extend(_write_invoices(root, build.invoices))

    plugin_path = root / "data/samples/plugin-email-batch.example.json"
    _write_json(plugin_path, build.plugin_batch)
    generated_paths.append(plugin_path)

    expected_path = root / "data/expected/expected_anomalies.json"
    _write_json(expected_path, build.expected_anomalies)
    generated_paths.append(expected_path)

    counts = {
        "products": len(build.products),
        "customers": len(build.customers),
        "suppliers": len(build.suppliers),
        "sales_lines": len(build.sales),
        "inventory_snapshots": len(build.inventory),
        "order_lines": len(build.orders),
        "invoices": len(build.invoices),
        "plugin_messages": len(build.plugin_batch["messages"]),
        "expected_anomalies": len(build.expected_anomalies["anomalies"]),
    }
    file_hashes = {
        str(path.relative_to(root)): _sha256(path)
        for path in sorted(generated_paths, key=lambda item: str(item.relative_to(root)))
    }
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "dataset_version": DATASET_VERSION,
        "contract_version": CONTRACT_VERSION,
        "seed": seed,
        "generated_at": FIXED_GENERATED_AT,
        "status": "implemented",
        "counts": counts,
        "files": file_hashes,
    }
    manifest_path = root / "data/expected/dataset_manifest.json"
    _write_json(manifest_path, manifest)
    return manifest
