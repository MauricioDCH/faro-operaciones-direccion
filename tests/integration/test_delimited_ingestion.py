"""Integration tests for profiled multi-source CSV/TSV ingestion."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from faro.ingestion.delimited import (
    DelimitedIngestionService,
    DelimitedInput,
    build_profile,
)
from faro.ingestion.formats import InputFormat


class DelimitedIngestionIntegrationTests(unittest.TestCase):
    def test_mixed_csv_tsv_batch_validates_references_and_types(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            products = root / "productos.csv"
            customers = root / "clientes.tsv"
            sales = root / "ventas.csv"
            products.write_text(
                "product_id,sku,product_name,category,unit,unit_cost_cop,sale_price_cop,active\n"
                "PRD-1,SKU-1,Café,Bebidas,unit,10000,15000,true\n",
                encoding="utf-8",
            )
            customers.write_bytes(
                (
                    "customer_id\tcustomer_name\tcustomer_type\ttax_id\tcity\temail\tphone\tactive\n"
                    "CUS-1\tCliente Uno\tretail\t\tMedellín\t\t\ttrue\n"
                ).encode("utf-8-sig")
            )
            sales.write_text(
                "sale_id;sale_line_id;sale_date;customer_id;product_id;quantity;unit_price_cop;discount_cop;line_total_cop;channel\n"
                "SAL-1;SALL-1;02/08/2026;CUS-1;PRD-1;2,5;15000,00;0,00;37500,00;phone\n",
                encoding="utf-8",
            )
            inputs = (
                DelimitedInput(products, build_profile("products", InputFormat.CSV)),
                DelimitedInput(customers, build_profile("customers", InputFormat.TSV)),
                DelimitedInput(
                    sales,
                    build_profile(
                        "sales",
                        InputFormat.CSV,
                        delimiter=";",
                        decimal_separator=",",
                        date_format="%d/%m/%Y",
                    ),
                ),
            )
            batch = DelimitedIngestionService(
                ingested_at=datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)
            ).ingest(inputs, validate_references=True)

        self.assertEqual("completed", batch.status)
        self.assertEqual(3, len(batch.source_files))
        self.assertEqual(3, len(batch.accepted_records))
        self.assertTrue(batch.raw_files_unchanged)
        self.assertEqual(set(), {item.code for item in batch.findings})
        self.assertEqual(
            {"product", "customer", "sale_line"},
            {item.entity_type for item in batch.records},
        )

    def test_unknown_reference_rejects_only_affected_record(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            products = root / "productos.csv"
            customers = root / "clientes.csv"
            sales = root / "ventas.csv"
            products.write_text(
                "product_id,sku,product_name,category,unit,unit_cost_cop,sale_price_cop,active\n"
                "PRD-1,SKU-1,A,B,unit,1,2,true\n",
                encoding="utf-8",
            )
            customers.write_text(
                "customer_id,customer_name,customer_type,tax_id,city,email,phone,active\n"
                "CUS-1,Cliente,retail,,Medellín,,,true\n",
                encoding="utf-8",
            )
            sales.write_text(
                "sale_id,sale_line_id,sale_date,customer_id,product_id,quantity,unit_price_cop,discount_cop,line_total_cop,channel\n"
                "SAL-1,SALL-1,2026-08-02,CUS-1,PRD-9999,1,2,0,2,phone\n",
                encoding="utf-8",
            )
            service = DelimitedIngestionService(
                ingested_at=datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)
            )
            batch = service.ingest(
                (
                    DelimitedInput(products, build_profile("products", InputFormat.CSV)),
                    DelimitedInput(customers, build_profile("customers", InputFormat.CSV)),
                    DelimitedInput(sales, build_profile("sales", InputFormat.CSV)),
                )
            )

        self.assertIn("unknown_product", {item.code for item in batch.findings})
        self.assertEqual(2, len(batch.accepted_records))
        self.assertEqual(("SALL-1",), tuple(item.record_id for item in batch.rejected_records))


if __name__ == "__main__":
    unittest.main()
