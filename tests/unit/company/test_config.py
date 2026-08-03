from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

import yaml

from faro.company.config import (
    CompanyConfigError,
    load_company_configuration,
    load_company_configuration_safe,
)


class CompanyConfigurationTests(unittest.TestCase):
    def test_loads_real_yaml_and_dashboard_preferences(self) -> None:
        config = load_company_configuration(Path("config/company.yaml"))
        self.assertEqual("empresa-prueba", config.company_id)
        self.assertEqual("inventory_control", config.indicator_preset)
        self.assertTrue(config.section_enabled("actions"))
        self.assertTrue(config.section_enabled("data_update"))
        self.assertEqual(64, len(config.config_hash))
        self.assertFalse(config.fallback_active)

    def test_rejects_arbitrary_dashboard_section(self) -> None:
        payload = yaml.safe_load(Path("config/company.yaml").read_text(encoding="utf-8"))
        payload["dashboard"]["sections"].append("banking")
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "company.yaml"
            path.write_text(yaml.safe_dump(payload), encoding="utf-8")
            with self.assertRaisesRegex(CompanyConfigError, "Unsupported dashboard section"):
                load_company_configuration(path)

    def test_rejects_unknown_company_fields(self) -> None:
        payload = yaml.safe_load(Path("config/company.yaml").read_text(encoding="utf-8"))
        payload["execute_sql"] = "DROP TABLE alert"
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "company.yaml"
            path.write_text(yaml.safe_dump(payload), encoding="utf-8")
            with self.assertRaisesRegex(CompanyConfigError, "Unsupported company fields"):
                load_company_configuration(path)

    def test_invalid_config_uses_safe_fallback_without_stopping_dashboard(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "company.yaml"
            path.write_text("dashboard: [invalid", encoding="utf-8")
            config = load_company_configuration_safe(path)
        self.assertTrue(config.fallback_active)
        self.assertEqual("faro-safe-default", config.company_id)
        self.assertTrue(config.section_enabled("data_update"))


if __name__ == "__main__":
    unittest.main()
