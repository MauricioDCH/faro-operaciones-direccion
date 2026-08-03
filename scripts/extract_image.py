
"""Extract one supported document image as JSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from faro.extraction.image import ImageInspectionError, ImageInspector
from faro.extraction.ocr import TesseractOcrEngine
from faro.ingestion.image_document import ImageDocumentIngestionService
from faro.settings import Settings


def main() -> int:
    parser = argparse.ArgumentParser(
        description="OCR a JPG, PNG, TIFF, or WebP document image."
    )
    parser.add_argument("image", type=Path)
    arguments = parser.parse_args()
    settings = Settings.from_environment()
    inspector = ImageInspector(
        max_file_size_mb=settings.image_max_file_size_mb,
        max_width=settings.image_max_width,
        max_height=settings.image_max_height,
        max_pixels=settings.image_max_pixels,
        min_width=settings.image_min_width,
        min_height=settings.image_min_height,
    )
    service = ImageDocumentIngestionService(
        ocr_engine=TesseractOcrEngine(
            command=settings.ocr_command,
            language=settings.ocr_language,
        ),
        ocr_enabled=settings.ocr_enabled,
        min_ocr_confidence=settings.ocr_min_confidence,
        inspector=inspector,
    )
    try:
        result = service.extract(arguments.image)
    except (ImageInspectionError, ValueError) as exc:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "error_code": getattr(exc, "code", "invalid_image_source"),
                    "message": str(exc),
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 2
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    return 0 if result.record_status.value != "rejected" else 1


if __name__ == "__main__":
    sys.exit(main())
