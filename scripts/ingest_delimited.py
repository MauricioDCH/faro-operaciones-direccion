"""CLI for deterministic CSV/TSV ingestion."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from faro.ingestion.delimited import (
    DelimitedIngestionService,
    DelimitedInput,
    build_profile,
)
from faro.ingestion.formats import InputFormat, detect_input_format
from faro.settings import Settings


_DELIMITER_ALIASES = {
    "auto": "auto",
    "comma": ",",
    "semicolon": ";",
    "tab": "\t",
    "pipe": "|",
    ",": ",",
    ";": ";",
    "\\t": "\t",
    "|": "|",
}


def _source_argument(value: str) -> tuple[str, Path]:
    profile_id, separator, path = value.partition("=")
    if not separator or not profile_id or not path:
        raise argparse.ArgumentTypeError(
            "Use PROFILE=PATH, for example sales=data/raw/tabular/ventas.csv."
        )
    return profile_id, Path(path)


def _delimiter(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        return _DELIMITER_ALIASES[value]
    except KeyError as exc:
        raise argparse.ArgumentTypeError(
            "Delimiter must be auto, comma, semicolon, tab, or pipe."
        ) from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Ingest explicitly profiled CSV and TSV sources."
    )
    parser.add_argument(
        "--source",
        action="append",
        required=True,
        type=_source_argument,
        metavar="PROFILE=PATH",
        help=(
            "Repeat for each source. Profiles: products, customers, suppliers, "
            "sales, inventory, orders."
        ),
    )
    parser.add_argument(
        "--delimiter",
        default=None,
        help="Optional shared delimiter: auto, comma, semicolon, tab, or pipe.",
    )
    parser.add_argument("--encoding", default="utf-8-sig")
    parser.add_argument("--decimal-separator", choices=(".", ","), default=".")
    parser.add_argument(
        "--thousands-separator",
        choices=(".", ",", " ", "'"),
        default=None,
    )
    parser.add_argument("--date-format", default="%Y-%m-%d")
    parser.add_argument(
        "--skip-reference-validation",
        action="store_true",
        help="Skip foreign-key checks when related catalogs are not in this batch.",
    )
    parser.add_argument(
        "--include-records",
        action="store_true",
        help="Include typed records in JSON output.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    delimiter = _delimiter(args.delimiter)
    settings = Settings.from_environment()
    sources: list[DelimitedInput] = []
    for profile_id, path in args.source:
        capability = detect_input_format(path)
        if capability is None or capability.format_id not in {
            InputFormat.CSV,
            InputFormat.TSV,
        }:
            parser.error(f"Source must end in .csv or .tsv: {path}")
        profile = build_profile(
            profile_id,
            capability.format_id,
            delimiter=delimiter,
            encoding=args.encoding,
            decimal_separator=args.decimal_separator,
            thousands_separator=args.thousands_separator,
            date_format=args.date_format,
        )
        sources.append(DelimitedInput(path=path, profile=profile))

    service = DelimitedIngestionService(
        max_file_size_bytes=settings.delimited_max_file_size_mb * 1024 * 1024,
        max_records=settings.delimited_max_records,
        max_columns=settings.delimited_max_columns,
        max_field_characters=settings.delimited_max_field_characters,
    )
    batch = service.ingest(
        sources,
        validate_references=not args.skip_reference_validation,
    )
    print(
        json.dumps(
            batch.to_dict(include_records=args.include_records),
            ensure_ascii=False,
            indent=2,
        )
    )
    return 1 if batch.status == "failed" else 0


if __name__ == "__main__":
    sys.exit(main())
