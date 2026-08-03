"""Local operational persistence interfaces."""

from faro.persistence.consolidation import (
    ConsolidationReport,
    UnifiedConsolidationService,
)
from faro.persistence.schema import SCHEMA_VERSION
from faro.persistence.sqlite_store import (
    SQLiteOperationalStore,
    database_counts,
    logical_content_hash,
)

__all__ = [
    "ConsolidationReport",
    "SCHEMA_VERSION",
    "SQLiteOperationalStore",
    "UnifiedConsolidationService",
    "database_counts",
    "logical_content_hash",
]
