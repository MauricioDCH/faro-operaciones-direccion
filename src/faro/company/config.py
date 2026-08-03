"""Load company configuration safely, with a built-in client-safe fallback."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

import yaml


class CompanyConfigError(ValueError):
    """Raised when a company profile is invalid or unsafe."""


ALLOWED_BUSINESS_PROFILES = {
    "retail_distribution",
    "sales_monitoring",
    "inventory_control",
    "data_quality",
    "custom_example",
}
ALLOWED_INDICATOR_PRESETS = {
    "retail_distribution",
    "sales_monitoring",
    "inventory_control",
}
ALLOWED_ALERT_PRESETS = {
    "retail_distribution",
    "sales_monitoring",
    "inventory_control",
    "data_quality",
    "custom_example",
}
ALLOWED_DASHBOARD_SECTIONS = {
    "summary",
    "actions",
    "top_products",
    "indicators",
    "alerts",
    "quality",
    "sources",
    "data_update",
}
ALLOWED_THEMES = {"professional_dark"}


@dataclass(frozen=True, slots=True)
class DashboardPreferences:
    title: str
    theme: str
    sections: tuple[str, ...]
    show_source_evidence: bool


@dataclass(frozen=True, slots=True)
class CompanyConfiguration:
    schema_version: str
    company_id: str
    display_name: str
    business_profile: str
    locale: str
    currency: str
    timezone: str
    indicator_preset: str
    alert_preset: str
    dashboard: DashboardPreferences
    config_hash: str
    fallback_active: bool = False
    fallback_reason: str | None = None

    def section_enabled(self, section_id: str) -> bool:
        return section_id in self.dashboard.sections


def _required_short_text(payload: dict[str, Any], key: str, max_length: int = 120) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip() or len(value) > max_length:
        raise CompanyConfigError(
            f"{key} must be a non-empty string of at most {max_length} characters"
        )
    return value.strip()


def _default_payload() -> dict[str, Any]:
    return {
        "schema_version": "1.1.0",
        "status": "implemented",
        "company_id": "faro-safe-default",
        "display_name": "Mi empresa",
        "business_profile": "retail_distribution",
        "locale": "es-CO",
        "currency": "COP",
        "timezone": "America/Bogota",
        "indicator_preset": "retail_distribution",
        "alert_preset": "retail_distribution",
        "dashboard": {
            "title": "Faro · Resumen del negocio",
            "theme": "professional_dark",
            "sections": [
                "summary",
                "actions",
                "alerts",
                "indicators",
                "top_products",
                "quality",
                "sources",
                "data_update",
            ],
            "show_source_evidence": True,
        },
    }


def default_company_configuration(*, reason: str | None = None) -> CompanyConfiguration:
    return _parse_company_payload(
        _default_payload(), fallback_active=reason is not None, fallback_reason=reason
    )


def _parse_company_payload(
    payload: dict[str, Any],
    *,
    fallback_active: bool = False,
    fallback_reason: str | None = None,
) -> CompanyConfiguration:
    if not isinstance(payload, dict) or payload.get("schema_version") not in {"1.0.0", "1.1.0"}:
        raise CompanyConfigError("Company config schema_version must be 1.0.0 or 1.1.0")
    unknown = set(payload) - {
        "schema_version",
        "status",
        "company_id",
        "display_name",
        "business_profile",
        "locale",
        "currency",
        "timezone",
        "indicator_preset",
        "alert_preset",
        "dashboard",
    }
    if unknown:
        raise CompanyConfigError(f"Unsupported company fields: {sorted(unknown)}")
    company_id = _required_short_text(payload, "company_id", 80)
    display_name = _required_short_text(payload, "display_name", 120)
    business_profile = _required_short_text(payload, "business_profile", 80)
    if business_profile not in ALLOWED_BUSINESS_PROFILES:
        raise CompanyConfigError(f"Unsupported business_profile: {business_profile}")
    indicator_preset = _required_short_text(payload, "indicator_preset", 80)
    alert_preset = _required_short_text(payload, "alert_preset", 80)
    if indicator_preset not in ALLOWED_INDICATOR_PRESETS:
        raise CompanyConfigError(f"Unsupported indicator_preset: {indicator_preset}")
    if alert_preset not in ALLOWED_ALERT_PRESETS:
        raise CompanyConfigError(f"Unsupported alert_preset: {alert_preset}")
    dashboard_payload = payload.get("dashboard")
    if not isinstance(dashboard_payload, dict):
        raise CompanyConfigError("dashboard must be an object")
    dashboard_unknown = set(dashboard_payload) - {
        "title",
        "theme",
        "sections",
        "show_source_evidence",
    }
    if dashboard_unknown:
        raise CompanyConfigError(
            f"Unsupported dashboard fields: {sorted(dashboard_unknown)}"
        )
    theme = _required_short_text(dashboard_payload, "theme", 80)
    if theme not in ALLOWED_THEMES:
        raise CompanyConfigError(f"Unsupported dashboard theme: {theme}")
    raw_sections = dashboard_payload.get("sections")
    if not isinstance(raw_sections, list) or not raw_sections:
        raise CompanyConfigError("dashboard.sections must be a non-empty list")
    sections: list[str] = []
    for section in raw_sections:
        if not isinstance(section, str) or section not in ALLOWED_DASHBOARD_SECTIONS:
            raise CompanyConfigError(f"Unsupported dashboard section: {section}")
        if section in sections:
            raise CompanyConfigError(f"Duplicated dashboard section: {section}")
        sections.append(section)
    show_evidence = dashboard_payload.get("show_source_evidence", True)
    if not isinstance(show_evidence, bool):
        raise CompanyConfigError("dashboard.show_source_evidence must be boolean")
    canonical = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return CompanyConfiguration(
        schema_version=str(payload["schema_version"]),
        company_id=company_id,
        display_name=display_name,
        business_profile=business_profile,
        locale=_required_short_text(payload, "locale", 20),
        currency=_required_short_text(payload, "currency", 8),
        timezone=_required_short_text(payload, "timezone", 80),
        indicator_preset=indicator_preset,
        alert_preset=alert_preset,
        dashboard=DashboardPreferences(
            title=_required_short_text(dashboard_payload, "title", 120),
            theme=theme,
            sections=tuple(sections),
            show_source_evidence=show_evidence,
        ),
        config_hash=sha256(canonical.encode("utf-8")).hexdigest(),
        fallback_active=fallback_active,
        fallback_reason=fallback_reason,
    )


def load_company_configuration(path: Path) -> CompanyConfiguration:
    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CompanyConfigError(f"Cannot read company config: {path}") from exc
    try:
        payload = yaml.safe_load(raw_text)
    except yaml.YAMLError as exc:
        raise CompanyConfigError("Company config must be valid safe YAML or JSON") from exc
    return _parse_company_payload(payload)


def load_company_configuration_safe(path: Path) -> CompanyConfiguration:
    """Return a validated profile or a safe default without stopping the dashboard."""

    try:
        return load_company_configuration(path)
    except (CompanyConfigError, OSError, ValueError) as exc:
        return default_company_configuration(reason=str(exc))
