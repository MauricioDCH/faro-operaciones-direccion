from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import json
import shutil
import unittest

from faro.synthetic.generator import generate_dataset
from faro.synthetic.validator import validate_dataset


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class SyntheticDatasetIntegrationTests(unittest.TestCase):
    def _prepare_support_files(self, root: Path) -> None:
        for relative in (
            "config/data-quality-rules.yaml",
            "schemas/plugin-email-batch.schema.json",
        ):
            source = PROJECT_ROOT / relative
            destination = root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)

    def test_generated_dataset_matches_ground_truth(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            self._prepare_support_files(root)
            manifest = generate_dataset(root)
            report = validate_dataset(root)
            self.assertEqual(report["status"], "passed", report["errors"])
            self.assertEqual(report["summary"], {"expected": 11, "detected": 11, "matched": 11, "missing": 0, "unexpected": 0})
            self.assertEqual(manifest["counts"]["expected_anomalies"], 11)

    def test_tampered_raw_file_fails_manifest_validation(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            self._prepare_support_files(root)
            generate_dataset(root)
            sales_path = root / "data/raw/ventas.xlsx"
            sales_path.write_bytes(sales_path.read_bytes() + b"tampered")
            report = validate_dataset(root)
            self.assertEqual(report["status"], "failed")
            self.assertTrue(any("Hash mismatch" in error for error in report["errors"]))

    def test_invalid_plugin_batch_is_rejected(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            self._prepare_support_files(root)
            generate_dataset(root)
            plugin_path = root / "data/samples/plugin-email-batch.example.json"
            plugin = json.loads(plugin_path.read_text(encoding="utf-8"))
            plugin["platform"] = "unsupported-platform"
            plugin_path.write_text(json.dumps(plugin), encoding="utf-8")
            report = validate_dataset(root)
            self.assertEqual(report["status"], "failed")
            self.assertTrue(any("Plugin schema error" in error for error in report["errors"]))


if __name__ == "__main__":
    unittest.main()
