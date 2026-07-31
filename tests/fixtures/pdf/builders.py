"""Build deterministic native, scanned, and mixed PDF fixtures with stdlib tools."""

from __future__ import annotations

from pathlib import Path
from subprocess import run
from tempfile import TemporaryDirectory
import zlib


PAGE_WIDTH = 595.0
PAGE_HEIGHT = 842.0


def create_native_pdf(path: Path, lines: tuple[str, ...]) -> Path:
    _write_text_pdf(path, (lines,))
    return path


def create_scanned_pdf(path: Path, lines: tuple[str, ...], dpi: int = 300) -> Path:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        native = root / "source.pdf"
        _write_text_pdf(native, (lines,))
        width, height, pixels = _render_pdf_page_to_ppm(native, 1, dpi=dpi)
        _write_image_pdf(path, width, height, pixels)
    return path


def create_mixed_pdf(
    path: Path,
    native_lines: tuple[str, ...],
    scanned_lines: tuple[str, ...],
    dpi: int = 300,
) -> Path:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        native = root / "native.pdf"
        scanned = root / "scanned.pdf"
        create_native_pdf(native, native_lines)
        create_scanned_pdf(scanned, scanned_lines, dpi=dpi)
        process = run(
            ["pdfunite", str(native), str(scanned), str(path)],
            capture_output=True,
            check=False,
        )
        if process.returncode != 0:
            raise RuntimeError(
                process.stderr.decode("utf-8", errors="replace")
                or "pdfunite failed while building a mixed fixture."
            )
    return path


def create_multi_page_pdf(path: Path, page_count: int) -> Path:
    pages = tuple((f"PAGE {index}", "Synthetic fixture content") for index in range(1, page_count + 1))
    _write_text_pdf(path, pages)
    return path


def _render_pdf_page_to_ppm(path: Path, page_number: int, dpi: int) -> tuple[int, int, bytes]:
    with TemporaryDirectory() as directory:
        output_root = Path(directory) / "page"
        process = run(
            [
                "pdftoppm",
                "-f",
                str(page_number),
                "-l",
                str(page_number),
                "-singlefile",
                "-r",
                str(dpi),
                str(path),
                str(output_root),
            ],
            capture_output=True,
            check=False,
        )
        ppm_path = output_root.with_suffix(".ppm")
        if process.returncode != 0 or not ppm_path.exists():
            raise RuntimeError(
                process.stderr.decode("utf-8", errors="replace")
                or "pdftoppm failed while building a scanned fixture."
            )
        return _parse_ppm(ppm_path.read_bytes())


def _parse_ppm(data: bytes) -> tuple[int, int, bytes]:
    if not data.startswith(b"P6"):
        raise ValueError("Expected a binary PPM image.")
    index = 2
    tokens: list[bytes] = []
    while len(tokens) < 3:
        while index < len(data) and data[index:index + 1].isspace():
            index += 1
        if data[index:index + 1] == b"#":
            while index < len(data) and data[index:index + 1] not in {b"\n", b"\r"}:
                index += 1
            continue
        start = index
        while index < len(data) and not data[index:index + 1].isspace():
            index += 1
        tokens.append(data[start:index])
    width, height, max_value = (int(token) for token in tokens)
    if max_value != 255:
        raise ValueError("Only 8-bit PPM fixtures are supported.")
    while index < len(data) and data[index:index + 1].isspace():
        index += 1
    pixels = data[index:]
    expected = width * height * 3
    if len(pixels) != expected:
        raise ValueError(f"Invalid PPM payload length: expected {expected}, got {len(pixels)}")
    return width, height, pixels


def _write_text_pdf(path: Path, pages: tuple[tuple[str, ...], ...]) -> None:
    page_count = len(pages)
    page_object_start = 3
    content_object_start = page_object_start + page_count
    font_object = content_object_start + page_count
    info_object = font_object + 1

    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        (
            f"<< /Type /Pages /Kids [{''.join(f'{page_object_start + i} 0 R ' for i in range(page_count))}] "
            f"/Count {page_count} >>"
        ).encode("ascii"),
    ]

    for index in range(page_count):
        content_object = content_object_start + index
        objects.append(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_WIDTH:g} {PAGE_HEIGHT:g}] "
                f"/Resources << /Font << /F1 {font_object} 0 R >> >> "
                f"/Contents {content_object} 0 R >>"
            ).encode("ascii")
        )

    for lines in pages:
        content = bytearray()
        y = 760.0
        for index, line in enumerate(lines):
            size = 24.0 if index == 0 else 16.0
            content.extend(_text_command(size, 60.0, y, line))
            y -= 48.0
        objects.append(
            b"<< /Length "
            + str(len(content)).encode("ascii")
            + b" >>\nstream\n"
            + bytes(content)
            + b"endstream"
        )

    objects.extend(
        [
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
            b"<< /Title (Faro synthetic PDF fixture) /Author (Faro Project) >>",
        ]
    )
    path.write_bytes(_build_pdf(objects, info_object=info_object))


def _write_image_pdf(path: Path, width: int, height: int, pixels: bytes) -> None:
    compressed = zlib.compress(pixels, level=9)
    content = f"q {PAGE_WIDTH:g} 0 0 {PAGE_HEIGHT:g} 0 0 cm /Im0 Do Q\n".encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_WIDTH:g} {PAGE_HEIGHT:g}] "
            "/Resources << /XObject << /Im0 4 0 R >> >> /Contents 5 0 R >>"
        ).encode("ascii"),
        (
            f"<< /Type /XObject /Subtype /Image /Width {width} /Height {height} "
            "/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /FlateDecode "
            f"/Length {len(compressed)} >>\nstream\n"
        ).encode("ascii")
        + compressed
        + b"\nendstream",
        b"<< /Length " + str(len(content)).encode("ascii") + b" >>\nstream\n" + content + b"endstream",
        b"<< /Title (Faro scanned PDF fixture) /Author (Faro Project) >>",
    ]
    path.write_bytes(_build_pdf(objects, info_object=6))


def _text_command(size: float, x: float, y: float, text: str) -> bytes:
    encoded = text.encode("cp1252", errors="replace")
    escaped = encoded.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")
    return (
        f"BT /F1 {size:g} Tf 1 0 0 1 {x:g} {y:g} Tm ".encode("ascii")
        + b"("
        + escaped
        + b") Tj ET\n"
    )


def _build_pdf(objects: list[bytes], info_object: int) -> bytes:
    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for number, body in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{number} 0 obj\n".encode("ascii"))
        output.extend(body)
        output.extend(b"\nendobj\n")
    xref_offset = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R /Info {info_object} 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode("ascii")
    )
    return bytes(output)
