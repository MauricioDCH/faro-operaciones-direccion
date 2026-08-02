"""Unit tests for deterministic JSON and NDJSON ingestion."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from faro.ingestion.formats import InputFormat
from faro.ingestion.json_records import (
    JsonIngestionService,
    build_json_profile,
)


PRODUCT = {
    "product_id": "PRD-1",
    "sku": "SKU-1",
    "product_name": "Café",
    "category": "Bebidas",
    "unit": "unit",
    "unit_cost_cop": 10000,
    "sale_price_cop": 15000,
    "active": True,
}


class JsonRecordIngestionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ingested_at = datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)
        self.service = JsonIngestionService(ingested_at=self.ingested_at)

    def test_versioned_batch_preserves_json_pointer_and_types(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "products.json"
            path.write_text(
                json.dumps(
                    {
                        "schema_version": "1.0.0",
                        "profile_id": "products",
                        "records": [PRODUCT],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            before = path.read_bytes()
            batch = self.service.ingest_file(
                path, build_json_profile("products", InputFormat.JSON)
            )
            after = path.read_bytes()

        self.assertEqual("completed", batch.status)
        self.assertEqual(1, len(batch.accepted_records))
        record = batch.records[0]
        self.assertEqual(Decimal("10000"), record.values["unit_cost_cop"])
        location = record.location_for("product_id")
        self.assertEqual("/records/0/product_id", location.json_pointer)
        self.assertIsNone(location.line)
        self.assertEqual(before, after)
        self.assertTrue(batch.raw_files_unchanged)

    def test_single_object_and_array_roots_are_supported_by_explicit_profile(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            single = root / "single.json"
            array = root / "array.json"
            single.write_text(json.dumps(PRODUCT), encoding="utf-8")
            array.write_text(json.dumps([PRODUCT]), encoding="utf-8")
            profile = build_json_profile("products", InputFormat.JSON)
            first = self.service.ingest_file(single, profile)
            second = self.service.ingest_file(array, profile)

        self.assertEqual("completed", first.status)
        self.assertEqual("/product_id", first.records[0].location_for("product_id").json_pointer)
        self.assertEqual("completed", second.status)
        self.assertEqual("/0/product_id", second.records[0].location_for("product_id").json_pointer)

    def test_ndjson_localizes_invalid_line_and_continues(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "products.ndjson"
            path.write_text(
                json.dumps(PRODUCT, ensure_ascii=False)
                + "\n{not valid}\n"
                + json.dumps({**PRODUCT, "product_id": "PRD-2", "sku": "SKU-2"})
                + "\n",
                encoding="utf-8",
            )
            batch = self.service.ingest_file(
                path, build_json_profile("products", InputFormat.NDJSON)
            )

        self.assertEqual("completed_with_findings", batch.status)
        self.assertEqual(2, len(batch.accepted_records))
        self.assertIn("invalid_json", {item.code for item in batch.findings})
        self.assertEqual(1, batch.records[0].location_for("product_id").line)
        self.assertEqual(3, batch.records[1].location_for("product_id").line)

    def test_duplicate_keys_are_rejected(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "products.json"
            path.write_text(
                '{"product_id":"PRD-1","product_id":"PRD-2"}',
                encoding="utf-8",
            )
            batch = self.service.ingest_file(
                path, build_json_profile("products", InputFormat.JSON)
            )

        self.assertEqual("failed", batch.status)
        self.assertIn("duplicate_json_key", {item.code for item in batch.findings})

    def test_schema_version_mismatch_is_rejected(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "products.json"
            path.write_text(
                json.dumps(
                    {
                        "schema_version": "2.0.0",
                        "profile_id": "products",
                        "records": [PRODUCT],
                    }
                ),
                encoding="utf-8",
            )
            batch = self.service.ingest_file(
                path, build_json_profile("products", InputFormat.JSON)
            )

        self.assertEqual("failed", batch.status)
        self.assertIn("schema_version_mismatch", {item.code for item in batch.findings})

    def test_nested_operational_field_rejects_only_record(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "products.json"
            payload = {**PRODUCT, "category": {"name": "Bebidas"}}
            path.write_text(json.dumps(payload), encoding="utf-8")
            batch = self.service.ingest_file(
                path, build_json_profile("products", InputFormat.JSON)
            )

        self.assertEqual("completed_with_findings", batch.status)
        self.assertEqual(1, len(batch.rejected_records))
        self.assertIn(
            "nested_field_not_supported", {item.code for item in batch.findings}
        )

    def test_depth_limit_is_enforced_before_record_conversion(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "products.json"
            path.write_text(
                json.dumps({"a": {"b": {"c": {"d": 1}}}}),
                encoding="utf-8",
            )
            batch = JsonIngestionService(
                ingested_at=self.ingested_at, max_depth=3
            ).ingest_file(path, build_json_profile("products", InputFormat.JSON))

        self.assertEqual("failed", batch.status)
        self.assertIn(
            "json_depth_limit_exceeded", {item.code for item in batch.findings}
        )

    def test_record_limit_is_enforced(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "products.json"
            path.write_text(json.dumps([PRODUCT, PRODUCT]), encoding="utf-8")
            batch = JsonIngestionService(
                ingested_at=self.ingested_at, max_records=1
            ).ingest_file(path, build_json_profile("products", InputFormat.JSON))

        self.assertEqual("failed", batch.status)
        self.assertIn("record_limit_exceeded", {item.code for item in batch.findings})

    def test_profile_format_must_match_extension(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "products.json"
            path.write_text(json.dumps(PRODUCT), encoding="utf-8")
            batch = self.service.ingest_file(
                path, build_json_profile("products", InputFormat.NDJSON)
            )

        self.assertEqual("failed", batch.status)
        self.assertIn("format_profile_mismatch", {item.code for item in batch.findings})

    def test_missing_sources_receive_unique_finding_ids(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            profile = build_json_profile("products", InputFormat.JSON)
            from faro.ingestion.json_records import JsonInput

            batch = self.service.ingest(
                (
                    JsonInput(root / "a.json", profile),
                    JsonInput(root / "b.json", profile),
                )
            )

        self.assertEqual(2, len(batch.findings))
        self.assertEqual(2, len({item.finding_id for item in batch.findings}))

    def test_repeated_ingestion_is_deterministic_and_raw_is_immutable(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "products.jsonl"
            path.write_text(json.dumps(PRODUCT) + "\n", encoding="utf-8")
            before = path.read_bytes()
            profile = build_json_profile("products", InputFormat.NDJSON)
            first = self.service.ingest_file(path, profile)
            second = self.service.ingest_file(path, profile)
            after = path.read_bytes()

        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
