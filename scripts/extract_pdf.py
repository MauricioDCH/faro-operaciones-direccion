"""Extract text and page provenance from one synthetic PDF."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from faro.extraction import NativeTextPolicy, PdfExtractionService, TesseractOcrEngine
from faro.settings import Settings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Recover native text or OCR from a Faro synthetic PDF."
    )
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--disable-ocr", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = Settings.from_environment()
    extraction_mode = "native_only" if args.disable_ocr else settings.pdf_extraction_mode
    ocr_enabled = settings.ocr_enabled and extraction_mode != "native_only"
    engine = (
        TesseractOcrEngine(
            command=settings.ocr_command,
            language=settings.ocr_language,
        )
        if ocr_enabled
        else None
    )
    service = PdfExtractionService(
        ocr_engine=engine,
        ocr_enabled=ocr_enabled,
        extraction_mode=extraction_mode,
        min_ocr_confidence=settings.ocr_min_confidence,
        render_dpi=settings.ocr_render_dpi,
        max_pages=settings.pdf_max_pages,
        native_text_policy=NativeTextPolicy(
            min_characters=settings.pdf_native_text_min_characters,
            min_words=settings.pdf_native_text_min_words,
        ),
    )
    payload = service.extract(args.pdf).to_dict()
    serialized = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized + "\n", encoding="utf-8")
    else:
        print(serialized)


if __name__ == "__main__":
    main()
