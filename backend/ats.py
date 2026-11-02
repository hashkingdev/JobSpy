"""Company career boards hosted on Greenhouse, Lever and Ashby.

These applicant tracking systems publish every company's open roles through a
public JSON endpoint that needs no API key, has no monthly quota, and links
straight to the employer's own posting, which opens and accepts applications
without an account.  The list of boards lives in ``ats_boards.json`` next to
this file and can be extended with ``ATS_BOARDS_EXTRA``.
"""

from __future__ import annotations

import html
import json
import logging
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests

from backend.config import (
    ATS_BOARDS_EXTRA,
    ATS_BOARDS_FILE,
    ATS_CACHE_MINUTES,
    ATS_DETAIL_LIMIT,
    ATS_WORKERS,
)
from backend.rapidapi import country_aliases, country_code
from backend.remote import remote_verdict
from backend.schemas import SearchRequest

log = logging.getLogger(__name__)

SOURCE_ID = "company-boards"
ATS_NAMES = ("greenhouse", "lever", "ashby")
TIMEOUT = 20

WINDOW_DAYS = {"today": 1, "3days": 3, "week": 7, "month": 31}

_session = requests.Session()
_session.headers["User-Agent"] = "Mozilla/5.0 (compatible; JobSpy job-link collector)"

_cache_lock = threading.Lock()
_board_cache: dict[tuple[str, str], tuple[float, list[dict[str, Any]]]] = {}
_detail_cache: dict[str, tuple[float, str]] = {}
DETAIL_TTL = 6 * 3600

_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")

# Country and region words used to tell "Remote - Canada" from "Remote - US".
FOREIGN_PLACES = {
    "canada", "toronto", "vancouver", "montreal", "united kingdom", "uk", "england", "london",
    "scotland", "ireland", "dublin", "germany", "berlin", "munich", "france", "paris", "spain",
    "madrid", "barcelona", "portugal", "lisbon", "netherlands", "amsterdam", "belgium", "poland",
    "warsaw", "krakow", "czech", "prague", "hungary", "romania", "bulgaria", "ukraine", "sweden",
    "stockholm", "norway", "denmark", "copenhagen", "finland", "switzerland", "zurich", "austria",
    "italy", "milan", "greece", "turkey", "israel", "tel aviv", "uae", "dubai", "india",
    "bangalore", "bengaluru", "hyderabad", "pune", "mumbai", "delhi", "chennai", "pakistan",
    "singapore", "philippines", "manila", "vietnam", "indonesia", "malaysia", "thailand", "japan",
    "tokyo", "korea", "seoul", "china", "shanghai", "beijing", "hong kong", "taiwan", "australia",
    "sydney", "melbourne", "new zealand", "auckland", "brazil", "sao paulo", "são paulo", "mexico",
    "argentina", "buenos aires", "colombia", "chile", "peru", "costa rica", "nigeria", "kenya",
    "south africa", "egypt", "latam", "emea", "apac", "europe", "european", "asia", "africa",
    "cet", "gmt", "bst",
}

SYNONYMS = {
    "developer": "engineer",
    "developers": "engineer",
    "engineers": "engineer",
    "programmer": "engineer",
    "fullstack": "fullstack",
    "full": "full",
    "stack": "stack",
    "frontend": "frontend",
    "front": "front",
    "end": "end",
    "backend": "backend",
    "back": "back",
    "nodejs": "node",
    "node": "node",
    "js": "javascript",
    "javascript": "javascript",
    "reactjs": "react",
    "react": "react",
    "sr": "senior",
    "senior": "senior",
}

COMPOUNDS = (
    ("full stack", "fullstack"),
    ("front end", "frontend"),
    ("back end", "backend"),
    ("node js", "node"),
    ("react js", "react"),
    ("vue js", "vue"),
    ("next js", "nextjs"),
    ("type script", "typescript"),
)


def _tokens(text: str) -> set[str]:
    lowered = re.sub(r"[-./_]+", " ", (text or "").lower())
    lowered = re.sub(r"[^a-z0-9+# ]+", " ", lowered)
    lowered = _WS.sub(" ", lowered).strip()
    for phrase, canon in COMPOUNDS:
        lowered = lowered.replace(phrase, canon)
    return {SYNONYMS.get(tok, tok) for tok in lowered.split() if tok}


def role_matches(role: str, title: str) -> bool:
    """Every word of the role (after synonyms) must appear in the title."""
    wanted = _tokens(role)
    if not wanted:
        return True
    return wanted <= _tokens(title)


def _plain(text: str | None, limit: int = 4000) -> str | None:
    if not text:
        return None
    # Greenhouse ships its HTML entity-escaped, so unescape before stripping tags
    # (twice, in case the text was escaped twice).
    cleaned = html.unescape(html.unescape(text))
    cleaned = _WS.sub(" ", html.unescape(_TAG.sub(" ", cleaned))).strip()
    return cleaned[:limit] or None


def _parse_time(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    try:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value / 1000 if value > 1e11 else value, tz=timezone.utc)
        text = str(value).strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except (ValueError, TypeError, OverflowError):
        return None


def pretty_name(slug: str) -> str:
    return " ".join(part.capitalize() for part in re.split(r"[-_]+", slug) if part)


# ---------------------------------------------------------------------------
# Board list
# ---------------------------------------------------------------------------


def load_boards() -> list[dict[str, str]]:
    """Boards from ats_boards.json plus ATS_BOARDS_EXTRA ("greenhouse:slug,lever:slug")."""
    boards: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def add(ats: str, slug: str, name: str | None = None) -> None:
        ats = (ats or "").strip().lower()
        slug = (slug or "").strip()
        if ats not in ATS_NAMES or not slug or (ats, slug) in seen:
            return
        seen.add((ats, slug))
        boards.append({"ats": ats, "slug": slug, "name": name or pretty_name(slug)})

    path = Path(ATS_BOARDS_FILE) if ATS_BOARDS_FILE else Path(__file__).with_name("ats_boards.json")
    try:
        for item in json.loads(path.read_text(encoding="utf-8")):
            if isinstance(item, dict):
                add(item.get("ats", ""), item.get("slug", ""), item.get("name"))
    except (OSError, ValueError) as exc:
        log.warning("ats: could not read %s: %s", path, exc)

    for part in (ATS_BOARDS_EXTRA or "").split(","):
        if ":" in part:
            ats, slug = part.split(":", 1)
            add(ats, slug)
    return boards


# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------


def _get_json(url: str, params: dict[str, str] | None = None) -> Any:
    response = _session.get(url, params=params, timeout=TIMEOUT)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.json()


def _greenhouse(board: dict[str, str]) -> list[dict[str, Any]]:
    data = _get_json(f"https://boards-api.greenhouse.io/v1/boards/{board['slug']}/jobs")
    jobs = []
    for raw in (data or {}).get("jobs", []) if isinstance(data, dict) else []:
        url = raw.get("absolute_url")
        if not url:
            continue
        jobs.append(
            {
                "job_url": url,
                "title": raw.get("title"),
                "company": raw.get("company_name") or board["name"],
                "site": "greenhouse",
                "location": (raw.get("location") or {}).get("name"),
                "job_type": None,
                "work_arrangement": None,
                "remote": None,
                "job_description": None,
                "_posted": _parse_time(raw.get("updated_at") or raw.get("first_published")),
                "_detail": f"https://boards-api.greenhouse.io/v1/boards/{board['slug']}/jobs/{raw.get('id')}",
            }
        )
    return jobs


def _lever(board: dict[str, str]) -> list[dict[str, Any]]:
    data = _get_json(f"https://api.lever.co/v0/postings/{board['slug']}", {"mode": "json"})
    jobs = []
    for raw in data if isinstance(data, list) else []:
        url = raw.get("hostedUrl") or raw.get("applyUrl")
        if not url:
            continue
        cats = raw.get("categories") or {}
        places = cats.get("allLocations") or [cats.get("location")]
        arrangement = (raw.get("workplaceType") or "").lower() or None
        remote = {"remote": True, "hybrid": False, "onsite": False, "on-site": False}.get(arrangement)
        jobs.append(
            {
                "job_url": url,
                "title": raw.get("text"),
                "company": board["name"],
                "site": "lever",
                "location": ", ".join(p for p in places if p) or raw.get("country"),
                "job_type": cats.get("commitment"),
                "work_arrangement": arrangement,
                "remote": remote,
                "job_description": _plain(raw.get("descriptionPlain") or raw.get("descriptionBodyPlain") or raw.get("description")),
                "_posted": _parse_time(raw.get("createdAt")),
            }
        )
    return jobs


def _ashby(board: dict[str, str]) -> list[dict[str, Any]]:
    data = _get_json(f"https://api.ashbyhq.com/posting-api/job-board/{board['slug']}")
    jobs = []
    for raw in (data or {}).get("jobs", []) if isinstance(data, dict) else []:
        url = raw.get("jobUrl") or raw.get("applyUrl")
        if not url or raw.get("isListed") is False:
            continue
        places = [raw.get("location")] + [
            (extra or {}).get("location") for extra in raw.get("secondaryLocations") or []
        ]
        arrangement = raw.get("workplaceType")
        remote: bool | None = None
        if raw.get("isRemote") is True or (arrangement or "").lower() == "remote":
            remote = True
        elif (arrangement or "").lower() in {"hybrid", "onsite", "on-site"}:
            remote = False
        jobs.append(
            {
                "job_url": url,
                "title": raw.get("title"),
                "company": board["name"],
                "site": "ashby",
                "location": ", ".join(p for p in places if p) or None,
                "job_type": raw.get("employmentType"),
                "work_arrangement": arrangement,
                "remote": remote,
                "job_description": _plain(raw.get("descriptionPlain") or raw.get("descriptionHtml")),
                "_posted": _parse_time(raw.get("publishedAt")),
            }
        )
    return jobs


FETCHERS = {"greenhouse": _greenhouse, "lever": _lever, "ashby": _ashby}


def fetch_board(board: dict[str, str]) -> list[dict[str, Any]]:
    key = (board["ats"], board["slug"])
    now = time.time()
    with _cache_lock:
        cached = _board_cache.get(key)
    if cached and now - cached[0] < ATS_CACHE_MINUTES * 60:
        return cached[1]
    jobs = FETCHERS[board["ats"]](board)
    with _cache_lock:
        _board_cache[key] = (now, jobs)
    return jobs


def fetch_all(boards: list[dict[str, str]]) -> tuple[list[dict[str, Any]], int, str | None]:
    """Fetch every board in parallel. Returns (jobs, failed_boards, last_error)."""
    jobs: list[dict[str, Any]] = []
    failed = 0
    last_error: str | None = None
    with ThreadPoolExecutor(max_workers=max(1, ATS_WORKERS)) as pool:
        for board, result in zip(boards, pool.map(_safe_fetch, boards)):
            if isinstance(result, str):
                failed += 1
                last_error = f"{board['ats']}/{board['slug']}: {result}"
            else:
                jobs.extend(result)
    return jobs, failed, last_error


def _safe_fetch(board: dict[str, str]) -> list[dict[str, Any]] | str:
    try:
        return fetch_board(board)
    except Exception as exc:  # one dead board must not sink the rest
        return str(exc)[:200]


def _greenhouse_description(job: dict[str, Any]) -> None:
    url = job.get("_detail")
    if not url or job.get("job_description"):
        return
    now = time.time()
    with _cache_lock:
        cached = _detail_cache.get(url)
    if cached and now - cached[0] < DETAIL_TTL:
        job["job_description"] = cached[1]
        return
    try:
        data = _get_json(url)
        text = _plain((data or {}).get("content")) or ""
    except Exception as exc:
        log.debug("ats: detail fetch failed for %s: %s", url, exc)
        return
    with _cache_lock:
        _detail_cache[url] = (now, text)
    job["job_description"] = text or None


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------


def location_in_country(location: str | None, code: str) -> bool:
    """True unless the location clearly names a different country or region."""
    text = (location or "").lower()
    if not text:
        return True
    if any(re.search(rf"\b{re.escape(alias)}\b", text) for alias in country_aliases(code)):
        return True
    if code == "us" and re.search(r"\b(north america|americas|us-based|u\.s\.)\b", text):
        return True
    return not any(re.search(rf"\b{re.escape(place)}\b", text) for place in FOREIGN_PLACES)


def _within(job: dict[str, Any], days: int | None) -> bool:
    if not days:
        return True
    posted = job.get("_posted")
    if posted is None:
        return True
    return posted >= datetime.now(timezone.utc) - timedelta(days=days)


def _arrangement_ok(job: dict[str, Any], location_type: str) -> bool:
    if location_type == "remote":
        return remote_verdict(job)[0]
    text = " ".join(str(job.get(k) or "") for k in ("title", "location", "work_arrangement")).lower()
    if location_type == "hybrid":
        return "hybrid" in text
    return not remote_verdict(job)[0]


def search_company_boards(
    payload: SearchRequest,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    boards = load_boards()
    if not boards:
        return [], [{"site": SOURCE_ID, "count": 0, "error": "no company boards configured"}]

    all_jobs, failed, last_error = fetch_all(boards)
    code = country_code(payload.country)
    days = WINDOW_DAYS.get(payload.date_posted)

    candidates = [
        job
        for job in all_jobs
        if role_matches(payload.role, job.get("title") or "")
        and location_in_country(job.get("location"), code)
        and _within(job, days)
    ]
    candidates.sort(key=lambda job: job.get("_posted") or datetime.min.replace(tzinfo=timezone.utc), reverse=True)

    # Greenhouse lists carry no description; pull it for the candidates so the
    # remote filter can see "hybrid" or "remote" wording in the body.
    needing = [job for job in candidates if job.get("_detail") and not job.get("job_description")]
    if needing:
        with ThreadPoolExecutor(max_workers=max(1, ATS_WORKERS)) as pool:
            list(pool.map(_greenhouse_description, needing[:ATS_DETAIL_LIMIT]))

    jobs: list[dict[str, Any]] = []
    seen: set[str] = set()
    limit = payload.results_wanted or 100
    for job in candidates:
        if not _arrangement_ok(job, payload.location_type):
            continue
        key = job["job_url"].strip().lower()
        if key in seen:
            continue
        seen.add(key)
        posted = job.get("_posted")
        clean = {k: v for k, v in job.items() if not k.startswith("_")}
        clean["date_posted"] = posted.date().isoformat() if posted else None
        jobs.append(clean)
        if len(jobs) >= limit:
            break

    error = None
    if not jobs:
        if failed == len(boards):
            error = f"company boards unreachable: {last_error}"
        else:
            error = f"{SOURCE_ID} returned no jobs for this query"
    note = {
        "site": SOURCE_ID,
        "count": len(jobs),
        "error": error,
        "boards": len(boards),
        "boards_failed": failed,
        "matched": len(candidates),
    }
    return jobs, [note]
