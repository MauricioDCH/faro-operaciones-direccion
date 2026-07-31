"""Immutable provenance models for source files and document evidence."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    """Return the SHA-256 digest without mutating the source file."""

    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_source_id(file_hash: str) -> str:
    """Build a deterministic source identifier from a file hash."""

    return f"SRC-{file_hash[:16].upper()}"


def stable_document_id(file_hash: str) -> str:
    """Build a deterministic document identifier from a file hash."""

    return f"DOC-{file_hash[:16].upper()}"


def stable_page_id(file_hash: str, page_number: int) -> str:
    """Build a deterministic page identifier from a file hash and page."""

    return f"DOCP-{file_hash[:12].upper()}-{page_number:03d}"


def stable_location_id(file_hash: str, page_number: int) -> str:
    """Build a deterministic source-location identifier."""

    return f"LOC-{file_hash[:12].upper()}-{page_number:03d}"


@dataclass(frozen=True, slots=True)
class BoundingBox:
    """Evidence region in rendered-page pixel coordinates."""

    x: int
    y: int
    width: int
    height: int

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class EvidenceFragment:
    """Text evidence linked to an optional page region."""

    text: str
    confidence: float | None = None
    bounding_box: BoundingBox | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "confidence": self.confidence,
            "bounding_box": (
                self.bounding_box.to_dict() if self.bounding_box else None
            ),
        }


@dataclass(frozen=True, slots=True)
class SourceFile:
    """Canonical immutable source-file provenance for DC-007."""

    source_file_id: str
    file_path: str
    file_name: str
    source_type: str
    contract_id: str
    contract_version: str
    dataset_version: str
    seed: int | None
    file_hash: str
    ingested_at: str
    record_status: str

    @property
    def sha256(self) -> str:
        return self.file_hash.removeprefix("sha256:")

    @classmethod
    def from_path(
        cls,
        path: Path,
        file_hash: str | None = None,
        ingested_at: datetime | None = None,
    ) -> "SourceFile":
        resolved = path.resolve()
        digest = file_hash or sha256_file(resolved)
        try:
            file_path = str(resolved.relative_to(Path.cwd().resolve()))
        except ValueError:
            file_path = str(resolved)
        timestamp = ingested_at or datetime.now(timezone.utc)
        return cls(
            source_file_id=stable_source_id(digest),
            file_path=file_path,
            file_name=resolved.name,
            source_type="pdf",
            contract_id="DC-007",
            contract_version="1.4.0",
            dataset_version="0.1.0",
            seed=20260731,
            file_hash=f"sha256:{digest}",
            ingested_at=timestamp.isoformat(),
            record_status="accepted",
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class SourceLocation:
    """Page-level provenance for a document result."""

    source_location_id: str
    source_file_id: str
    page_number: int
    text_excerpt: str
    evidence: tuple[EvidenceFragment, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_location_id": self.source_location_id,
            "source_file_id": self.source_file_id,
            "page_number": self.page_number,
            "text_excerpt": self.text_excerpt,
            "evidence": [item.to_dict() for item in self.evidence],
        }
