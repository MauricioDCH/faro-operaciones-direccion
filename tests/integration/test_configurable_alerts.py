from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from unit.indicators.test_calculator import build_database


class ConfigurableAlertsIntegrationTests(unittest.TestCase):
    def test_cli_calculates_indicators_evaluates_alerts_and_persists_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "faro.db"
            build_database(database)
            process = subprocess.run(
                [
                    sys.executable,
                    "scripts/evaluate_alerts.py",
                    "--database", str(database),
                    "--preset", "inventory_control",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            payload = json.loads(process.stdout)
            self.assertIn(payload["status"], {"completed", "completed_with_alerts"})
            self.assertEqual(payload["preset_id"], "inventory_control")
            self.assertGreater(payload["evaluation_count"], 0)
            with sqlite3.connect(database) as connection:
                alert = connection.execute(
                    "SELECT rule_id, source_location_ids_json, delivery_status FROM alert ORDER BY rule_id LIMIT 1"
                ).fetchone()
                self.assertIsNotNone(alert)
                self.assertTrue(json.loads(alert[1]))
                self.assertEqual(alert[2], "not_configured")
