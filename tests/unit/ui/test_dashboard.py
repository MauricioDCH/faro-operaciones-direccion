from __future__ import annotations

from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest

from faro.ui.dashboard import DashboardRepository


TEST_DDL = """
CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE source_file (
  source_file_id TEXT PRIMARY KEY,
  file_path TEXT NOT NULL,
  file_name TEXT NOT NULL,
  source_type TEXT NOT NULL,
  contract_id TEXT NOT NULL,
  contract_version TEXT NOT NULL,
  dataset_version TEXT NOT NULL,
  seed INTEGER,
  file_hash TEXT NOT NULL UNIQUE,
  ingested_at TEXT NOT NULL,
  record_status TEXT NOT NULL,
  media_type_declared TEXT,
  media_type_detected TEXT,
  detected_format TEXT,
  format_version TEXT,
  ingestion_adapter TEXT,
  file_size_bytes INTEGER,
  format_metadata_json TEXT NOT NULL
);
CREATE TABLE source_location (
  source_location_id TEXT PRIMARY KEY,
  source_file_id TEXT NOT NULL,
  locator_type TEXT NOT NULL,
  sheet TEXT,
  row_number INTEGER,
  column_name TEXT,
  cell_reference TEXT,
  page_number INTEGER,
  record_number INTEGER,
  line_number INTEGER,
  json_pointer TEXT,
  xml_xpath TEXT,
  text_excerpt TEXT,
  raw_value TEXT,
  evidence_json TEXT NOT NULL
);
CREATE TABLE product (
  product_id TEXT PRIMARY KEY,
  sku TEXT NOT NULL,
  product_name TEXT NOT NULL,
  product_name_raw TEXT,
  category TEXT NOT NULL,
  unit TEXT NOT NULL,
  unit_cost_cop TEXT NOT NULL,
  sale_price_cop TEXT NOT NULL,
  active INTEGER NOT NULL,
  record_status TEXT NOT NULL,
  source_file_id TEXT NOT NULL,
  source_location_id TEXT
);
CREATE TABLE customer (
  customer_id TEXT PRIMARY KEY,
  customer_name TEXT NOT NULL,
  customer_type TEXT NOT NULL,
  tax_id TEXT,
  city TEXT NOT NULL,
  email TEXT,
  phone TEXT,
  active INTEGER NOT NULL,
  record_status TEXT NOT NULL,
  source_file_id TEXT NOT NULL,
  source_location_id TEXT
);
CREATE TABLE supplier (
  supplier_id TEXT PRIMARY KEY,
  supplier_name TEXT NOT NULL,
  supplier_name_raw TEXT,
  tax_id TEXT,
  city TEXT NOT NULL,
  email TEXT,
  phone TEXT,
  active INTEGER NOT NULL,
  record_status TEXT NOT NULL,
  source_file_id TEXT NOT NULL,
  source_location_id TEXT
);
CREATE TABLE sale_line (
  sale_line_id TEXT PRIMARY KEY,
  sale_id TEXT NOT NULL,
  sale_date TEXT NOT NULL,
  customer_id TEXT NOT NULL,
  product_id TEXT NOT NULL,
  quantity TEXT NOT NULL,
  unit_price_cop TEXT NOT NULL,
  discount_cop TEXT NOT NULL,
  line_total_cop TEXT NOT NULL,
  channel TEXT NOT NULL,
  record_status TEXT NOT NULL,
  source_file_id TEXT NOT NULL,
  source_location_id TEXT
);
CREATE TABLE inventory_snapshot (
  snapshot_date TEXT NOT NULL,
  product_id TEXT NOT NULL,
  stock_on_hand TEXT NOT NULL,
  committed_quantity TEXT NOT NULL,
  available_quantity TEXT NOT NULL,
  reorder_point TEXT NOT NULL,
  record_status TEXT NOT NULL,
  source_file_id TEXT NOT NULL,
  source_location_id TEXT,
  PRIMARY KEY(snapshot_date, product_id)
);
CREATE TABLE purchase_order_line (
  order_line_id TEXT PRIMARY KEY,
  order_id TEXT NOT NULL,
  order_date TEXT NOT NULL,
  supplier_id TEXT NOT NULL,
  product_id TEXT NOT NULL,
  ordered_quantity TEXT NOT NULL,
  expected_unit_cost_cop TEXT NOT NULL,
  expected_delivery_date TEXT,
  status TEXT NOT NULL,
  source_message_id TEXT,
  notes TEXT,
  record_status TEXT NOT NULL,
  source_file_id TEXT NOT NULL,
  source_location_id TEXT
);
CREATE TABLE document (
  document_id TEXT PRIMARY KEY,
  source_file_id TEXT NOT NULL,
  document_type TEXT NOT NULL,
  page_count INTEGER NOT NULL,
  classification_method TEXT NOT NULL,
  classification_confidence REAL,
  processing_status TEXT NOT NULL,
  record_status TEXT NOT NULL,
  ubl_version TEXT,
  root_document_type TEXT,
  source_location_id TEXT
);
CREATE TABLE document_page (
  document_page_id TEXT PRIMARY KEY,
  document_id TEXT NOT NULL,
  page_number INTEGER NOT NULL,
  extraction_method TEXT NOT NULL,
  native_text_length INTEGER NOT NULL,
  render_dpi INTEGER,
  ocr_engine TEXT,
  ocr_engine_version TEXT,
  ocr_language TEXT,
  ocr_confidence REAL,
  page_text TEXT NOT NULL,
  processing_status TEXT NOT NULL,
  error_code TEXT,
  error_message TEXT,
  record_status TEXT NOT NULL,
  source_file_id TEXT NOT NULL,
  source_location_id TEXT
);
CREATE TABLE quality_finding (
  finding_id TEXT PRIMARY KEY,
  rule_id TEXT NOT NULL,
  code TEXT NOT NULL,
  category TEXT NOT NULL,
  severity TEXT NOT NULL,
  message TEXT NOT NULL,
  source_location_id TEXT,
  entity_type TEXT,
  record_id TEXT,
  field TEXT,
  observed_value TEXT,
  expected_value TEXT
);
CREATE TABLE indicator_run (
  run_id TEXT PRIMARY KEY,
  preset_id TEXT NOT NULL,
  preset_label TEXT NOT NULL,
  config_hash TEXT NOT NULL,
  database_logical_hash TEXT NOT NULL,
  as_of_date TEXT NOT NULL,
  calculated_at TEXT NOT NULL,
  result_count INTEGER NOT NULL
);
CREATE TABLE indicator_result (
  indicator_result_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  preset_id TEXT NOT NULL,
  indicator_id TEXT NOT NULL,
  indicator_name TEXT NOT NULL,
  period_start TEXT,
  period_end TEXT,
  dimension TEXT,
  dimension_value TEXT,
  numeric_value TEXT,
  unit TEXT NOT NULL,
  formula_version TEXT NOT NULL,
  source_record_ids_json TEXT NOT NULL,
  source_location_ids_json TEXT NOT NULL,
  details_json TEXT NOT NULL
);
CREATE TABLE alert_run (
  run_id TEXT PRIMARY KEY,
  preset_id TEXT NOT NULL,
  preset_label TEXT NOT NULL,
  alert_config_hash TEXT NOT NULL,
  indicator_run_id TEXT NOT NULL,
  indicator_preset_id TEXT NOT NULL,
  database_logical_hash TEXT NOT NULL,
  as_of_date TEXT NOT NULL,
  evaluated_at TEXT NOT NULL,
  evaluation_count INTEGER NOT NULL,
  alert_count INTEGER NOT NULL
);
CREATE TABLE alert_evaluation (
  evaluation_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  preset_id TEXT NOT NULL,
  rule_id TEXT NOT NULL,
  rule_name TEXT NOT NULL,
  source_type TEXT NOT NULL,
  source_id TEXT NOT NULL,
  aggregation TEXT NOT NULL,
  status TEXT NOT NULL,
  observed_value TEXT,
  operator TEXT NOT NULL,
  threshold_value TEXT NOT NULL,
  unit TEXT NOT NULL,
  severity TEXT NOT NULL,
  period_start TEXT,
  period_end TEXT,
  dimension TEXT,
  dimension_value TEXT,
  indicator_result_ids_json TEXT NOT NULL,
  finding_ids_json TEXT NOT NULL,
  source_record_ids_json TEXT NOT NULL,
  source_location_ids_json TEXT NOT NULL,
  reason TEXT,
  details_json TEXT NOT NULL
);
CREATE TABLE alert (
  alert_id TEXT PRIMARY KEY,
  evaluation_id TEXT NOT NULL,
  run_id TEXT NOT NULL,
  preset_id TEXT NOT NULL,
  rule_id TEXT NOT NULL,
  alert_type TEXT NOT NULL,
  severity TEXT NOT NULL,
  title TEXT NOT NULL,
  description TEXT NOT NULL,
  observed_value TEXT NOT NULL,
  operator TEXT NOT NULL,
  threshold_value TEXT NOT NULL,
  unit TEXT NOT NULL,
  indicator_result_ids_json TEXT NOT NULL,
  finding_ids_json TEXT NOT NULL,
  related_record_ids_json TEXT NOT NULL,
  source_location_ids_json TEXT NOT NULL,
  generated_at TEXT NOT NULL,
  review_status TEXT NOT NULL,
  delivery_status TEXT NOT NULL,
  cooldown_minutes INTEGER NOT NULL
);
CREATE VIEW v_entity_counts AS
SELECT 'product' AS entity_type, COUNT(*) AS record_count FROM product
UNION ALL SELECT 'customer', COUNT(*) FROM customer
UNION ALL SELECT 'supplier', COUNT(*) FROM supplier
UNION ALL SELECT 'sale_line', COUNT(*) FROM sale_line
UNION ALL SELECT 'inventory_snapshot', COUNT(*) FROM inventory_snapshot
UNION ALL SELECT 'purchase_order_line', COUNT(*) FROM purchase_order_line
UNION ALL SELECT 'document', COUNT(*) FROM document
UNION ALL SELECT 'document_page', COUNT(*) FROM document_page;
"""


def seed_dashboard_database(path: Path) -> None:
    with closing(sqlite3.connect(path)) as connection:
        connection.executescript(TEST_DDL)
        connection.execute("INSERT INTO metadata(key, value) VALUES (?, ?)", ("consolidated_at", "2026-07-31T09:00:00+00:00"))
        connection.execute("INSERT INTO metadata(key, value) VALUES (?, ?)", ("database_logical_hash", "abc123"))
        connection.execute(
            "INSERT INTO source_file VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "SRC-001", "data/raw/ventas.xlsx", "ventas.xlsx", "xlsx", "DC-004", "1.4.2", "0.1.0", 20260731,
                "sha256:file", "2026-07-31T09:00:00+00:00", "accepted", None, None, None, None, "xlsx", 100, "{}",
            ),
        )
        connection.execute(
            "INSERT INTO source_location VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("LOC-001", "SRC-001", "sheet_row", "ventas", 2, "sale_id", "A2", None, None, None, None, None, "Venta ejemplo", None, "[]"),
        )
        connection.execute(
            "INSERT INTO product VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("PRD-001", "SKU-001", "Café molido 500 g", None, "cafe", "unidad", "10000", "12000", 1, "accepted", "SRC-001", "LOC-001"),
        )
        connection.execute(
            "INSERT INTO customer VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("CUS-001", "Tienda Demo", "retail", None, "Medellín", None, None, 1, "accepted", "SRC-001", "LOC-001"),
        )
        connection.execute(
            "INSERT INTO supplier VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("SUP-001", "Proveedor Demo", None, None, "Medellín", None, None, 1, "accepted", "SRC-001", "LOC-001"),
        )
        connection.execute(
            "INSERT INTO sale_line VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("SALL-001", "SAL-001", "2026-07-31", "CUS-001", "PRD-001", "5", "12000", "0", "60000", "store", "accepted", "SRC-001", "LOC-001"),
        )
        connection.execute(
            "INSERT INTO inventory_snapshot VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("2026-07-31", "PRD-001", "8", "0", "8", "10", "accepted", "SRC-001", "LOC-001"),
        )
        connection.execute(
            "INSERT INTO quality_finding VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("FND-001", "RULE-LOW-STOCK-001", "low_inventory", "operational", "warning", "Inventario bajo", "LOC-001", "inventory_snapshot", "2026-07-31|PRD-001", None, "8", ">=10"),
        )
        connection.execute(
            "INSERT INTO indicator_run VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("INDRUN-001", "inventory_control", "Inventory control", "cfg", "hash", "2026-07-31", "2026-07-31T09:00:00+00:00", 1),
        )
        connection.execute(
            "INSERT INTO indicator_result VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("INDRES-001", "INDRUN-001", "inventory_control", "monthly_sales_total", "Ventas totales", "2026-07-01", "2026-07-31", None, None, "60000", "COP", "1.0.0", '["SALL-001"]', '["LOC-001"]', '{"description": "venta total"}'),
        )
        connection.execute(
            "INSERT INTO alert_run VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("ALRUN-001", "inventory_control", "Inventory control", "cfg", "INDRUN-001", "retail_distribution", "hash", "2026-07-31", "2026-07-31T09:00:00+00:00", 1, 1),
        )
        connection.execute(
            "INSERT INTO alert_evaluation VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("ALEVAL-001", "ALRUN-001", "inventory_control", "low_stock", "Inventario crítico", "indicator", "inventory_below_reorder", "count", "triggered", "1", "greater_than", "0", "products", "critical", None, None, None, None, '["INDRES-001"]', '[]', '["PRD-001"]', '["LOC-001"]', 'bajo punto de reorden', '{"kind": "inventory"}'),
        )
        connection.execute(
            "INSERT INTO alert VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("ALT-001", "ALEVAL-001", "ALRUN-001", "inventory_control", "low_stock", "threshold", "critical", "Reposición requerida", "Inventario por debajo del punto de reorden.", "1", "greater_than", "0", "products", '["INDRES-001"]', '[]', '["PRD-001"]', '["LOC-001"]', '2026-07-31T09:00:00+00:00', 'pending_review', 'not_configured', 1440),
        )
        connection.commit()


class DashboardRepositoryTests(unittest.TestCase):
    def test_fetch_snapshot_returns_professional_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "faro.db"
            seed_dashboard_database(db_path)
            repository = DashboardRepository(db_path)
            snapshot = repository.fetch_snapshot()

        self.assertEqual("abc123", snapshot.logical_hash)
        self.assertEqual(4, len(snapshot.summary_cards))
        self.assertEqual("inventory_control", snapshot.indicator_preset)
        self.assertEqual("inventory_control", snapshot.alert_preset)
        self.assertEqual("Café molido 500 g", snapshot.top_products[0]["product_name"])
        self.assertEqual("Reposición requerida", snapshot.alerts[0]["title"])
        self.assertEqual("warning", snapshot.quality_summary[0]["severity"])


if __name__ == "__main__":
    unittest.main()
