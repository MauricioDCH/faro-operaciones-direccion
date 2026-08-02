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

    def test_phase_one_formats_are_recognized_but_planned(self) -> None:
        for path, expected in (
            ("ventas.csv", InputFormat.CSV),
            ("ventas.tsv", InputFormat.TSV),
            ("factura.xml", InputFormat.UBL_XML),
            ("factura.JPG", InputFormat.JPEG),
            ("events.ndjson", InputFormat.NDJSON),
        ):
            with self.subTest(path=path):
                capability = detect_input_format(path)
                self.assertIsNotNone(capability)
                assert capability is not None
                self.assertEqual(expected, capability.format_id)
                self.assertEqual(CapabilityStatus.PLANNED, capability.status)

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

    def test_require_implemented_format_rejects_planned_format(self) -> None:
        with self.assertRaisesRegex(NotImplementedError, "csv is planned"):
            require_implemented_format("ventas.csv")

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
