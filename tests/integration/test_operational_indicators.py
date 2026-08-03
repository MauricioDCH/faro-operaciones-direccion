from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from faro.indicators import OperationalIndicatorService, load_indicator_configuration
from faro.persistence.consolidation import UnifiedConsolidationService
from faro.settings import Settings


class OperationalIndicatorsIntegrationTests(unittest.TestCase):
    def test_consolidated_store_produces_reproducible_indicator_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "faro.db"
            settings = Settings(data_dir=Path("data"), database_path=database)
            UnifiedConsolidationService(settings).consolidate(database_path=database, include_samples=True)
            config = load_indicator_configuration(Path("config/indicators.yaml"))
            service = OperationalIndicatorService()
            first = service.calculate(database_path=database, configuration=config)
            second = service.calculate(database_path=database, configuration=config)
            self.assertEqual(first.run_id, second.run_id)
            self.assertEqual(first.to_dict(), second.to_dict())
            self.assertGreater(len(first.results), 0)
            self.assertIn("sales_total", {item.indicator_id for item in first.results})
