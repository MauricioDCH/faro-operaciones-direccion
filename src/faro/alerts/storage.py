"""SQLite persistence for deterministic alert runs, evaluations and alerts."""

from __future__ import annotations

from contextlib import closing

import json
from pathlib import Path
import sqlite3

from faro.alerts.models import AlertRun

ALERT_SCHEMA_VERSION = "1.0.0"

ALERT_DDL = """
CREATE TABLE IF NOT EXISTS alert_run (
    run_id TEXT PRIMARY KEY,
    preset_id TEXT NOT NULL,
    preset_label TEXT NOT NULL,
    alert_config_hash TEXT NOT NULL,
    indicator_run_id TEXT NOT NULL REFERENCES indicator_run(run_id),
    indicator_preset_id TEXT NOT NULL,
    database_logical_hash TEXT NOT NULL,
    as_of_date TEXT NOT NULL,
    evaluated_at TEXT NOT NULL,
    evaluation_count INTEGER NOT NULL,
    alert_count INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS alert_evaluation (
    evaluation_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES alert_run(run_id) ON DELETE CASCADE,
    preset_id TEXT NOT NULL,
    rule_id TEXT NOT NULL,
    rule_name TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_id TEXT NOT NULL,
    aggregation TEXT NOT NULL,
    status TEXT NOT NULL,
    observed_value TEXT,
    operator TEXT NOT NULL,
    threshold_value TEXT NOT NULL,
    unit TEXT NOT NULL,
    severity TEXT NOT NULL,
    period_start TEXT,
    period_end TEXT,
    dimension TEXT,
    dimension_value TEXT,
    indicator_result_ids_json TEXT NOT NULL,
    finding_ids_json TEXT NOT NULL,
    source_record_ids_json TEXT NOT NULL,
    source_location_ids_json TEXT NOT NULL,
    reason TEXT,
    details_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_alert_evaluation_run ON alert_evaluation(run_id, status, severity);
CREATE TABLE IF NOT EXISTS alert (
    alert_id TEXT PRIMARY KEY,
    evaluation_id TEXT NOT NULL REFERENCES alert_evaluation(evaluation_id) ON DELETE CASCADE,
    run_id TEXT NOT NULL REFERENCES alert_run(run_id) ON DELETE CASCADE,
    preset_id TEXT NOT NULL,
    rule_id TEXT NOT NULL,
    alert_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    observed_value TEXT NOT NULL,
    operator TEXT NOT NULL,
    threshold_value TEXT NOT NULL,
    unit TEXT NOT NULL,
    indicator_result_ids_json TEXT NOT NULL,
    finding_ids_json TEXT NOT NULL,
    related_record_ids_json TEXT NOT NULL,
    source_location_ids_json TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    review_status TEXT NOT NULL,
    delivery_status TEXT NOT NULL,
    cooldown_minutes INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_alert_run ON alert(run_id, severity, review_status);
"""


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def persist_alert_run(database_path: Path, run: AlertRun) -> None:
    with closing(sqlite3.connect(database_path)) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(ALERT_DDL)
        with connection:
            connection.execute(
                "INSERT OR REPLACE INTO metadata(key, value) VALUES (?, ?)",
                ("alert_schema_version", ALERT_SCHEMA_VERSION),
            )
            connection.execute("DELETE FROM alert WHERE run_id = ?", (run.run_id,))
            connection.execute("DELETE FROM alert_evaluation WHERE run_id = ?", (run.run_id,))
            connection.execute(
                """INSERT OR REPLACE INTO alert_run VALUES
                   (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    run.run_id, run.preset_id, run.preset_label, run.alert_config_hash,
                    run.indicator_run_id, run.indicator_preset_id, run.database_logical_hash,
                    run.as_of_date, run.evaluated_at, len(run.evaluations), len(run.alerts),
                ),
            )
            connection.executemany(
                """INSERT INTO alert_evaluation VALUES
                   (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    (
                        item.evaluation_id, item.run_id, item.preset_id, item.rule_id,
                        item.rule_name, item.source_type, item.source_id, item.aggregation,
                        item.status,
                        None if item.observed_value is None else str(item.observed_value),
                        item.operator, str(item.threshold_value), item.unit, item.severity,
                        item.period_start, item.period_end, item.dimension, item.dimension_value,
                        _json(item.indicator_result_ids), _json(item.finding_ids),
                        _json(item.source_record_ids), _json(item.source_location_ids),
                        item.reason, _json(item.details),
                    )
                    for item in run.evaluations
                ],
            )
            connection.executemany(
                """INSERT INTO alert VALUES
                   (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    (
                        item.alert_id, item.evaluation_id, item.run_id, item.preset_id,
                        item.rule_id, item.alert_type, item.severity, item.title,
                        item.description, str(item.observed_value), item.operator,
                        str(item.threshold_value), item.unit,
                        _json(item.indicator_result_ids), _json(item.finding_ids),
                        _json(item.related_record_ids), _json(item.source_location_ids),
                        item.generated_at, item.review_status, item.delivery_status,
                        item.cooldown_minutes,
                    )
                    for item in run.alerts
                ],
            )
