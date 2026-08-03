"""Immutable models for deterministic alert evaluations and triggered alerts."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


@dataclass(frozen=True, slots=True)
class AlertEvaluation:
    evaluation_id: str
    run_id: str
    preset_id: str
    rule_id: str
    rule_name: str
    source_type: str
    source_id: str
    aggregation: str
    status: str
    observed_value: Decimal | None
    operator: str
    threshold_value: Decimal
    unit: str
    severity: str
    period_start: str | None = None
    period_end: str | None = None
    dimension: str | None = None
    dimension_value: str | None = None
    indicator_result_ids: tuple[str, ...] = ()
    finding_ids: tuple[str, ...] = ()
    source_record_ids: tuple[str, ...] = ()
    source_location_ids: tuple[str, ...] = ()
    reason: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "evaluation_id": self.evaluation_id,
            "run_id": self.run_id,
            "preset_id": self.preset_id,
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "source_type": self.source_type,
            "source_id": self.source_id,
            "aggregation": self.aggregation,
            "status": self.status,
            "observed_value": None if self.observed_value is None else str(self.observed_value),
            "operator": self.operator,
            "threshold_value": str(self.threshold_value),
            "unit": self.unit,
            "severity": self.severity,
            "period_start": self.period_start,
            "period_end": self.period_end,
            "dimension": self.dimension,
            "dimension_value": self.dimension_value,
            "indicator_result_ids": list(self.indicator_result_ids),
            "finding_ids": list(self.finding_ids),
            "source_record_ids": list(self.source_record_ids),
            "source_location_ids": list(self.source_location_ids),
            "reason": self.reason,
            "details": self.details,
        }


@dataclass(frozen=True, slots=True)
class Alert:
    alert_id: str
    evaluation_id: str
    run_id: str
    preset_id: str
    rule_id: str
    alert_type: str
    severity: str
    title: str
    description: str
    observed_value: Decimal
    operator: str
    threshold_value: Decimal
    unit: str
    indicator_result_ids: tuple[str, ...]
    finding_ids: tuple[str, ...]
    related_record_ids: tuple[str, ...]
    source_location_ids: tuple[str, ...]
    generated_at: str
    review_status: str
    delivery_status: str
    cooldown_minutes: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "evaluation_id": self.evaluation_id,
            "run_id": self.run_id,
            "preset_id": self.preset_id,
            "rule_id": self.rule_id,
            "alert_type": self.alert_type,
            "severity": self.severity,
            "title": self.title,
            "description": self.description,
            "observed_value": str(self.observed_value),
            "operator": self.operator,
            "threshold_value": str(self.threshold_value),
            "unit": self.unit,
            "indicator_result_ids": list(self.indicator_result_ids),
            "finding_ids": list(self.finding_ids),
            "related_record_ids": list(self.related_record_ids),
            "source_location_ids": list(self.source_location_ids),
            "generated_at": self.generated_at,
            "review_status": self.review_status,
            "delivery_status": self.delivery_status,
            "cooldown_minutes": self.cooldown_minutes,
        }


@dataclass(frozen=True, slots=True)
class AlertRun:
    run_id: str
    preset_id: str
    preset_label: str
    alert_config_hash: str
    indicator_run_id: str
    indicator_preset_id: str
    database_logical_hash: str
    as_of_date: str
    evaluated_at: str
    evaluations: tuple[AlertEvaluation, ...]
    alerts: tuple[Alert, ...]

    def to_dict(self) -> dict[str, Any]:
        counts = {
            "triggered": sum(item.status == "triggered" for item in self.evaluations),
            "clear": sum(item.status == "clear" for item in self.evaluations),
            "not_evaluated": sum(item.status == "not_evaluated" for item in self.evaluations),
        }
        return {
            "status": "completed_with_alerts" if self.alerts else "completed",
            "run_id": self.run_id,
            "preset_id": self.preset_id,
            "preset_label": self.preset_label,
            "alert_config_hash": self.alert_config_hash,
            "indicator_run_id": self.indicator_run_id,
            "indicator_preset_id": self.indicator_preset_id,
            "database_logical_hash": self.database_logical_hash,
            "as_of_date": self.as_of_date,
            "evaluated_at": self.evaluated_at,
            "evaluation_count": len(self.evaluations),
            "alert_count": len(self.alerts),
            "counts": counts,
            "evaluations": [item.to_dict() for item in self.evaluations],
            "alerts": [item.to_dict() for item in self.alerts],
        }
