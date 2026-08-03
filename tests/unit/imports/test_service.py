from __future__ import annotations

import io
from pathlib import Path
import tempfile
import unittest

from faro.company.config import default_company_configuration
from faro.imports.service import (
    ImportRequest,
    ImportValidationError,
    IncrementalImportService,
)
from faro.settings import Settings


class IncrementalImportServiceTests(unittest.TestCase):
    def test_rejects_unsupported_extension_before_touching_database(self) -> None:
        service = IncrementalImportService(Settings(), default_company_configuration())
        with self.assertRaisesRegex(ImportValidationError, "Tipo de archivo"):
            service.import_stream(
                io.BytesIO(b"unsafe"), ImportRequest("archivo.exe"), job_id="IMP-TEST"
            )

    def test_tabular_upload_requires_explicit_business_profile(self) -> None:
        service = IncrementalImportService(Settings(), default_company_configuration())
        with self.assertRaisesRegex(ImportValidationError, "Selecciona qué contiene"):
            service.import_stream(
                io.BytesIO(b"a,b\n1,2\n"), ImportRequest("ventas.csv"), job_id="IMP-TEST"
            )

    def test_copy_limit_rejects_oversized_file_and_removes_partial_upload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            settings = Settings(import_max_file_size_mb=1)
            service = IncrementalImportService(settings, default_company_configuration())
            target = Path(tmp_dir) / "large.csv"
            with self.assertRaisesRegex(ImportValidationError, "máximo permitido"):
                service._copy_limited(io.BytesIO(b"x" * (1024 * 1024 + 1)), target)
        self.assertFalse(target.exists())

    def test_file_name_is_reduced_to_safe_basename(self) -> None:
        self.assertEqual(
            "ventas_ agosto.csv",
            IncrementalImportService._safe_file_name("../../ventas_ agosto.csv"),
        )


if __name__ == "__main__":
    unittest.main()
