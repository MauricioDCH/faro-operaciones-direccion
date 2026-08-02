"""Unit tests for deterministic CSV and TSV ingestion."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from faro.ingestion.delimited import (
    DelimitedIngestionService,
    DelimitedInput,
    build_profile,
    detect_delimiter,
)
from faro.ingestion.formats import InputFormat


PRODUCT_HEADER = (
    "product_id,sku,product_name,category,unit,unit_cost_cop,"
    "sale_price_cop,active\n"
)


class DelimiterDetectionTests(unittest.TestCase):
    def test_detects_all_approved_delimiters(self) -> None:
        for delimiter in (",", ";", "\t", "|"):
            with self.subTest(delimiter=repr(delimiter)):
                text = f"field_a{delimiter}field_b\n1{delimiter}2\n"
                self.assertEqual(delimiter, detect_delimiter(text))

    def test_rejects_single_column_text_as_ambiguous(self) -> None:
        with self.assertRaisesRegex(ValueError, "declare it explicitly"):
            detect_delimiter("field\nvalue\n")


class DelimitedIngestionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ingested_at = datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)


    def test_all_approved_profiles_are_available(self) -> None:
        for profile_id in (
            "products",
            "customers",
            "suppliers",
            "sales",
            "inventory",
            "orders",
        ):
            with self.subTest(profile_id=profile_id):
                profile = build_profile(profile_id, InputFormat.CSV, delimiter=",")
                self.assertEqual(profile_id, profile.profile_id)

    def test_rejects_non_utf8_content(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "productos.csv"
            path.write_bytes(PRODUCT_HEADER.encode("ascii") + b"PRD-1,SKU-1,Caf\xe9,B,unit,1,2,true\n")
            batch = DelimitedIngestionService(
                ingested_at=self.ingested_at
            ).ingest_file(path, build_profile("products", InputFormat.CSV))

        self.assertEqual("failed", batch.status)
        self.assertIn("invalid_utf8", {item.code for item in batch.findings})

    def test_file_size_limit_is_enforced_before_parsing(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "productos.csv"
            path.write_text(PRODUCT_HEADER, encoding="utf-8")
            batch = DelimitedIngestionService(
                ingested_at=self.ingested_at,
                max_file_size_bytes=8,
            ).ingest_file(path, build_profile("products", InputFormat.CSV))

        self.assertEqual("failed", batch.status)
        self.assertIn(
            "file_size_limit_exceeded", {item.code for item in batch.findings}
        )

    def test_reads_utf8_bom_and_preserves_field_provenance(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "productos.csv"
            path.write_bytes(
                (PRODUCT_HEADER + "PRD-1,SKU-1,Café,Bebidas,unit,1000,1500,true\n")
                .encode("utf-8-sig")
            )
            batch = DelimitedIngestionService(
                ingested_at=self.ingested_at
            ).ingest_file(path, build_profile("products", InputFormat.CSV))

        self.assertEqual("completed", batch.status)
        self.assertTrue(batch.raw_files_unchanged)
        self.assertEqual(1, len(batch.accepted_records))
        record = batch.accepted_records[0]
        self.assertEqual(Decimal("1000"), record.values["unit_cost_cop"])
        self.assertEqual("Café", record.values["product_name"])
        location = record.location_for("product_name")
        self.assertEqual(1, location.record_number)
        self.assertEqual(2, location.row)
        self.assertEqual("product_name", location.column)
        source = batch.source_files[0]
        self.assertEqual("csv", source.detected_format)
        self.assertEqual("utf-8-sig", source.format_metadata["encoding"])

    def test_parses_decimal_comma_and_custom_date_format(self) -> None:
        header = (
            "sale_id;sale_line_id;sale_date;customer_id;product_id;quantity;"
            "unit_price_cop;discount_cop;line_total_cop;channel\n"
        )
        row = "SAL-1;SALL-1;02/08/2026;CUS-1;PRD-1;2,5;10000,00;0,00;25000,00;phone\n"
        with TemporaryDirectory() as directory:
            path = Path(directory) / "ventas.csv"
            path.write_text(header + row, encoding="utf-8")
            profile = build_profile(
                "sales",
                InputFormat.CSV,
                delimiter=";",
                decimal_separator=",",
                date_format="%d/%m/%Y",
            )
            batch = DelimitedIngestionService(
                ingested_at=self.ingested_at
            ).ingest_file(path, profile)

        record = batch.accepted_records[0]
        self.assertEqual(Decimal("2.5"), record.values["quantity"])
        self.assertEqual("2026-08-02", record.values["sale_date"].isoformat())
        self.assertFalse(any(item.code == "sale_line_total_mismatch" for item in batch.findings))

    def test_missing_required_header_fails_only_the_source(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "productos.csv"
            path.write_text(
                "product_id,sku,product_name\nPRD-1,SKU-1,Café\n",
                encoding="utf-8",
            )
            batch = DelimitedIngestionService(
                ingested_at=self.ingested_at
            ).ingest_file(path, build_profile("products", InputFormat.CSV))

        self.assertEqual("failed", batch.status)
        self.assertEqual(0, len(batch.records))
        self.assertIn("missing_required_header", {item.code for item in batch.findings})

    def test_malformed_row_is_rejected_with_localizable_finding(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "productos.csv"
            path.write_text(
                PRODUCT_HEADER + "PRD-1,SKU-1,Café,Bebidas,unit,1000,1500\n",
                encoding="utf-8",
            )
            batch = DelimitedIngestionService(
                ingested_at=self.ingested_at
            ).ingest_file(path, build_profile("products", InputFormat.CSV))

        self.assertEqual(1, len(batch.rejected_records))
        finding = next(item for item in batch.findings if item.code == "malformed_row_width")
        self.assertIsNotNone(finding.source_location_id)
        self.assertEqual(batch.records[0].record_id, finding.record_id)

    def test_record_limit_is_enforced(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "productos.csv"
            path.write_text(
                PRODUCT_HEADER
                + "PRD-1,SKU-1,A,B,unit,1,2,true\n"
                + "PRD-2,SKU-2,C,D,unit,1,2,true\n",
                encoding="utf-8",
            )
            batch = DelimitedIngestionService(
                ingested_at=self.ingested_at,
                max_records=1,
            ).ingest_file(path, build_profile("products", InputFormat.CSV))

        self.assertEqual("failed", batch.status)
        self.assertEqual(1, len(batch.records))
        self.assertIn("record_limit_exceeded", {item.code for item in batch.findings})

    def test_profile_format_must_match_extension(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "productos.csv"
            path.write_text(PRODUCT_HEADER, encoding="utf-8")
            batch = DelimitedIngestionService(
                ingested_at=self.ingested_at
            ).ingest_file(path, build_profile("products", InputFormat.TSV))

        self.assertEqual("failed", batch.status)
        self.assertIn("format_profile_mismatch", {item.code for item in batch.findings})

    def test_repeated_ingestion_is_deterministic_and_raw_is_immutable(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "productos.tsv"
            path.write_text(
                PRODUCT_HEADER.replace(",", "\t")
                + "PRD-1\tSKU-1\tA\tB\tunit\t1\t2\ttrue\n",
                encoding="utf-8",
            )
            before = path.read_bytes()
            service = DelimitedIngestionService(ingested_at=self.ingested_at)
            profile = build_profile("products", InputFormat.TSV)
            first = service.ingest_file(path, profile)
            second = service.ingest_file(path, profile)
            after = path.read_bytes()

        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
