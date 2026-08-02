"""Excel ingestion public interface."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "CapabilityStatus": (
        "faro.ingestion.formats",
        "CapabilityStatus",
    ),
    "FormatCapability": (
        "faro.ingestion.formats",
        "FormatCapability",
    ),
    "InputFormat": (
        "faro.ingestion.formats",
        "InputFormat",
    ),
    "all_capabilities": (
        "faro.ingestion.formats",
        "all_capabilities",
    ),
    "capability_for": (
        "faro.ingestion.formats",
        "capability_for",
    ),
    "detect_input_format": (
        "faro.ingestion.formats",
        "detect_input_format",
    ),
    "require_implemented_format": (
        "faro.ingestion.formats",
        "require_implemented_format",
    ),
    "ExcelIngestionService": (
        "faro.ingestion.excel",
        "ExcelIngestionService",
    ),
    "ExcelIngestionBatch": (
        "faro.ingestion.models",
        "ExcelIngestionBatch",
    ),
    "IngestionFinding": (
        "faro.ingestion.models",
        "IngestionFinding",
    ),
    "TabularRecord": (
        "faro.ingestion.models",
        "TabularRecord",
    ),
    "XlsxFormatError": (
        "faro.ingestion.xlsx",
        "XlsxFormatError",
    ),
    "XlsxWorkbook": (
        "faro.ingestion.xlsx",
        "XlsxWorkbook",
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
