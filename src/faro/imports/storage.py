"""Separate SQLite job ledger so failed uploads never affect operational data."""

from __future__ import annotations

from contextlib import closing
from dataclasses import replace
from pathlib import Path
import sqlite3

from faro.imports.models import ImportJob


DDL = """
PRAGMA journal_mode = WAL;
CREATE TABLE IF NOT EXISTS import_job (
    job_id TEXT PRIMARY KEY,
    file_name TEXT NOT NULL,
    profile_id TEXT,
    mode TEXT NOT NULL,
    status TEXT NOT NULL,
    message TEXT NOT NULL,
    created_at TEXT NOT NULL,
    completed_at TEXT,
    source_file_id TEXT,
    file_hash TEXT,
    records_added INTEGER NOT NULL DEFAULT 0,
    findings_added INTEGER NOT NULL DEFAULT 0,
    backup_path TEXT
);
CREATE INDEX IF NOT EXISTS idx_import_job_created_at
ON import_job(created_at DESC);
"""


class ImportJobStore:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def _connect(self) -> sqlite3.Connection:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.executescript(DDL)
        return connection

    def create(self, job: ImportJob) -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """INSERT INTO import_job VALUES
                   (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    job.job_id,
                    job.file_name,
                    job.profile_id,
                    job.mode,
                    job.status,
                    job.message,
                    job.created_at,
                    job.completed_at,
                    job.source_file_id,
                    job.file_hash,
                    job.records_added,
                    job.findings_added,
                    job.backup_path,
                ),
            )

    def update(self, job_id: str, **changes: object) -> ImportJob:
        current = self.get(job_id)
        if current is None:
            raise KeyError(job_id)
        updated = replace(current, **changes)
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """UPDATE import_job SET
                   status=?, message=?, completed_at=?, source_file_id=?, file_hash=?,
                   records_added=?, findings_added=?, backup_path=?
                   WHERE job_id=?""",
                (
                    updated.status,
                    updated.message,
                    updated.completed_at,
                    updated.source_file_id,
                    updated.file_hash,
                    updated.records_added,
                    updated.findings_added,
                    updated.backup_path,
                    updated.job_id,
                ),
            )
        return updated

    def get(self, job_id: str) -> ImportJob | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM import_job WHERE job_id = ?", (job_id,)
            ).fetchone()
        return ImportJob(**dict(row)) if row else None

    def recent(self, limit: int = 10) -> list[ImportJob]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT * FROM import_job ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [ImportJob(**dict(row)) for row in rows]
