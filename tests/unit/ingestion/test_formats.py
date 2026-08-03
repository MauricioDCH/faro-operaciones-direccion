"""Tests for the central input-format capability registry."""

from __future__ import annotations

from pathlib import PureWindowsPath
import unittest

from faro.ingestion.formats import (
    CapabilityStatus,
    InputFormat,
    all_capabilities,
    capability_for,
    detect_input_format,
    require_implemented_format,
)


class FormatRegistryTests(unittest.TestCase):
    def test_current_formats_are_implemented(self) -> None:
        self.assertEqual(
            CapabilityStatus.IMPLEMENTED,
            capability_for(InputFormat.XLSX).status,
        )
        self.assertEqual(
            CapabilityStatus.IMPLEMENTED,
            capability_for(InputFormat.PDF).status,
        )

    def test_csv_and_tsv_are_implemented(self) -> None:
        for path, expected in (
            ("ventas.csv", InputFormat.CSV),
            ("ventas.tsv", InputFormat.TSV),
        ):
            with self.subTest(path=path):
                capability = detect_input_format(path)
                self.assertIsNotNone(capability)
                assert capability is not None
                self.assertEqual(expected, capability.format_id)
                self.assertEqual(CapabilityStatus.IMPLEMENTED, capability.status)

    def test_json_and_ndjson_are_implemented(self) -> None:
        for path, expected in (
            ("records.json", InputFormat.JSON),
            ("events.ndjson", InputFormat.NDJSON),
            ("events.jsonl", InputFormat.NDJSON),
        ):
            with self.subTest(path=path):
                capability = detect_input_format(path)
                self.assertIsNotNone(capability)
                assert capability is not None
                self.assertEqual(expected, capability.format_id)
                self.assertEqual(CapabilityStatus.IMPLEMENTED, capability.status)

    def test_image_formats_are_implemented(self) -> None:
        for path, expected in (
            ("factura.JPG", InputFormat.JPEG),
            ("factura.png", InputFormat.PNG),
            ("factura.tiff", InputFormat.TIFF),
            ("factura.webp", InputFormat.WEBP),
        ):
            with self.subTest(path=path):
                capability = detect_input_format(path)
                self.assertIsNotNone(capability)
                assert capability is not None
                self.assertEqual(expected, capability.format_id)
                self.assertEqual(CapabilityStatus.IMPLEMENTED, capability.status)

    def test_phase_one_xml_is_implemented(self) -> None:
        capability = detect_input_format("factura.xml")
        self.assertIsNotNone(capability)
        assert capability is not None
        self.assertEqual(InputFormat.UBL_XML, capability.format_id)
        self.assertEqual(CapabilityStatus.IMPLEMENTED, capability.status)

    def test_windows_paths_are_detected_without_running_on_windows(self) -> None:
        capability = detect_input_format(
            PureWindowsPath(r"C:\Faro\data\raw\catalogos.xlsx")
        )
        self.assertIsNotNone(capability)
        assert capability is not None
        self.assertEqual(InputFormat.XLSX, capability.format_id)

    def test_compound_camt_suffix_wins_over_generic_xml(self) -> None:
        capability = detect_input_format("extract.camt.053.xml")
        self.assertIsNotNone(capability)
        assert capability is not None
        self.assertEqual(InputFormat.CAMT053, capability.format_id)

    def test_unknown_extension_returns_none(self) -> None:
        self.assertIsNone(detect_input_format("source.exe"))

    def test_require_implemented_format_accepts_csv_json_and_images(self) -> None:
        self.assertEqual(
            InputFormat.CSV,
            require_implemented_format("ventas.csv").format_id,
        )
        self.assertEqual(
            InputFormat.JSON,
            require_implemented_format("productos.json").format_id,
        )
        self.assertEqual(
            InputFormat.PNG,
            require_implemented_format("factura.png").format_id,
        )

    def test_require_implemented_format_accepts_ubl_xml(self) -> None:
        self.assertEqual(
            InputFormat.UBL_XML,
            require_implemented_format("factura.xml").format_id,
        )

    def test_registry_has_unique_identifiers_and_extensions(self) -> None:
        capabilities = all_capabilities()
        self.assertEqual(
            len(capabilities),
            len({item.format_id for item in capabilities}),
        )
        extensions = [
            extension
            for item in capabilities
            for extension in item.extensions
        ]
        self.assertEqual(len(extensions), len(set(extensions)))


if __name__ == "__main__":
    unittest.main()
