"""SQLite persistence for derived indicator runs and results."""

from __future__ import annotations

import json
from pathlib import Path
import sqlite3

from faro.indicators.models import IndicatorRun

INDICATOR_SCHEMA_VERSION = "1.0.0"

INDICATOR_DDL = """
CREATE TABLE IF NOT EXISTS indicator_run (
    run_id TEXT PRIMARY KEY,
    preset_id TEXT NOT NULL,
    preset_label TEXT NOT NULL,
    config_hash TEXT NOT NULL,
    database_logical_hash TEXT NOT NULL,
    as_of_date TEXT NOT NULL,
    calculated_at TEXT NOT NULL,
    result_count INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS indicator_result (
    indicator_result_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES indicator_run(run_id) ON DELETE CASCADE,
    preset_id TEXT NOT NULL,
    indicator_id TEXT NOT NULL,
    indicator_name TEXT NOT NULL,
    period_start TEXT,
    period_end TEXT,
    dimension TEXT,
    dimension_value TEXT,
    numeric_value TEXT,
    unit TEXT NOT NULL,
    formula_version TEXT NOT NULL,
    source_record_ids_json TEXT NOT NULL,
    source_location_ids_json TEXT NOT NULL,
    details_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_indicator_result_run ON indicator_result(run_id, indicator_id);
"""


def persist_indicator_run(database_path: Path, run: IndicatorRun) -> None:
    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(INDICATOR_DDL)
        with connection:
            connection.execute(
                "INSERT OR REPLACE INTO metadata(key, value) VALUES (?, ?)",
                ("indicator_schema_version", INDICATOR_SCHEMA_VERSION),
            )
            connection.execute("DELETE FROM indicator_result WHERE run_id = ?", (run.run_id,))
            connection.execute(
                """INSERT OR REPLACE INTO indicator_run
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (run.run_id, run.preset_id, run.preset_label, run.config_hash,
                 run.database_logical_hash, run.as_of_date, run.calculated_at, len(run.results)),
            )
            connection.executemany(
                """INSERT INTO indicator_result VALUES
                   (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    (
                        item.indicator_result_id, item.run_id, item.preset_id,
                        item.indicator_id, item.indicator_name, item.period_start,
                        item.period_end, item.dimension, item.dimension_value,
                        None if item.numeric_value is None else str(item.numeric_value),
                        item.unit, item.formula_version,
                        json.dumps(item.source_record_ids, ensure_ascii=False),
                        json.dumps(item.source_location_ids, ensure_ascii=False),
                        json.dumps(item.details, ensure_ascii=False, sort_keys=True),
                    )
                    for item in run.results
                ],
            )
