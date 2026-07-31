"""Excel ingestion public interface."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
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
