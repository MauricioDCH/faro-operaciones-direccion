from __future__ import annotations

from unittest.mock import patch
import unittest

from faro.settings import Settings


class SettingsTests(unittest.TestCase):
    def test_loads_ocr_environment(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "OCR_ENABLED": "false",
                "OCR_LANGUAGE": "spa",
                "OCR_RENDER_DPI": "250",
                "OCR_MIN_CONFIDENCE": "0.80",
            },
            clear=True,
        ):
            settings = Settings.from_environment()
        self.assertFalse(settings.ocr_enabled)
        self.assertEqual(settings.ocr_render_dpi, 250)
        self.assertEqual(settings.ocr_min_confidence, 0.80)

    def test_rejects_invalid_confidence(self) -> None:
        with patch.dict("os.environ", {"OCR_MIN_CONFIDENCE": "1.5"}, clear=True):
            with self.assertRaises(ValueError):
                Settings.from_environment()

    def test_loads_delimited_limits(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "DELIMITED_MAX_FILE_SIZE_MB": "10",
                "DELIMITED_MAX_RECORDS": "500",
                "DELIMITED_MAX_COLUMNS": "20",
                "DELIMITED_MAX_FIELD_CHARACTERS": "2000",
            },
            clear=True,
        ):
            settings = Settings.from_environment()
        self.assertEqual(10, settings.delimited_max_file_size_mb)
        self.assertEqual(500, settings.delimited_max_records)
        self.assertEqual(20, settings.delimited_max_columns)
        self.assertEqual(2000, settings.delimited_max_field_characters)

    def test_rejects_invalid_delimited_limit(self) -> None:
        with patch.dict(
            "os.environ", {"DELIMITED_MAX_RECORDS": "0"}, clear=True
        ):
            with self.assertRaisesRegex(ValueError, "must be positive"):
                Settings.from_environment()

    def test_loads_json_limits(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "JSON_MAX_FILE_SIZE_MB": "12",
                "JSON_MAX_RECORDS": "700",
                "JSON_MAX_DEPTH": "15",
                "JSON_MAX_FIELDS": "80",
                "JSON_MAX_FIELD_CHARACTERS": "5000",
            },
            clear=True,
        ):
            settings = Settings.from_environment()
        self.assertEqual(12, settings.json_max_file_size_mb)
        self.assertEqual(700, settings.json_max_records)
        self.assertEqual(15, settings.json_max_depth)
        self.assertEqual(80, settings.json_max_fields)
        self.assertEqual(5000, settings.json_max_field_characters)

    def test_rejects_invalid_json_limit(self) -> None:
        with patch.dict("os.environ", {"JSON_MAX_DEPTH": "0"}, clear=True):
            with self.assertRaisesRegex(ValueError, "JSON_MAX_DEPTH"):
                Settings.from_environment()


if __name__ == "__main__":
    unittest.main()
