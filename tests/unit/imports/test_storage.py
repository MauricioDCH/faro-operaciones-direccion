from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from faro.imports.models import ImportJob
from faro.imports.storage import ImportJobStore


class ImportJobStoreTests(unittest.TestCase):
    def test_persists_status_without_using_operational_database(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "imports.db"
            store = ImportJobStore(path)
            store.create(
                ImportJob(
                    job_id="IMP-001",
                    file_name="ventas.csv",
                    profile_id="sales",
                    mode="upsert",
                    status="processing",
                    message="Validando",
                    created_at="2026-08-03T06:00:00+00:00",
                    completed_at=None,
                    source_file_id=None,
                    file_hash=None,
                    records_added=0,
                    findings_added=0,
                    backup_path=None,
                )
            )
            updated = store.update(
                "IMP-001",
                status="completed",
                message="Actualizada",
                completed_at="2026-08-03T06:01:00+00:00",
                records_added=2,
            )
            recent = store.recent()
        self.assertEqual("completed", updated.status)
        self.assertEqual(2, recent[0].records_added)


if __name__ == "__main__":
    unittest.main()
