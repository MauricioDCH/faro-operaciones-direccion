"""Generate Faro's deterministic synthetic operational dataset."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from faro.synthetic.generator import DEFAULT_SEED, generate_dataset


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository-like output root. Defaults to the project root.",
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Explicitly replace a previously generated dataset.",
    )
    return parser


def main() -> None:
    args = _parser().parse_args()
    manifest = generate_dataset(root=args.root, seed=args.seed, force=args.force)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
