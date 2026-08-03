\
"""CLI for secure UBL XML ingestion."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from faro.ingestion.ubl_xml import UblFormatError, UblLimits, UblXmlIngestionService
from faro.settings import Settings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Ingest one UBL 2.1 Invoice or AttachedDocument XML."
    )
    parser.add_argument("xml", type=Path, help="Path to the UBL XML source.")
    parser.add_argument(
        "--omit-locations",
        action="store_true",
        help="Omit field-level XPath locations from JSON output.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    settings = Settings.from_environment()
    service = UblXmlIngestionService(
        limits=UblLimits(
            max_file_size_mb=settings.ubl_max_file_size_mb,
            max_elements=settings.ubl_max_elements,
            max_depth=settings.ubl_max_depth,
            max_text_characters=settings.ubl_max_text_characters,
        )
    )
    try:
        result = service.ingest(args.xml)
    except (UblFormatError, OSError, ValueError) as exc:
        payload = {
            "status": "failed",
            "error_code": getattr(exc, "code", "ubl_ingestion_error"),
            "message": str(exc),
            "xml_xpath": getattr(exc, "xml_xpath", None),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 1
    print(
        json.dumps(
            result.to_dict(include_locations=not args.omit_locations),
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if result.status == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
