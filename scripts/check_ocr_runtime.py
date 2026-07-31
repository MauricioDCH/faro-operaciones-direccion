"""Verify the local Poppler and Tesseract runtimes required by Faro."""

from __future__ import annotations

import json

from faro.extraction.ocr import TesseractOcrEngine
from faro.extraction.pdf import PopplerRuntime
from faro.settings import Settings


def main() -> None:
    settings = Settings.from_environment()
    poppler = PopplerRuntime().runtime_info
    tesseract = TesseractOcrEngine(
        command=settings.ocr_command,
        language=settings.ocr_language,
    ).runtime_info
    payload = {
        "status": "available" if poppler.available and tesseract.available else "unavailable",
        "poppler": poppler.to_dict(),
        "tesseract": tesseract.to_dict(),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if payload["status"] != "available":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
