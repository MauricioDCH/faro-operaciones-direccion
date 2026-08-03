from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from faro.indicators.catalog import IndicatorConfigError
from faro.indicators.config import load_indicator_configuration


class IndicatorConfigurationTests(unittest.TestCase):
    def test_loads_examples_and_selects_override(self) -> None:
        config = load_indicator_configuration(Path("config/indicators.yaml"))
        self.assertEqual(config.active_preset, "retail_distribution")
        self.assertEqual(config.select("sales_monitoring").preset_id, "sales_monitoring")
        self.assertGreaterEqual(len(config.select().indicators), 8)

    def test_rejects_unknown_indicator(self) -> None:
        payload = {
            "schema_version": "1.0.0", "active_preset": "bad",
            "calculated_at_source": "database_metadata",
            "presets": {"bad": {"indicators": [{"indicator_id": "invented", "parameters": {}}]}},
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "indicators.yaml"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(IndicatorConfigError):
                load_indicator_configuration(path)

    def test_rejects_invalid_limit(self) -> None:
        payload = {
            "schema_version": "1.0.0", "active_preset": "bad",
            "calculated_at_source": "database_metadata",
            "presets": {"bad": {"indicators": [{"indicator_id": "top_products", "parameters": {"limit": 0}}]}},
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "indicators.yaml"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(IndicatorConfigError):
                load_indicator_configuration(path)
