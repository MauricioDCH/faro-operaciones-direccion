\
"""Synthetic UBL 2.1 fixtures for deterministic tests."""

from __future__ import annotations

import base64
from pathlib import Path
from xml.sax.saxutils import escape


INVOICE_NS = "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
ATTACHED_NS = "urn:oasis:names:specification:ubl:schema:xsd:AttachedDocument-2"
CBC_NS = "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
CAC_NS = "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"


def invoice_xml(
    *,
    version: str = "2.1",
    invoice_number: str = "FV-UBL-001",
    subtotal: str = "100000.00",
    tax: str = "19000.00",
    total: str = "119000.00",
    line_total: str = "100000.00",
    currency: str = "COP",
    issue_date: str = "2026-08-02",
    include_supplier: bool = True,
) -> bytes:
    supplier = "" if not include_supplier else f"""
  <cac:AccountingSupplierParty>
    <cac:Party>
      <cac:PartyIdentification><cbc:ID>SUP-0001</cbc:ID></cac:PartyIdentification>
      <cac:PartyName><cbc:Name>Proveedor UBL SAS</cbc:Name></cac:PartyName>
      <cac:PartyTaxScheme>
        <cbc:RegistrationName>Proveedor UBL SAS</cbc:RegistrationName>
        <cbc:CompanyID>900123456</cbc:CompanyID>
        <cac:TaxScheme><cbc:ID>01</cbc:ID><cbc:Name>IVA</cbc:Name></cac:TaxScheme>
      </cac:PartyTaxScheme>
      <cac:PartyLegalEntity><cbc:RegistrationName>Proveedor UBL SAS</cbc:RegistrationName></cac:PartyLegalEntity>
      <cac:Contact><cbc:ElectronicMail>proveedor@example.test</cbc:ElectronicMail></cac:Contact>
    </cac:Party>
  </cac:AccountingSupplierParty>"""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Invoice xmlns="{INVOICE_NS}" xmlns:cbc="{CBC_NS}" xmlns:cac="{CAC_NS}">
  <cbc:UBLVersionID>{escape(version)}</cbc:UBLVersionID>
  <cbc:CustomizationID>DIAN 2.1</cbc:CustomizationID>
  <cbc:ProfileID>DIAN 2.1: Factura Electrónica de Venta</cbc:ProfileID>
  <cbc:ID>{escape(invoice_number)}</cbc:ID>
  <cbc:IssueDate>{escape(issue_date)}</cbc:IssueDate>
  <cbc:DocumentCurrencyCode>{escape(currency)}</cbc:DocumentCurrencyCode>
  <cac:OrderReference><cbc:ID>ORD-000001</cbc:ID></cac:OrderReference>
  {supplier}
  <cac:AccountingCustomerParty>
    <cac:Party>
      <cac:PartyIdentification><cbc:ID>CUS-0001</cbc:ID></cac:PartyIdentification>
      <cac:PartyName><cbc:Name>Cliente UBL SAS</cbc:Name></cac:PartyName>
      <cac:PartyTaxScheme><cbc:CompanyID>800987654</cbc:CompanyID><cac:TaxScheme><cbc:ID>01</cbc:ID></cac:TaxScheme></cac:PartyTaxScheme>
    </cac:Party>
  </cac:AccountingCustomerParty>
  <cac:TaxTotal>
    <cbc:TaxAmount currencyID="{escape(currency)}">{escape(tax)}</cbc:TaxAmount>
    <cac:TaxSubtotal>
      <cbc:TaxableAmount currencyID="{escape(currency)}">{escape(subtotal)}</cbc:TaxableAmount>
      <cbc:TaxAmount currencyID="{escape(currency)}">{escape(tax)}</cbc:TaxAmount>
      <cac:TaxCategory><cbc:Percent>19.00</cbc:Percent><cac:TaxScheme><cbc:ID>01</cbc:ID><cbc:Name>IVA</cbc:Name></cac:TaxScheme></cac:TaxCategory>
    </cac:TaxSubtotal>
  </cac:TaxTotal>
  <cac:LegalMonetaryTotal>
    <cbc:LineExtensionAmount currencyID="{escape(currency)}">{escape(subtotal)}</cbc:LineExtensionAmount>
    <cbc:TaxExclusiveAmount currencyID="{escape(currency)}">{escape(subtotal)}</cbc:TaxExclusiveAmount>
    <cbc:TaxInclusiveAmount currencyID="{escape(currency)}">{escape(total)}</cbc:TaxInclusiveAmount>
    <cbc:PayableAmount currencyID="{escape(currency)}">{escape(total)}</cbc:PayableAmount>
  </cac:LegalMonetaryTotal>
  <cac:InvoiceLine>
    <cbc:ID>1</cbc:ID>
    <cbc:InvoicedQuantity unitCode="EA">10</cbc:InvoicedQuantity>
    <cbc:LineExtensionAmount currencyID="{escape(currency)}">{escape(line_total)}</cbc:LineExtensionAmount>
    <cac:Item>
      <cbc:Description>Café molido 500 g</cbc:Description>
      <cbc:Name>Café molido 500 g</cbc:Name>
      <cac:SellersItemIdentification><cbc:ID>PRD-0001</cbc:ID></cac:SellersItemIdentification>
    </cac:Item>
    <cac:Price><cbc:PriceAmount currencyID="{escape(currency)}">10000.00</cbc:PriceAmount></cac:Price>
  </cac:InvoiceLine>
</Invoice>
""".encode("utf-8")


def attached_document_xml(invoice: bytes, *, base64_embed: bool = False) -> bytes:
    if base64_embed:
        body = f"<cbc:EmbeddedDocumentBinaryObject mimeCode=\"application/xml\">{base64.b64encode(invoice).decode('ascii')}</cbc:EmbeddedDocumentBinaryObject>"
    else:
        body = f"<cbc:Description>{escape(invoice.decode('utf-8'))}</cbc:Description>"
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<AttachedDocument xmlns="{ATTACHED_NS}" xmlns:cbc="{CBC_NS}" xmlns:cac="{CAC_NS}">
  <cbc:UBLVersionID>2.1</cbc:UBLVersionID>
  <cbc:ID>AD-001</cbc:ID>
  <cac:Attachment><cac:ExternalReference>{body}</cac:ExternalReference></cac:Attachment>
</AttachedDocument>
""".encode("utf-8")


def write_fixture(path: Path, payload: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return path
