from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.models import JobLink


def _key(url: str | None) -> str:
    return (url or "").strip().lower()


def existing_keys(db: Session, urls: list[str]) -> set[str]:
    keys = {_key(url) for url in urls if _key(url)}
    if not keys:
        return set()
    rows = (
        db.query(func.lower(func.btrim(JobLink.url)))
        .filter(func.lower(func.btrim(JobLink.url)).in_(keys))
        .all()
    )
    return {row[0] for row in rows}


def upsert_links(
    db: Session,
    jobs: list[dict[str, Any]],
    *,
    update_existing: bool = True,
) -> tuple[int, int, int]:
    """Insert job links. Returns (inserted, updated, skipped)."""
    inserted = updated = skipped = 0
    seen: set[str] = set()
    known = existing_keys(db, [job.get("job_url") or "" for job in jobs])

    for job in jobs:
        url = (job.get("job_url") or "").strip()
        key = url.lower()
        if not url or key in seen:
            skipped += 1
            continue
        seen.add(key)

        if key in known:
            if not update_existing:
                skipped += 1
                continue
            existing = (
                db.query(JobLink)
                .filter(func.lower(func.btrim(JobLink.url)) == key)
                .first()
            )
            if existing:
                existing.company = (job.get("company") or existing.company or "")[:255]
                existing.role = (job.get("title") or existing.role or "")[:255]
                existing.location = (job.get("location") or existing.location or "")[:255]
                existing.site = (job.get("site") or existing.site or "")[:120]
                existing.url = url
                updated += 1
                continue

        # The live table was created with NOT NULL on these columns, so never pass None.
        db.add(
            JobLink(
                url=url,
                company=(job.get("company") or "")[:255],
                role=(job.get("title") or "")[:255],
                location=(job.get("location") or "")[:255],
                site=(job.get("site") or "")[:120],
                job_description=job.get("job_description") or "",
            )
        )
        known.add(key)
        inserted += 1

    db.commit()
    return inserted, updated, skipped


def count_links_for_date(db: Session, day: date) -> int:
    return db.query(JobLink).filter(func.date(JobLink.created_at) == day).count()


def links_for_date(db: Session, day: date) -> list[dict[str, Any]]:
    rows = (
        db.query(JobLink)
        .filter(func.date(JobLink.created_at) == day)
        .order_by(JobLink.id.desc())
        .all()
    )
    return [
        {
            "id": row.id,
            "job_url": row.url,
            "title": row.role,
            "company": row.company,
            "site": row.site,
            "location": row.location,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]
