"""Calculate a company-selected indicator preset over Faro's SQLite store."""

from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path

from faro.indicators import OperationalIndicatorService, load_indicator_configuration
from faro.indicators.catalog import IndicatorConfigError
from faro.settings import Settings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--preset")
    parser.add_argument("--as-of-date", type=date.fromisoformat)
    parser.add_argument("--no-persist", action="store_true")
    parser.add_argument("--list-presets", action="store_true")
    args = parser.parse_args()
    settings = Settings.from_environment()
    config_path = args.config or settings.indicator_config_path
    try:
        configuration = load_indicator_configuration(config_path)
        if args.list_presets:
            print(json.dumps({key: {"label": item.label, "description": item.description} for key, item in configuration.presets.items()}, ensure_ascii=False, indent=2))
            return
        run = OperationalIndicatorService().calculate(
            database_path=args.database or settings.database_path,
            configuration=configuration,
            preset_id=args.preset,
            as_of_date=args.as_of_date,
            persist=not args.no_persist,
        )
    except (IndicatorConfigError, ValueError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False, indent=2))
        raise SystemExit(2) from exc
    print(json.dumps(run.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
