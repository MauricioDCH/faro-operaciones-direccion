"""Approved indicator catalog and parameter validation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class IndicatorConfigError(ValueError):
    """Raised when an indicator preset is not executable."""


@dataclass(frozen=True, slots=True)
class IndicatorDefinition:
    indicator_id: str
    name: str
    formula_version: str
    allowed_parameters: frozenset[str]


CATALOG: dict[str, IndicatorDefinition] = {
    "sales_total": IndicatorDefinition("sales_total", "Ventas totales", "1.0.0", frozenset({"period"})),
    "sales_change": IndicatorDefinition("sales_change", "Variación de ventas", "1.0.0", frozenset({"period"})),
    "top_products": IndicatorDefinition("top_products", "Productos más vendidos", "1.0.0", frozenset({"period", "metric", "limit"})),
    "low_inventory": IndicatorDefinition("low_inventory", "Productos con inventario bajo", "1.0.0", frozenset({"snapshot", "include_equal"})),
    "order_invoice_mismatch": IndicatorDefinition("order_invoice_mismatch", "Diferencias pedido-factura", "1.0.0", frozenset()),
    "data_quality_summary": IndicatorDefinition("data_quality_summary", "Resumen de calidad de datos", "1.0.0", frozenset({"severities"})),
    "source_coverage": IndicatorDefinition("source_coverage", "Cobertura de fuentes", "1.0.0", frozenset()),
    "data_freshness": IndicatorDefinition("data_freshness", "Frescura de datos", "1.0.0", frozenset({"entities"})),
}


def validate_parameters(indicator_id: str, parameters: dict[str, Any]) -> dict[str, Any]:
    try:
        definition = CATALOG[indicator_id]
    except KeyError as exc:
        raise IndicatorConfigError(f"Unknown indicator_id: {indicator_id}") from exc
    unknown = set(parameters) - definition.allowed_parameters
    if unknown:
        raise IndicatorConfigError(f"Unsupported parameters for {indicator_id}: {sorted(unknown)}")
    normalized = dict(parameters)
    if indicator_id in {"sales_total", "sales_change", "top_products"}:
        period = normalized.get("period", "latest_available_month")
        if period != "latest_available_month":
            raise IndicatorConfigError(f"{indicator_id}.period must be latest_available_month")
        normalized["period"] = period
    if indicator_id == "top_products":
        metric = normalized.get("metric", "revenue")
        if metric not in {"revenue", "quantity"}:
            raise IndicatorConfigError("top_products.metric must be revenue or quantity")
        limit = normalized.get("limit", 5)
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 50:
            raise IndicatorConfigError("top_products.limit must be an integer between 1 and 50")
        normalized.update(metric=metric, limit=limit)
    if indicator_id == "low_inventory":
        snapshot = normalized.get("snapshot", "latest")
        include_equal = normalized.get("include_equal", False)
        if snapshot != "latest":
            raise IndicatorConfigError("low_inventory.snapshot must be latest")
        if not isinstance(include_equal, bool):
            raise IndicatorConfigError("low_inventory.include_equal must be boolean")
        normalized.update(snapshot=snapshot, include_equal=include_equal)
    if indicator_id == "data_quality_summary":
        severities = normalized.get("severities", ["error", "warning"])
        if not isinstance(severities, list) or not severities or any(item not in {"error", "warning", "info"} for item in severities):
            raise IndicatorConfigError("data_quality_summary.severities contains an unsupported value")
        normalized["severities"] = list(dict.fromkeys(severities))
    if indicator_id == "data_freshness":
        entities = normalized.get("entities", ["sales", "inventory", "orders", "invoices"])
        allowed = {"sales", "inventory", "orders", "invoices", "quotations"}
        if not isinstance(entities, list) or not entities or any(item not in allowed for item in entities):
            raise IndicatorConfigError("data_freshness.entities contains an unsupported value")
        normalized["entities"] = list(dict.fromkeys(entities))
    return normalized
