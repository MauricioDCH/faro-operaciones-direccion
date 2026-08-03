"""Cross-source normalization and canonicalization."""

from faro.normalization.consolidation import (
    CanonicalizationResult,
    RecordObservation,
    TransformationEvent,
    canonicalize,
    canonical_json,
    extraction_results_from_document,
    observations_from_document,
    observations_from_tabular,
    observations_from_ubl,
    payload_hash,
    stable_id,
)

__all__ = [
    "CanonicalizationResult",
    "RecordObservation",
    "TransformationEvent",
    "canonicalize",
    "canonical_json",
    "extraction_results_from_document",
    "observations_from_document",
    "observations_from_tabular",
    "observations_from_ubl",
    "payload_hash",
    "stable_id",
]
