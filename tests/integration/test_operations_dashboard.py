from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from faro.imports.service import ImportResult
from faro.imports.storage import ImportJobStore
from faro.ui.app import app
from faro.ui.dashboard import DashboardRepository
from tests.unit.ui.test_dashboard import seed_dashboard_database


class OperationsDashboardIntegrationTests(unittest.TestCase):
    def test_dashboard_renders_simple_decision_view_and_upload_button(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "faro.db"
            seed_dashboard_database(db_path)
            with patch(
                "faro.ui.app._repository",
                return_value=DashboardRepository(db_path),
            ):
                with TestClient(app) as client:
                    response = client.get("/dashboard")

        self.assertEqual(200, response.status_code)
        self.assertIn("Panel de Empresa de Prueba", response.text)
        self.assertIn("Qué revisar hoy", response.text)
        self.assertIn("Reposición requerida", response.text)
        self.assertIn("Productos por reponer", response.text)
        self.assertIn("Actualizar información", response.text)
        self.assertNotIn("greater_than", response.text)

    def test_upload_button_records_successful_client_update(self) -> None:
        class FakeImportService:
            def import_stream(self, stream, request, *, job_id=None):
                self.payload = stream.read()
                return ImportResult(
                    job_id=job_id or "IMP-FAKE",
                    status="completed",
                    message="Actualizada",
                    records_added=1,
                    findings_added=0,
                    source_file_id="SRC-FAKE",
                )

        with tempfile.TemporaryDirectory() as tmp_dir:
            store = ImportJobStore(Path(tmp_dir) / "imports.db")
            with patch("faro.ui.app._job_store", return_value=store), patch(
                "faro.ui.app._import_service", return_value=FakeImportService()
            ):
                with TestClient(app) as client:
                    response = client.post(
                        "/data/import",
                        files={"file": ("ventas.csv", b"a,b\n1,2\n", "text/csv")},
                        data={"profile_id": "sales", "mode": "upsert"},
                        follow_redirects=False,
                    )
            jobs = store.recent()
        self.assertEqual(303, response.status_code)
        self.assertIn("import_status=completed", response.headers["location"])
        self.assertEqual("completed", jobs[0].status)
        self.assertEqual(1, jobs[0].records_added)

    def test_health_endpoint_is_explicit_when_database_is_not_ready(self) -> None:
        with TestClient(app) as client:
            response = client.get("/health")
        self.assertEqual(200, response.status_code)
        self.assertIn(response.json()["status"], {"ok", "degraded"})
        self.assertIn("database_available", response.json())


if __name__ == "__main__":
    unittest.main()
