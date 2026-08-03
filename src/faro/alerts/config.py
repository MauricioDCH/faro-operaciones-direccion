"""Load company-selectable alert presets from a dependency-free config."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from faro.alerts.catalog import (
    AlertConfigError,
    SEVERITIES,
    validate_condition,
    validate_identifier,
    validate_source,
)


@dataclass(frozen=True, slots=True)
class AlertRule:
    rule_id: str
    name: str
    description: str
    source: dict[str, Any]
    operator: str
    threshold: Decimal
    unit: str
    severity: str
    cooldown_minutes: int


@dataclass(frozen=True, slots=True)
class AlertPreset:
    preset_id: str
    label: str
    description: str
    indicator_preset: str
    rules: tuple[AlertRule, ...]


@dataclass(frozen=True, slots=True)
class AlertConfiguration:
    schema_version: str
    active_preset: str
    presets: dict[str, AlertPreset]
    config_hash: str

    def select(self, preset_id: str | None = None) -> AlertPreset:
        selected = preset_id or self.active_preset
        try:
            return self.presets[selected]
        except KeyError as exc:
            raise AlertConfigError(f"Unknown alert preset: {selected}") from exc


def _short_text(value: Any, *, field: str, default: str = "") -> str:
    if value is None:
        return default
    if not isinstance(value, str) or len(value) > 500:
        raise AlertConfigError(f"{field} must be a string of at most 500 characters")
    return value


def load_alert_configuration(path: Path) -> AlertConfiguration:
    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise AlertConfigError(f"Cannot read alert config: {path}") from exc
    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise AlertConfigError("config/alerts.yaml must use JSON-compatible YAML syntax") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != "1.0.0":
        raise AlertConfigError("Alert config schema_version must be 1.0.0")
    raw_presets = payload.get("presets")
    if not isinstance(raw_presets, dict) or not raw_presets:
        raise AlertConfigError("Alert config requires at least one preset")
    presets: dict[str, AlertPreset] = {}
    global_rule_ids: set[str] = set()
    for preset_id, raw_preset in raw_presets.items():
        validate_identifier(preset_id, field="preset_id")
        if not isinstance(raw_preset, dict):
            raise AlertConfigError(f"Preset {preset_id} must be an object")
        indicator_preset = validate_identifier(
            raw_preset.get("indicator_preset"), field=f"{preset_id}.indicator_preset"
        )
        raw_rules = raw_preset.get("rules")
        if not isinstance(raw_rules, list) or not raw_rules:
            raise AlertConfigError(f"Preset {preset_id} requires alert rules")
        rules: list[AlertRule] = []
        for item in raw_rules:
            if not isinstance(item, dict):
                raise AlertConfigError(f"Preset {preset_id} contains an invalid rule")
            enabled = item.get("enabled", True)
            if not isinstance(enabled, bool):
                raise AlertConfigError(f"{preset_id}.rule.enabled must be boolean")
            if not enabled:
                continue
            rule_id = validate_identifier(item.get("rule_id"), field="rule_id")
            if rule_id in global_rule_ids:
                raise AlertConfigError(f"Alert rule_id is duplicated: {rule_id}")
            global_rule_ids.add(rule_id)
            source = validate_source(item.get("source"))
            condition = validate_condition(item.get("condition"))
            severity = item.get("severity")
            if severity not in SEVERITIES:
                raise AlertConfigError(f"Unsupported severity for {rule_id}: {severity}")
            cooldown = item.get("cooldown_minutes", 0)
            if isinstance(cooldown, bool) or not isinstance(cooldown, int) or not 0 <= cooldown <= 43_200:
                raise AlertConfigError(f"{rule_id}.cooldown_minutes must be between 0 and 43200")
            unknown = set(item) - {
                "rule_id", "name", "description", "enabled", "source", "condition",
                "severity", "cooldown_minutes",
            }
            if unknown:
                raise AlertConfigError(f"Unsupported fields in {rule_id}: {sorted(unknown)}")
            rules.append(
                AlertRule(
                    rule_id=rule_id,
                    name=_short_text(item.get("name"), field=f"{rule_id}.name", default=rule_id),
                    description=_short_text(item.get("description"), field=f"{rule_id}.description"),
                    source=source,
                    operator=condition["operator"],
                    threshold=condition["threshold"],
                    unit=condition["unit"],
                    severity=severity,
                    cooldown_minutes=cooldown,
                )
            )
        if not rules:
            raise AlertConfigError(f"Preset {preset_id} has no enabled rules")
        presets[preset_id] = AlertPreset(
            preset_id=preset_id,
            label=_short_text(raw_preset.get("label"), field=f"{preset_id}.label", default=preset_id),
            description=_short_text(raw_preset.get("description"), field=f"{preset_id}.description"),
            indicator_preset=indicator_preset,
            rules=tuple(rules),
        )
    active = payload.get("active_preset")
    if active not in presets:
        raise AlertConfigError(f"active_preset does not exist: {active}")
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return AlertConfiguration("1.0.0", active, presets, sha256(canonical.encode()).hexdigest())
