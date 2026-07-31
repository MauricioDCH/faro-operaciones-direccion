"""Deterministic data-quality public interface."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "validate_tabular_records": (
        "faro.quality.tabular",
        "validate_tabular_records",
    ),
    "validate_document_totals": (
        "faro.quality.documents",
        "validate_document_totals",
    ),
    "validate_line_totals": (
        "faro.quality.documents",
        "validate_line_totals",
    ),
    "validate_quotation_dates": (
        "faro.quality.documents",
        "validate_quotation_dates",
    ),
    "validate_required": (
        "faro.quality.documents",
        "validate_required",
    ),
    "validate_subtotal": (
        "faro.quality.documents",
        "validate_subtotal",
    ),
}

__all__ = list(_EXPORTS)


def __getattr__(name: str) -> Any:
    try:
        module_name, attribute_name = _EXPORTS[name]
    except KeyError as error:
        raise AttributeError(name) from error

    value = getattr(import_module(module_name), attribute_name)
    globals()[name] = value
    return value
