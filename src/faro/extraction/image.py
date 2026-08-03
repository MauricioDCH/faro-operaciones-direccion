
"""Deterministic inspection for supported document-image formats."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import struct


class ImageInspectionError(ValueError):
    """Base error for invalid or unsupported document images."""

    code = "invalid_image"


class ImageFormatMismatchError(ImageInspectionError):
    code = "image_format_mismatch"


class ImageLimitError(ImageInspectionError):
    code = "image_limit_exceeded"


@dataclass(frozen=True, slots=True)
class ImageMetadata:
    format_id: str
    media_type: str
    width: int
    height: int
    frame_count: int
    orientation: int
    file_size_bytes: int

    @property
    def pixel_count(self) -> int:
        return self.width * self.height

    def to_dict(self) -> dict[str, int | str]:
        return {
            "format_id": self.format_id,
            "media_type": self.media_type,
            "width": self.width,
            "height": self.height,
            "frame_count": self.frame_count,
            "orientation": self.orientation,
            "pixel_count": self.pixel_count,
            "file_size_bytes": self.file_size_bytes,
        }


class ImageInspector:
    """Inspect image headers without decoding or modifying the raw source."""

    def __init__(
        self,
        *,
        max_file_size_mb: int = 25,
        max_width: int = 12_000,
        max_height: int = 12_000,
        max_pixels: int = 40_000_000,
        min_width: int = 64,
        min_height: int = 64,
    ) -> None:
        self.max_file_size_bytes = max_file_size_mb * 1024 * 1024
        self.max_width = max_width
        self.max_height = max_height
        self.max_pixels = max_pixels
        self.min_width = min_width
        self.min_height = min_height

    def inspect(self, path: Path) -> ImageMetadata:
        resolved = path.resolve()
        if not resolved.is_file():
            raise ImageInspectionError(f"Image source does not exist: {resolved}")
        size = resolved.stat().st_size
        if size <= 0:
            raise ImageInspectionError("Image source is empty.")
        if size > self.max_file_size_bytes:
            raise ImageLimitError(
                f"Image size {size} exceeds {self.max_file_size_bytes} bytes."
            )
        data = resolved.read_bytes()
        detected = _inspect_bytes(data, size)
        expected = _expected_format(resolved.suffix)
        if expected is None:
            raise ImageInspectionError(
                f"Unsupported image extension: {resolved.suffix or '<none>'}"
            )
        if detected.format_id != expected:
            raise ImageFormatMismatchError(
                f"Extension expects {expected}, content is {detected.format_id}."
            )
        self._validate_limits(detected)
        return detected

    def _validate_limits(self, metadata: ImageMetadata) -> None:
        if metadata.frame_count != 1:
            raise ImageLimitError(
                "Only single-frame document images are supported in the MVP."
            )
        if metadata.width < self.min_width or metadata.height < self.min_height:
            raise ImageLimitError(
                f"Image dimensions {metadata.width}x{metadata.height} are below "
                f"{self.min_width}x{self.min_height}."
            )
        if metadata.width > self.max_width or metadata.height > self.max_height:
            raise ImageLimitError(
                f"Image dimensions {metadata.width}x{metadata.height} exceed "
                f"{self.max_width}x{self.max_height}."
            )
        if metadata.pixel_count > self.max_pixels:
            raise ImageLimitError(
                f"Image pixel count {metadata.pixel_count} exceeds {self.max_pixels}."
            )
        if metadata.orientation not in {1}:
            raise ImageInspectionError(
                "Images with EXIF/TIFF orientation other than 1 require review "
                "instead of implicit rotation."
            )


def _expected_format(suffix: str) -> str | None:
    return {
        ".jpg": "jpeg",
        ".jpeg": "jpeg",
        ".png": "png",
        ".tif": "tiff",
        ".tiff": "tiff",
        ".webp": "webp",
    }.get(suffix.casefold())


def _inspect_bytes(data: bytes, size: int) -> ImageMetadata:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        width, height = _png_dimensions(data)
        return ImageMetadata("png", "image/png", width, height, 1, 1, size)
    if data.startswith(b"\xff\xd8"):
        width, height, orientation = _jpeg_metadata(data)
        return ImageMetadata(
            "jpeg", "image/jpeg", width, height, 1, orientation, size
        )
    if data[:4] in {b"II*\x00", b"MM\x00*"}:
        width, height, frames, orientation = _tiff_metadata(data)
        return ImageMetadata(
            "tiff", "image/tiff", width, height, frames, orientation, size
        )
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        width, height = _webp_dimensions(data)
        return ImageMetadata("webp", "image/webp", width, height, 1, 1, size)
    raise ImageInspectionError("Image signature is not supported.")


def _png_dimensions(data: bytes) -> tuple[int, int]:
    if len(data) < 24 or data[12:16] != b"IHDR":
        raise ImageInspectionError("Invalid PNG header.")
    width, height = struct.unpack(">II", data[16:24])
    return _positive_dimensions(width, height)


_JPEG_SOF = {
    0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
    0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF,
}


def _jpeg_metadata(data: bytes) -> tuple[int, int, int]:
    index = 2
    width = height = None
    orientation = 1
    while index + 4 <= len(data):
        while index < len(data) and data[index] != 0xFF:
            index += 1
        while index < len(data) and data[index] == 0xFF:
            index += 1
        if index >= len(data):
            break
        marker = data[index]
        index += 1
        if marker in {0xD8, 0xD9}:
            continue
        if marker == 0xDA:
            break
        if index + 2 > len(data):
            break
        length = int.from_bytes(data[index:index + 2], "big")
        if length < 2 or index + length > len(data):
            raise ImageInspectionError("Invalid JPEG segment length.")
        payload = data[index + 2:index + length]
        if marker in _JPEG_SOF and len(payload) >= 5:
            height = int.from_bytes(payload[1:3], "big")
            width = int.from_bytes(payload[3:5], "big")
        elif marker == 0xE1 and payload.startswith(b"Exif\x00\x00"):
            orientation = _tiff_orientation(payload[6:])
        index += length
    if width is None or height is None:
        raise ImageInspectionError("JPEG dimensions were not found.")
    width, height = _positive_dimensions(width, height)
    return width, height, orientation


def _tiff_orientation(data: bytes) -> int:
    try:
        _, _, _, orientation = _tiff_metadata(data, count_frames=False)
        return orientation
    except ImageInspectionError:
        return 1


def _tiff_metadata(
    data: bytes,
    *,
    count_frames: bool = True,
) -> tuple[int, int, int, int]:
    if len(data) < 8:
        raise ImageInspectionError("Invalid TIFF header.")
    if data[:2] == b"II":
        endian = "little"
    elif data[:2] == b"MM":
        endian = "big"
    else:
        raise ImageInspectionError("Invalid TIFF byte order.")
    if int.from_bytes(data[2:4], endian) != 42:
        raise ImageInspectionError("Invalid TIFF magic number.")
    offset = int.from_bytes(data[4:8], endian)
    frames = 0
    first_width = first_height = None
    orientation = 1
    visited: set[int] = set()
    while offset:
        if offset in visited or offset + 2 > len(data):
            raise ImageInspectionError("Invalid TIFF IFD chain.")
        visited.add(offset)
        frames += 1
        count = int.from_bytes(data[offset:offset + 2], endian)
        entries_start = offset + 2
        if entries_start + count * 12 + 4 > len(data):
            raise ImageInspectionError("Invalid TIFF IFD length.")
        width = height = None
        for item in range(count):
            entry = entries_start + item * 12
            tag = int.from_bytes(data[entry:entry + 2], endian)
            field_type = int.from_bytes(data[entry + 2:entry + 4], endian)
            value_count = int.from_bytes(data[entry + 4:entry + 8], endian)
            value = _tiff_scalar(
                data,
                entry + 8,
                field_type,
                value_count,
                endian,
            )
            if tag == 256:
                width = value
            elif tag == 257:
                height = value
            elif tag == 274 and value:
                orientation = value
        if frames == 1:
            first_width, first_height = width, height
        next_offset_pos = entries_start + count * 12
        offset = int.from_bytes(
            data[next_offset_pos:next_offset_pos + 4], endian
        )
        if not count_frames:
            break
        if frames > 100:
            raise ImageInspectionError("TIFF contains too many frames.")
    if first_width is None or first_height is None:
        raise ImageInspectionError("TIFF dimensions were not found.")
    width, height = _positive_dimensions(first_width, first_height)
    return width, height, frames, orientation


def _tiff_scalar(
    data: bytes,
    value_pos: int,
    field_type: int,
    value_count: int,
    endian: str,
) -> int | None:
    sizes = {1: 1, 3: 2, 4: 4}
    unit = sizes.get(field_type)
    if unit is None or value_count < 1:
        return None
    total = unit * value_count
    if total <= 4:
        raw = data[value_pos:value_pos + unit]
    else:
        offset = int.from_bytes(data[value_pos:value_pos + 4], endian)
        raw = data[offset:offset + unit]
    if len(raw) != unit:
        return None
    return int.from_bytes(raw, endian)


def _webp_dimensions(data: bytes) -> tuple[int, int]:
    if len(data) < 30:
        raise ImageInspectionError("Invalid WebP header.")
    chunk = data[12:16]
    payload = data[20:]
    if chunk == b"VP8X":
        if len(payload) < 10:
            raise ImageInspectionError("Invalid VP8X header.")
        width = 1 + int.from_bytes(payload[4:7], "little")
        height = 1 + int.from_bytes(payload[7:10], "little")
        return _positive_dimensions(width, height)
    if chunk == b"VP8L":
        if len(payload) < 5 or payload[0] != 0x2F:
            raise ImageInspectionError("Invalid VP8L header.")
        b1, b2, b3, b4 = payload[1:5]
        width = 1 + b1 + ((b2 & 0x3F) << 8)
        height = 1 + (b2 >> 6) + (b3 << 2) + ((b4 & 0x0F) << 10)
        return _positive_dimensions(width, height)
    if chunk == b"VP8 ":
        frame = payload.find(b"\x9d\x01\x2a")
        if frame < 0 or frame + 7 > len(payload):
            raise ImageInspectionError("Invalid VP8 frame header.")
        width = int.from_bytes(payload[frame + 3:frame + 5], "little") & 0x3FFF
        height = int.from_bytes(payload[frame + 5:frame + 7], "little") & 0x3FFF
        return _positive_dimensions(width, height)
    raise ImageInspectionError("Unsupported WebP encoding.")


def _positive_dimensions(width: int, height: int) -> tuple[int, int]:
    if width <= 0 or height <= 0:
        raise ImageInspectionError("Image dimensions must be positive.")
    return width, height
