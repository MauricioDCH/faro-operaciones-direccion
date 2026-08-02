"""Deterministic validation for typed Excel records."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Iterable

from faro.ingestion.models import (
    IngestionFinding,
    TabularRecord,
    display_value,
    make_finding,
)


_display = display_value


def _field_location_id(record: TabularRecord, field: str) -> str:
    return record.location_for(field).source_location_id


def _validate_unique(
    records: Iterable[TabularRecord],
    field: str,
    rule_id: str,
    code: str,
) -> list[IngestionFinding]:
    findings: list[IngestionFinding] = []
    seen: dict[object, TabularRecord] = {}
    for record in records:
        value = record.values.get(field)
        if value is None:
            continue
        previous = seen.get(value)
        if previous is None:
            seen[value] = record
            continue
        findings.append(
            make_finding(
                rule_id=rule_id,
                code=code,
                category="data_quality",
                severity="error",
                message=f"Duplicate value for unique field: {field}.",
                source_location_id=_field_location_id(record, field),
                entity_type=record.entity_type,
                record_id=record.record_id,
                field=field,
                observed_value=value,
                expected_value=f"unique; first seen in {previous.record_id}",
            )
        )
    return findings


def _validate_logical_unique(
    records: Iterable[TabularRecord],
    fields: tuple[str, ...],
    rule_id: str,
    code: str,
) -> list[IngestionFinding]:
    findings: list[IngestionFinding] = []
    seen: dict[tuple[object, ...], TabularRecord] = {}
    for record in records:
        key = tuple(record.values.get(field) for field in fields)
        if any(value is None for value in key):
            continue
        previous = seen.get(key)
        if previous is None:
            seen[key] = record
            continue
        findings.append(
            make_finding(
                rule_id=rule_id,
                code=code,
                category="data_quality",
                severity="error",
                message=f"Duplicate logical record using fields: {', '.join(fields)}.",
                source_location_id=record.source_location_id,
                entity_type=record.entity_type,
                record_id=record.record_id,
                observed_value="|".join(_display(item) or "" for item in key),
                expected_value=f"unique; first seen in {previous.record_id}",
            )
        )
    return findings


def validate_tabular_records(
    records: list[TabularRecord], *, validate_references: bool = True
) -> list[IngestionFinding]:
    findings: list[IngestionFinding] = []
    by_entity = {
        entity: [item for item in records if item.entity_type == entity]
        for entity in {item.entity_type for item in records}
    }
    findings.extend(
        _validate_unique(
            by_entity.get("product", []),
            "product_id",
            "RULE-PRODUCT-ID-001",
            "duplicate_product_id",
        )
    )
    findings.extend(
        _validate_unique(
            by_entity.get("product", []),
            "sku",
            "RULE-PRODUCT-SKU-001",
            "duplicate_sku",
        )
    )
    findings.extend(
        _validate_unique(
            by_entity.get("customer", []),
            "customer_id",
            "RULE-CUSTOMER-ID-001",
            "duplicate_customer_id",
        )
    )
    findings.extend(
        _validate_unique(
            by_entity.get("supplier", []),
            "supplier_id",
            "RULE-SUPPLIER-ID-001",
            "duplicate_supplier_id",
        )
    )
    findings.extend(
        _validate_unique(
            by_entity.get("sale_line", []),
            "sale_line_id",
            "RULE-SALE-LINE-ID-001",
            "duplicate_sale_line_id",
        )
    )
    findings.extend(
        _validate_unique(
            by_entity.get("purchase_order_line", []),
            "order_line_id",
            "RULE-ORDER-LINE-ID-001",
            "duplicate_order_line_id",
        )
    )
    findings.extend(
        _validate_logical_unique(
            by_entity.get("inventory_snapshot", []),
            ("snapshot_date", "product_id"),
            "RULE-INVENTORY-KEY-001",
            "duplicate_inventory_snapshot",
        )
    )

    product_ids = {
        item.values["product_id"]
        for item in by_entity.get("product", [])
        if item.values.get("product_id") is not None
    }
    customer_ids = {
        item.values["customer_id"]
        for item in by_entity.get("customer", [])
        if item.values.get("customer_id") is not None
    }
    supplier_ids = {
        item.values["supplier_id"]
        for item in by_entity.get("supplier", [])
        if item.values.get("supplier_id") is not None
    }

    for product in by_entity.get("product", []):
        cost = product.values.get("unit_cost_cop")
        price = product.values.get("sale_price_cop")
        if isinstance(cost, Decimal) and isinstance(price, Decimal) and price < cost:
            findings.append(
                make_finding(
                    rule_id="RULE-PRODUCT-MARGIN-001",
                    code="sale_price_below_cost",
                    category="data_quality",
                    severity="warning",
                    message="Sale price is below unit cost.",
                    source_location_id=_field_location_id(product, "sale_price_cop"),
                    entity_type=product.entity_type,
                    record_id=product.record_id,
                    field="sale_price_cop",
                    observed_value=price,
                    expected_value=f">={cost}",
                )
            )

    sales = by_entity.get("sale_line", [])
    duplicate_sale_fields = (
        "sale_id",
        "sale_date",
        "customer_id",
        "product_id",
        "quantity",
        "unit_price_cop",
        "discount_cop",
        "line_total_cop",
        "channel",
    )
    findings.extend(
        _validate_logical_unique(
            sales,
            duplicate_sale_fields,
            "RULE-DUP-SALE-001",
            "duplicate_sale_line",
        )
    )
    for sale in sales:
        customer_id = sale.values.get("customer_id")
        product_id = sale.values.get("product_id")
        quantity = sale.values.get("quantity")
        unit_price = sale.values.get("unit_price_cop")
        discount = sale.values.get("discount_cop")
        line_total = sale.values.get("line_total_cop")
        if validate_references and customer_id is not None and customer_id not in customer_ids:
            findings.append(
                make_finding(
                    rule_id="RULE-FK-CUSTOMER-001",
                    code="unknown_customer",
                    category="data_quality",
                    severity="error",
                    message="Sale references an unknown customer.",
                    source_location_id=_field_location_id(sale, "customer_id"),
                    entity_type=sale.entity_type,
                    record_id=sale.record_id,
                    field="customer_id",
                    observed_value=customer_id,
                    expected_value="existing customer_id",
                )
            )
        if validate_references and product_id is not None and product_id not in product_ids:
            findings.append(
                make_finding(
                    rule_id="RULE-FK-PRODUCT-001",
                    code="unknown_product",
                    category="data_quality",
                    severity="error",
                    message="Sale references an unknown product.",
                    source_location_id=_field_location_id(sale, "product_id"),
                    entity_type=sale.entity_type,
                    record_id=sale.record_id,
                    field="product_id",
                    observed_value=product_id,
                    expected_value="existing product_id",
                )
            )
        if isinstance(quantity, Decimal) and quantity <= 0:
            findings.append(
                make_finding(
                    rule_id="RULE-QUANTITY-001",
                    code="negative_quantity" if quantity < 0 else "zero_quantity",
                    category="data_quality",
                    severity="error",
                    message="Sale quantity must be greater than zero.",
                    source_location_id=_field_location_id(sale, "quantity"),
                    entity_type=sale.entity_type,
                    record_id=sale.record_id,
                    field="quantity",
                    observed_value=quantity,
                    expected_value=">0",
                )
            )
        if all(
            isinstance(value, Decimal)
            for value in (quantity, unit_price, discount, line_total)
        ):
            expected = quantity * unit_price - discount
            if abs(expected - line_total) > Decimal("0.01"):
                findings.append(
                    make_finding(
                        rule_id="RULE-SALE-TOTAL-001",
                        code="sale_line_total_mismatch",
                        category="data_quality",
                        severity="error",
                        message="Sale line total does not match the contract formula.",
                        source_location_id=_field_location_id(sale, "line_total_cop"),
                        entity_type=sale.entity_type,
                        record_id=sale.record_id,
                        field="line_total_cop",
                        observed_value=line_total,
                        expected_value=expected,
                    )
                )

    for inventory in by_entity.get("inventory_snapshot", []):
        product_id = inventory.values.get("product_id")
        if validate_references and product_id is not None and product_id not in product_ids:
            findings.append(
                make_finding(
                    rule_id="RULE-FK-PRODUCT-001",
                    code="unknown_product",
                    category="data_quality",
                    severity="error",
                    message="Inventory references an unknown product.",
                    source_location_id=_field_location_id(inventory, "product_id"),
                    entity_type=inventory.entity_type,
                    record_id=inventory.record_id,
                    field="product_id",
                    observed_value=product_id,
                    expected_value="existing product_id",
                )
            )
        stock = inventory.values.get("stock_on_hand")
        committed = inventory.values.get("committed_quantity")
        reorder = inventory.values.get("reorder_point")
        if all(isinstance(value, Decimal) for value in (stock, committed, reorder)):
            available = stock - committed
            if available < reorder:
                findings.append(
                    make_finding(
                        rule_id="RULE-LOW-STOCK-001",
                        code="low_inventory",
                        category="operational",
                        severity="warning",
                        message="Available inventory is below the reorder point.",
                        source_location_id=inventory.source_location_id,
                        entity_type=inventory.entity_type,
                        record_id=inventory.record_id,
                        observed_value=available,
                        expected_value=f">={reorder}",
                    )
                )

    for order in by_entity.get("purchase_order_line", []):
        supplier_id = order.values.get("supplier_id")
        product_id = order.values.get("product_id")
        quantity = order.values.get("ordered_quantity")
        order_date = order.values.get("order_date")
        delivery_date = order.values.get("expected_delivery_date")
        if validate_references and supplier_id is not None and supplier_id not in supplier_ids:
            findings.append(
                make_finding(
                    rule_id="RULE-FK-SUPPLIER-001",
                    code="unknown_supplier",
                    category="data_quality",
                    severity="error",
                    message="Order references an unknown supplier.",
                    source_location_id=_field_location_id(order, "supplier_id"),
                    entity_type=order.entity_type,
                    record_id=order.record_id,
                    field="supplier_id",
                    observed_value=supplier_id,
                    expected_value="existing supplier_id",
                )
            )
        if validate_references and product_id is not None and product_id not in product_ids:
            findings.append(
                make_finding(
                    rule_id="RULE-FK-PRODUCT-001",
                    code="unknown_product",
                    category="data_quality",
                    severity="error",
                    message="Order references an unknown product.",
                    source_location_id=_field_location_id(order, "product_id"),
                    entity_type=order.entity_type,
                    record_id=order.record_id,
                    field="product_id",
                    observed_value=product_id,
                    expected_value="existing product_id",
                )
            )
        if isinstance(quantity, Decimal) and quantity <= 0:
            findings.append(
                make_finding(
                    rule_id="RULE-ORDER-QUANTITY-001",
                    code="invalid_order_quantity",
                    category="data_quality",
                    severity="error",
                    message="Ordered quantity must be greater than zero.",
                    source_location_id=_field_location_id(order, "ordered_quantity"),
                    entity_type=order.entity_type,
                    record_id=order.record_id,
                    field="ordered_quantity",
                    observed_value=quantity,
                    expected_value=">0",
                )
            )
        if (
            isinstance(order_date, date)
            and isinstance(delivery_date, date)
            and delivery_date < order_date
        ):
            findings.append(
                make_finding(
                    rule_id="RULE-ORDER-DATE-001",
                    code="invalid_expected_delivery_date",
                    category="data_quality",
                    severity="error",
                    message="Expected delivery date cannot precede order date.",
                    source_location_id=_field_location_id(
                        order, "expected_delivery_date"
                    ),
                    entity_type=order.entity_type,
                    record_id=order.record_id,
                    field="expected_delivery_date",
                    observed_value=delivery_date,
                    expected_value=f">={order_date.isoformat()}",
                )
            )
    return findings

