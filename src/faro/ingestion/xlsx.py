"""Small deterministic XLSX reader built on the Python standard library."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any
from zipfile import BadZipFile, ZipFile
import xml.etree.ElementTree as ET


MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


class XlsxFormatError(ValueError):
    """Raised when an XLSX package cannot be read deterministically."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True, slots=True)
class RawCell:
    reference: str
    raw_value: str | bool | None
    formula: str | None = None


@dataclass(frozen=True, slots=True)
class RawRow:
    row_number: int
    cells: dict[int, RawCell]


@dataclass(frozen=True, slots=True)
class RawSheet:
    name: str
    rows: tuple[RawRow, ...]


def column_letters(index: int) -> str:
    value = index + 1
    letters = ""
    while value:
        value, remainder = divmod(value - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def column_index(reference: str) -> int:
    letters = "".join(char for char in reference if char.isalpha()).upper()
    if not letters:
        raise XlsxFormatError("invalid_cell_reference", reference)
    value = 0
    for letter in letters:
        value = value * 26 + ord(letter) - 64
    return value - 1


def _normalized_target(target: str) -> str:
    path = PurePosixPath(target.lstrip("/"))
    if path.parts and path.parts[0] == "xl":
        return str(path)
    return str(PurePosixPath("xl") / path)


def _text_from_inline(cell: ET.Element) -> str:
    return "".join(
        node.text or "" for node in cell.iter(f"{{{MAIN_NS}}}t")
    )


class XlsxWorkbook:
    """Read workbook sheet names and raw cells without modifying the source."""

    def __init__(self, path: Path) -> None:
        self.path = path
        try:
            self._archive = ZipFile(path)
        except (BadZipFile, OSError) as exc:
            raise XlsxFormatError("invalid_xlsx", str(exc)) from exc
        self._shared_strings = self._read_shared_strings()
        self._sheet_targets = self._read_sheet_targets()

    def close(self) -> None:
        self._archive.close()

    def __enter__(self) -> "XlsxWorkbook":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    @property
    def sheet_names(self) -> tuple[str, ...]:
        return tuple(self._sheet_targets)

    def _read_shared_strings(self) -> tuple[str, ...]:
        name = "xl/sharedStrings.xml"
        if name not in self._archive.namelist():
            return ()
        root = ET.fromstring(self._archive.read(name))
        values: list[str] = []
        for item in root.findall(f"{{{MAIN_NS}}}si"):
            values.append(
                "".join(
                    node.text or ""
                    for node in item.iter(f"{{{MAIN_NS}}}t")
                )
            )
        return tuple(values)

    def _read_sheet_targets(self) -> dict[str, str]:
        required = {
            "xl/workbook.xml",
            "xl/_rels/workbook.xml.rels",
        }
        missing = required.difference(self._archive.namelist())
        if missing:
            raise XlsxFormatError(
                "missing_xlsx_part", f"Missing XLSX parts: {sorted(missing)}"
            )
        workbook = ET.fromstring(self._archive.read("xl/workbook.xml"))
        relationships = ET.fromstring(
            self._archive.read("xl/_rels/workbook.xml.rels")
        )
        rel_map = {
            item.attrib["Id"]: item.attrib["Target"]
            for item in relationships.findall(f"{{{PACKAGE_REL_NS}}}Relationship")
        }
        targets: dict[str, str] = {}
        sheets = workbook.find(f"{{{MAIN_NS}}}sheets")
        if sheets is None:
            raise XlsxFormatError("missing_sheets", "Workbook has no sheets.")
        for sheet in sheets:
            relation_id = sheet.attrib.get(f"{{{REL_NS}}}id")
            if relation_id not in rel_map:
                raise XlsxFormatError(
                    "missing_sheet_relationship",
                    f"Sheet relationship not found: {relation_id}",
                )
            targets[sheet.attrib["name"]] = _normalized_target(
                rel_map[relation_id]
            )
        return targets

    def read_sheet(self, name: str) -> RawSheet:
        target = self._sheet_targets.get(name)
        if target is None:
            raise KeyError(name)
        if target not in self._archive.namelist():
            raise XlsxFormatError(
                "missing_worksheet_part", f"Worksheet part not found: {target}"
            )
        root = ET.fromstring(self._archive.read(target))
        rows: list[RawRow] = []
        for row in root.findall(f".//{{{MAIN_NS}}}sheetData/{{{MAIN_NS}}}row"):
            row_number = int(row.attrib.get("r", len(rows) + 1))
            cells: dict[int, RawCell] = {}
            for cell in row.findall(f"{{{MAIN_NS}}}c"):
                reference = cell.attrib.get("r", "")
                index = column_index(reference)
                cell_type = cell.attrib.get("t")
                formula_node = cell.find(f"{{{MAIN_NS}}}f")
                formula = formula_node.text if formula_node is not None else None
                value_node = cell.find(f"{{{MAIN_NS}}}v")
                inline_node = cell.find(f"{{{MAIN_NS}}}is")
                value: Any = None
                if inline_node is not None:
                    value = _text_from_inline(cell)
                elif value_node is not None:
                    raw = value_node.text or ""
                    if cell_type == "s":
                        try:
                            value = self._shared_strings[int(raw)]
                        except (ValueError, IndexError) as exc:
                            raise XlsxFormatError(
                                "invalid_shared_string", reference
                            ) from exc
                    elif cell_type == "b":
                        value = raw == "1"
                    else:
                        value = raw
                cells[index] = RawCell(reference, value, formula)
            if cells:
                rows.append(RawRow(row_number, cells))
        return RawSheet(name=name, rows=tuple(rows))
