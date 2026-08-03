from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from contextlib import closing
import tempfile
import unittest

from faro.normalization.consolidation import observation
from faro.persistence.sqlite_store import SQLiteOperationalStore
from faro.provenance.models import SourceFile, SpreadsheetSourceLocation


class SQLiteOperationalStoreTests(unittest.TestCase):
    def _source(self, root: Path) -> SourceFile:
        path = root / "products.csv"
        path.write_text("product_id\nPRD-1\n", encoding="utf-8")
        return SourceFile.from_path(
            path,
            ingested_at=datetime(2026, 7, 31, tzinfo=timezone.utc),
            source_type="csv",
            contract_id="DC-001",
            detected_format="csv",
        )

    def test_store_is_atomic_and_logically_reproducible(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._source(root)
            location = SpreadsheetSourceLocation(
                source_location_id="LOC-1",
                source_file_id=source.source_file_id,
                sheet="products",
                row=2,
                column=None,
                cell_reference=None,
                raw_value=None,
            )
            record = observation(
                entity_type="product",
                record_id="PRD-1",
                source_file=source,
                source_location_id=location.source_location_id,
                record_status="accepted",
                payload={
                    "product_id": "PRD-1",
                    "sku": "SKU-1",
                    "product_name": "Product",
                    "category": "Test",
                    "unit": "unit",
                    "unit_cost_cop": "10.00",
                    "sale_price_cop": "20.00",
                    "active": True,
                    "record_status": "accepted",
                    "source_location_id": "LOC-1",
                },
            )
            path = root / "faro.db"
            store = SQLiteOperationalStore(path)
            arguments = dict(
                source_files=(source,),
                source_locations=(location,),
                observations=(record,),
                canonical_records=(record,),
                findings=(),
                transformations=(),
                extraction_results=(),
                consolidated_at="2026-07-31T09:00:00+00:00",
                input_digest="input",
            )
            first = store.write(**arguments)
            first_bytes = path.read_bytes()
            second = store.write(**arguments)

            self.assertEqual(first["logical_content_hash"], second["logical_content_hash"])
            self.assertEqual(first_bytes, path.read_bytes())
            with closing(sqlite3.connect(path)) as connection:
                self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM product").fetchone()[0], 1)

    def test_failed_rebuild_preserves_previous_database(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._source(root)
            location = SpreadsheetSourceLocation(
                source_location_id="LOC-1",
                source_file_id=source.source_file_id,
                sheet="products",
                row=2,
                column=None,
                cell_reference=None,
                raw_value=None,
            )
            product = observation(
                entity_type="product",
                record_id="PRD-1",
                source_file=source,
                source_location_id="LOC-1",
                record_status="accepted",
                payload={
                    "product_id": "PRD-1", "sku": "SKU-1", "product_name": "Product",
                    "category": "Test", "unit": "unit", "unit_cost_cop": "10",
                    "sale_price_cop": "20", "active": True,
                },
            )
            path = root / "faro.db"
            store = SQLiteOperationalStore(path)
            store.write(
                source_files=(source,), source_locations=(location,), observations=(product,),
                canonical_records=(product,), findings=(), transformations=(), extraction_results=(),
                consolidated_at="2026-07-31T09:00:00+00:00", input_digest="ok",
            )
            before = path.read_bytes()
            broken = observation(
                entity_type="invoice_line", record_id="INVL-1", source_file=source,
                source_location_id="LOC-1", record_status="accepted",
                payload={
                    "invoice_line_id": "INVL-1", "invoice_id": "MISSING",
                    "product_name_raw": "Product", "product_id": "PRD-1", "quantity": "1",
                    "unit_price_cop": "10", "line_total_cop": "10",
                },
            )
            with self.assertRaises(sqlite3.IntegrityError):
                store.write(
                    source_files=(source,), source_locations=(location,), observations=(broken,),
                    canonical_records=(broken,), findings=(), transformations=(), extraction_results=(),
                    consolidated_at="2026-07-31T09:00:00+00:00", input_digest="broken",
                )
            self.assertEqual(path.read_bytes(), before)
