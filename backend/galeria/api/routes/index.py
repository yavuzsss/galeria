from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, status

from galeria.api.jobs import JobAlreadyRunning, JobStatus
from galeria.api.schemas import IndexRequest, JobOut, ReportOut, StatsOut

router = APIRouter()


@router.post("/index", response_model=JobOut, status_code=status.HTTP_202_ACCEPTED)
def start_index(body: IndexRequest, request: Request) -> JobOut:
    """Start indexing a folder in the background; poll /api/index/status for progress."""
    settings = request.app.state.services.settings
    folder = Path(body.folder).expanduser().resolve()
    if not folder.is_dir():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"{body.folder} is not a directory")
    if settings.allowed_roots and not any(
        folder.is_relative_to(Path(root).resolve()) for root in settings.allowed_roots
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"{folder} is outside GALERIA_ALLOWED_ROOTS")
    try:
        job = request.app.state.jobs.start(folder)
    except JobAlreadyRunning as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, f"already indexing {exc}") from exc
    return _job_out(job)


@router.get("/index/status", response_model=JobOut)
def index_status(request: Request) -> JobOut:
    return _job_out(request.app.state.jobs.status)


@router.get("/stats", response_model=StatsOut)
def stats(request: Request) -> StatsOut:
    services = request.app.state.services
    return StatsOut(
        **services.meta.counts(),
        encoder=services.encoder.name,
        roots=services.meta.roots(),
        allowed_roots=[str(root) for root in services.settings.allowed_roots],
    )


def _job_out(job: JobStatus) -> JobOut:
    return JobOut(
        state=job.state,
        folder=job.folder,
        done=job.done,
        total=job.total,
        current=job.current,
        report=ReportOut.from_report(job.report) if job.report else None,
        error=job.error,
    )
