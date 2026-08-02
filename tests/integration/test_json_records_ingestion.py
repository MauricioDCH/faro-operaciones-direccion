"""Integration tests for mixed JSON and NDJSON operational ingestion."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from faro.ingestion.formats import InputFormat
from faro.ingestion.json_records import (
    JsonIngestionService,
    JsonInput,
    build_json_profile,
)


class JsonRecordsIntegrationTests(unittest.TestCase):
    def test_mixed_json_ndjson_batch_validates_references_and_provenance(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            products = root / "products.json"
            customers = root / "customers.ndjson"
            sales = root / "sales.json"
            products.write_text(
                json.dumps(
                    {
                        "schema_version": "1.0.0",
                        "profile_id": "products",
                        "records": [
                            {
                                "product_id": "PRD-1",
                                "sku": "SKU-1",
                                "product_name": "Café",
                                "category": "Bebidas",
                                "unit": "unit",
                                "unit_cost_cop": 10000,
                                "sale_price_cop": 15000,
                                "active": True,
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            customers.write_text(
                json.dumps(
                    {
                        "_schema_version": "1.0.0",
                        "_profile_id": "customers",
                        "customer_id": "CUS-1",
                        "customer_name": "Cliente Uno",
                        "customer_type": "retail",
                        "tax_id": None,
                        "city": "Medellín",
                        "email": None,
                        "phone": None,
                        "active": True,
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            sales.write_text(
                json.dumps(
                    [
                        {
                            "sale_id": "SAL-1",
                            "sale_line_id": "SALL-1",
                            "sale_date": "2026-08-02",
                            "customer_id": "CUS-1",
                            "product_id": "PRD-1",
                            "quantity": 2,
                            "unit_price_cop": 15000,
                            "discount_cop": 0,
                            "line_total_cop": 30000,
                            "channel": "phone",
                        }
                    ]
                ),
                encoding="utf-8",
            )
            service = JsonIngestionService(
                ingested_at=datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)
            )
            batch = service.ingest(
                (
                    JsonInput(products, build_json_profile("products", InputFormat.JSON)),
                    JsonInput(customers, build_json_profile("customers", InputFormat.NDJSON)),
                    JsonInput(sales, build_json_profile("sales", InputFormat.JSON)),
                )
            )

        self.assertEqual("completed", batch.status)
        self.assertEqual(3, len(batch.accepted_records))
        self.assertTrue(batch.raw_files_unchanged)
        self.assertEqual(set(), {item.code for item in batch.findings})
        self.assertEqual(
            {"product", "customer", "sale_line"},
            {item.entity_type for item in batch.records},
        )
        for record in batch.records:
            self.assertTrue(record.field_locations)
            self.assertTrue(
                all(location.json_pointer.startswith("/") for location in record.field_locations)
            )

    def test_unknown_reference_rejects_only_affected_json_record(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            products = root / "products.json"
            customers = root / "customers.json"
            sales = root / "sales.ndjson"
            products.write_text(
                json.dumps(
                    {
                        "product_id": "PRD-1",
                        "sku": "SKU-1",
                        "product_name": "A",
                        "category": "B",
                        "unit": "unit",
                        "unit_cost_cop": 1,
                        "sale_price_cop": 2,
                        "active": True,
                    }
                ),
                encoding="utf-8",
            )
            customers.write_text(
                json.dumps(
                    {
                        "customer_id": "CUS-1",
                        "customer_name": "Cliente",
                        "customer_type": "retail",
                        "tax_id": None,
                        "city": "Medellín",
                        "email": None,
                        "phone": None,
                        "active": True,
                    }
                ),
                encoding="utf-8",
            )
            sales.write_text(
                json.dumps(
                    {
                        "sale_id": "SAL-1",
                        "sale_line_id": "SALL-1",
                        "sale_date": "2026-08-02",
                        "customer_id": "CUS-1",
                        "product_id": "PRD-9999",
                        "quantity": 1,
                        "unit_price_cop": 2,
                        "discount_cop": 0,
                        "line_total_cop": 2,
                        "channel": "phone",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            service = JsonIngestionService(
                ingested_at=datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)
            )
            batch = service.ingest(
                (
                    JsonInput(products, build_json_profile("products", InputFormat.JSON)),
                    JsonInput(customers, build_json_profile("customers", InputFormat.JSON)),
                    JsonInput(sales, build_json_profile("sales", InputFormat.NDJSON)),
                )
            )

        self.assertIn("unknown_product", {item.code for item in batch.findings})
        self.assertEqual(2, len(batch.accepted_records))
        self.assertEqual(("SALL-1",), tuple(item.record_id for item in batch.rejected_records))


if __name__ == "__main__":
    unittest.main()
