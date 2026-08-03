\
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from faro.ingestion.formats import CapabilityStatus, InputFormat, detect_input_format
from faro.ingestion.ubl_xml import UblXmlIngestionService
from tests.fixtures.ubl.builders import attached_document_xml, invoice_xml, write_fixture


class UblXmlIngestionIntegrationTests(unittest.TestCase):
    def test_direct_and_attached_invoice_share_canonical_values(self) -> None:
        with TemporaryDirectory() as directory:
            base = Path(directory)
            direct = write_fixture(base / "invoice.xml", invoice_xml())
            attached = write_fixture(
                base / "attached.xml", attached_document_xml(invoice_xml())
            )
            service = UblXmlIngestionService()
            direct_result = service.ingest(direct)
            attached_result = service.ingest(attached)
            self.assertEqual(
                direct_result.structured_document.invoice_number,
                attached_result.structured_document.invoice_number,
            )
            self.assertEqual(
                direct_result.structured_document.total_cop,
                attached_result.structured_document.total_cop,
            )
            self.assertTrue(direct_result.raw_file_unchanged)
            self.assertTrue(attached_result.raw_file_unchanged)

    def test_registry_exposes_xml_as_implemented(self) -> None:
        capability = detect_input_format(r"C:\\Faro\\data\\invoice.xml")
        self.assertIsNotNone(capability)
        assert capability is not None
        self.assertEqual(InputFormat.UBL_XML, capability.format_id)
        self.assertEqual(CapabilityStatus.IMPLEMENTED, capability.status)


if __name__ == "__main__":
    unittest.main()
