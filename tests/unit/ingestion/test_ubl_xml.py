\
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from faro.domain.documents import RecordStatus
from faro.ingestion.ubl_xml import UblFormatError, UblLimits, UblXmlIngestionService
from faro.provenance.models import sha256_file
from tests.fixtures.ubl.builders import attached_document_xml, invoice_xml, write_fixture


class UblXmlIngestionServiceTests(unittest.TestCase):
    def test_ingests_invoice_with_parties_lines_totals_and_xpath(self) -> None:
        with TemporaryDirectory() as directory:
            path = write_fixture(Path(directory) / "invoice.xml", invoice_xml())
            before = sha256_file(path)
            result = UblXmlIngestionService().ingest(path)
            self.assertEqual(before, sha256_file(path))
            self.assertEqual("completed", result.status)
            self.assertTrue(result.raw_file_unchanged)
            self.assertEqual("Invoice", result.root_document_type)
            self.assertEqual("2.1", result.ubl_version)
            self.assertEqual("Proveedor UBL SAS", result.supplier["name"])
            self.assertEqual("Cliente UBL SAS", result.customer["name"])
            self.assertEqual("DC-011", result.source_file.contract_id)
            self.assertEqual("ubl_xml", result.source_file.detected_format)
            document = result.structured_document
            self.assertIsNotNone(document)
            assert document is not None
            self.assertEqual("FV-UBL-001", document.invoice_number)
            self.assertEqual("119000.00", str(document.total_cop))
            self.assertEqual(1, len(document.lines))
            self.assertEqual(RecordStatus.ACCEPTED, document.record_status)
            self.assertTrue(
                any(
                    item.xml_xpath.endswith("/Invoice/LegalMonetaryTotal/PayableAmount")
                    and item.field == "total_cop"
                    for item in result.field_locations
                )
            )

    def test_unwraps_attached_document_description(self) -> None:
        with TemporaryDirectory() as directory:
            path = write_fixture(
                Path(directory) / "attached.xml",
                attached_document_xml(invoice_xml()),
            )
            result = UblXmlIngestionService().ingest(path)
            self.assertEqual("AttachedDocument", result.root_document_type)
            self.assertTrue(result.source_file.format_metadata["embedded"])
            self.assertTrue(
                any("embedded-document/Invoice/ID" in item.xml_xpath for item in result.field_locations)
            )

    def test_unwraps_base64_attached_document(self) -> None:
        with TemporaryDirectory() as directory:
            path = write_fixture(
                Path(directory) / "attached.xml",
                attached_document_xml(invoice_xml(), base64_embed=True),
            )
            result = UblXmlIngestionService().ingest(path)
            self.assertEqual("FV-UBL-001", result.structured_document.invoice_number)

    def test_rejects_doctype_and_entity_declarations(self) -> None:
        malicious = b'<?xml version="1.0"?><!DOCTYPE Invoice [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><Invoice>&xxe;</Invoice>'
        with TemporaryDirectory() as directory:
            path = write_fixture(Path(directory) / "invoice.xml", malicious)
            with self.assertRaisesRegex(UblFormatError, "DTD and entity"):
                UblXmlIngestionService().ingest(path)

    def test_rejects_unsupported_root_and_version(self) -> None:
        with TemporaryDirectory() as directory:
            unsupported = write_fixture(
                Path(directory) / "credit.xml",
                b'<CreditNote xmlns="urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2"/>',
            )
            with self.assertRaisesRegex(UblFormatError, "Unsupported UBL root"):
                UblXmlIngestionService().ingest(unsupported)
            version = write_fixture(
                Path(directory) / "invoice.xml", invoice_xml(version="2.0")
            )
            with self.assertRaisesRegex(UblFormatError, "Unsupported UBL version"):
                UblXmlIngestionService().ingest(version)

    def test_total_mismatch_and_missing_supplier_require_review(self) -> None:
        with TemporaryDirectory() as directory:
            path = write_fixture(
                Path(directory) / "invoice.xml",
                invoice_xml(total="118000.00", include_supplier=False),
            )
            result = UblXmlIngestionService().ingest(path)
            self.assertEqual("completed_with_findings", result.status)
            self.assertEqual(RecordStatus.PENDING_REVIEW, result.structured_document.record_status)
            codes = {item.code for item in result.findings}
            self.assertIn("document_total_mismatch", codes)
            self.assertIn("missing_supplier_party", codes)

    def test_enforces_depth_limit(self) -> None:
        payload = b'<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"><UBLVersionID>2.1</UBLVersionID><a><b><c/></b></a></Invoice>'
        with TemporaryDirectory() as directory:
            path = write_fixture(Path(directory) / "invoice.xml", payload)
            with self.assertRaisesRegex(UblFormatError, "depth"):
                UblXmlIngestionService(limits=UblLimits(max_depth=3)).ingest(path)


if __name__ == "__main__":
    unittest.main()
