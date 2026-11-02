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
    DAILY_FALLBACK_DATE_POSTED,
    DAILY_JOB_TYPE,
    DAILY_LOCATION_TYPE,
    DAILY_MAX_MINUTES,
    DAILY_RATE_LIMIT_RETRIES,
    DAILY_RATE_LIMIT_WAIT,
    DAILY_REMOTE_ONLY,
    DAILY_ROLES,
    DAILY_RUN_AT,
    DAILY_SOURCES,
    DAILY_TARGET,
)
from backend.db import SessionLocal
from backend.links import (
    count_links_for_date,
    count_remote_links_for_date,
    existing_keys,
    upsert_links,
)
from backend.models import DailyRun
from backend.no_login import filter_no_login
from backend.providers import PROVIDERS
from backend.remote import filter_remote
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


def date_windows() -> list[str]:
    """The first window, then each comma-separated fallback window that is wider."""
    windows = [DAILY_DATE_POSTED]
    for part in (DAILY_FALLBACK_DATE_POSTED or "").split(","):
        part = part.strip()
        if part and part not in windows:
            windows.append(part)
    return windows


def _is_unavailable(error: str) -> bool:
    lowered = error.lower()
    return (
        "subscribe" in lowered
        or "not subscribed" in lowered
        or "disabled for your subscription" in lowered
        or "quota exhausted" in lowered
        or ("quota" in lowered and "exceeded" in lowered)
        or "rate-limited" in lowered  # still limited after the retries: skip it for the rest of this run
    )


def _is_quota_exhausted(error: str) -> bool:
    lowered = error.lower()
    return "quota exhausted" in lowered or ("quota" in lowered and "exceeded" in lowered)


def _is_rate_limited(errors: list[str]) -> bool:
    return any("rate-limited" in error or "429" in error for error in errors)


def _search(source: str, payload: SearchRequest, note: dict[str, Any]) -> list[dict[str, Any]]:
    """Call one provider, waiting out RapidAPI per-minute limits a few times before giving up."""
    attempts = 0
    while True:
        jobs, status = PROVIDERS[source](payload)
        errors = [item["error"] for item in status if item.get("error")]
        if jobs or not errors:
            return jobs
        if (
            _is_rate_limited(errors)
            and not any(_is_quota_exhausted(e) for e in errors)
            and attempts < DAILY_RATE_LIMIT_RETRIES
        ):
            attempts += 1
            note["retries"] = attempts
            log.info("daily: %s rate-limited; waiting %ss (retry %s)", source, DAILY_RATE_LIMIT_WAIT, attempts)
            _stop.wait(DAILY_RATE_LIMIT_WAIT)
            continue
        note["error"] = "; ".join(errors)[:300]
        return []


def remote_only() -> bool:
    return DAILY_REMOTE_ONLY and DAILY_LOCATION_TYPE == "remote"


def count_for_target(db, day: date) -> int:
    """Rows that count toward the daily target: verified-remote rows when the filter is on."""
    if remote_only():
        return count_remote_links_for_date(db, day)
    return count_links_for_date(db, day)


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
        have = count_for_target(db, today)
        dead_sources: set[str] = set()  # not subscribed or disabled: no point asking again
        deadline = datetime.now() + timedelta(minutes=DAILY_MAX_MINUTES)
        out_of_time = False
        for window in date_windows():
            for role in roles():
                for source in sources():
                    if have >= target:
                        break
                    if datetime.now() >= deadline:
                        out_of_time = True
                        notes.append({"error": f"stopped after {DAILY_MAX_MINUTES} minutes (DAILY_MAX_MINUTES)"})
                        break
                    if source in dead_sources:
                        continue
                    payload = SearchRequest(
                        source=source,
                        role=role,
                        location_type=DAILY_LOCATION_TYPE,
                        country=DAILY_COUNTRY,
                        job_type=DAILY_JOB_TYPE or None,
                        date_posted=window,
                        num_pages=20,
                        # Company boards are free, so ask for the whole matching pool and
                        # let the database de-duplicate; paid feeds stay at 100 per call.
                        results_wanted=2000 if source == "company-boards" else 100,
                        no_login_only=True,
                        remote_only=remote_only(),
                    )
                    note: dict[str, Any] = {"source": source, "role": role, "window": window}
                    try:
                        jobs = _search(source, payload, note)
                    except Exception as exc:  # provider errors must not stop the run
                        note["error"] = str(exc)[:300]
                        if _is_unavailable(note["error"]):
                            dead_sources.add(source)
                        notes.append(note)
                        log.warning("daily: %s failed for %r: %s", source, role, exc)
                        continue
                    if note.get("error"):
                        if _is_unavailable(note["error"]):
                            dead_sources.add(source)
                        notes.append(note)
                        continue
                    for job in jobs:
                        job.pop("matched_site", None)
                    kept, dropped = filter_no_login(jobs)
                    not_remote = 0
                    if remote_only():
                        kept, not_remote = filter_remote(kept)
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
                    filtered += dropped + not_remote
                    duplicates += skipped
                    saved += inserted
                    note.update(
                        {
                            "found": len(jobs),
                            "no_login": len(kept) + not_remote,
                            "remote": len(kept),
                            "not_remote": not_remote,
                            "new": inserted,
                            "duplicates": skipped,
                        }
                    )
                    notes.append(note)
                if have >= target or out_of_time:
                    break
            if have >= target or out_of_time:
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
            result["today_count"] = count_for_target(db, today)
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
