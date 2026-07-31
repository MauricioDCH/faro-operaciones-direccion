"""Ingest Faro's approved Excel sources and print a traceable JSON result."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from faro.ingestion import ExcelIngestionService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=Path("data/raw"),
        help="Directory containing the four approved Excel workbooks.",
    )
    parser.add_argument(
        "--include-records",
        action="store_true",
        help="Include every typed record and cell location in stdout.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = ExcelIngestionService().ingest(args.raw_dir)
    print(
        json.dumps(
            result.to_dict(include_records=args.include_records),
            ensure_ascii=False,
            indent=2,
        )
    )
    if result.status == "failed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
