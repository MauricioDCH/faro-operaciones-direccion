"""CLI for rebuilding Faro's unified local SQLite store."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from faro.persistence.consolidation import UnifiedConsolidationService
from faro.settings import Settings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Consolidate implemented Faro sources into an atomic SQLite store."
    )
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--database", type=Path)
    parser.add_argument(
        "--exclude-samples",
        action="store_true",
        help="Do not include synthetic UBL examples from data/samples.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = Settings.from_environment()
    try:
        report = UnifiedConsolidationService(settings).consolidate(
            data_dir=args.data_dir,
            database_path=args.database,
            include_samples=not args.exclude_samples,
        )
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "error_code": "operational_consolidation_failed",
                    "message": str(exc),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
