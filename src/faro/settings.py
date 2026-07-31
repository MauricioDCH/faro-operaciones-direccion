"""Application settings contract.

Concrete environment loading will be added with the first executable vertical slice.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Settings:
    """Minimal immutable paths required by the scaffold."""

    data_dir: Path = Path("data")
    config_path: Path = Path("config/app.example.yaml")
