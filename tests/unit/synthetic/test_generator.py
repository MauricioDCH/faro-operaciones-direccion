from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from faro.synthetic.generator import DEFAULT_SEED, build_dataset, generate_dataset


class SyntheticGeneratorTests(unittest.TestCase):
    def test_default_build_contains_approved_anomaly_catalog(self) -> None:
        build = build_dataset(DEFAULT_SEED)
        anomaly_types = {item["type"] for item in build.expected_anomalies["anomalies"]}
        self.assertEqual(
            anomaly_types,
            {
                "duplicate_sale_line",
                "missing_required_field",
                "invalid_date",
                "negative_quantity",
                "unknown_product",
                "inconsistent_supplier_name",
                "low_inventory",
                "order_invoice_mismatch",
                "duplicate_invoice",
                "email_order_conflict",
                "abnormal_sales_decline",
            },
        )

    def test_same_seed_produces_byte_identical_artifacts(self) -> None:
        with TemporaryDirectory() as first_directory, TemporaryDirectory() as second_directory:
            first_root = Path(first_directory)
            second_root = Path(second_directory)
            first = generate_dataset(first_root, seed=DEFAULT_SEED)
            second = generate_dataset(second_root, seed=DEFAULT_SEED)
            self.assertEqual(first["counts"], second["counts"])
            self.assertEqual(first["files"], second["files"])
            for relative_path in first["files"]:
                first_digest = sha256((first_root / relative_path).read_bytes()).hexdigest()
                second_digest = sha256((second_root / relative_path).read_bytes()).hexdigest()
                self.assertEqual(first_digest, second_digest, relative_path)

    def test_existing_generated_run_is_reused_without_overwrite(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            first = generate_dataset(root)
            sales_before = (root / "data/raw/ventas.xlsx").read_bytes()
            second = generate_dataset(root)
            self.assertEqual(first, second)
            self.assertEqual(sales_before, (root / "data/raw/ventas.xlsx").read_bytes())

    def test_modified_generated_run_requires_explicit_force(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            generate_dataset(root)
            sales_path = root / "data/raw/ventas.xlsx"
            sales_path.write_bytes(sales_path.read_bytes() + b"modified")
            with self.assertRaises(FileExistsError):
                generate_dataset(root)
            manifest = generate_dataset(root, force=True)
            self.assertEqual(manifest["seed"], DEFAULT_SEED)

    def test_ground_truth_has_stable_ids_and_seed(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            generate_dataset(root)
            expected = json.loads(
                (root / "data/expected/expected_anomalies.json").read_text(encoding="utf-8")
            )
            self.assertEqual(expected["seed"], DEFAULT_SEED)
            self.assertEqual(
                [item["anomaly_id"] for item in expected["anomalies"]],
                [f"ANOM-{index:03d}" for index in range(1, 12)],
            )


if __name__ == "__main__":
    unittest.main()
