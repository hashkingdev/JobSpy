from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.db import Base, engine, ensure_database, get_db
from backend.models import JobLink
from backend.schemas import SaveRequest, SaveResponse, SearchRequest
from backend.scraper_service import search_job_links


@asynccontextmanager
async def lifespan(_app: FastAPI):
    ensure_database()
    Base.metadata.create_all(bind=engine)
    yield


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

    saved = 0
    skipped = 0
    seen: set[str] = set()

    for job in payload.jobs:
        url = (job.job_url or "").strip()
        key = url.lower()
        if not url or key in seen:
            skipped += 1
            continue
        seen.add(key)

        existing = (
            db.query(JobLink)
            .filter(func.lower(func.btrim(JobLink.url)) == key)
            .one_or_none()
        )
        if existing:
            existing.company = job.company
            existing.role = job.title
            existing.location = job.location
            existing.url = url
        else:
            db.add(
                JobLink(
                    url=url,
                    company=job.company,
                    role=job.title,
                    location=job.location,
                    job_description="",
                )
            )
        saved += 1

    db.commit()
    return SaveResponse(saved=saved, skipped=skipped)
