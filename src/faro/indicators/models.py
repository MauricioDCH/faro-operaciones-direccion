"""Immutable models for deterministic operational indicators."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


@dataclass(frozen=True, slots=True)
class IndicatorResult:
    indicator_result_id: str
    run_id: str
    preset_id: str
    indicator_id: str
    indicator_name: str
    period_start: str | None
    period_end: str | None
    dimension: str | None
    dimension_value: str | None
    numeric_value: Decimal | None
    unit: str
    formula_version: str
    source_record_ids: tuple[str, ...] = ()
    source_location_ids: tuple[str, ...] = ()
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "indicator_result_id": self.indicator_result_id,
            "run_id": self.run_id,
            "preset_id": self.preset_id,
            "indicator_id": self.indicator_id,
            "indicator_name": self.indicator_name,
            "period_start": self.period_start,
            "period_end": self.period_end,
            "dimension": self.dimension,
            "dimension_value": self.dimension_value,
            "numeric_value": None if self.numeric_value is None else str(self.numeric_value),
            "unit": self.unit,
            "formula_version": self.formula_version,
            "source_record_ids": list(self.source_record_ids),
            "source_location_ids": list(self.source_location_ids),
            "details": self.details,
        }


@dataclass(frozen=True, slots=True)
class IndicatorRun:
    run_id: str
    preset_id: str
    preset_label: str
    config_hash: str
    database_logical_hash: str
    as_of_date: str
    calculated_at: str
    results: tuple[IndicatorResult, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": "completed",
            "run_id": self.run_id,
            "preset_id": self.preset_id,
            "preset_label": self.preset_label,
            "config_hash": self.config_hash,
            "database_logical_hash": self.database_logical_hash,
            "as_of_date": self.as_of_date,
            "calculated_at": self.calculated_at,
            "result_count": len(self.results),
            "results": [item.to_dict() for item in self.results],
        }
