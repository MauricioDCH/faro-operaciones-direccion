"""Load company-selectable indicator presets from a dependency-free config."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from faro.indicators.catalog import IndicatorConfigError, validate_parameters


@dataclass(frozen=True, slots=True)
class IndicatorSelection:
    indicator_id: str
    parameters: dict[str, Any]


@dataclass(frozen=True, slots=True)
class IndicatorPreset:
    preset_id: str
    label: str
    description: str
    indicators: tuple[IndicatorSelection, ...]


@dataclass(frozen=True, slots=True)
class IndicatorConfiguration:
    schema_version: str
    active_preset: str
    calculated_at_source: str
    presets: dict[str, IndicatorPreset]
    config_hash: str

    def select(self, preset_id: str | None = None) -> IndicatorPreset:
        selected = preset_id or self.active_preset
        try:
            return self.presets[selected]
        except KeyError as exc:
            raise IndicatorConfigError(f"Unknown preset: {selected}") from exc


def load_indicator_configuration(path: Path) -> IndicatorConfiguration:
    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise IndicatorConfigError(f"Cannot read indicator config: {path}") from exc
    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise IndicatorConfigError(
            "config/indicators.yaml must use JSON-compatible YAML syntax."
        ) from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != "1.0.0":
        raise IndicatorConfigError("Indicator config schema_version must be 1.0.0")
    active = payload.get("active_preset")
    source = payload.get("calculated_at_source", "database_metadata")
    if source != "database_metadata":
        raise IndicatorConfigError("calculated_at_source must be database_metadata")
    raw_presets = payload.get("presets")
    if not isinstance(raw_presets, dict) or not raw_presets:
        raise IndicatorConfigError("Indicator config requires at least one preset")
    presets: dict[str, IndicatorPreset] = {}
    for preset_id, raw_preset in raw_presets.items():
        if not isinstance(raw_preset, dict):
            raise IndicatorConfigError(f"Preset {preset_id} must be an object")
        raw_indicators = raw_preset.get("indicators")
        if not isinstance(raw_indicators, list) or not raw_indicators:
            raise IndicatorConfigError(f"Preset {preset_id} requires indicators")
        selections: list[IndicatorSelection] = []
        seen: set[str] = set()
        for item in raw_indicators:
            if not isinstance(item, dict):
                raise IndicatorConfigError(f"Preset {preset_id} contains an invalid indicator")
            indicator_id = item.get("indicator_id")
            if not isinstance(indicator_id, str):
                raise IndicatorConfigError(f"Preset {preset_id} has an indicator without indicator_id")
            if indicator_id in seen:
                raise IndicatorConfigError(f"Preset {preset_id} repeats {indicator_id}")
            seen.add(indicator_id)
            enabled = item.get("enabled", True)
            if not isinstance(enabled, bool):
                raise IndicatorConfigError(f"{indicator_id}.enabled must be boolean")
            if not enabled:
                continue
            parameters = item.get("parameters", {})
            if not isinstance(parameters, dict):
                raise IndicatorConfigError(f"{indicator_id}.parameters must be an object")
            selections.append(IndicatorSelection(indicator_id, validate_parameters(indicator_id, parameters)))
        if not selections:
            raise IndicatorConfigError(f"Preset {preset_id} has no enabled indicators")
        presets[preset_id] = IndicatorPreset(
            preset_id=preset_id,
            label=str(raw_preset.get("label", preset_id)),
            description=str(raw_preset.get("description", "")),
            indicators=tuple(selections),
        )
    if active not in presets:
        raise IndicatorConfigError(f"active_preset does not exist: {active}")
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return IndicatorConfiguration("1.0.0", active, source, presets, sha256(canonical.encode()).hexdigest())
