"""FastAPI application for Faro's client-safe operations dashboard."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from faro.company.config import load_company_configuration_safe
from faro.imports.models import ImportJob
from faro.imports.service import (
    ImportRequest,
    ImportValidationError,
    IncrementalImportService,
)
from faro.imports.storage import ImportJobStore
from faro.settings import Settings
from faro.ui.dashboard import DashboardRepository


settings = Settings.from_environment()
startup_company = load_company_configuration_safe(settings.company_config_path)
BASE_DIR = Path(__file__).resolve().parent
app = FastAPI(title=startup_company.dashboard.title)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def _company():
    return load_company_configuration_safe(settings.company_config_path)


def _repository(company) -> DashboardRepository:
    return DashboardRepository(settings.database_path, currency=company.currency)


def _job_store() -> ImportJobStore:
    return ImportJobStore(settings.import_database_path)


def _safe_job_update(store: ImportJobStore, job_id: str, **changes: object) -> None:
    try:
        store.update(job_id, **changes)
    except Exception:
        # Import ledger failure must not hide a successful operational update.
        return


def _import_service(company) -> IncrementalImportService:
    return IncrementalImportService(settings, company)


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/dashboard")


@app.get("/health")
def health() -> dict[str, object]:
    company = _company()
    database_available = settings.database_path.is_file()
    status = "ok" if database_available and not company.fallback_active else "degraded"
    return {
        "status": status,
        "database_available": database_available,
        "database_path": str(settings.database_path),
        "company_id": company.company_id,
        "company_config_hash": company.config_hash,
        "company_fallback_active": company.fallback_active,
        "company_fallback_reason": company.fallback_reason,
    }


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(
    request: Request,
    severity: str | None = None,
    q: str | None = None,
    import_status: str | None = None,
    job_id: str | None = None,
) -> HTMLResponse:
    company = _company()
    snapshot = _repository(company).fetch_snapshot(
        indicator_preset=company.indicator_preset,
        alert_preset=company.alert_preset,
        severity=severity,
        query=q,
    )
    try:
        recent_imports = _job_store().recent(limit=8)
    except Exception:
        recent_imports = []
    context = {
        "request": request,
        "title": company.dashboard.title,
        "company": company,
        "snapshot": snapshot,
        "recent_imports": recent_imports,
        "selected_severity": severity or "",
        "search_query": q or "",
        "import_status": import_status,
        "job_id": job_id,
        "settings": settings,
    }
    return templates.TemplateResponse(request, "dashboard.html", context)


@app.post("/data/import", include_in_schema=False)
def import_data(
    file: UploadFile = File(...),
    profile_id: str | None = Form(None),
    mode: str = Form("upsert"),
) -> RedirectResponse:
    company = _company()
    job_id = f"IMP-{uuid4().hex[:16].upper()}"
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    store = _job_store()
    try:
        store.create(
            ImportJob(
                job_id=job_id,
                file_name=file.filename or "archivo",
                profile_id=profile_id,
                mode=mode,
                status="processing",
                message="Faro está validando el archivo sin afectar la base activa.",
                created_at=now,
                completed_at=None,
                source_file_id=None,
                file_hash=None,
                records_added=0,
                findings_added=0,
                backup_path=None,
            )
        )
    except Exception:
        file.file.close()
        return RedirectResponse(
            url="/dashboard?import_status=failed#actualizar-datos",
            status_code=303,
        )
    try:
        result = _import_service(company).import_stream(
            file.file,
            ImportRequest(
                file_name=file.filename or "archivo",
                profile_id=profile_id,
                mode=mode,
            ),
            job_id=job_id,
        )
        completed_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        _safe_job_update(
            store,
            job_id,
            status=result.status,
            message=result.message,
            completed_at=completed_at,
            source_file_id=result.source_file_id,
            records_added=result.records_added,
            findings_added=result.findings_added,
            backup_path=str(settings.database_path.with_suffix(settings.database_path.suffix + ".bak")),
        )
        return RedirectResponse(
            url=f"/dashboard?import_status={result.status}&job_id={job_id}#actualizar-datos",
            status_code=303,
        )
    except ImportValidationError as exc:
        status = "rejected"
        message = str(exc)
    except Exception:
        status = "failed"
        message = (
            "No pudimos actualizar los datos. La base anterior sigue intacta. "
            "Revisa el archivo o consulta el registro técnico."
        )
    finally:
        file.file.close()
    completed_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    _safe_job_update(
        store,
        job_id,
        status=status,
        message=message,
        completed_at=completed_at,
    )
    return RedirectResponse(
        url=f"/dashboard?import_status={status}&job_id={job_id}#actualizar-datos",
        status_code=303,
    )
