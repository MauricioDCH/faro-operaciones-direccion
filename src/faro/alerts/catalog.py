"""Closed catalog and validation primitives for configurable alert rules."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
import re
from typing import Any

from faro.indicators.catalog import CATALOG as INDICATOR_CATALOG


class AlertConfigError(ValueError):
    """Raised when an alert preset cannot be evaluated safely."""


OPERATORS = frozenset(
    {
        "greater_than",
        "greater_or_equal",
        "less_than",
        "less_or_equal",
        "equal",
        "not_equal",
    }
)
AGGREGATIONS = frozenset({"single", "count", "sum", "minimum", "maximum", "average"})
SEVERITIES = frozenset({"info", "warning", "error", "critical"})
FINDING_MATCH_FIELDS = frozenset({"code", "severity"})
_IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{1,127}$")


def decimal_value(value: Any, *, field: str) -> Decimal:
    if isinstance(value, bool):
        raise AlertConfigError(f"{field} must be numeric")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise AlertConfigError(f"{field} must be a finite decimal") from exc
    if not result.is_finite():
        raise AlertConfigError(f"{field} must be a finite decimal")
    return result


def validate_identifier(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise AlertConfigError(f"{field} has an invalid identifier")
    return value


def validate_source(source: Any) -> dict[str, Any]:
    if not isinstance(source, dict):
        raise AlertConfigError("alert source must be an object")
    source_type = source.get("type")
    if source_type not in {"indicator", "quality_finding"}:
        raise AlertConfigError("source.type must be indicator or quality_finding")
    source_id = validate_identifier(source.get("id"), field="source.id")
    aggregation = source.get("aggregation", "single")
    if aggregation not in AGGREGATIONS:
        raise AlertConfigError(f"Unsupported aggregation: {aggregation}")
    normalized: dict[str, Any] = {
        "type": source_type,
        "id": source_id,
        "aggregation": aggregation,
    }
    if source_type == "indicator":
        if source_id not in INDICATOR_CATALOG:
            raise AlertConfigError(f"Unknown indicator source: {source_id}")
        dimension = source.get("dimension")
        dimension_value = source.get("dimension_value")
        if (dimension is None) != (dimension_value is None):
            raise AlertConfigError("source.dimension and source.dimension_value must be provided together")
        if dimension is not None:
            normalized["dimension"] = validate_identifier(dimension, field="source.dimension")
            if not isinstance(dimension_value, str) or not dimension_value:
                raise AlertConfigError("source.dimension_value must be a non-empty string")
            normalized["dimension_value"] = dimension_value
        if "match_field" in source:
            raise AlertConfigError("indicator sources do not support match_field")
    else:
        if aggregation != "count":
            raise AlertConfigError("quality_finding sources only support count aggregation")
        match_field = source.get("match_field", "code")
        if match_field not in FINDING_MATCH_FIELDS:
            raise AlertConfigError("quality_finding.match_field must be code or severity")
        if match_field == "severity" and source_id not in {"info", "warning", "error", "critical"}:
            raise AlertConfigError("quality_finding severity source is invalid")
        normalized["match_field"] = match_field
    unknown = set(source) - {"type", "id", "aggregation", "dimension", "dimension_value", "match_field"}
    if unknown:
        raise AlertConfigError(f"Unsupported source fields: {sorted(unknown)}")
    return normalized


def validate_condition(condition: Any) -> dict[str, Any]:
    if not isinstance(condition, dict):
        raise AlertConfigError("alert condition must be an object")
    operator = condition.get("operator")
    if operator not in OPERATORS:
        raise AlertConfigError(f"Unsupported alert operator: {operator}")
    threshold = decimal_value(condition.get("threshold"), field="condition.threshold")
    unit = condition.get("unit")
    if not isinstance(unit, str) or not unit or len(unit) > 32:
        raise AlertConfigError("condition.unit must be a short non-empty string")
    unknown = set(condition) - {"operator", "threshold", "unit"}
    if unknown:
        raise AlertConfigError(f"Unsupported condition fields: {sorted(unknown)}")
    return {"operator": operator, "threshold": threshold, "unit": unit}


def compare(observed: Decimal, operator: str, threshold: Decimal) -> bool:
    if operator == "greater_than":
        return observed > threshold
    if operator == "greater_or_equal":
        return observed >= threshold
    if operator == "less_than":
        return observed < threshold
    if operator == "less_or_equal":
        return observed <= threshold
    if operator == "equal":
        return observed == threshold
    if operator == "not_equal":
        return observed != threshold
    raise AlertConfigError(f"Unsupported alert operator: {operator}")
