"""Canonical Excel field contracts for DC-001 through DC-006."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class FieldSpec:
    name: str
    value_type: str
    required: bool = True
    minimum: Decimal | None = None
    allowed_values: frozenset[str] | None = None


@dataclass(frozen=True, slots=True)
class SheetSpec:
    contract_id: str
    entity_type: str
    file_name: str
    sheet_name: str
    fields: tuple[FieldSpec, ...]
    record_id_fields: tuple[str, ...]

    @property
    def field_names(self) -> tuple[str, ...]:
        return tuple(field.name for field in self.fields)


STRING = "string"
DECIMAL = "decimal"
DATE = "date"
BOOLEAN = "boolean"


SHEET_SPECS: tuple[SheetSpec, ...] = (
    SheetSpec(
        contract_id="DC-001",
        entity_type="product",
        file_name="catalogos.xlsx",
        sheet_name="productos",
        record_id_fields=("product_id",),
        fields=(
            FieldSpec("product_id", STRING),
            FieldSpec("sku", STRING),
            FieldSpec("product_name", STRING),
            FieldSpec("category", STRING),
            FieldSpec("unit", STRING),
            FieldSpec("unit_cost_cop", DECIMAL, minimum=Decimal("0")),
            FieldSpec("sale_price_cop", DECIMAL, minimum=Decimal("0")),
            FieldSpec("active", BOOLEAN),
        ),
    ),
    SheetSpec(
        contract_id="DC-002",
        entity_type="customer",
        file_name="catalogos.xlsx",
        sheet_name="clientes",
        record_id_fields=("customer_id",),
        fields=(
            FieldSpec("customer_id", STRING),
            FieldSpec("customer_name", STRING),
            FieldSpec("customer_type", STRING),
            FieldSpec("tax_id", STRING, required=False),
            FieldSpec("city", STRING),
            FieldSpec("email", STRING, required=False),
            FieldSpec("phone", STRING, required=False),
            FieldSpec("active", BOOLEAN),
        ),
    ),
    SheetSpec(
        contract_id="DC-003",
        entity_type="supplier",
        file_name="catalogos.xlsx",
        sheet_name="proveedores",
        record_id_fields=("supplier_id",),
        fields=(
            FieldSpec("supplier_id", STRING),
            FieldSpec("supplier_name", STRING),
            FieldSpec("tax_id", STRING, required=False),
            FieldSpec("city", STRING),
            FieldSpec("email", STRING, required=False),
            FieldSpec("phone", STRING, required=False),
            FieldSpec("active", BOOLEAN),
        ),
    ),
    SheetSpec(
        contract_id="DC-004",
        entity_type="sale_line",
        file_name="ventas.xlsx",
        sheet_name="ventas",
        record_id_fields=("sale_line_id",),
        fields=(
            FieldSpec("sale_id", STRING),
            FieldSpec("sale_line_id", STRING),
            FieldSpec("sale_date", DATE),
            FieldSpec("customer_id", STRING),
            FieldSpec("product_id", STRING),
            FieldSpec("quantity", DECIMAL),
            FieldSpec("unit_price_cop", DECIMAL, minimum=Decimal("0")),
            FieldSpec("discount_cop", DECIMAL, minimum=Decimal("0")),
            FieldSpec("line_total_cop", DECIMAL),
            FieldSpec(
                "channel",
                STRING,
                allowed_values=frozenset(
                    {"store", "whatsapp", "email", "phone"}
                ),
            ),
        ),
    ),
    SheetSpec(
        contract_id="DC-005",
        entity_type="inventory_snapshot",
        file_name="inventario.xlsx",
        sheet_name="inventario",
        record_id_fields=("snapshot_date", "product_id"),
        fields=(
            FieldSpec("snapshot_date", DATE),
            FieldSpec("product_id", STRING),
            FieldSpec("stock_on_hand", DECIMAL, minimum=Decimal("0")),
            FieldSpec("committed_quantity", DECIMAL, minimum=Decimal("0")),
            FieldSpec("reorder_point", DECIMAL, minimum=Decimal("0")),
        ),
    ),
    SheetSpec(
        contract_id="DC-006",
        entity_type="purchase_order_line",
        file_name="pedidos.xlsx",
        sheet_name="pedidos",
        record_id_fields=("order_line_id",),
        fields=(
            FieldSpec("order_id", STRING),
            FieldSpec("order_line_id", STRING),
            FieldSpec("order_date", DATE),
            FieldSpec("supplier_id", STRING),
            FieldSpec("product_id", STRING),
            FieldSpec("ordered_quantity", DECIMAL),
            FieldSpec(
                "expected_unit_cost_cop", DECIMAL, minimum=Decimal("0")
            ),
            FieldSpec("expected_delivery_date", DATE, required=False),
            FieldSpec(
                "status",
                STRING,
                allowed_values=frozenset(
                    {"draft", "sent", "confirmed", "received", "cancelled"}
                ),
            ),
            FieldSpec("source_message_id", STRING, required=False),
            FieldSpec("notes", STRING, required=False),
        ),
    ),
)


SPECS_BY_FILE: dict[str, tuple[SheetSpec, ...]] = {}
for _spec in SHEET_SPECS:
    SPECS_BY_FILE.setdefault(_spec.file_name, tuple())
    SPECS_BY_FILE[_spec.file_name] += (_spec,)
