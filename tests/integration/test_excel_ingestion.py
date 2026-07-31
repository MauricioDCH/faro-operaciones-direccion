from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import unittest

from faro.ingestion import ExcelIngestionService


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "data" / "raw"


class ExcelIngestionIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = ExcelIngestionService(
            datetime(2026, 7, 31, 21, 0, tzinfo=timezone.utc)
        ).ingest(RAW_DIR)

    def test_all_approved_workbooks_and_rows_are_ingested(self) -> None:
        self.assertEqual(len(self.result.source_files), 4)
        self.assertEqual(len(self.result.records), 86)
        self.assertEqual(len(self.result.records_for("product")), 12)
        self.assertEqual(len(self.result.records_for("customer")), 6)
        self.assertEqual(len(self.result.records_for("supplier")), 4)
        self.assertEqual(len(self.result.records_for("sale_line")), 47)
        self.assertEqual(len(self.result.records_for("inventory_snapshot")), 12)
        self.assertEqual(len(self.result.records_for("purchase_order_line")), 5)
        self.assertTrue(self.result.raw_files_unchanged)
        self.assertEqual(self.result.status, "completed_with_findings")

    def test_seeded_excel_anomalies_are_detected(self) -> None:
        codes = {item.code for item in self.result.findings}
        self.assertTrue(
            {
                "duplicate_sale_line",
                "missing_required_field",
                "invalid_date",
                "negative_quantity",
                "unknown_product",
                "low_inventory",
            }.issubset(codes)
        )
        self.assertEqual(len(self.result.rejected_records), 5)

    def test_every_record_has_row_and_field_provenance(self) -> None:
        for record in self.result.records:
            self.assertTrue(record.source_location_id.startswith("LOC-"))
            self.assertTrue(record.field_locations)
            self.assertTrue(
                all(location.cell_reference for location in record.field_locations)
            )
            self.assertTrue(
                all(
                    location.source_file_id == record.source_file_id
                    for location in record.field_locations
                )
            )


if __name__ == "__main__":
    unittest.main()
