from __future__ import annotations

from pathlib import Path
import sqlite3
import tempfile
import unittest

from faro.alerts import ConfigurableAlertService, load_alert_configuration
from faro.indicators import load_indicator_configuration
from unit.indicators.test_calculator import build_database


class ConfigurableAlertServiceTests(unittest.TestCase):
    def test_evaluates_rules_persists_alerts_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "faro.db"
            build_database(database)
            alert_config = load_alert_configuration(Path("config/alerts.yaml"))
            indicator_config = load_indicator_configuration(Path("config/indicators.yaml"))
            service = ConfigurableAlertService()
            first = service.evaluate(
                database_path=database,
                alert_configuration=alert_config,
                indicator_configuration=indicator_config,
            )
            second = service.evaluate(
                database_path=database,
                alert_configuration=alert_config,
                indicator_configuration=indicator_config,
            )
            self.assertEqual(first.run_id, second.run_id)
            self.assertEqual(first.to_dict(), second.to_dict())
            self.assertIn("ALERT-LOW-INVENTORY-001", {item.rule_id for item in first.alerts})
            self.assertIn("ALERT-ORDER-INVOICE-001", {item.rule_id for item in first.alerts})
            self.assertTrue(all(item.source_location_ids for item in first.alerts))
            with sqlite3.connect(database) as connection:
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM alert_run").fetchone()[0], 1)
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM alert_evaluation").fetchone()[0], len(first.evaluations))
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM alert").fetchone()[0], len(first.alerts))

    def test_quality_finding_count_uses_all_matching_rows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "faro.db"
            build_database(database)
            with sqlite3.connect(database) as connection:
                connection.executemany(
                    "INSERT INTO quality_finding VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    [
                        ("FC1", "RC", "cross_source_conflict", "quality", "error", "c1", "LOC-1", "product", "P1", None, "a", "b"),
                        ("FC2", "RC", "cross_source_conflict", "quality", "error", "c2", "LOC-2", "product", "P2", None, "a", "b"),
                    ],
                )
            run = ConfigurableAlertService().evaluate(
                database_path=database,
                alert_configuration=load_alert_configuration(Path("config/alerts.yaml")),
                indicator_configuration=load_indicator_configuration(Path("config/indicators.yaml")),
                preset_id="data_quality",
            )
            evaluation = next(item for item in run.evaluations if item.rule_id == "ALERT-SOURCE-CONFLICT-002")
            self.assertEqual(evaluation.observed_value, 2)
            self.assertEqual(evaluation.finding_ids, ("FC1", "FC2"))
            self.assertEqual(evaluation.status, "triggered")

    def test_company_preset_changes_thresholds_and_rules(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "faro.db"
            build_database(database)
            run = ConfigurableAlertService().evaluate(
                database_path=database,
                alert_configuration=load_alert_configuration(Path("config/alerts.yaml")),
                indicator_configuration=load_indicator_configuration(Path("config/indicators.yaml")),
                preset_id="sales_monitoring",
                persist=False,
            )
            self.assertEqual(run.preset_id, "sales_monitoring")
            self.assertIn("ALERT-SALES-TARGET-001", {item.rule_id for item in run.alerts})
            self.assertNotIn("ALERT-LOW-INVENTORY-001", {item.rule_id for item in run.evaluations})
