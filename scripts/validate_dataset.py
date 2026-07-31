"""Validate Faro's synthetic dataset against its expected anomaly ground truth."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from faro.synthetic.validator import validate_dataset


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository-like dataset root. Defaults to the project root.",
    )
    parser.add_argument("--report", type=Path, default=None)
    return parser


def main() -> None:
    args = _parser().parse_args()
    report = validate_dataset(root=args.root, report_path=args.report)
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    if report["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
