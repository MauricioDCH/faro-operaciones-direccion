"""PDF inspection, native-text detection, and rendering through Poppler."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from shutil import which
from subprocess import CompletedProcess, run
from typing import Callable

from faro.extraction.errors import InvalidPdfError, PdfRuntimeError, UnsupportedPdfError


Runner = Callable[..., CompletedProcess[bytes]]


@dataclass(frozen=True, slots=True)
class NativeTextPolicy:
    """Deterministic policy for deciding whether native text is usable."""

    min_characters: int = 40
    min_words: int = 5

    def is_sufficient(self, text: str) -> bool:
        normalized = normalize_text(text)
        alphanumeric_count = sum(character.isalnum() for character in normalized)
        word_count = len(re.findall(r"\b\w+\b", normalized))
        return (
            alphanumeric_count >= self.min_characters
            and word_count >= self.min_words
        )


@dataclass(frozen=True, slots=True)
class PdfMetadata:
    page_count: int
    encrypted: bool


@dataclass(frozen=True, slots=True)
class PopplerRuntimeInfo:
    pdfinfo_command: str
    pdftotext_command: str
    pdftoppm_command: str
    available: bool
    version: str | None
    error: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "engine": "poppler",
            "pdfinfo_command": self.pdfinfo_command,
            "pdftotext_command": self.pdftotext_command,
            "pdftoppm_command": self.pdftoppm_command,
            "available": self.available,
            "version": self.version,
            "error": self.error,
        }


class PopplerRuntime:
    """Inspect the external Poppler commands used by the PDF boundary."""

    def __init__(
        self,
        *,
        pdfinfo_command: str = "pdfinfo",
        pdftotext_command: str = "pdftotext",
        pdftoppm_command: str = "pdftoppm",
        runner: Runner = run,
    ) -> None:
        self.pdfinfo_command = pdfinfo_command
        self.pdftotext_command = pdftotext_command
        self.pdftoppm_command = pdftoppm_command
        self._runner = runner
        self._runtime_info: PopplerRuntimeInfo | None = None

    @property
    def runtime_info(self) -> PopplerRuntimeInfo:
        if self._runtime_info is None:
            self._runtime_info = self._inspect()
        return self._runtime_info

    def _inspect(self) -> PopplerRuntimeInfo:
        resolved = {
            "pdfinfo": which(self.pdfinfo_command),
            "pdftotext": which(self.pdftotext_command),
            "pdftoppm": which(self.pdftoppm_command),
        }
        missing = [name for name, path in resolved.items() if path is None]
        if missing:
            return PopplerRuntimeInfo(
                pdfinfo_command=self.pdfinfo_command,
                pdftotext_command=self.pdftotext_command,
                pdftoppm_command=self.pdftoppm_command,
                available=False,
                version=None,
                error=f"Missing Poppler commands: {', '.join(missing)}",
            )

        process = self._runner(
            [resolved["pdfinfo"], "-v"],
            capture_output=True,
            check=False,
        )
        version_text = (
            process.stderr.decode("utf-8", errors="replace")
            or process.stdout.decode("utf-8", errors="replace")
        )
        match = re.search(r"version\s+([^\s]+)", version_text, flags=re.IGNORECASE)
        version = match.group(1) if match else None
        return PopplerRuntimeInfo(
            pdfinfo_command=resolved["pdfinfo"] or self.pdfinfo_command,
            pdftotext_command=resolved["pdftotext"] or self.pdftotext_command,
            pdftoppm_command=resolved["pdftoppm"] or self.pdftoppm_command,
            available=process.returncode == 0 and version is not None,
            version=version,
            error=None if process.returncode == 0 else "Unable to inspect Poppler.",
        )


class PdfInspector:
    """Validate PDF constraints before page processing."""

    def __init__(
        self,
        max_pages: int = 3,
        runtime: PopplerRuntime | None = None,
        runner: Runner = run,
    ) -> None:
        self.max_pages = max_pages
        self.runtime = runtime or PopplerRuntime(runner=runner)
        self._runner = runner

    def inspect(self, path: Path) -> PdfMetadata:
        if not path.exists() or not path.is_file():
            raise InvalidPdfError(f"PDF file does not exist: {path}")
        if path.suffix.casefold() != ".pdf":
            raise InvalidPdfError(f"Expected a PDF file: {path}")

        runtime = self.runtime.runtime_info
        if not runtime.available:
            raise PdfRuntimeError(runtime.error or "Poppler runtime is unavailable.")

        process = self._runner(
            [runtime.pdfinfo_command, str(path)],
            capture_output=True,
            check=False,
        )
        if process.returncode != 0:
            error = process.stderr.decode("utf-8", errors="replace").strip()
            raise InvalidPdfError(error or f"Unable to inspect PDF: {path}")

        values = _parse_pdfinfo(process.stdout.decode("utf-8", errors="replace"))
        try:
            page_count = int(values["Pages"])
        except (KeyError, ValueError) as exc:
            raise InvalidPdfError("pdfinfo did not report a valid page count.") from exc
        encrypted = values.get("Encrypted", "no").casefold().startswith("yes")
        if encrypted:
            raise UnsupportedPdfError("Password-protected PDFs are unsupported.")
        if page_count < 1:
            raise InvalidPdfError("PDF contains no pages.")
        if page_count > self.max_pages:
            raise UnsupportedPdfError(
                f"PDF has {page_count} pages; the MVP limit is {self.max_pages}."
            )
        return PdfMetadata(page_count=page_count, encrypted=False)


class PdfPageReader:
    """Read native text and render pages without changing the source PDF."""

    def __init__(
        self,
        render_dpi: int = 300,
        runtime: PopplerRuntime | None = None,
        runner: Runner = run,
    ) -> None:
        self.render_dpi = render_dpi
        self.runtime = runtime or PopplerRuntime(runner=runner)
        self._runner = runner

    def native_text(self, path: Path, page_number: int) -> str:
        runtime = self._require_runtime()
        process = self._runner(
            [
                runtime.pdftotext_command,
                "-f",
                str(page_number),
                "-l",
                str(page_number),
                "-layout",
                str(path),
                "-",
            ],
            capture_output=True,
            check=False,
        )
        if process.returncode != 0:
            error = process.stderr.decode("utf-8", errors="replace").strip()
            raise PdfRuntimeError(error or "pdftotext failed.")
        return normalize_text(process.stdout.decode("utf-8", errors="replace"))

    def render_png(self, path: Path, page_number: int) -> bytes:
        from tempfile import TemporaryDirectory

        runtime = self._require_runtime()
        with TemporaryDirectory() as directory:
            output_root = Path(directory) / "page"
            process = self._runner(
                [
                    runtime.pdftoppm_command,
                    "-f",
                    str(page_number),
                    "-l",
                    str(page_number),
                    "-singlefile",
                    "-r",
                    str(self.render_dpi),
                    "-png",
                    str(path),
                    str(output_root),
                ],
                capture_output=True,
                check=False,
            )
            output_path = output_root.with_suffix(".png")
            if process.returncode != 0 or not output_path.exists():
                error = process.stderr.decode("utf-8", errors="replace").strip()
                raise PdfRuntimeError(error or "pdftoppm did not produce a PNG image.")
            image = output_path.read_bytes()
        if not image.startswith(b"\x89PNG"):
            raise PdfRuntimeError("pdftoppm output is not a PNG image.")
        return image

    def _require_runtime(self) -> PopplerRuntimeInfo:
        runtime = self.runtime.runtime_info
        if not runtime.available:
            raise PdfRuntimeError(runtime.error or "Poppler runtime is unavailable.")
        return runtime


def _parse_pdfinfo(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in text.splitlines():
        key, separator, value = line.partition(":")
        if separator:
            values[key.strip()] = value.strip()
    return values


def normalize_text(text: str) -> str:
    """Normalize PDF text while preserving human-readable line breaks."""

    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line).strip()
