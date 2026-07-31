"""Dependency-free deterministic writers for Faro's XLSX and PDF fixtures."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
import re
import zipfile
from typing import Any, Mapping, Sequence
from xml.sax.saxutils import escape, quoteattr

FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)
FIXED_CORE_TIME = "2026-07-31T09:00:00Z"
XLSX_MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
XLSX_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def _column_name(index: int) -> str:
    value = index + 1
    letters: list[str] = []
    while value:
        value, remainder = divmod(value - 1, 26)
        letters.append(chr(ord("A") + remainder))
    return "".join(reversed(letters))


def _excel_serial(value: date | datetime) -> float:
    moment = value if isinstance(value, datetime) else datetime.combine(value, datetime.min.time())
    epoch = datetime(1899, 12, 30)
    delta = moment - epoch
    return delta.days + delta.seconds / 86400 + delta.microseconds / 86400000000


def _display(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def _column_width(header: str, rows: Sequence[Mapping[str, Any]]) -> int:
    maximum = len(header)
    for row in rows:
        maximum = max(maximum, len(_display(row.get(header))))
    return min(max(maximum + 2, 12), 36)


def _style_index(header: str, value: Any) -> int:
    if isinstance(value, (date, datetime)):
        return 3
    if isinstance(value, bool):
        return 6
    if isinstance(value, Decimal):
        if header.endswith("_cop"):
            return 4
        if "quantity" in header or header in {"stock_on_hand", "reorder_point"}:
            return 5
        return 2
    return 2


def _inline_string_cell(reference: str, value: str, style: int) -> str:
    preserve = ' xml:space="preserve"' if value[:1].isspace() or value[-1:].isspace() else ""
    return (
        f'<c r="{reference}" s="{style}" t="inlineStr">'
        f'<is><t{preserve}>{escape(value)}</t></is></c>'
    )


def _cell_xml(reference: str, header: str, value: Any, style_override: int | None = None) -> str:
    style = style_override if style_override is not None else _style_index(header, value)
    if value is None:
        return f'<c r="{reference}" s="{style}"/>'
    if isinstance(value, bool):
        return f'<c r="{reference}" s="{style}" t="b"><v>{1 if value else 0}</v></c>'
    if isinstance(value, (date, datetime)):
        return f'<c r="{reference}" s="{style}"><v>{_excel_serial(value):.10f}</v></c>'
    if isinstance(value, Decimal):
        return f'<c r="{reference}" s="{style}"><v>{value}</v></c>'
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f'<c r="{reference}" s="{style}"><v>{value}</v></c>'
    return _inline_string_cell(reference, str(value), style)


def _worksheet_xml(headers: Sequence[str], rows: Sequence[Mapping[str, Any]]) -> bytes:
    last_column = _column_name(len(headers) - 1)
    last_row = len(rows) + 1
    dimension = f"A1:{last_column}{last_row}"
    columns_xml = "".join(
        f'<col min="{index + 1}" max="{index + 1}" width="{_column_width(header, rows)}" customWidth="1"/>'
        for index, header in enumerate(headers)
    )

    header_cells = "".join(
        _inline_string_cell(f"{_column_name(index)}1", header, 1)
        for index, header in enumerate(headers)
    )
    row_xml = [f'<row r="1" ht="24" customHeight="1">{header_cells}</row>']
    for row_number, row in enumerate(rows, start=2):
        cells = "".join(
            _cell_xml(
                f"{_column_name(column_index)}{row_number}",
                header,
                row.get(header),
            )
            for column_index, header in enumerate(headers)
        )
        row_xml.append(f'<row r="{row_number}">{cells}</row>')

    xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<worksheet xmlns="{XLSX_MAIN_NS}">'
        f'<dimension ref="{dimension}"/>'
        '<sheetViews><sheetView workbookViewId="0">'
        '<pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>'
        '<selection pane="bottomLeft" activeCell="A2" sqref="A2"/>'
        '</sheetView></sheetViews>'
        '<sheetFormatPr defaultRowHeight="15"/>'
        f'<cols>{columns_xml}</cols>'
        f'<sheetData>{"".join(row_xml)}</sheetData>'
        f'<autoFilter ref="{dimension}"/>'
        '<pageMargins left="0.7" right="0.7" top="0.75" bottom="0.75" header="0.3" footer="0.3"/>'
        '</worksheet>'
    )
    return xml.encode("utf-8")


def _styles_xml() -> bytes:
    xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="{XLSX_MAIN_NS}">
  <numFmts count="3">
    <numFmt numFmtId="164" formatCode="yyyy-mm-dd"/>
    <numFmt numFmtId="165" formatCode="#,##0.00 &quot;COP&quot;"/>
    <numFmt numFmtId="166" formatCode="0.000"/>
  </numFmts>
  <fonts count="2">
    <font><sz val="11"/><color theme="1"/><name val="Calibri"/><family val="2"/><scheme val="minor"/></font>
    <font><b/><sz val="11"/><color rgb="FFFFFFFF"/><name val="Calibri"/><family val="2"/><scheme val="minor"/></font>
  </fonts>
  <fills count="3">
    <fill><patternFill patternType="none"/></fill>
    <fill><patternFill patternType="gray125"/></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FF1F4E78"/><bgColor indexed="64"/></patternFill></fill>
  </fills>
  <borders count="2">
    <border><left/><right/><top/><bottom/><diagonal/></border>
    <border>
      <left style="thin"><color rgb="FFD9E2F3"/></left>
      <right style="thin"><color rgb="FFD9E2F3"/></right>
      <top style="thin"><color rgb="FFD9E2F3"/></top>
      <bottom style="thin"><color rgb="FFD9E2F3"/></bottom>
      <diagonal/>
    </border>
  </borders>
  <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
  <cellXfs count="7">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
    <xf numFmtId="0" fontId="1" fillId="2" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center"/></xf>
    <xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1"/>
    <xf numFmtId="164" fontId="0" fillId="0" borderId="1" xfId="0" applyNumberFormat="1" applyBorder="1"/>
    <xf numFmtId="165" fontId="0" fillId="0" borderId="1" xfId="0" applyNumberFormat="1" applyBorder="1"/>
    <xf numFmtId="166" fontId="0" fillId="0" borderId="1" xfId="0" applyNumberFormat="1" applyBorder="1"/>
    <xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1" applyAlignment="1"><alignment horizontal="center"/></xf>
  </cellXfs>
  <cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
  <dxfs count="0"/>
  <tableStyles count="0" defaultTableStyle="TableStyleMedium2" defaultPivotStyle="PivotStyleLight16"/>
</styleSheet>'''
    return xml.encode("utf-8")


def _content_types(sheet_count: int) -> bytes:
    overrides = "".join(
        f'<Override PartName="/xl/worksheets/sheet{index}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for index in range(1, sheet_count + 1)
    )
    xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
        '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>'
        f'{overrides}</Types>'
    )
    return xml.encode("utf-8")


def _root_rels() -> bytes:
    return b'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>'''


def _workbook_xml(sheet_names: Sequence[str]) -> bytes:
    sheets = "".join(
        f'<sheet name={quoteattr(name)} sheetId="{index}" r:id="rId{index}"/>'
        for index, name in enumerate(sheet_names, start=1)
    )
    xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<workbook xmlns="{XLSX_MAIN_NS}" xmlns:r="{XLSX_REL_NS}">'
        '<fileVersion appName="Faro" lastEdited="7" lowestEdited="7" rupBuild="0"/>'
        '<workbookPr defaultThemeVersion="164011"/>'
        '<bookViews><workbookView xWindow="0" yWindow="0" windowWidth="16000" windowHeight="9000"/></bookViews>'
        f'<sheets>{sheets}</sheets>'
        '<calcPr calcId="0" calcMode="manual"/>'
        '</workbook>'
    )
    return xml.encode("utf-8")


def _workbook_rels(sheet_count: int) -> bytes:
    relationships = "".join(
        f'<Relationship Id="rId{index}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{index}.xml"/>'
        for index in range(1, sheet_count + 1)
    )
    styles_id = sheet_count + 1
    xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f'{relationships}'
        f'<Relationship Id="rId{styles_id}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
        '</Relationships>'
    )
    return xml.encode("utf-8")


def _core_properties(title: str, subject: str) -> bytes:
    xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>{escape(title)}</dc:title>
  <dc:subject>{escape(subject)}</dc:subject>
  <dc:creator>Faro Project</dc:creator>
  <cp:lastModifiedBy>Faro Project</cp:lastModifiedBy>
  <dcterms:created xsi:type="dcterms:W3CDTF">{FIXED_CORE_TIME}</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">{FIXED_CORE_TIME}</dcterms:modified>
</cp:coreProperties>'''
    return xml.encode("utf-8")


def _app_properties(sheet_names: Sequence[str]) -> bytes:
    titles = "".join(f'<vt:lpstr>{escape(name)}</vt:lpstr>' for name in sheet_names)
    xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>Faro deterministic generator</Application>
  <DocSecurity>0</DocSecurity>
  <ScaleCrop>false</ScaleCrop>
  <HeadingPairs><vt:vector size="2" baseType="variant"><vt:variant><vt:lpstr>Worksheets</vt:lpstr></vt:variant><vt:variant><vt:i4>{len(sheet_names)}</vt:i4></vt:variant></vt:vector></HeadingPairs>
  <TitlesOfParts><vt:vector size="{len(sheet_names)}" baseType="lpstr">{titles}</vt:vector></TitlesOfParts>
  <Company>Faro Project</Company>
  <LinksUpToDate>false</LinksUpToDate>
  <SharedDoc>false</SharedDoc>
  <HyperlinksChanged>false</HyperlinksChanged>
  <AppVersion>1.0</AppVersion>
</Properties>'''
    return xml.encode("utf-8")


def _zip_write(archive: zipfile.ZipFile, name: str, content: bytes) -> None:
    info = zipfile.ZipInfo(filename=name, date_time=FIXED_ZIP_TIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = 0o600 << 16
    archive.writestr(info, content)


def write_xlsx(
    path: Path,
    sheets: Sequence[tuple[str, Sequence[str], Sequence[Mapping[str, Any]]]],
    *,
    title: str,
    subject: str,
) -> None:
    """Write a polished deterministic XLSX using only OOXML and the stdlib."""

    path.parent.mkdir(parents=True, exist_ok=True)
    sheet_names = [name for name, _, _ in sheets]
    parts: list[tuple[str, bytes]] = [
        ("[Content_Types].xml", _content_types(len(sheets))),
        ("_rels/.rels", _root_rels()),
        ("docProps/app.xml", _app_properties(sheet_names)),
        ("docProps/core.xml", _core_properties(title, subject)),
        ("xl/_rels/workbook.xml.rels", _workbook_rels(len(sheets))),
        ("xl/styles.xml", _styles_xml()),
        ("xl/workbook.xml", _workbook_xml(sheet_names)),
    ]
    for index, (_, headers, rows) in enumerate(sheets, start=1):
        parts.append((f"xl/worksheets/sheet{index}.xml", _worksheet_xml(headers, rows)))

    with zipfile.ZipFile(path, "w") as archive:
        for name, content in parts:
            _zip_write(archive, name, content)


# ---------------------------------------------------------------------------
# Minimal deterministic PDF writer.
# ---------------------------------------------------------------------------


def _pdf_escape(value: str) -> bytes:
    encoded = value.encode("cp1252", errors="replace")
    encoded = encoded.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")
    encoded = encoded.replace(b"\r", b"\\r").replace(b"\n", b"\\n")
    return encoded


def _pdf_text_command(font: str, size: float, x: float, y: float, text: str) -> bytes:
    return (
        f"BT /{font} {size:g} Tf 1 0 0 1 {x:.2f} {y:.2f} Tm ".encode("ascii")
        + b"("
        + _pdf_escape(text)
        + b") Tj ET\n"
    )


def _pdf_object(number: int, body: bytes) -> bytes:
    return f"{number} 0 obj\n".encode("ascii") + body + b"\nendobj\n"


def _build_pdf(objects: Sequence[bytes], info_object: int) -> bytes:
    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for number, body in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(_pdf_object(number, body))
    xref_offset = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R /Info {info_object} 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode("ascii")
    )
    return bytes(output)


def write_invoice_pdf(path: Path, invoice: Mapping[str, Any]) -> None:
    """Write a one-page, text-extractable synthetic invoice."""

    width, height = 595.28, 841.89
    commands = bytearray()
    commands.extend(b"0.12 0.31 0.47 rg\n0 736.89 595.28 105 re f\n")
    commands.extend(b"1 1 1 rg\n")
    commands.extend(_pdf_text_command("F2", 20, 42, 794, "FARO"))
    commands.extend(_pdf_text_command("F1", 10, 42, 774, "Factura sintetica para demostracion"))
    commands.extend(_pdf_text_command("F2", 14, 470, 794, str(invoice["invoice_number"])))
    commands.extend(_pdf_text_command("F1", 9, 445, 774, f"Fecha: {invoice['issue_date'].isoformat()}"))
    commands.extend(_pdf_text_command("F1", 9, 435, 758, f"Pedido: {invoice['related_order_id']}"))

    commands.extend(b"0.1 0.1 0.1 rg\n")
    commands.extend(_pdf_text_command("F2", 10, 42, 700, "Proveedor"))
    commands.extend(_pdf_text_command("F1", 9, 42, 681, str(invoice["supplier_name_raw"])))
    commands.extend(_pdf_text_command("F1", 9, 42, 664, f"ID sintetico: {invoice['supplier_id']}"))
    commands.extend(_pdf_text_command("F1", 9, 42, 647, "Moneda: COP"))
    commands.extend(_pdf_text_command("F2", 9, 420, 700, f"Factura interna: {invoice['invoice_id']}"))
    commands.extend(_pdf_text_command("F1", 8, 320, 679, "DOCUMENTO DE DEMOSTRACION - SIN VALIDEZ TRIBUTARIA"))

    # Table header and line item.
    commands.extend(b"0.88 0.93 0.97 rg\n42 570 511.28 24 re f\n")
    commands.extend(b"0.1 0.1 0.1 rg\n")
    for x, label in [(46, "Producto"), (270, "ID"), (350, "Cant."), (402, "Precio unit."), (500, "Total")]:
        commands.extend(_pdf_text_command("F2", 8, x, 578, label))
    line = invoice["lines"][0]
    commands.extend(_pdf_text_command("F1", 8, 46, 548, str(line["product_name_raw"])))
    commands.extend(_pdf_text_command("F1", 8, 270, 548, str(line["product_id"])))
    commands.extend(_pdf_text_command("F1", 8, 365, 548, str(line["quantity"])))
    commands.extend(_pdf_text_command("F1", 8, 430, 548, f"{line['unit_price_cop']:,.2f}"))
    commands.extend(_pdf_text_command("F1", 8, 505, 548, f"{line['line_total_cop']:,.2f}"))
    commands.extend(b"0.78 0.82 0.86 RG\n42 538 m 553.28 538 l S\n")

    totals = [
        ("Subtotal", invoice["subtotal_cop"], 510),
        ("IVA 19%", invoice["tax_cop"], 492),
        ("Total", invoice["total_cop"], 474),
    ]
    for label, value, y in totals:
        commands.extend(_pdf_text_command("F2" if label == "Total" else "F1", 9, 380, y, label))
        commands.extend(_pdf_text_command("F2" if label == "Total" else "F1", 9, 465, y, f"COP {value:,.2f}"))
    commands.extend(b"0.12 0.31 0.47 RG\n380 466 m 553.28 466 l S\n")

    # Machine-readable evidence block.
    evidence_y = 125.0
    fields = [
        ("invoice_id", invoice["invoice_id"]),
        ("invoice_number", invoice["invoice_number"]),
        ("supplier_name_raw", invoice["supplier_name_raw"]),
        ("supplier_id", invoice["supplier_id"]),
        ("issue_date", invoice["issue_date"].isoformat()),
        ("related_order_id", invoice["related_order_id"]),
        ("currency", invoice["currency"]),
        ("subtotal_cop", f"{invoice['subtotal_cop']:.2f}"),
        ("tax_cop", f"{invoice['tax_cop']:.2f}"),
        ("total_cop", f"{invoice['total_cop']:.2f}"),
    ]
    commands.extend(b"0.45 0.45 0.45 rg\n")
    for key, value in fields:
        commands.extend(_pdf_text_command("F1", 5.5, 42, evidence_y, f"{key}: {value}"))
        evidence_y -= 8
    machine_line = "LINE|{}|{}|{}|{}|{:.2f}|{:.2f}".format(
        line["invoice_line_id"],
        line["product_name_raw"],
        line["product_id"],
        line["quantity"],
        line["unit_price_cop"],
        line["line_total_cop"],
    )
    commands.extend(_pdf_text_command("F1", 5.5, 42, evidence_y, machine_line))
    commands.extend(b"0.2 0.2 0.2 rg\n")
    commands.extend(_pdf_text_command("F3", 7, 42, 35, "Todos los nombres, correos e identificadores son sinteticos."))

    content = bytes(commands)
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {width:.2f} {height:.2f}] "
            "/Resources << /Font << /F1 4 0 R /F2 5 0 R /F3 6 0 R >> >> "
            "/Contents 7 0 R >>"
        ).encode("ascii"),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Oblique /Encoding /WinAnsiEncoding >>",
        b"<< /Length " + str(len(content)).encode("ascii") + b" >>\nstream\n" + content + b"endstream",
        (
            b"<< /Title (Synthetic invoice) /Author (Faro Project) "
            b"/Creator (Faro deterministic generator) "
            b"/CreationDate (D:20260731090000Z) /ModDate (D:20260731090000Z) >>"
        ),
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_build_pdf(objects, info_object=8))


_PDF_STRING_PATTERN = re.compile(rb"\(((?:\\.|[^\\)])*)\)\s*Tj")


def _pdf_unescape(value: bytes) -> str:
    output = bytearray()
    index = 0
    while index < len(value):
        byte = value[index]
        if byte != 0x5C:  # backslash
            output.append(byte)
            index += 1
            continue
        index += 1
        if index >= len(value):
            break
        escaped = value[index]
        mapping = {ord("n"): 10, ord("r"): 13, ord("t"): 9, ord("b"): 8, ord("f"): 12}
        if escaped in mapping:
            output.append(mapping[escaped])
        else:
            output.append(escaped)
        index += 1
    return output.decode("cp1252", errors="replace")


def extract_pdf_text_lines(path: Path) -> list[str]:
    """Extract literal text strings from Faro's uncompressed synthetic PDFs."""

    data = path.read_bytes()
    return [_pdf_unescape(match.group(1)) for match in _PDF_STRING_PATTERN.finditer(data)]
