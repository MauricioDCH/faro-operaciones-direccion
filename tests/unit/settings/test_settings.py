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
                "IMAGE_MAX_FILE_SIZE_MB": "12",
                "IMAGE_MAX_WIDTH": "8000",
                "IMAGE_MAX_HEIGHT": "9000",
                "IMAGE_MAX_PIXELS": "25000000",
                "IMAGE_MIN_WIDTH": "80",
                "IMAGE_MIN_HEIGHT": "90",
            },
            clear=True,
        ):
            settings = Settings.from_environment()
        self.assertFalse(settings.ocr_enabled)
        self.assertEqual(settings.ocr_render_dpi, 250)
        self.assertEqual(settings.ocr_min_confidence, 0.80)
        self.assertEqual(settings.image_max_file_size_mb, 12)
        self.assertEqual(settings.image_max_width, 8000)
        self.assertEqual(settings.image_max_height, 9000)
        self.assertEqual(settings.image_max_pixels, 25000000)
        self.assertEqual(settings.image_min_width, 80)
        self.assertEqual(settings.image_min_height, 90)

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

    def test_rejects_invalid_image_limit(self) -> None:
        with patch.dict(
            "os.environ", {"IMAGE_MIN_WIDTH": "100", "IMAGE_MAX_WIDTH": "50"}, clear=True
        ):
            with self.assertRaisesRegex(ValueError, "IMAGE_MIN_WIDTH"):
                Settings.from_environment()

    def test_rejects_invalid_json_limit(self) -> None:
        with patch.dict("os.environ", {"JSON_MAX_DEPTH": "0"}, clear=True):
            with self.assertRaisesRegex(ValueError, "JSON_MAX_DEPTH"):
                Settings.from_environment()


    def test_loads_ubl_limits(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "UBL_MAX_FILE_SIZE_MB": "30",
                "UBL_MAX_ELEMENTS": "60000",
                "UBL_MAX_DEPTH": "40",
                "UBL_MAX_TEXT_CHARACTERS": "7000000",
            },
            clear=True,
        ):
            settings = Settings.from_environment()
        self.assertEqual(30, settings.ubl_max_file_size_mb)
        self.assertEqual(60000, settings.ubl_max_elements)
        self.assertEqual(40, settings.ubl_max_depth)
        self.assertEqual(7000000, settings.ubl_max_text_characters)

    def test_loads_operational_store_environment(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "FARO_DATABASE_PATH": "custom/store.db",
                "FARO_CONSOLIDATION_TIMESTAMP": "2026-08-02T12:00:00-05:00",
            },
            clear=True,
        ):
            settings = Settings.from_environment()
        self.assertEqual(str(settings.database_path), "custom/store.db")
        self.assertEqual(
            settings.consolidation_timestamp, "2026-08-02T12:00:00-05:00"
        )

    def test_loads_indicator_config_path(self) -> None:
        with patch.dict(
            "os.environ",
            {"FARO_INDICATOR_CONFIG_PATH": "config/company-indicators.yaml"},
            clear=True,
        ):
            settings = Settings.from_environment()
        self.assertEqual(str(settings.indicator_config_path), "config/company-indicators.yaml")

    def test_loads_alert_config_path(self) -> None:
        with patch.dict(
            "os.environ",
            {"FARO_ALERT_CONFIG_PATH": "config/company-alerts.yaml"},
            clear=True,
        ):
            settings = Settings.from_environment()
        self.assertEqual(str(settings.alert_config_path), "config/company-alerts.yaml")

    def test_rejects_invalid_consolidation_timestamp(self) -> None:
        with patch.dict(
            "os.environ",
            {"FARO_CONSOLIDATION_TIMESTAMP": "not-a-date"},
            clear=True,
        ):
            with self.assertRaisesRegex(ValueError, "ISO 8601"):
                Settings.from_environment()

if __name__ == "__main__":
    unittest.main()
