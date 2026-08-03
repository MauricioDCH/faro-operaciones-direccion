"""Evaluate approved alert presets over indicator results and quality findings."""

from __future__ import annotations

from contextlib import closing

from datetime import date
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterable

from faro.alerts.catalog import AlertConfigError, compare
from faro.alerts.config import AlertConfiguration, AlertRule
from faro.alerts.models import Alert, AlertEvaluation, AlertRun
from faro.alerts.storage import persist_alert_run
from faro.indicators import IndicatorConfiguration, OperationalIndicatorService


def _stable_id(prefix: str, *parts: object) -> str:
    payload = "|".join("" if item is None else str(item) for item in parts)
    return f"{prefix}-{sha256(payload.encode()).hexdigest()[:16].upper()}"


def _unique(values: Iterable[str | None]) -> tuple[str, ...]:
    return tuple(sorted({item for item in values if item}))


def _json_list(value: str | None) -> list[str]:
    if not value:
        return []
    parsed = json.loads(value)
    return [str(item) for item in parsed] if isinstance(parsed, list) else []


class ConfigurableAlertService:
    def evaluate(
        self,
        *,
        database_path: Path,
        alert_configuration: AlertConfiguration,
        indicator_configuration: IndicatorConfiguration,
        preset_id: str | None = None,
        as_of_date: date | None = None,
        persist: bool = True,
    ) -> AlertRun:
        preset = alert_configuration.select(preset_id)
        indicator_configuration.select(preset.indicator_preset)
        indicator_run = OperationalIndicatorService().calculate(
            database_path=database_path,
            configuration=indicator_configuration,
            preset_id=preset.indicator_preset,
            as_of_date=as_of_date,
            persist=True,
        )
        with closing(sqlite3.connect(database_path)) as connection:
            connection.row_factory = sqlite3.Row
            metadata = dict(connection.execute("SELECT key, value FROM metadata"))
            logical_hash = metadata.get("logical_content_hash", "unknown")
            run_id = _stable_id(
                "ALTRUN", logical_hash, alert_configuration.config_hash,
                preset.preset_id, indicator_run.run_id,
            )
            evaluations = tuple(
                self._evaluate_rule(connection, run_id, preset.preset_id, rule, indicator_run.run_id)
                for rule in preset.rules
            )
        alerts = tuple(
            self._to_alert(item, rule, indicator_run.calculated_at)
            for item, rule in zip(evaluations, preset.rules, strict=True)
            if item.status == "triggered" and item.observed_value is not None
        )
        run = AlertRun(
            run_id=run_id,
            preset_id=preset.preset_id,
            preset_label=preset.label,
            alert_config_hash=alert_configuration.config_hash,
            indicator_run_id=indicator_run.run_id,
            indicator_preset_id=preset.indicator_preset,
            database_logical_hash=logical_hash,
            as_of_date=indicator_run.as_of_date,
            evaluated_at=indicator_run.calculated_at,
            evaluations=tuple(sorted(evaluations, key=lambda item: item.rule_id)),
            alerts=tuple(sorted(alerts, key=lambda item: (item.severity, item.rule_id))),
        )
        if persist:
            persist_alert_run(database_path, run)
        return run

    def _evaluate_rule(
        self,
        connection: sqlite3.Connection,
        run_id: str,
        preset_id: str,
        rule: AlertRule,
        indicator_run_id: str,
    ) -> AlertEvaluation:
        if rule.source["type"] == "indicator":
            evidence = self._indicator_evidence(connection, indicator_run_id, rule)
        else:
            evidence = self._finding_evidence(connection, rule)
        values: list[Decimal] = evidence["values"]
        source_units = evidence["units"]
        if rule.source["aggregation"] != "count" and source_units and source_units != {rule.unit}:
            raise AlertConfigError(
                f"{rule.rule_id} expects unit {rule.unit} but source provides {sorted(source_units)}"
            )
        observed, reason = self._aggregate(values, rule.source["aggregation"])
        if observed is None:
            status = "not_evaluated"
        else:
            status = "triggered" if compare(observed, rule.operator, rule.threshold) else "clear"
        evaluation_id = _stable_id("ALTEVAL", run_id, rule.rule_id)
        return AlertEvaluation(
            evaluation_id=evaluation_id,
            run_id=run_id,
            preset_id=preset_id,
            rule_id=rule.rule_id,
            rule_name=rule.name,
            source_type=rule.source["type"],
            source_id=rule.source["id"],
            aggregation=rule.source["aggregation"],
            status=status,
            observed_value=observed,
            operator=rule.operator,
            threshold_value=rule.threshold,
            unit=rule.unit,
            severity=rule.severity,
            period_start=evidence.get("period_start"),
            period_end=evidence.get("period_end"),
            dimension=rule.source.get("dimension"),
            dimension_value=rule.source.get("dimension_value"),
            indicator_result_ids=_unique(evidence["indicator_result_ids"]),
            finding_ids=_unique(evidence["finding_ids"]),
            source_record_ids=_unique(evidence["source_record_ids"]),
            source_location_ids=_unique(evidence["source_location_ids"]),
            reason=reason,
            details={
                "source_match_count": evidence["match_count"],
                "source_units": sorted(evidence["units"]),
                "condition": f"{rule.operator} {rule.threshold}",
            },
        )

    @staticmethod
    def _indicator_evidence(
        connection: sqlite3.Connection, indicator_run_id: str, rule: AlertRule
    ) -> dict[str, Any]:
        clauses = ["run_id = ?", "indicator_id = ?"]
        params: list[Any] = [indicator_run_id, rule.source["id"]]
        if "dimension" in rule.source:
            clauses.extend(["dimension = ?", "dimension_value = ?"])
            params.extend([rule.source["dimension"], rule.source["dimension_value"]])
        rows = list(
            connection.execute(
                f"""SELECT * FROM indicator_result
                    WHERE {' AND '.join(clauses)}
                    ORDER BY indicator_result_id""",
                params,
            )
        )
        values = [Decimal(row["numeric_value"]) for row in rows if row["numeric_value"] is not None]
        return {
            "values": values,
            "match_count": len(rows),
            "indicator_result_ids": [row["indicator_result_id"] for row in rows],
            "finding_ids": [],
            "source_record_ids": [item for row in rows for item in _json_list(row["source_record_ids_json"])],
            "source_location_ids": [item for row in rows for item in _json_list(row["source_location_ids_json"])],
            "units": {row["unit"] for row in rows},
            "period_start": min((row["period_start"] for row in rows if row["period_start"]), default=None),
            "period_end": max((row["period_end"] for row in rows if row["period_end"]), default=None),
        }

    @staticmethod
    def _finding_evidence(connection: sqlite3.Connection, rule: AlertRule) -> dict[str, Any]:
        field = rule.source["match_field"]
        rows = list(
            connection.execute(
                f"""SELECT finding_id, record_id, source_location_id
                    FROM quality_finding WHERE {field} = ? ORDER BY finding_id""",
                (rule.source["id"],),
            )
        )
        return {
            "values": [Decimal("1") for _ in rows],
            "match_count": len(rows),
            "indicator_result_ids": [],
            "finding_ids": [row["finding_id"] for row in rows],
            "source_record_ids": [row["record_id"] for row in rows],
            "source_location_ids": [row["source_location_id"] for row in rows],
            "units": {"finding"},
            "period_start": None,
            "period_end": None,
        }

    @staticmethod
    def _aggregate(values: list[Decimal], aggregation: str) -> tuple[Decimal | None, str | None]:
        if aggregation == "count":
            return Decimal(len(values)), None
        if not values:
            return None, "No numeric source values matched the rule"
        if aggregation == "single":
            if len(values) != 1:
                return None, f"single aggregation expected one value and found {len(values)}"
            return values[0], None
        if aggregation == "sum":
            return sum(values, Decimal("0")), None
        if aggregation == "minimum":
            return min(values), None
        if aggregation == "maximum":
            return max(values), None
        if aggregation == "average":
            return sum(values, Decimal("0")) / Decimal(len(values)), None
        raise AlertConfigError(f"Unsupported aggregation: {aggregation}")

    @staticmethod
    def _to_alert(evaluation: AlertEvaluation, rule: AlertRule, generated_at: str) -> Alert:
        observed = evaluation.observed_value
        if observed is None:
            raise AlertConfigError("Cannot create an alert without an observed value")
        alert_id = _stable_id("ALT", evaluation.evaluation_id)
        description = (
            f"{rule.description} Valor observado: {observed} {rule.unit}; "
            f"condición: {rule.operator} {rule.threshold} {rule.unit}."
        ).strip()
        return Alert(
            alert_id=alert_id,
            evaluation_id=evaluation.evaluation_id,
            run_id=evaluation.run_id,
            preset_id=evaluation.preset_id,
            rule_id=evaluation.rule_id,
            alert_type=evaluation.source_id,
            severity=evaluation.severity,
            title=rule.name,
            description=description,
            observed_value=observed,
            operator=evaluation.operator,
            threshold_value=evaluation.threshold_value,
            unit=evaluation.unit,
            indicator_result_ids=evaluation.indicator_result_ids,
            finding_ids=evaluation.finding_ids,
            related_record_ids=evaluation.source_record_ids,
            source_location_ids=evaluation.source_location_ids,
            generated_at=generated_at,
            review_status="pending",
            delivery_status="not_configured",
            cooldown_minutes=rule.cooldown_minutes,
        )
