"""Immutable models for client-safe import jobs."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ImportJob:
    job_id: str
    file_name: str
    profile_id: str | None
    mode: str
    status: str
    message: str
    created_at: str
    completed_at: str | None
    source_file_id: str | None
    file_hash: str | None
    records_added: int
    findings_added: int
    backup_path: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "job_id": self.job_id,
            "file_name": self.file_name,
            "profile_id": self.profile_id,
            "mode": self.mode,
            "status": self.status,
            "message": self.message,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "source_file_id": self.source_file_id,
            "file_hash": self.file_hash,
            "records_added": self.records_added,
            "findings_added": self.findings_added,
            "backup_path": self.backup_path,
        }
