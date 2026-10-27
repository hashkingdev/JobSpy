from contextlib import asynccontextmanager
from datetime import date

from fastapi import Depends, FastAPI, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from backend import daily
from backend.config import (
    DAILY_DATE_POSTED,
    DAILY_ENABLED,
    DAILY_LOCATION_TYPE,
    DAILY_RUN_AT,
    DAILY_TARGET,
    NO_LOGIN_STRICT,
)
from backend.db import Base, engine, ensure_columns, ensure_database, get_db
from backend.links import count_links_for_date, links_for_date, upsert_links
from backend.models import DailyRun
from backend.schemas import SaveRequest, SaveResponse, SearchRequest
from backend.scraper_service import search_job_links


@asynccontextmanager
async def lifespan(_app: FastAPI):
    ensure_database()
    Base.metadata.create_all(bind=engine)
    ensure_columns()
    daily.start_scheduler()
    yield
    daily.stop_scheduler()


app = FastAPI(title="JobSpy API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"ok": True}


@app.post("/api/jobs/search")
def search_jobs(payload: SearchRequest):
    try:
        jobs, unsupported_sites, site_status = search_job_links(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Job search failed: {exc}",
        ) from exc
    return {
        "jobs": jobs,
        "count": len(jobs),
        "unsupported_sites": unsupported_sites,
        "site_status": site_status,
    }


@app.post("/api/jobs/save", response_model=SaveResponse)
def save_jobs(payload: SaveRequest, db: Session = Depends(get_db)):
    if not payload.jobs:
        raise HTTPException(status_code=400, detail="No job links to save")
    inserted, updated, skipped = upsert_links(
        db, [job.model_dump() for job in payload.jobs], update_existing=True
    )
    return SaveResponse(saved=inserted + updated, skipped=skipped)


def _parse_day(value: str | None) -> date:
    if not value or value == "today":
        return date.today()
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="date must be YYYY-MM-DD") from exc


@app.get("/api/daily/status")
def daily_status(db: Session = Depends(get_db)):
    today = date.today()
    last_run = db.query(DailyRun).order_by(DailyRun.id.desc()).first()
    return {
        "enabled": DAILY_ENABLED,
        "target": DAILY_TARGET,
        "run_at": DAILY_RUN_AT,
        "next_run_at": daily.next_run_at().isoformat() if DAILY_ENABLED else None,
        "today": today.isoformat(),
        "today_count": count_links_for_date(db, today),
        "running": daily.is_running(),
        "roles": daily.roles(),
        "sources": daily.sources(),
        "location_type": DAILY_LOCATION_TYPE,
        "date_posted": DAILY_DATE_POSTED,
        "no_login_strict": NO_LOGIN_STRICT,
        "last_run": daily.run_to_dict(last_run),
    }


@app.post("/api/daily/run")
async def daily_run():
    if daily.is_running():
        raise HTTPException(status_code=409, detail="A daily run is already in progress")
    try:
        return await run_in_threadpool(daily.collect, "manual")
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/api/daily/links")
def daily_links(date: str | None = None, db: Session = Depends(get_db)):
    day = _parse_day(date)
    links = links_for_date(db, day)
    return {"date": day.isoformat(), "count": len(links), "links": links}


@app.get("/api/daily/runs")
def daily_runs(limit: int = 14, db: Session = Depends(get_db)):
    limit = max(1, min(limit, 100))
    rows = db.query(DailyRun).order_by(DailyRun.id.desc()).limit(limit).all()
    return {"runs": [daily.run_to_dict(row) for row in rows]}
