from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from faro.ingestion.models import TabularRecord
from faro.normalization.consolidation import canonicalize, observations_from_tabular
from faro.provenance.models import SourceFile, SpreadsheetSourceLocation


class CanonicalizationTests(unittest.TestCase):
    def _source(self, root: Path, name: str, source_type: str) -> SourceFile:
        path = root / name
        path.write_text(name, encoding="utf-8")
        return SourceFile.from_path(
            path,
            ingested_at=datetime(2026, 7, 31, tzinfo=timezone.utc),
            source_type=source_type,
            contract_id="DC-001",
            detected_format=source_type,
        )

    def _record(self, source: SourceFile, name: str) -> TabularRecord:
        location = SpreadsheetSourceLocation(
            source_location_id=f"LOC-{source.source_file_id}",
            source_file_id=source.source_file_id,
            sheet="productos",
            row=2,
            column="product_name",
            cell_reference="C2",
            raw_value=name,
        )
        return TabularRecord(
            contract_id="DC-001",
            entity_type="product",
            record_id="PRD-1",
            source_file_id=source.source_file_id,
            source_location_id=location.source_location_id,
            row_number=2,
            values={
                "product_id": "PRD-1",
                "sku": "SKU-1",
                "product_name": name,
                "category": "Test",
                "unit": "unit",
                "unit_cost_cop": 10,
                "sale_price_cop": 20,
                "active": True,
            },
            raw_values={},
            field_locations=(location,),
        )

    def test_higher_priority_source_wins_and_conflict_is_traceable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            xlsx = self._source(root, "products.xlsx", "xlsx")
            csv = self._source(root, "products.csv", "csv")
            observations = observations_from_tabular(
                (xlsx, csv),
                (self._record(xlsx, "Canonical"), self._record(csv, "Other")),
            )
            result = canonicalize(
                observations,
                created_at="2026-07-31T09:00:00+00:00",
            )

        self.assertEqual(result.canonical_records[0].source_file_id, xlsx.source_file_id)
        self.assertEqual(result.findings[0].code, "cross_source_conflict")
        self.assertEqual(result.transformations[0].rule_id, "select_canonical_source_v1")

    def test_rejected_observations_do_not_enter_canonical_records(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = self._source(Path(directory), "products.xlsx", "xlsx")
            record = self._record(source, "Rejected").with_status("rejected")
            observations = observations_from_tabular((source,), (record,))
            result = canonicalize(
                observations,
                created_at="2026-07-31T09:00:00+00:00",
            )

        self.assertEqual(result.canonical_records, ())
