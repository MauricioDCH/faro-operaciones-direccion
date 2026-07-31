"""Immutable application settings loaded from environment variables."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


def _parse_bool(value: str) -> bool:
    normalized = value.strip().casefold()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Invalid boolean value: {value!r}")


@dataclass(frozen=True, slots=True)
class Settings:
    """Paths and PDF/OCR controls required by the current vertical slice."""

    data_dir: Path = Path("data")
    config_path: Path = Path("config/app.example.yaml")
    pdf_extraction_mode: str = "auto"
    ocr_enabled: bool = True
    ocr_command: str = "tesseract"
    ocr_language: str = "spa"
    ocr_render_dpi: int = 300
    ocr_min_confidence: float = 0.75
    pdf_native_text_min_characters: int = 40
    pdf_native_text_min_words: int = 5
    pdf_max_pages: int = 3

    @classmethod
    def from_environment(cls) -> "Settings":
        settings = cls(
            data_dir=Path(os.getenv("FARO_DATA_DIR", "data")),
            config_path=Path(
                os.getenv("FARO_CONFIG_PATH", "config/app.example.yaml")
            ),
            pdf_extraction_mode=os.getenv("PDF_EXTRACTION_MODE", "auto"),
            ocr_enabled=_parse_bool(os.getenv("OCR_ENABLED", "true")),
            ocr_command=os.getenv("OCR_COMMAND", "tesseract"),
            ocr_language=os.getenv("OCR_LANGUAGE", "spa"),
            ocr_render_dpi=int(os.getenv("OCR_RENDER_DPI", "300")),
            ocr_min_confidence=float(
                os.getenv("OCR_MIN_CONFIDENCE", "0.75")
            ),
            pdf_native_text_min_characters=int(
                os.getenv("PDF_NATIVE_TEXT_MIN_CHARACTERS", "40")
            ),
            pdf_native_text_min_words=int(
                os.getenv("PDF_NATIVE_TEXT_MIN_WORDS", "5")
            ),
            pdf_max_pages=int(os.getenv("PDF_MAX_PAGES", "3")),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if self.pdf_extraction_mode not in {"auto", "native_only", "ocr_only"}:
            raise ValueError(
                "PDF_EXTRACTION_MODE must be auto, native_only, or ocr_only."
            )
        if not 72 <= self.ocr_render_dpi <= 600:
            raise ValueError("OCR_RENDER_DPI must be between 72 and 600.")
        if not 0.0 <= self.ocr_min_confidence <= 1.0:
            raise ValueError("OCR_MIN_CONFIDENCE must be between 0 and 1.")
        if self.pdf_native_text_min_characters < 1:
            raise ValueError("PDF_NATIVE_TEXT_MIN_CHARACTERS must be positive.")
        if self.pdf_native_text_min_words < 1:
            raise ValueError("PDF_NATIVE_TEXT_MIN_WORDS must be positive.")
        if not 1 <= self.pdf_max_pages <= 20:
            raise ValueError("PDF_MAX_PAGES must be between 1 and 20.")
