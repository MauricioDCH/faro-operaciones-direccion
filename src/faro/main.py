"""Minimal executable entry point for the repository scaffold."""

from __future__ import annotations

import json
from typing import Final

from faro import __version__

APP_NAME: Final[str] = "Faro"


def get_status() -> dict[str, str]:
    """Return the current scaffold status without claiming MVP capabilities."""
    return {
        "application": APP_NAME,
        "version": __version__,
        "status": "repository-scaffold",
    }


def main() -> None:
    """Print the current project status as machine-readable JSON."""
    print(json.dumps(get_status(), ensure_ascii=False))


if __name__ == "__main__":
    main()
