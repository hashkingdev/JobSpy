"""Collect a fixed number of no-login job links per day, on a schedule or on demand."""

from __future__ import annotations

import json
import logging
import threading
from datetime import date, datetime, timedelta
from typing import Any

from backend.config import (
    DAILY_COUNTRY,
    DAILY_DATE_POSTED,
    DAILY_ENABLED,
    DAILY_JOB_TYPE,
    DAILY_LOCATION_TYPE,
    DAILY_ROLES,
    DAILY_RUN_AT,
    DAILY_SOURCES,
    DAILY_TARGET,
)
from backend.db import SessionLocal
from backend.links import count_links_for_date, existing_keys, upsert_links
from backend.models import DailyRun
from backend.no_login import filter_no_login
from backend.providers import PROVIDERS
from backend.schemas import SearchRequest

log = logging.getLogger("daily")

_run_lock = threading.Lock()
_stop = threading.Event()
_thread: threading.Thread | None = None


def roles() -> list[str]:
    return [part.strip() for part in DAILY_ROLES.split(",") if part.strip()] or [
        "full stack software engineer"
    ]


def sources() -> list[str]:
    return [
        part.strip() for part in DAILY_SOURCES.split(",") if part.strip() in PROVIDERS
    ]


def run_time() -> tuple[int, int]:
    try:
        hour, minute = DAILY_RUN_AT.split(":")
        return max(0, min(23, int(hour))), max(0, min(59, int(minute)))
    except ValueError:
        return 8, 0


def next_run_at(now: datetime | None = None) -> datetime:
    now = now or datetime.now()
    hour, minute = run_time()
    candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate <= now:
        candidate += timedelta(days=1)
    return candidate


def is_running() -> bool:
    return _run_lock.locked()


def collect(trigger: str = "manual", target: int | None = None) -> dict[str, Any]:
    """Search every configured source until today's saved count reaches the target."""
    if not _run_lock.acquire(blocking=False):
        raise RuntimeError("A daily run is already in progress")
    target = target or DAILY_TARGET
    today = date.today()
    db = SessionLocal()
    run = DailyRun(run_date=today, trigger=trigger, target=target, status="running")
    db.add(run)
    db.commit()
    notes: list[dict[str, Any]] = []
    found = filtered = duplicates = saved = 0
    try:
        have = count_links_for_date(db, today)
        for role in roles():
            for source in sources():
                if have >= target:
                    break
                payload = SearchRequest(
                    source=source,
                    role=role,
                    location_type=DAILY_LOCATION_TYPE,
                    country=DAILY_COUNTRY,
                    job_type=DAILY_JOB_TYPE or None,
                    date_posted=DAILY_DATE_POSTED,
                    num_pages=20,
                    results_wanted=100,
                    no_login_only=True,
                )
                note: dict[str, Any] = {"source": source, "role": role}
                try:
                    jobs, status = PROVIDERS[source](payload)
                    errors = [item["error"] for item in status if item.get("error")]
                    if errors and not jobs:
                        note["error"] = "; ".join(errors)[:300]
                except Exception as exc:  # provider errors must not stop the run
                    note["error"] = str(exc)[:300]
                    notes.append(note)
                    log.warning("daily: %s failed for %r: %s", source, role, exc)
                    continue
                for job in jobs:
                    job.pop("matched_site", None)
                kept, dropped = filter_no_login(jobs)
                room = target - have
                known = existing_keys(db, [job.get("job_url") or "" for job in kept])
                seen: set[str] = set()
                fresh: list[dict[str, Any]] = []
                skipped = 0
                for job in kept:
                    key = (job.get("job_url") or "").strip().lower()
                    if not key or key in known or key in seen:
                        skipped += 1
                        continue
                    seen.add(key)
                    fresh.append(job)
                    if len(fresh) >= room:
                        break
                try:
                    inserted, _updated, _skipped = upsert_links(db, fresh, update_existing=False)
                except Exception as exc:  # keep the run alive if one batch fails to insert
                    db.rollback()
                    note["error"] = f"save failed: {str(exc)[:200]}"
                    notes.append(note)
                    log.warning("daily: saving %s links failed: %s", source, exc)
                    continue
                have += inserted
                found += len(jobs)
                filtered += dropped
                duplicates += skipped
                saved += inserted
                note.update(
                    {
                        "found": len(jobs),
                        "no_login": len(kept),
                        "new": inserted,
                        "duplicates": skipped,
                    }
                )
                notes.append(note)
            if have >= target:
                break
        run.status = "done" if have >= target else "short"
    except Exception as exc:
        db.rollback()
        run.status = "error"
        notes.append({"error": str(exc)[:300]})
        log.exception("daily run failed")
    finally:
        try:
            run = db.merge(run)
            run.finished_at = datetime.now()
            run.found = found
            run.filtered = filtered
            run.duplicates = duplicates
            run.saved = saved
            run.notes = json.dumps(notes)
            db.commit()
            result = run_to_dict(run)
            result["today_count"] = count_links_for_date(db, today)
        except Exception:
            db.rollback()
            log.exception("daily: could not record run result")
            result = {
                "status": "error",
                "saved": saved,
                "found": found,
                "filtered": filtered,
                "duplicates": duplicates,
                "target": target,
                "notes": notes,
                "today_count": None,
            }
        finally:
            db.close()
            _run_lock.release()
    return result


def run_to_dict(run: DailyRun | None) -> dict[str, Any] | None:
    if run is None:
        return None
    try:
        notes = json.loads(run.notes) if run.notes else []
    except ValueError:
        notes = []
    return {
        "id": run.id,
        "run_date": run.run_date.isoformat(),
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "status": run.status,
        "trigger": run.trigger,
        "target": run.target,
        "saved": run.saved,
        "found": run.found,
        "filtered": run.filtered,
        "duplicates": run.duplicates,
        "notes": notes,
    }


def _scheduler_loop() -> None:
    log.info("daily scheduler started; next run at %s", next_run_at())
    while not _stop.is_set():
        now = datetime.now()
        hour, minute = run_time()
        due = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if now >= due and not _ran_today(now.date()):
            try:
                result = collect(trigger="schedule")
                log.info("daily run finished: %s", result["status"])
            except Exception as exc:
                log.warning("daily scheduled run skipped: %s", exc)
        _stop.wait(60)


def _ran_today(today: date) -> bool:
    db = SessionLocal()
    try:
        return (
            db.query(DailyRun)
            .filter(DailyRun.run_date == today, DailyRun.trigger == "schedule")
            .first()
            is not None
        )
    finally:
        db.close()


def start_scheduler() -> None:
    global _thread
    if not DAILY_ENABLED or _thread is not None:
        return
    _stop.clear()
    _thread = threading.Thread(target=_scheduler_loop, name="daily-scheduler", daemon=True)
    _thread.start()


def stop_scheduler() -> None:
    global _thread
    _stop.set()
    _thread = None
