"""Resilient read-only queries and business view models for the Faro dashboard."""

from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
import json
from pathlib import Path
import sqlite3
from typing import Any

from faro.ui.presentation import (
    alert_copy,
    entity_label,
    indicator_copy,
    source_label,
)


@dataclass(frozen=True, slots=True)
class DashboardSnapshot:
    available: bool
    error_message: str | None
    database_path: Path
    generated_at: str | None
    logical_hash: str | None
    indicator_preset: str | None
    alert_preset: str | None
    status: dict[str, str]
    summary_cards: list[dict[str, str]]
    action_cards: list[dict[str, Any]]
    entity_counts: list[dict[str, Any]]
    quality_summary: list[dict[str, Any]]
    source_summary: list[dict[str, Any]]
    top_products: list[dict[str, Any]]
    indicators: list[dict[str, Any]]
    alerts: list[dict[str, Any]]
    latest_indicator_run: dict[str, Any] | None
    latest_alert_run: dict[str, Any] | None


class DashboardRepository:
    def __init__(self, database_path: Path, *, currency: str = "COP") -> None:
        self.database_path = database_path
        self.currency = currency

    def fetch_snapshot(
        self,
        indicator_preset: str | None = None,
        alert_preset: str | None = None,
        severity: str | None = None,
        query: str | None = None,
    ) -> DashboardSnapshot:
        try:
            if not self.database_path.is_file():
                return self._unavailable(
                    "Todavía no hay una base de datos disponible. Realiza la consolidación inicial."
                )
            with closing(sqlite3.connect(self.database_path)) as connection:
                connection.row_factory = sqlite3.Row
                metadata = self._load_metadata(connection)
                latest_indicator_run = self._latest_indicator_run(
                    connection, indicator_preset
                )
                latest_alert_run = self._latest_alert_run(connection, alert_preset)
                entity_counts = self._entity_counts(connection)
                quality_summary = self._quality_summary(connection)
                source_summary = self._source_summary(connection)
                top_products = self._top_products(connection)
                indicators = (
                    self._indicator_results(connection, latest_indicator_run["run_id"])
                    if latest_indicator_run
                    else []
                )
                alerts = (
                    self._alerts(connection, latest_alert_run["run_id"])
                    if latest_alert_run
                    else []
                )
        except (sqlite3.Error, OSError, ValueError, json.JSONDecodeError) as exc:
            return self._unavailable(
                "Faro no pudo leer la información en este momento. La base activa no fue modificada.",
                technical=str(exc),
            )

        presented_indicators = [
            indicator_copy(item, currency=self.currency) for item in indicators
        ]
        presented_alerts = [alert_copy(item, currency=self.currency) for item in alerts]
        if severity:
            presented_alerts = [
                item for item in presented_alerts if item["severity"] == severity
            ]
        if query:
            normalized = query.casefold().strip()
            presented_alerts = [
                item
                for item in presented_alerts
                if normalized in f"{item['title']} {item['simple_description']} {item['action_text']}".casefold()
            ]
        status = self._business_status(presented_alerts)
        summary_cards = self._summary_cards(
            quality_summary=quality_summary,
            indicators=presented_indicators,
            alerts=presented_alerts,
            status=status,
        )
        return DashboardSnapshot(
            available=True,
            error_message=None,
            database_path=self.database_path,
            generated_at=metadata.get("consolidated_at"),
            logical_hash=metadata.get("logical_content_hash") or metadata.get("database_logical_hash"),
            indicator_preset=(
                latest_indicator_run["preset_id"] if latest_indicator_run else None
            ),
            alert_preset=latest_alert_run["preset_id"] if latest_alert_run else None,
            status=status,
            summary_cards=summary_cards,
            action_cards=presented_alerts[:5],
            entity_counts=entity_counts,
            quality_summary=quality_summary,
            source_summary=source_summary,
            top_products=top_products,
            indicators=presented_indicators,
            alerts=presented_alerts,
            latest_indicator_run=latest_indicator_run,
            latest_alert_run=latest_alert_run,
        )

    def _unavailable(
        self, message: str, *, technical: str | None = None
    ) -> DashboardSnapshot:
        return DashboardSnapshot(
            available=False,
            error_message=message,
            database_path=self.database_path,
            generated_at=None,
            logical_hash=technical,
            indicator_preset=None,
            alert_preset=None,
            status={
                "tone": "warning",
                "label": "Información no disponible",
                "summary": "Tus datos anteriores siguen protegidos.",
            },
            summary_cards=[],
            action_cards=[],
            entity_counts=[],
            quality_summary=[],
            source_summary=[],
            top_products=[],
            indicators=[],
            alerts=[],
            latest_indicator_run=None,
            latest_alert_run=None,
        )

    @staticmethod
    def _load_metadata(connection: sqlite3.Connection) -> dict[str, str]:
        rows = connection.execute("SELECT key, value FROM metadata").fetchall()
        return {row["key"]: row["value"] for row in rows}

    @staticmethod
    def _latest_indicator_run(
        connection: sqlite3.Connection, preset_id: str | None
    ) -> dict[str, Any] | None:
        if not DashboardRepository._table_exists(connection, "indicator_run"):
            return None
        if preset_id:
            row = connection.execute(
                """SELECT * FROM indicator_run WHERE preset_id = ?
                   ORDER BY calculated_at DESC LIMIT 1""",
                (preset_id,),
            ).fetchone()
        else:
            row = connection.execute(
                "SELECT * FROM indicator_run ORDER BY calculated_at DESC LIMIT 1"
            ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def _latest_alert_run(
        connection: sqlite3.Connection, preset_id: str | None
    ) -> dict[str, Any] | None:
        if not DashboardRepository._table_exists(connection, "alert_run"):
            return None
        if preset_id:
            row = connection.execute(
                """SELECT * FROM alert_run WHERE preset_id = ?
                   ORDER BY evaluated_at DESC LIMIT 1""",
                (preset_id,),
            ).fetchone()
        else:
            row = connection.execute(
                "SELECT * FROM alert_run ORDER BY evaluated_at DESC LIMIT 1"
            ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def _entity_counts(connection: sqlite3.Connection) -> list[dict[str, Any]]:
        if not DashboardRepository._view_exists(connection, "v_entity_counts"):
            return []
        rows = connection.execute(
            "SELECT entity_type, record_count FROM v_entity_counts ORDER BY record_count DESC, entity_type"
        ).fetchall()
        return [
            {
                **dict(row),
                "label": entity_label(row["entity_type"]),
            }
            for row in rows
            if int(row["record_count"]) > 0
        ]

    @staticmethod
    def _quality_summary(connection: sqlite3.Connection) -> list[dict[str, Any]]:
        if not DashboardRepository._table_exists(connection, "quality_finding"):
            return []
        rows = connection.execute(
            """
            SELECT severity, COUNT(*) AS total
            FROM quality_finding
            GROUP BY severity
            ORDER BY CASE severity
                WHEN 'critical' THEN 1
                WHEN 'error' THEN 2
                WHEN 'warning' THEN 3
                ELSE 4
            END
            """
        ).fetchall()
        labels = {
            "critical": "Urgentes",
            "error": "Errores",
            "warning": "Advertencias",
            "info": "Información",
        }
        return [
            {**dict(row), "label": labels.get(row["severity"], row["severity"])}
            for row in rows
        ]

    @staticmethod
    def _source_summary(connection: sqlite3.Connection) -> list[dict[str, Any]]:
        if not DashboardRepository._table_exists(connection, "source_file"):
            return []
        rows = connection.execute(
            """
            SELECT COALESCE(ingestion_adapter, detected_format, 'unknown') AS adapter,
                   COUNT(*) AS source_files,
                   COUNT(DISTINCT source_type) AS source_types
            FROM source_file
            GROUP BY COALESCE(ingestion_adapter, detected_format, 'unknown')
            ORDER BY source_files DESC, adapter
            """
        ).fetchall()
        return [
            {**dict(row), "label": source_label(row["adapter"])} for row in rows
        ]

    @staticmethod
    def _top_products(connection: sqlite3.Connection) -> list[dict[str, Any]]:
        if not all(
            DashboardRepository._table_exists(connection, table)
            for table in ("sale_line", "product")
        ):
            return []
        rows = connection.execute(
            """
            SELECT p.product_name,
                   SUM(CAST(sl.quantity AS REAL)) AS total_quantity,
                   SUM(CAST(sl.line_total_cop AS REAL)) AS total_sales_cop
            FROM sale_line sl
            JOIN product p ON p.product_id = sl.product_id
            WHERE sl.record_status = 'accepted'
            GROUP BY p.product_id, p.product_name
            ORDER BY total_sales_cop DESC, p.product_name
            LIMIT 5
            """
        ).fetchall()
        values = [dict(row) for row in rows]
        max_sales = max((row["total_sales_cop"] or 0 for row in values), default=0)
        for row in values:
            row["sales_bar"] = (
                0
                if max_sales == 0
                else round((row["total_sales_cop"] / max_sales) * 100, 2)
            )
            row["sales_text"] = f"$ {row['total_sales_cop']:,.0f}".replace(",", ".")
            row["quantity_text"] = f"{row['total_quantity']:,.0f} unidades".replace(",", ".")
        return values

    @staticmethod
    def _indicator_results(
        connection: sqlite3.Connection, run_id: str
    ) -> list[dict[str, Any]]:
        rows = connection.execute(
            """
            SELECT indicator_id, indicator_name, numeric_value, unit,
                   period_start, period_end, details_json, dimension, dimension_value,
                   source_record_ids_json, source_location_ids_json
            FROM indicator_result
            WHERE run_id = ?
            ORDER BY indicator_name, COALESCE(dimension_value, '')
            """,
            (run_id,),
        ).fetchall()
        values: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["details"] = json.loads(item.pop("details_json") or "{}")
            item["source_record_ids"] = json.loads(
                item.pop("source_record_ids_json") or "[]"
            )
            item["source_location_ids"] = json.loads(
                item.pop("source_location_ids_json") or "[]"
            )
            values.append(item)
        return values

    @staticmethod
    def _alerts(connection: sqlite3.Connection, run_id: str) -> list[dict[str, Any]]:
        rows = connection.execute(
            """
            SELECT alert_id, alert_type, severity, title, description, observed_value,
                   operator, threshold_value, unit, review_status,
                   delivery_status, generated_at,
                   indicator_result_ids_json, finding_ids_json,
                   related_record_ids_json, source_location_ids_json
            FROM alert
            WHERE run_id = ?
            ORDER BY CASE severity
                WHEN 'critical' THEN 1
                WHEN 'error' THEN 2
                WHEN 'warning' THEN 3
                ELSE 4
            END, generated_at DESC, title
            """,
            (run_id,),
        ).fetchall()
        alerts: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            for key in (
                "indicator_result_ids_json",
                "finding_ids_json",
                "related_record_ids_json",
                "source_location_ids_json",
            ):
                item[key[:-5]] = json.loads(item.pop(key) or "[]")
            alerts.append(item)
        return alerts

    @staticmethod
    def _business_status(alerts: list[dict[str, Any]]) -> dict[str, str]:
        if any(item["severity"] == "critical" for item in alerts):
            return {
                "tone": "danger",
                "label": "Necesita atención hoy",
                "summary": "Hay al menos una situación urgente que conviene revisar primero.",
            }
        if alerts:
            return {
                "tone": "warning",
                "label": "Hay temas por revisar",
                "summary": "El negocio puede seguir operando, pero hay situaciones pendientes.",
            }
        return {
            "tone": "good",
            "label": "Todo está en orden",
            "summary": "No hay alertas activas con la información disponible.",
        }

    @staticmethod
    def _summary_cards(
        *,
        quality_summary: list[dict[str, Any]],
        indicators: list[dict[str, Any]],
        alerts: list[dict[str, Any]],
        status: dict[str, str],
    ) -> list[dict[str, str]]:
        error_total = sum(
            int(item["total"])
            for item in quality_summary
            if item["severity"] in {"critical", "error"}
        )
        low_inventory = sum(
            1 for item in indicators if item["indicator_id"] == "low_inventory"
        )
        urgent = sum(1 for item in alerts if item["severity"] == "critical")
        return [
            {
                "label": "Estado del negocio",
                "value": status["label"],
                "hint": status["summary"],
                "tone": status["tone"],
            },
            {
                "label": "Situaciones activas",
                "value": str(len(alerts)),
                "hint": f"{urgent} urgentes" if urgent else "ninguna urgente",
                "tone": "danger" if urgent else "warning" if alerts else "good",
            },
            {
                "label": "Productos por reponer",
                "value": str(low_inventory),
                "hint": "según el inventario disponible",
                "tone": "warning" if low_inventory else "good",
            },
            {
                "label": "Errores en los datos",
                "value": str(error_total),
                "hint": "pueden afectar reportes",
                "tone": "danger" if error_total else "good",
            },
        ]

    @staticmethod
    def _table_exists(connection: sqlite3.Connection, name: str) -> bool:
        return (
            connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
            ).fetchone()
            is not None
        )

    @staticmethod
    def _view_exists(connection: sqlite3.Connection, name: str) -> bool:
        return (
            connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='view' AND name=?", (name,)
            ).fetchone()
            is not None
        )
