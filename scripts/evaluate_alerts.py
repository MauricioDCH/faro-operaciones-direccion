"""Evaluate a company-selected alert preset over Faro's SQLite store."""

from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path

from faro.alerts import AlertConfigError, ConfigurableAlertService, load_alert_configuration
from faro.indicators import load_indicator_configuration
from faro.indicators.catalog import IndicatorConfigError
from faro.settings import Settings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path)
    parser.add_argument("--alert-config", type=Path)
    parser.add_argument("--indicator-config", type=Path)
    parser.add_argument("--preset")
    parser.add_argument("--as-of-date", type=date.fromisoformat)
    parser.add_argument("--no-persist", action="store_true")
    parser.add_argument("--list-presets", action="store_true")
    args = parser.parse_args()
    settings = Settings.from_environment()
    try:
        alert_configuration = load_alert_configuration(
            args.alert_config or settings.alert_config_path
        )
        if args.list_presets:
            print(
                json.dumps(
                    {
                        key: {
                            "label": item.label,
                            "description": item.description,
                            "indicator_preset": item.indicator_preset,
                            "rule_count": len(item.rules),
                        }
                        for key, item in alert_configuration.presets.items()
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return
        indicator_configuration = load_indicator_configuration(
            args.indicator_config or settings.indicator_config_path
        )
        run = ConfigurableAlertService().evaluate(
            database_path=args.database or settings.database_path,
            alert_configuration=alert_configuration,
            indicator_configuration=indicator_configuration,
            preset_id=args.preset,
            as_of_date=args.as_of_date,
            persist=not args.no_persist,
        )
    except (AlertConfigError, IndicatorConfigError, ValueError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False, indent=2))
        raise SystemExit(2) from exc
    print(json.dumps(run.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
