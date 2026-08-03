from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from faro.alerts import AlertConfigError, load_alert_configuration


class AlertConfigurationTests(unittest.TestCase):
    def test_loads_company_presets_and_custom_example(self) -> None:
        config = load_alert_configuration(Path("config/alerts.yaml"))
        self.assertEqual(config.active_preset, "retail_distribution")
        self.assertIn("sales_monitoring", config.presets)
        self.assertIn("inventory_control", config.presets)
        self.assertIn("data_quality", config.presets)
        self.assertIn("custom_example", config.presets)
        self.assertGreaterEqual(len(config.select().rules), 6)

    def test_rejects_unknown_operator(self) -> None:
        payload = {
            "schema_version": "1.0.0",
            "active_preset": "bad",
            "presets": {
                "bad": {
                    "indicator_preset": "retail_distribution",
                    "rules": [{
                        "rule_id": "ALERT-BAD-001",
                        "source": {"type": "indicator", "id": "sales_total", "aggregation": "single"},
                        "condition": {"operator": "execute_sql", "threshold": 1, "unit": "COP"},
                        "severity": "warning"
                    }]
                }
            }
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "alerts.yaml"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(AlertConfigError):
                load_alert_configuration(path)

    def test_rejects_arbitrary_source_fields(self) -> None:
        payload = {
            "schema_version": "1.0.0",
            "active_preset": "bad",
            "presets": {
                "bad": {
                    "indicator_preset": "retail_distribution",
                    "rules": [{
                        "rule_id": "ALERT-BAD-002",
                        "source": {
                            "type": "indicator", "id": "sales_total",
                            "aggregation": "single", "sql": "DROP TABLE sale_line"
                        },
                        "condition": {"operator": "less_than", "threshold": 1, "unit": "COP"},
                        "severity": "warning"
                    }]
                }
            }
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "alerts.yaml"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(AlertConfigError):
                load_alert_configuration(path)

    def test_rejects_duplicate_rule_ids_across_presets(self) -> None:
        rule = {
            "rule_id": "ALERT-DUP-001",
            "source": {"type": "indicator", "id": "sales_total", "aggregation": "single"},
            "condition": {"operator": "less_than", "threshold": 1, "unit": "COP"},
            "severity": "warning"
        }
        payload = {
            "schema_version": "1.0.0",
            "active_preset": "one",
            "presets": {
                "one": {"indicator_preset": "retail_distribution", "rules": [rule]},
                "two": {"indicator_preset": "retail_distribution", "rules": [rule]},
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "alerts.yaml"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(AlertConfigError):
                load_alert_configuration(path)
