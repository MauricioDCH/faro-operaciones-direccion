from __future__ import annotations

from pathlib import Path
import sqlite3
import tempfile
import unittest

from faro.indicators import OperationalIndicatorService, load_indicator_configuration


DDL = """
CREATE TABLE metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE source_file(source_file_id TEXT PRIMARY KEY,file_path TEXT,file_name TEXT,source_type TEXT,contract_id TEXT,contract_version TEXT,dataset_version TEXT,seed INTEGER,file_hash TEXT UNIQUE,ingested_at TEXT,record_status TEXT,media_type_declared TEXT,media_type_detected TEXT,detected_format TEXT,format_version TEXT,ingestion_adapter TEXT,file_size_bytes INTEGER,format_metadata_json TEXT);
CREATE TABLE source_location(source_location_id TEXT PRIMARY KEY,source_file_id TEXT,locator_type TEXT,sheet TEXT,row_number INTEGER,column_name TEXT,cell_reference TEXT,page_number INTEGER,record_number INTEGER,line_number INTEGER,json_pointer TEXT,xml_xpath TEXT,text_excerpt TEXT,raw_value TEXT,evidence_json TEXT);
CREATE TABLE product(product_id TEXT PRIMARY KEY,sku TEXT,product_name TEXT,product_name_raw TEXT,category TEXT,unit TEXT,unit_cost_cop TEXT,sale_price_cop TEXT,active INTEGER,record_status TEXT,source_file_id TEXT,source_location_id TEXT);
CREATE TABLE customer(customer_id TEXT PRIMARY KEY,customer_name TEXT,customer_type TEXT,tax_id TEXT,city TEXT,email TEXT,phone TEXT,active INTEGER,record_status TEXT,source_file_id TEXT,source_location_id TEXT);
CREATE TABLE supplier(supplier_id TEXT PRIMARY KEY,supplier_name TEXT,supplier_name_raw TEXT,tax_id TEXT,city TEXT,email TEXT,phone TEXT,active INTEGER,record_status TEXT,source_file_id TEXT,source_location_id TEXT);
CREATE TABLE sale_line(sale_line_id TEXT PRIMARY KEY,sale_id TEXT,sale_date TEXT,customer_id TEXT,product_id TEXT,quantity TEXT,unit_price_cop TEXT,discount_cop TEXT,line_total_cop TEXT,channel TEXT,record_status TEXT,source_file_id TEXT,source_location_id TEXT);
CREATE TABLE inventory_snapshot(snapshot_date TEXT,product_id TEXT,stock_on_hand TEXT,committed_quantity TEXT,available_quantity TEXT,reorder_point TEXT,record_status TEXT,source_file_id TEXT,source_location_id TEXT);
CREATE TABLE purchase_order_line(order_line_id TEXT PRIMARY KEY,order_id TEXT,order_date TEXT,supplier_id TEXT,product_id TEXT,ordered_quantity TEXT,expected_unit_cost_cop TEXT,expected_delivery_date TEXT,status TEXT,source_message_id TEXT,notes TEXT,record_status TEXT,source_file_id TEXT,source_location_id TEXT);
CREATE TABLE invoice(invoice_id TEXT PRIMARY KEY,document_id TEXT,invoice_number TEXT,supplier_name_raw TEXT,supplier_id TEXT,issue_date TEXT,related_order_id TEXT,currency TEXT,subtotal_cop TEXT,tax_cop TEXT,total_cop TEXT,record_status TEXT,source_file_id TEXT,source_location_id TEXT);
CREATE TABLE quotation(quotation_id TEXT PRIMARY KEY,document_id TEXT,quotation_number TEXT,supplier_name_raw TEXT,supplier_id TEXT,issue_date TEXT,valid_until TEXT,currency TEXT,subtotal_cop TEXT,tax_cop TEXT,total_cop TEXT,record_status TEXT,source_file_id TEXT,source_location_id TEXT);
CREATE TABLE quality_finding(finding_id TEXT PRIMARY KEY,rule_id TEXT,code TEXT,category TEXT,severity TEXT,message TEXT,source_location_id TEXT,entity_type TEXT,record_id TEXT,field TEXT,observed_value TEXT,expected_value TEXT);
"""

def build_database(path: Path) -> None:
    with sqlite3.connect(path) as c:
        c.executescript(DDL)
        c.executemany("INSERT INTO metadata(key,value) VALUES (?,?)", [
            ("schema_version", "1.0.0"), ("consolidated_at", "2026-07-31T09:00:00+00:00"),
            ("input_digest", "input"), ("logical_content_hash", "logical"),
        ])
        source = ("SRC-1", "source.xlsx", "source.xlsx", "xlsx", "DC", "1", "1", 1, "sha256:x", "2026-07-31T09:00:00+00:00", "accepted", None, None, "xlsx", "1", "xlsx", 1, "{}")
        c.execute("INSERT INTO source_file VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", source)
        for loc in ("LOC-1", "LOC-2", "LOC-3", "LOC-4"):
            c.execute("INSERT INTO source_location VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (loc,"SRC-1","spreadsheet","s",2,"c","A2",None,None,None,None,None,None,"x","[]"))
        c.execute("INSERT INTO product VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", ("P1","S1","Producto 1",None,"cat","unit","5","10",1,"accepted","SRC-1","LOC-1"))
        c.execute("INSERT INTO product VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", ("P2","S2","Producto 2",None,"cat","unit","5","10",1,"accepted","SRC-1","LOC-2"))
        c.execute("INSERT INTO customer VALUES (?,?,?,?,?,?,?,?,?,?,?)", ("C1","Cliente","retail",None,"Medellín",None,None,1,"accepted","SRC-1","LOC-1"))
        c.execute("INSERT INTO supplier VALUES (?,?,?,?,?,?,?,?,?,?,?)", ("SUP1","Proveedor",None,None,"Medellín",None,None,1,"accepted","SRC-1","LOC-1"))
        sales = [
            ("L1","S1","2026-06-10","C1","P1","1","100","0","100","store","accepted","SRC-1","LOC-1"),
            ("L2","S2","2026-07-10","C1","P1","2","100","0","200","store","accepted","SRC-1","LOC-2"),
            ("L3","S3","2026-07-11","C1","P2","1","150","0","150","store","accepted","SRC-1","LOC-3"),
        ]
        c.executemany("INSERT INTO sale_line VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", sales)
        c.execute("INSERT INTO inventory_snapshot VALUES (?,?,?,?,?,?,?,?,?)", ("2026-07-31","P1","5","0","5","10","accepted","SRC-1","LOC-1"))
        c.execute("INSERT INTO inventory_snapshot VALUES (?,?,?,?,?,?,?,?,?)", ("2026-07-31","P2","20","0","20","10","accepted","SRC-1","LOC-2"))
        c.execute("INSERT INTO purchase_order_line VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", ("OL1","O1","2026-07-20","SUP1","P1","10","5","2026-08-01","open",None,None,"accepted","SRC-1","LOC-3"))
        c.execute("INSERT INTO quality_finding VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", ("F1","R1","order_invoice_mismatch","quality","error","mismatch","LOC-4","invoice","I1",None,"1","2"))
        c.execute("INSERT INTO quality_finding VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", ("F2","R2","low_inventory","quality","warning","low","LOC-1","inventory","P1",None,"5","10"))


class OperationalIndicatorServiceTests(unittest.TestCase):
    def test_calculates_configured_formulas_and_persists_results(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "faro.db"
            build_database(database)
            config = load_indicator_configuration(Path("config/indicators.yaml"))
            run = OperationalIndicatorService().calculate(database_path=database, configuration=config)
            by_id = {}
            for result in run.results:
                by_id.setdefault(result.indicator_id, []).append(result)
            self.assertEqual(by_id["sales_total"][0].numeric_value, 350)
            self.assertEqual(by_id["sales_change"][0].numeric_value, 250)
            self.assertEqual(by_id["top_products"][0].dimension_value, "P1")
            self.assertEqual(len(by_id["low_inventory"]), 1)
            with sqlite3.connect(database) as c:
                self.assertEqual(c.execute("SELECT COUNT(*) FROM indicator_run").fetchone()[0], 1)
                self.assertEqual(c.execute("SELECT COUNT(*) FROM indicator_result").fetchone()[0], len(run.results))

    def test_preset_changes_the_result_set(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "faro.db"
            build_database(database)
            config = load_indicator_configuration(Path("config/indicators.yaml"))
            run = OperationalIndicatorService().calculate(database_path=database, configuration=config, preset_id="inventory_control", persist=False)
            self.assertNotIn("sales_total", {item.indicator_id for item in run.results})
            self.assertIn("low_inventory", {item.indicator_id for item in run.results})
