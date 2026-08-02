"""CLI for deterministic profiled JSON and NDJSON ingestion."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from faro.ingestion.formats import InputFormat, detect_input_format
from faro.ingestion.json_records import (
    JsonIngestionService,
    JsonInput,
    build_json_profile,
)
from faro.settings import Settings


def _source(value: str) -> tuple[str, Path]:
    profile_id, separator, path = value.partition("=")
    if not separator or not profile_id or not path:
        raise argparse.ArgumentTypeError(
            "Source must use PROFILE=PATH, for example products=data/products.json."
        )
    return profile_id, Path(path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Ingest profiled JSON and NDJSON files without modifying them."
    )
    parser.add_argument(
        "--source",
        action="append",
        required=True,
        type=_source,
        metavar="PROFILE=PATH",
        help="Repeat for each input source.",
    )
    parser.add_argument("--schema-version", default="1.0.0")
    parser.add_argument("--date-format", default="%Y-%m-%d")
    parser.add_argument("--include-records", action="store_true")
    parser.add_argument("--no-reference-validation", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = Settings.from_environment()
    inputs: list[JsonInput] = []
    for profile_id, path in args.source:
        capability = detect_input_format(path)
        if capability is None or capability.format_id not in {
            InputFormat.JSON,
            InputFormat.NDJSON,
        }:
            build_parser().error(f"Expected .json, .ndjson, or .jsonl: {path}")
        inputs.append(
            JsonInput(
                path=path,
                profile=build_json_profile(
                    profile_id,
                    capability.format_id,
                    schema_version=args.schema_version,
                    date_format=args.date_format,
                ),
            )
        )

    service = JsonIngestionService(
        max_file_size_bytes=settings.json_max_file_size_mb * 1024 * 1024,
        max_records=settings.json_max_records,
        max_depth=settings.json_max_depth,
        max_fields=settings.json_max_fields,
        max_field_characters=settings.json_max_field_characters,
    )
    batch = service.ingest(
        inputs,
        validate_references=not args.no_reference_validation,
    )
    print(
        json.dumps(
            batch.to_dict(include_records=args.include_records),
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if batch.status != "failed" else 1


if __name__ == "__main__":
    sys.exit(main())
