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


if __name__ == "__main__":
    unittest.main()
