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


if __name__ == "__main__":
    unittest.main()
