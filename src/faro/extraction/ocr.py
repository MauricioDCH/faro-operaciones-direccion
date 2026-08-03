"""OCR engine boundary and local Tesseract implementation."""

from __future__ import annotations

from csv import DictReader
from dataclasses import dataclass
from io import StringIO
from shutil import which
from subprocess import CompletedProcess, run
from typing import Callable, Protocol

from faro.extraction.errors import OcrRuntimeError
from faro.provenance.models import BoundingBox, EvidenceFragment


@dataclass(frozen=True, slots=True)
class OcrRuntimeInfo:
    engine: str
    command: str
    available: bool
    version: str | None
    languages: tuple[str, ...]
    error: str | None = None

    def supports(self, language: str) -> bool:
        return language in self.languages

    def to_dict(self) -> dict[str, object]:
        return {
            "engine": self.engine,
            "command": self.command,
            "available": self.available,
            "version": self.version,
            "languages": list(self.languages),
            "error": self.error,
        }


@dataclass(frozen=True, slots=True)
class OcrResult:
    text: str
    confidence: float | None
    evidence: tuple[EvidenceFragment, ...]
    engine: str
    engine_version: str
    language: str


class OcrEngine(Protocol):
    """Stable OCR interface used by the extraction service."""

    @property
    def runtime_info(self) -> OcrRuntimeInfo: ...

    def extract_png(self, image_bytes: bytes) -> OcrResult: ...


Runner = Callable[..., CompletedProcess[bytes]]


class TesseractOcrEngine:
    """Run Tesseract locally and parse TSV word evidence."""

    engine_name = "tesseract"

    def __init__(
        self,
        command: str = "tesseract",
        language: str = "spa",
        page_segmentation_mode: int = 6,
        runner: Runner = run,
    ) -> None:
        self.command = command
        self.language = language
        self.page_segmentation_mode = page_segmentation_mode
        self._runner = runner
        self._runtime_info: OcrRuntimeInfo | None = None

    @property
    def runtime_info(self) -> OcrRuntimeInfo:
        if self._runtime_info is None:
            self._runtime_info = self._inspect_runtime()
        return self._runtime_info

    def _inspect_runtime(self) -> OcrRuntimeInfo:
        resolved = which(self.command)
        if resolved is None:
            return OcrRuntimeInfo(
                engine=self.engine_name,
                command=self.command,
                available=False,
                version=None,
                languages=(),
                error=f"OCR command not found: {self.command}",
            )

        try:
            version_process = self._runner(
                [resolved, "--version"],
                capture_output=True,
                check=False,
            )
            language_process = self._runner(
                [resolved, "--list-langs"],
                capture_output=True,
                check=False,
            )
        except OSError as exc:
            return OcrRuntimeInfo(
                engine=self.engine_name,
                command=resolved,
                available=False,
                version=None,
                languages=(),
                error=str(exc),
            )

        version_text = version_process.stdout.decode("utf-8", errors="replace")
        if not version_text.strip():
            version_text = version_process.stderr.decode("utf-8", errors="replace")
        version_line = version_text.splitlines()[0].strip() if version_text else ""
        version = version_line.removeprefix("tesseract ") or None

        language_text = (
            language_process.stdout.decode("utf-8", errors="replace")
            or language_process.stderr.decode("utf-8", errors="replace")
        )
        languages = tuple(
            line.strip()
            for line in language_text.splitlines()
            if line.strip() and not line.lower().startswith("list of available")
        )
        available = (
            version_process.returncode == 0
            and language_process.returncode == 0
            and version is not None
        )
        error = None
        if not available:
            error = "Unable to inspect the Tesseract runtime."
        elif self.language not in languages:
            error = f"OCR language is not installed: {self.language}"
            available = False

        return OcrRuntimeInfo(
            engine=self.engine_name,
            command=resolved,
            available=available,
            version=version,
            languages=languages,
            error=error,
        )

    def extract_png(self, image_bytes: bytes) -> OcrResult:
        runtime = self.runtime_info
        if not runtime.available or runtime.version is None:
            raise OcrRuntimeError(runtime.error or "OCR runtime is unavailable.")

        process = self._runner(
            [
                runtime.command,
                "stdin",
                "stdout",
                "-l",
                self.language,
                "--psm",
                str(self.page_segmentation_mode),
                "tsv",
            ],
            input=image_bytes,
            capture_output=True,
            check=False,
        )
        if process.returncode != 0:
            stderr = process.stderr.decode("utf-8", errors="replace").strip()
            raise OcrRuntimeError(stderr or "Tesseract failed without an error message.")

        tsv = process.stdout.decode("utf-8", errors="replace")
        text, confidence, evidence = parse_tesseract_tsv(tsv)
        return OcrResult(
            text=text,
            confidence=confidence,
            evidence=evidence,
            engine=self.engine_name,
            engine_version=runtime.version,
            language=self.language,
        )


def parse_tesseract_tsv(
    tsv: str,
) -> tuple[str, float | None, tuple[EvidenceFragment, ...]]:
    """Parse Tesseract TSV into normalized text and word-level evidence."""

    reader = DictReader(StringIO(tsv), delimiter="\t")
    lines: list[list[str]] = []
    current_line_key: tuple[str, str, str, str] | None = None
    current_words: list[str] = []
    confidences: list[float] = []
    evidence: list[EvidenceFragment] = []

    for row in reader:
        text = (row.get("text") or "").strip()
        if not text:
            continue
        try:
            raw_confidence = float(row.get("conf") or "-1")
        except ValueError:
            raw_confidence = -1.0
        confidence = None
        if raw_confidence >= 0:
            confidence = min(raw_confidence / 100.0, 1.0)
            confidences.append(confidence)

        try:
            box = BoundingBox(
                x=int(row.get("left") or 0),
                y=int(row.get("top") or 0),
                width=int(row.get("width") or 0),
                height=int(row.get("height") or 0),
            )
        except ValueError:
            box = None

        line_key = (
            row.get("page_num") or "",
            row.get("block_num") or "",
            row.get("par_num") or "",
            row.get("line_num") or "",
        )
        if current_line_key is not None and line_key != current_line_key:
            lines.append(current_words)
            current_words = []
        current_line_key = line_key
        current_words.append(text)
        evidence.append(
            EvidenceFragment(
                text=text,
                confidence=confidence,
                bounding_box=box,
            )
        )

    if current_words:
        lines.append(current_words)
    average = sum(confidences) / len(confidences) if confidences else None
    return "\n".join(" ".join(words) for words in lines), average, tuple(evidence)
