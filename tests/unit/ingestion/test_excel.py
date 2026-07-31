from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
import shutil
import unittest
from zipfile import ZIP_DEFLATED, ZipFile

from faro.ingestion import ExcelIngestionService


PROJECT_ROOT = Path(__file__).resolve().parents[3]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
FIXED_TIME = datetime(2026, 7, 31, 21, 0, tzinfo=timezone.utc)


def copy_raw(destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for name in ("catalogos.xlsx", "ventas.xlsx", "inventario.xlsx", "pedidos.xlsx"):
        shutil.copy2(RAW_DIR / name, destination / name)


def replace_archive_text(path: Path, member: str, old: bytes, new: bytes) -> None:
    temporary = path.with_suffix(".tmp")
    with ZipFile(path) as source, ZipFile(temporary, "w", ZIP_DEFLATED) as target:
        for item in source.infolist():
            content = source.read(item.filename)
            if item.filename == member:
                content = content.replace(old, new)
            target.writestr(item, content)
    temporary.replace(path)


class ExcelIngestionServiceTests(unittest.TestCase):
    def test_ingests_typed_values_and_cell_provenance(self) -> None:
        result = ExcelIngestionService(FIXED_TIME).ingest(RAW_DIR)
        product = result.records_for("product")[0]
        sale = result.records_for("sale_line")[0]
        self.assertEqual(product.values["unit_cost_cop"], Decimal("12000.00"))
        self.assertIs(product.values["active"], True)
        self.assertEqual(sale.values["sale_date"], date(2026, 6, 19))
        location = sale.location_for("product_id")
        self.assertEqual(location.sheet, "ventas")
        self.assertEqual(location.row, 2)
        self.assertEqual(location.cell_reference, "E2")
        self.assertEqual(location.raw_value, "PRD-0001")

    def test_repeated_ingestion_is_deterministic_and_does_not_modify_raw(self) -> None:
        first = ExcelIngestionService(FIXED_TIME).ingest(RAW_DIR)
        second = ExcelIngestionService(FIXED_TIME).ingest(RAW_DIR)
        self.assertTrue(first.raw_files_unchanged)
        self.assertEqual(first.source_hashes_before, first.source_hashes_after)
        self.assertEqual(first.to_dict(), second.to_dict())

    def test_missing_required_header_fails_only_the_affected_sheet(self) -> None:
        with TemporaryDirectory() as directory:
            raw_dir = Path(directory)
            copy_raw(raw_dir)
            replace_archive_text(
                raw_dir / "ventas.xlsx",
                "xl/worksheets/sheet1.xml",
                b">channel<",
                b">channel_removed<",
            )
            result = ExcelIngestionService(FIXED_TIME).ingest(raw_dir)
        codes = {item.code for item in result.findings}
        self.assertIn("missing_required_header", codes)
        self.assertEqual(len(result.records_for("sale_line")), 0)
        self.assertEqual(len(result.records_for("product")), 12)
        self.assertEqual(result.status, "failed")

    def test_missing_workbook_returns_structured_error(self) -> None:
        with TemporaryDirectory() as directory:
            raw_dir = Path(directory)
            copy_raw(raw_dir)
            (raw_dir / "pedidos.xlsx").unlink()
            result = ExcelIngestionService(FIXED_TIME).ingest(raw_dir)
        finding = next(
            item for item in result.findings if item.code == "missing_source_file"
        )
        self.assertEqual(finding.severity, "error")
        self.assertEqual(finding.expected_value, "pedidos.xlsx")
        self.assertEqual(result.status, "failed")


if __name__ == "__main__":
    unittest.main()
