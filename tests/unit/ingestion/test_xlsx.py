from __future__ import annotations

from pathlib import Path
import unittest

from faro.ingestion.xlsx import XlsxWorkbook, column_index, column_letters


RAW_DIR = Path(__file__).resolve().parents[3] / "data" / "raw"


class XlsxWorkbookTests(unittest.TestCase):
    def test_reads_approved_catalog_sheets(self) -> None:
        with XlsxWorkbook(RAW_DIR / "catalogos.xlsx") as workbook:
            self.assertEqual(
                workbook.sheet_names,
                ("productos", "clientes", "proveedores"),
            )
            products = workbook.read_sheet("productos")
        self.assertEqual(products.rows[0].cells[0].raw_value, "product_id")
        self.assertEqual(products.rows[1].cells[0].raw_value, "PRD-0001")
        self.assertEqual(products.rows[1].cells[7].raw_value, True)

    def test_column_references_round_trip(self) -> None:
        for index in (0, 25, 26, 51, 702):
            letters = column_letters(index)
            self.assertEqual(column_index(f"{letters}99"), index)


if __name__ == "__main__":
    unittest.main()
