from __future__ import annotations

from pathlib import Path
import sqlite3
from contextlib import closing
import tempfile
import unittest

from faro.persistence.consolidation import UnifiedConsolidationService
from faro.settings import Settings


class UnifiedOperationalStoreIntegrationTests(unittest.TestCase):
    def test_all_implemented_sources_are_consolidated_idempotently(self) -> None:
        settings = Settings(
            data_dir=Path("data"),
            database_path=Path("data/processed/faro.db"),
        )
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "faro.db"
            service = UnifiedConsolidationService(settings)
            first = service.consolidate(database_path=database, include_samples=True)
            second = service.consolidate(database_path=database, include_samples=True)

            self.assertTrue(first.raw_files_unchanged)
            self.assertEqual(first.integrity_check, "ok")
            self.assertEqual(first.logical_content_hash, second.logical_content_hash)
            self.assertEqual(first.adapters["xlsx"], 4)
            self.assertGreaterEqual(first.adapters["pdf"], 1)
            self.assertGreaterEqual(first.adapters["ubl_xml"], 1)
            self.assertGreaterEqual(first.counts["product"], 12)
            self.assertGreaterEqual(first.counts["invoice"], 1)
            with closing(sqlite3.connect(database)) as connection:
                self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")
                self.assertGreater(connection.execute("SELECT COUNT(*) FROM source_location").fetchone()[0], 0)
                self.assertGreater(connection.execute("SELECT COUNT(*) FROM transformation_event").fetchone()[0], 0)
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM sale_line WHERE record_status <> 'accepted'").fetchone()[0], 0)
