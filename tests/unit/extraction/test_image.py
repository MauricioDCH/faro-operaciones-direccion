
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from faro.extraction.image import (
    ImageFormatMismatchError,
    ImageInspector,
    ImageLimitError,
)
from tests.fixtures.images.builders import write_blank_image


class ImageInspectorTests(unittest.TestCase):
    def test_detects_supported_formats_and_dimensions(self) -> None:
        suffixes = {
            "jpeg": ".jpg",
            "png": ".png",
            "tiff": ".tiff",
            "webp": ".webp",
        }
        with TemporaryDirectory() as directory:
            root = Path(directory)
            inspector = ImageInspector(min_width=1, min_height=1)
            for format_id, suffix in suffixes.items():
                with self.subTest(format_id=format_id):
                    path = write_blank_image(
                        root / f"source{suffix}", format_id
                    )
                    metadata = inspector.inspect(path)
                    self.assertEqual(metadata.format_id, format_id)
                    self.assertEqual((metadata.width, metadata.height), (32, 24))
                    self.assertEqual(metadata.frame_count, 1)

    def test_rejects_extension_content_mismatch(self) -> None:
        with TemporaryDirectory() as directory:
            path = write_blank_image(Path(directory) / "source.jpg", "png")
            with self.assertRaises(ImageFormatMismatchError):
                ImageInspector(min_width=1, min_height=1).inspect(path)

    def test_rejects_images_below_minimum_dimensions(self) -> None:
        with TemporaryDirectory() as directory:
            path = write_blank_image(Path(directory) / "source.png", "png")
            with self.assertRaises(ImageLimitError):
                ImageInspector(min_width=64, min_height=64).inspect(path)


if __name__ == "__main__":
    unittest.main()
