from __future__ import annotations

from hashlib import sha256
import io
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest

from faro.company.config import load_company_configuration
from faro.imports.service import ImportRequest, IncrementalImportService
from faro.settings import Settings


class IncrementalImportSafetyIntegrationTests(unittest.TestCase):
    """Uses an optional local fixture DB; skips cleanly when the fixture is absent."""

    fixture_database = Path("data/processed/faro.db")

    def test_valid_upload_updates_candidate_and_invalid_upload_preserves_active_database(self) -> None:
        if not self.fixture_database.is_file():
            self.skipTest("Run make consolidate to create the local integration fixture")
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            database = root / "faro.db"
            shutil.copy2(self.fixture_database, database)
            settings = Settings(
                database_path=database,
                indicator_config_path=Path("config/indicators.yaml"),
                alert_config_path=Path("config/alerts.yaml"),
                company_config_path=Path("config/company.yaml"),
                import_database_path=root / "imports.db",
                import_staging_dir=root / "inbox",
                import_archive_dir=root / "uploads",
            )
            service = IncrementalImportService(
                settings, load_company_configuration(settings.company_config_path)
            )
            valid = (
                "sale_id,sale_line_id,sale_date,customer_id,product_id,quantity,"
                "unit_price_cop,discount_cop,line_total_cop,channel\n"
                "SAL-UPLOAD-1,SALL-UPLOAD-1,2026-08-03,CUS-0001,PRD-0001,"
                "3,12000,0,36000,store\n"
            ).encode()
            result = service.import_stream(
                io.BytesIO(valid),
                ImportRequest("ventas_nuevas.csv", "sales", "upsert"),
                job_id="IMP-INTEGRATION-01",
            )
            self.assertEqual("completed", result.status)
            with sqlite3.connect(database) as connection:
                self.assertEqual(
                    1,
                    connection.execute(
                        "SELECT COUNT(*) FROM sale_line WHERE sale_line_id='SALL-UPLOAD-1'"
                    ).fetchone()[0],
                )
                self.assertEqual("ok", connection.execute("PRAGMA integrity_check").fetchone()[0])
            before_invalid = sha256(database.read_bytes()).hexdigest()
            invalid = valid.replace(b"PRD-0001", b"PRD-NOT-FOUND")
            with self.assertRaises(sqlite3.IntegrityError):
                service.import_stream(
                    io.BytesIO(invalid),
                    ImportRequest("ventas_invalidas.csv", "sales", "upsert"),
                    job_id="IMP-INTEGRATION-02",
                )
            self.assertEqual(before_invalid, sha256(database.read_bytes()).hexdigest())


if __name__ == "__main__":
    unittest.main()
