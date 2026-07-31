from __future__ import annotations

import unittest

from faro.domain.documents import DocumentType
from faro.extraction.classifier import DocumentClassifier


class DocumentClassifierTests(unittest.TestCase):
    def setUp(self) -> None:
        self.classifier = DocumentClassifier()

    def test_classifies_invoice(self) -> None:
        result = self.classifier.classify("FACTURA DE VENTA Numero de factura FV-1001")
        self.assertEqual(result.document_type, DocumentType.INVOICE)
        self.assertGreaterEqual(result.confidence, 0.8)

    def test_classifies_quotation_without_accent(self) -> None:
        result = self.classifier.classify("COTIZACION Numero de cotizacion COT-41")
        self.assertEqual(result.document_type, DocumentType.QUOTATION)

    def test_rejects_unknown_document(self) -> None:
        result = self.classifier.classify("Informe interno de actividades")
        self.assertEqual(result.document_type, DocumentType.UNSUPPORTED)
        self.assertEqual(result.confidence, 0.0)


if __name__ == "__main__":
    unittest.main()
