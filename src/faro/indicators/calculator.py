"""Deterministic indicator calculations over Faro's canonical SQLite store."""

from __future__ import annotations

from contextlib import closing

from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from typing import Any, Callable

from faro.indicators.catalog import CATALOG, IndicatorConfigError
from faro.indicators.config import IndicatorConfiguration
from faro.indicators.models import IndicatorResult, IndicatorRun
from faro.indicators.storage import persist_indicator_run

ZERO = Decimal("0")


def _decimal(value: Any) -> Decimal:
    return Decimal(str(value or "0"))


def _month_bounds(value: date) -> tuple[date, date]:
    start = value.replace(day=1)
    next_month = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
    return start, next_month - timedelta(days=1)


def _previous_month(start: date) -> tuple[date, date]:
    previous_end = start - timedelta(days=1)
    return _month_bounds(previous_end)


def _stable_id(prefix: str, *parts: object) -> str:
    payload = "|".join("" if item is None else str(item) for item in parts)
    return f"{prefix}-{sha256(payload.encode()).hexdigest()[:16].upper()}"


def _unique(values: list[str | None]) -> tuple[str, ...]:
    return tuple(sorted({item for item in values if item}))


class OperationalIndicatorService:
    def calculate(
        self,
        *,
        database_path: Path,
        configuration: IndicatorConfiguration,
        preset_id: str | None = None,
        as_of_date: date | None = None,
        persist: bool = True,
    ) -> IndicatorRun:
        if not database_path.is_file():
            raise IndicatorConfigError(f"Operational database does not exist: {database_path}")
        preset = configuration.select(preset_id)
        with closing(sqlite3.connect(database_path)) as connection:
            connection.row_factory = sqlite3.Row
            self._validate_database(connection)
            metadata = dict(connection.execute("SELECT key, value FROM metadata"))
            calculated_at = metadata.get("consolidated_at")
            if not calculated_at:
                raise IndicatorConfigError("Database metadata does not contain consolidated_at")
            logical_hash = metadata.get("logical_content_hash", "unknown")
            latest_available = self._latest_available_date(connection)
            resolved_as_of = as_of_date or latest_available
            if resolved_as_of < latest_available:
                raise IndicatorConfigError(
                    "as_of_date cannot be earlier than the latest operational date"
                )
            run_id = _stable_id(
                "KPIRUN", logical_hash, configuration.config_hash, preset.preset_id,
                resolved_as_of.isoformat(), calculated_at,
            )
            results: list[IndicatorResult] = []
            dispatch: dict[str, Callable[..., list[IndicatorResult]]] = {
                "sales_total": self._sales_total,
                "sales_change": self._sales_change,
                "top_products": self._top_products,
                "low_inventory": self._low_inventory,
                "order_invoice_mismatch": self._order_invoice_mismatch,
                "data_quality_summary": self._data_quality_summary,
                "source_coverage": self._source_coverage,
                "data_freshness": self._data_freshness,
            }
            for selection in preset.indicators:
                results.extend(dispatch[selection.indicator_id](
                    connection, run_id, preset.preset_id, selection.parameters, resolved_as_of
                ))
        run = IndicatorRun(
            run_id, preset.preset_id, preset.label, configuration.config_hash,
            logical_hash, resolved_as_of.isoformat(), calculated_at,
            tuple(sorted(results, key=lambda item: (item.indicator_id, item.dimension_value or "", item.indicator_result_id))),
        )
        if persist:
            persist_indicator_run(database_path, run)
        return run

    @staticmethod
    def _validate_database(connection: sqlite3.Connection) -> None:
        required = {"metadata", "sale_line", "product", "inventory_snapshot", "quality_finding", "source_file"}
        existing = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        missing = required - existing
        if missing:
            raise IndicatorConfigError(f"Operational database is missing tables: {sorted(missing)}")

    @staticmethod
    def _latest_available_date(connection: sqlite3.Connection) -> date:
        candidates: list[str] = []
        for table, column in (
            ("sale_line", "sale_date"), ("inventory_snapshot", "snapshot_date"),
            ("purchase_order_line", "order_date"), ("invoice", "issue_date"),
            ("quotation", "issue_date"),
        ):
            row = connection.execute(f"SELECT MAX({column}) FROM {table}").fetchone()
            if row and row[0]:
                candidates.append(row[0])
        if not candidates:
            raise IndicatorConfigError("No operational dates are available for indicator calculation")
        return max(date.fromisoformat(item) for item in candidates)

    @staticmethod
    def _sales_rows(connection: sqlite3.Connection, start: date, end: date) -> list[sqlite3.Row]:
        return list(connection.execute(
            """SELECT s.sale_line_id, s.sale_id, s.sale_date, s.product_id,
                      p.product_name, s.quantity, s.line_total_cop, s.source_location_id
               FROM sale_line s JOIN product p ON p.product_id = s.product_id
               WHERE s.sale_date BETWEEN ? AND ? AND s.record_status = 'accepted'
               ORDER BY s.sale_line_id""", (start.isoformat(), end.isoformat())
        ))

    @staticmethod
    def _make_result(run_id: str, preset_id: str, indicator_id: str, *,
                     period_start: str | None, period_end: str | None,
                     dimension: str | None, dimension_value: str | None,
                     numeric_value: Decimal | None, unit: str,
                     source_record_ids: tuple[str, ...] = (),
                     source_location_ids: tuple[str, ...] = (),
                     details: dict[str, Any] | None = None) -> IndicatorResult:
        definition = CATALOG[indicator_id]
        result_id = _stable_id("KPI", run_id, indicator_id, dimension, dimension_value)
        return IndicatorResult(
            result_id, run_id, preset_id, indicator_id, definition.name,
            period_start, period_end, dimension, dimension_value, numeric_value,
            unit, definition.formula_version, source_record_ids,
            source_location_ids, details or {},
        )

    def _sales_total(self, c, run, preset, params, as_of):
        latest = date.fromisoformat(c.execute("SELECT MAX(sale_date) FROM sale_line").fetchone()[0])
        start, end = _month_bounds(latest)
        rows = self._sales_rows(c, start, end)
        total = sum((_decimal(row["line_total_cop"]) for row in rows), ZERO)
        units = sum((_decimal(row["quantity"]) for row in rows), ZERO)
        return [self._make_result(run, preset, "sales_total", period_start=start.isoformat(), period_end=end.isoformat(),
            dimension=None, dimension_value=None, numeric_value=total, unit="COP",
            source_record_ids=_unique([row["sale_line_id"] for row in rows]),
            source_location_ids=_unique([row["source_location_id"] for row in rows]),
            details={"sale_count": len({row["sale_id"] for row in rows}), "line_count": len(rows), "units": str(units), "formula": "sum(line_total_cop)"})]

    def _sales_change(self, c, run, preset, params, as_of):
        latest = date.fromisoformat(c.execute("SELECT MAX(sale_date) FROM sale_line").fetchone()[0])
        start, end = _month_bounds(latest)
        prev_start, prev_end = _previous_month(start)
        current = self._sales_rows(c, start, end)
        previous = self._sales_rows(c, prev_start, prev_end)
        current_total = sum((_decimal(row["line_total_cop"]) for row in current), ZERO)
        previous_total = sum((_decimal(row["line_total_cop"]) for row in previous), ZERO)
        change = None if previous_total == ZERO else (((current_total - previous_total) / previous_total) * Decimal("100")).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        all_rows = current + previous
        return [self._make_result(run, preset, "sales_change", period_start=start.isoformat(), period_end=end.isoformat(),
            dimension=None, dimension_value=None, numeric_value=change, unit="percent",
            source_record_ids=_unique([row["sale_line_id"] for row in all_rows]),
            source_location_ids=_unique([row["source_location_id"] for row in all_rows]),
            details={"current_total_cop": str(current_total), "previous_total_cop": str(previous_total), "previous_period_start": prev_start.isoformat(), "previous_period_end": prev_end.isoformat(), "formula": "((current-previous)/previous)*100"})]

    def _top_products(self, c, run, preset, params, as_of):
        latest = date.fromisoformat(c.execute("SELECT MAX(sale_date) FROM sale_line").fetchone()[0])
        start, end = _month_bounds(latest)
        rows = self._sales_rows(c, start, end)
        grouped: dict[str, dict[str, Any]] = {}
        for row in rows:
            item = grouped.setdefault(row["product_id"], {"name": row["product_name"], "revenue": ZERO, "quantity": ZERO, "records": [], "locations": []})
            item["revenue"] += _decimal(row["line_total_cop"])
            item["quantity"] += _decimal(row["quantity"])
            item["records"].append(row["sale_line_id"])
            item["locations"].append(row["source_location_id"])
        metric = params["metric"]
        ordered = sorted(grouped.items(), key=lambda pair: (-pair[1][metric], pair[0]))[:params["limit"]]
        results = []
        for rank, (product_id, item) in enumerate(ordered, 1):
            results.append(self._make_result(run, preset, "top_products", period_start=start.isoformat(), period_end=end.isoformat(),
                dimension="product", dimension_value=product_id, numeric_value=item[metric], unit="COP" if metric == "revenue" else "unit",
                source_record_ids=_unique(item["records"]), source_location_ids=_unique(item["locations"]),
                details={"rank": rank, "product_name": item["name"], "metric": metric, "revenue_cop": str(item["revenue"]), "quantity": str(item["quantity"]) }))
        return results

    def _low_inventory(self, c, run, preset, params, as_of):
        snapshot = c.execute("SELECT MAX(snapshot_date) FROM inventory_snapshot").fetchone()[0]
        rows = c.execute(
            """SELECT i.snapshot_date, i.product_id, p.product_name, p.unit,
                      i.available_quantity, i.reorder_point, i.source_location_id
               FROM inventory_snapshot i JOIN product p ON p.product_id=i.product_id
               WHERE i.snapshot_date=? ORDER BY i.product_id""", (snapshot,)
        )
        results = []
        for row in rows:
            available, reorder = _decimal(row["available_quantity"]), _decimal(row["reorder_point"])
            qualifies = available <= reorder if params["include_equal"] else available < reorder
            if qualifies:
                results.append(self._make_result(run, preset, "low_inventory", period_start=snapshot, period_end=snapshot,
                    dimension="product", dimension_value=row["product_id"], numeric_value=available, unit=row["unit"],
                    source_record_ids=(f"{snapshot}|{row['product_id']}",), source_location_ids=_unique([row["source_location_id"]]),
                    details={"product_name": row["product_name"], "reorder_point": str(reorder), "gap": str(reorder-available), "formula": "available_quantity < reorder_point"}))
        return results

    def _order_invoice_mismatch(self, c, run, preset, params, as_of):
        rows = list(c.execute("SELECT finding_id, record_id, source_location_id FROM quality_finding WHERE code='order_invoice_mismatch' ORDER BY finding_id"))
        return [self._make_result(run, preset, "order_invoice_mismatch", period_start=None, period_end=None,
            dimension=None, dimension_value=None, numeric_value=Decimal(len(rows)), unit="finding",
            source_record_ids=_unique([row["record_id"] or row["finding_id"] for row in rows]),
            source_location_ids=_unique([row["source_location_id"] for row in rows]),
            details={"formula": "count(quality_finding where code=order_invoice_mismatch)"})]

    def _data_quality_summary(self, c, run, preset, params, as_of):
        results = []
        for severity in params["severities"]:
            rows = list(c.execute("SELECT finding_id, record_id, source_location_id FROM quality_finding WHERE severity=? ORDER BY finding_id", (severity,)))
            results.append(self._make_result(run, preset, "data_quality_summary", period_start=None, period_end=None,
                dimension="severity", dimension_value=severity, numeric_value=Decimal(len(rows)), unit="finding",
                source_record_ids=_unique([row["record_id"] or row["finding_id"] for row in rows]),
                source_location_ids=_unique([row["source_location_id"] for row in rows]), details={"formula": "count(quality_finding by severity)"}))
        return results

    def _source_coverage(self, c, run, preset, params, as_of):
        rows = list(c.execute("SELECT COALESCE(ingestion_adapter, source_type) adapter, COUNT(*) total, GROUP_CONCAT(source_file_id) ids FROM source_file GROUP BY adapter ORDER BY adapter"))
        return [self._make_result(run, preset, "source_coverage", period_start=None, period_end=None,
            dimension="adapter", dimension_value=row["adapter"], numeric_value=Decimal(row["total"]), unit="source_file",
            source_record_ids=_unique((row["ids"] or "").split(",")), details={"formula": "count(source_file by ingestion_adapter)"}) for row in rows]

    def _data_freshness(self, c, run, preset, params, as_of):
        mapping = {
            "sales": ("sale_line", "sale_date", "sale_line_id", "source_location_id"),
            "inventory": ("inventory_snapshot", "snapshot_date", "product_id", "source_location_id"),
            "orders": ("purchase_order_line", "order_date", "order_line_id", "source_location_id"),
            "invoices": ("invoice", "issue_date", "invoice_id", "source_location_id"),
            "quotations": ("quotation", "issue_date", "quotation_id", "source_location_id"),
        }
        results = []
        for entity in params["entities"]:
            table, date_col, id_col, loc_col = mapping[entity]
            latest = c.execute(f"SELECT MAX({date_col}) FROM {table}").fetchone()[0]
            if latest:
                rows = list(c.execute(f"SELECT {id_col} record_id, {loc_col} source_location_id FROM {table} WHERE {date_col}=? ORDER BY {id_col}", (latest,)))
                lag = Decimal((as_of - date.fromisoformat(latest)).days)
                records = _unique([row["record_id"] for row in rows])
                locations = _unique([row["source_location_id"] for row in rows])
            else:
                lag, records, locations = None, (), ()
            results.append(self._make_result(run, preset, "data_freshness", period_start=latest, period_end=latest,
                dimension="entity", dimension_value=entity, numeric_value=lag, unit="day",
                source_record_ids=records, source_location_ids=locations,
                details={"latest_available_date": latest, "as_of_date": as_of.isoformat(), "formula": "as_of_date-latest_available_date"}))
        return results
