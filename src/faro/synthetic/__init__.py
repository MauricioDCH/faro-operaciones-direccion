"""Deterministic synthetic-data generation and validation for Faro."""

from faro.synthetic.generator import DEFAULT_SEED, generate_dataset
from faro.synthetic.validator import validate_dataset

__all__ = ["DEFAULT_SEED", "generate_dataset", "validate_dataset"]
