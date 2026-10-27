from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import requests

from backend.config import (
    JSEARCH_COUNTRY,
    JSEARCH_DATE_POSTED,
    JSEARCH_NUM_PAGES,
    JSEARCH_QUERY,
    JSEARCH_SEARCH_URL,
    RAPIDAPI_HOST,
    RAPIDAPI_KEY,
)
from backend.schemas import CustomBoard, SearchRequest

COUNTRY_CODES = {
    "usa": "us",
    "us": "us",
    "united states": "us",
    "canada": "ca",
    "uk": "gb",
    "united kingdom": "gb",
    "germany": "de",
    "france": "fr",
    "india": "in",
    "australia": "au",
    "netherlands": "nl",
    "ireland": "ie",
    "singapore": "sg",
}

COUNTRY_NAMES = {
    "us": "United States",
    "ca": "Canada",
    "gb": "United Kingdom",
    "de": "Germany",
    "fr": "France",
    "in": "India",
    "au": "Australia",
    "nl": "Netherlands",
    "ie": "Ireland",
    "sg": "Singapore",
}

DATE_POSTED = {
    "today": "today",
    "3days": "3days",
    "72h": "3days",
    "week": "week",
    "month": "month",
}

EMPLOYMENT_TYPES = {
    "fulltime": "FULLTIME",
    "parttime": "PARTTIME",
    "contract": "CONTRACTOR",
    "internship": "INTERN",
}

SITE_ALIASES = {
    "linkedin": ("linkedin",),
    "indeed": ("indeed",),
    "zip_recruiter": ("ziprecruiter", "zip recruiter"),
    "glassdoor": ("glassdoor",),
    "google": ("google",),
    "bayt": ("bayt",),
    "naukri": ("naukri",),
    "bdjobs": ("bdjobs", "bd jobs"),
}


def search_jsearch(payload: SearchRequest) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not RAPIDAPI_KEY:
        raise ValueError("RAPIDAPI_KEY is missing. Add it to backend/.env")

    country = COUNTRY_CODES.get((payload.country or JSEARCH_COUNTRY).lower(), JSEARCH_COUNTRY)
    date_posted = DATE_POSTED.get(payload.date_posted, JSEARCH_DATE_POSTED)
    roles = [part.strip() for part in payload.role.split(",") if part.strip()] or [
        JSEARCH_QUERY.split(" in ")[0]
    ]
    wanted = payload.results_wanted or 100
    pages = max(1, min(20, payload.num_pages or max(JSEARCH_NUM_PAGES, (wanted + 9) // 10)))
    jobs_by_url: dict[str, dict[str, Any]] = {}
    site_status: list[dict[str, Any]] = []

    for role in roles:
        query = _build_query(role, country, payload.location_type)
        params = {
            "query": query,
            "country": country,
            "date_posted": date_posted,
            "num_pages": str(pages),
            "work_from_home": "true" if payload.location_type == "remote" else "false",
        }
        if payload.job_type in EMPLOYMENT_TYPES:
            params["employment_types"] = EMPLOYMENT_TYPES[payload.job_type]

        raw_jobs = _request_jobs(params)
        matched, unmatched = _map_jobs(raw_jobs, payload)
        chosen = matched or unmatched
        for job in chosen:
            jobs_by_url[job["job_url"]] = job
        site_status.append(
            {
                "site": "jsearch",
                "count": len(chosen),
                "error": None if chosen else "JSearch returned no jobs for this query",
            }
        )

    jobs = list(jobs_by_url.values())
    if payload.results_wanted:
        jobs = jobs[: payload.results_wanted]
    return jobs, site_status


def _build_query(role: str, country: str, location_type: str) -> str:
    place = COUNTRY_NAMES.get(country, "United States")
    if location_type == "hybrid":
        return f"{role} hybrid in {place}"
    if location_type == "onsite":
        return f"{role} onsite in {place}"
    return f"{role} in {place}"


def _request_jobs(params: dict[str, str]) -> list[dict[str, Any]]:
    response = requests.get(
        JSEARCH_SEARCH_URL,
        headers={
            "X-RapidAPI-Key": RAPIDAPI_KEY,
            "X-RapidAPI-Host": RAPIDAPI_HOST,
        },
        params=params,
        timeout=60,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"JSearch error {response.status_code}: {response.text[:300]}")
    payload = response.json()
    if payload.get("status") not in (None, "OK"):
        raise RuntimeError(f"JSearch status: {payload.get('status')}")
    data = payload.get("data")
    if isinstance(data, dict):
        return data.get("jobs") or []
    if isinstance(data, list):
        return data
    return []


def _map_jobs(
    raw_jobs: list[dict[str, Any]], payload: SearchRequest
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    selected = set(payload.sites or [])
    matched: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []
    for raw in raw_jobs:
        job = _to_job(raw, selected, payload.custom_boards)
        if not job:
            continue
        if selected and job.get("matched_site"):
            matched.append(job)
        else:
            unmatched.append(job)
    return matched, unmatched


def _to_job(
    raw: dict[str, Any],
    selected: set[str],
    custom_boards: list[CustomBoard],
) -> dict[str, Any] | None:
    apply_link = raw.get("job_apply_link") or raw.get("job_google_link")
    site = _match_publisher(raw.get("job_publisher"), selected, custom_boards)
    for option in raw.get("apply_options") or []:
        option_site = _match_publisher(option.get("publisher"), selected, custom_boards)
        if option_site and option.get("apply_link"):
            site = option_site
            apply_link = option.get("apply_link")
            break
    if not apply_link:
        return None

    location_parts = [raw.get("job_city"), raw.get("job_state"), raw.get("job_country")]
    location = raw.get("job_location") or ", ".join(part for part in location_parts if part)
    return {
        "job_url": apply_link,
        "title": raw.get("job_title"),
        "company": raw.get("employer_name"),
        "site": site or raw.get("job_publisher") or "jsearch",
        "location": location or None,
        "job_type": raw.get("job_employment_type"),
        "date_posted": raw.get("job_posted_at_datetime_utc") or raw.get("job_posted_at"),
        "matched_site": bool(site),
    }


def _match_publisher(
    publisher: str | None,
    selected: set[str],
    custom_boards: list[CustomBoard],
) -> str | None:
    if not publisher or not selected:
        return None
    lowered = publisher.lower()
    for site_id in selected:
        aliases = SITE_ALIASES.get(site_id)
        if aliases and any(alias in lowered for alias in aliases):
            return site_id
        if site_id.replace("_", " ") in lowered:
            return site_id
    for board in custom_boards:
        if board.id not in selected:
            continue
        labels = [board.id.replace("_", " "), board.label.lower()]
        if board.url:
            host = urlparse(board.url).netloc.lower().removeprefix("www.")
            if host:
                labels.append(host)
                labels.append(host.split(".")[0])
        if any(label and label in lowered for label in labels):
            return board.id
    return None
