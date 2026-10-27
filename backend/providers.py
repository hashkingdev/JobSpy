from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Callable

from backend.config import (
    DAILY_INTERNATIONAL_HOST,
    JOB_POSTING_FEED_HOST,
    JOBS_API_HOST,
    OPEN_TO_WORK_HOST,
    RAPIDAPI_KEY,
    REMOTE_JOBS_ATS_HOST,
    REMOTE_JOBS_HOST,
)
from backend.jsearch import search_jsearch
from backend.rapidapi import (
    RapidAPIError,
    country_aliases,
    country_code,
    country_name,
    extract_items,
    pick_company,
    pick_location,
    pick_text,
    pick_title,
    pick_url,
    rapidapi_request,
    status,
    to_job,
)
from backend.schemas import SearchRequest

ProviderFn = Callable[[SearchRequest], tuple[list[dict[str, Any]], list[dict[str, Any]]]]

JOB_TYPE_MAP = {
    "fulltime": "fulltime",
    "parttime": "parttime",
    "contract": "contractor",
    "internship": "temporary",
}

FEED_WORK = {
    "remote": "Remote Solely,Remote OK",
    "hybrid": "Hybrid",
    "onsite": "On-site",
}

DAILY_WORK = {
    "remote": "remote",
    "hybrid": "hybrid",
    "onsite": "onsite",
}

DAILY_CONTRACT = {
    "fulltime": "permanent",
    "parttime": "parttime",
    "contract": "contract",
    "internship": "internship",
}


def search_jobs_api(payload: SearchRequest) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    code = country_code(payload.country)
    params: dict[str, Any] = {
        "query": payload.role,
        "countryCode": code,
        "location": country_name(code),
        "sortType": "date",
    }
    jobs: list[dict[str, Any]] = []
    token = None
    wanted = payload.results_wanted or 100
    pages = max(1, min(payload.num_pages or max(1, (wanted + 9) // 10), 20))
    last_error = None

    for _ in range(pages):
        page_params = dict(params)
        if token:
            page_params["token"] = token
        try:
            data = rapidapi_request(
                "GET",
                f"https://{JOBS_API_HOST}/v2/indeed/search",
                JOBS_API_HOST,
                params=page_params,
            )
        except RuntimeError as exc:
            last_error = str(exc)
            if not jobs and "403" not in last_error:
                jobs, last_error = _jobs_api_bing(payload)
            break
        page_jobs = []
        for raw in extract_items(data):
            if not isinstance(raw, dict):
                continue
            job = to_job(
                {
                    **raw,
                    "applyUrl": raw.get("applyUrl"),
                    "company": pick_company(raw),
                    "location": pick_location(raw, country_name(code)),
                },
                site="jobs-api",
                fallback_location=country_name(code),
            )
            if job:
                page_jobs.append(job)
        jobs.extend(page_jobs)
        token = (data.get("meta") or {}).get("nextToken") if isinstance(data, dict) else None
        if not token or not page_jobs:
            break
        if len(_unique(jobs)) >= wanted:
            break

    unique = _unique(jobs)[:wanted]
    return unique, [status("jobs-api", unique, last_error)]


def _jobs_api_bing(payload: SearchRequest) -> tuple[list[dict[str, Any]], str | None]:
    code = country_code(payload.country)
    params: dict[str, Any] = {
        "query": payload.role,
        "location": country_name(code),
        "datePosted": "day" if payload.date_posted in {"today", "3days"} else "week",
        "remoteOnly": "true" if payload.location_type == "remote" else "false",
    }
    if payload.job_type in JOB_TYPE_MAP:
        params["employmentTypes"] = JOB_TYPE_MAP[payload.job_type]
    try:
        data = rapidapi_request(
            "GET",
            f"https://{JOBS_API_HOST}/v2/bing/search",
            JOBS_API_HOST,
            params=params,
        )
    except RuntimeError as exc:
        return [], str(exc)

    jobs: list[dict[str, Any]] = []
    for raw in extract_items(data)[:20]:
        if not isinstance(raw, dict):
            continue
        job_id = raw.get("id")
        apply_url = pick_url(raw)
        if job_id and not apply_url:
            try:
                detail = rapidapi_request(
                    "GET",
                    f"https://{JOBS_API_HOST}/v2/bing/get",
                    JOBS_API_HOST,
                    params={"id": job_id},
                )
                detail_data = detail.get("data") if isinstance(detail, dict) else None
                if isinstance(detail_data, dict):
                    apply_url = pick_url(detail_data)
                    raw = {**raw, **detail_data, "applyUrl": apply_url}
            except RuntimeError:
                continue
        job = to_job(raw, site="jobs-api", fallback_location=country_name(code))
        if job:
            jobs.append(job)
    return jobs, None


def search_job_posting_feed(
    payload: SearchRequest,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    code = country_code(payload.country)
    time_frame = {
        "today": "24h",
        "3days": "7d",
        "week": "7d",
        "month": "7d",
    }.get(payload.date_posted, "24h")
    wanted = payload.results_wanted or 100
    limit = max(10, min(wanted, 100))
    params: dict[str, Any] = {
        "title": payload.role,
        "location": country_name(code),
        "time_frame": time_frame,
        "limit": str(limit),
        "offset": "0",
        "include_basic_organization_details": "true",
        "ai_work_arrangement": FEED_WORK.get(payload.location_type, "Remote OK"),
    }
    if payload.job_type:
        params["ai_employment_type"] = {
            "fulltime": "FULL_TIME",
            "parttime": "PART_TIME",
            "contract": "CONTRACTOR",
            "internship": "INTERN",
        }.get(payload.job_type)
        if not params["ai_employment_type"]:
            params.pop("ai_employment_type")

    hosts = (JOB_POSTING_FEED_HOST, "active-jobs-db.p.rapidapi.com")
    data = None
    error = None
    for host in hosts:
        try:
            data = rapidapi_request(
                "GET",
                f"https://{host}/active-ats",
                host,
                params=params,
            )
            error = None
            break
        except RapidAPIError as exc:
            error = error or str(exc)
            if exc.status_code not in {401, 403, 404}:
                break
    if data is None:
        return [], [status("job-posting-feed", [], error)]

    jobs = []
    for raw in extract_items(data):
        if not isinstance(raw, dict):
            continue
        job = to_job(
            raw,
            site="job-posting-feed",
            fallback_location=country_name(code),
        )
        if job:
            jobs.append(job)
    unique = _unique(jobs)[:wanted]
    return unique, [status("job-posting-feed", unique, error)]


def search_daily_international(
    payload: SearchRequest,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    code = country_code(payload.country)
    wanted = payload.results_wanted or 100
    pages = max(1, min(payload.num_pages or max(1, (wanted + 9) // 10), 20))
    jobs: list[dict[str, Any]] = []
    last_error = None
    today = date.today()
    date_created = {
        "today": today.isoformat(),
        "3days": (today - timedelta(days=2)).isoformat(),
        "week": today.strftime("%Y-%m"),
        "month": today.strftime("%Y-%m"),
    }.get(payload.date_posted, today.isoformat())

    for page in range(1, pages + 1):
        params: dict[str, Any] = {
            "format": "json",
            "countryCode": "uk" if code == "gb" else code,
            "title": payload.role,
            "workPlace": DAILY_WORK.get(payload.location_type, "remote"),
            "dateCreated": date_created,
            "page": str(page),
        }
        if payload.job_type in DAILY_CONTRACT:
            params["contractType"] = DAILY_CONTRACT[payload.job_type]
        try:
            data = rapidapi_request(
                "GET",
                f"https://{DAILY_INTERNATIONAL_HOST}/api/v2/jobs/search",
                DAILY_INTERNATIONAL_HOST,
                params=params,
                extra_headers={"Authorization": f"Bearer {RAPIDAPI_KEY}"},
            )
        except RuntimeError as exc:
            last_error = str(exc)
            break
        page_jobs = []
        for raw in extract_items(data):
            if not isinstance(raw, dict):
                continue
            json_ld = raw.get("jsonLD") if isinstance(raw.get("jsonLD"), dict) else {}
            merged = {**raw, **json_ld}
            location = pick_text(
                raw.get("city"),
                pick_location(merged),
                country_name(code),
            )
            job = {
                "job_url": pick_url(merged),
                "title": pick_title(merged),
                "company": pick_company(merged) or pick_text(raw.get("company")),
                "site": pick_text(raw.get("portal"), raw.get("source")) or "daily-international",
                "location": location,
                "job_type": pick_text(raw.get("contractType"), json_ld.get("employmentType")),
                "date_posted": pick_text(
                    raw.get("dateCreated"),
                    json_ld.get("datePosted"),
                ),
            }
            if job["job_url"]:
                page_jobs.append(job)
        jobs.extend(page_jobs)
        if not page_jobs:
            break
        if len(_unique(jobs)) >= wanted:
            break

    unique = _unique(jobs)[:wanted]
    return unique, [status("daily-international", unique, last_error)]


def search_remote_jobs(
    payload: SearchRequest,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    code = country_code(payload.country)
    jobs, error = _search_remote_jobs_api(payload, code)
    if not jobs:
        fallback, fallback_error = _search_remote_jobs_ats(payload, code)
        if fallback:
            return fallback, [status("remote-jobs", fallback)]
        error = error or fallback_error
    unique = _unique(jobs)
    return unique, [status("remote-jobs", unique, error)]


def _search_remote_jobs_api(
    payload: SearchRequest, code: str
) -> tuple[list[dict[str, Any]], str | None]:
    body = {
        "search": payload.role,
        "country": "usa" if code == "us" else country_name(code).lower(),
        "max_results": max(10, min((payload.num_pages or 1) * 10, 50)),
        "after": 0,
    }
    try:
        data = rapidapi_request(
            "POST",
            f"https://{REMOTE_JOBS_HOST}/jobs/search",
            REMOTE_JOBS_HOST,
            json_body=body,
        )
    except RuntimeError as exc:
        return [], str(exc)
    return _map_items(extract_items(data), "remote-jobs", country_name(code)), None


def _search_remote_jobs_ats(
    payload: SearchRequest, code: str
) -> tuple[list[dict[str, Any]], str | None]:
    params = {
        "title": payload.role,
        "countries": code,
    }
    try:
        data = rapidapi_request(
            "GET",
            f"https://{REMOTE_JOBS_ATS_HOST}/jobs",
            REMOTE_JOBS_ATS_HOST,
            params=params,
        )
    except RuntimeError:
        try:
            data = rapidapi_request(
                "POST",
                f"https://{REMOTE_JOBS_ATS_HOST}/jobs",
                REMOTE_JOBS_ATS_HOST,
                json_body={"title": payload.role, "countries": [code]},
            )
        except RuntimeError as exc:
            return [], str(exc)
    return _map_items(extract_items(data), "remote-jobs", country_name(code)), None


def search_open_to_work(
    payload: SearchRequest,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    code = country_code(payload.country)
    pages = max(1, min(payload.num_pages or 1, 10))
    jobs: list[dict[str, Any]] = []
    last_error = None
    paths = ("/jobs", "/api/jobs", "/v1/jobs", "/remote-jobs")
    working_path = None

    for page in range(1, pages + 1):
        params = {
            "title": payload.role,
            "location": country_name(code),
            "page": str(page),
            "perPage": "20",
        }
        data = None
        if working_path:
            try:
                data = rapidapi_request(
                    "GET",
                    f"https://{OPEN_TO_WORK_HOST}{working_path}",
                    OPEN_TO_WORK_HOST,
                    params=params,
                )
            except RapidAPIError as exc:
                last_error = str(exc)
                break
        else:
            for path in paths:
                try:
                    data = rapidapi_request(
                        "GET",
                        f"https://{OPEN_TO_WORK_HOST}{path}",
                        OPEN_TO_WORK_HOST,
                        params=params,
                    )
                    working_path = path
                    last_error = None
                    break
                except RapidAPIError as exc:
                    last_error = str(exc)
                    if exc.status_code in {401, 403, 429}:
                        break
                    continue
        if data is None:
            break
        page_jobs = _map_items(extract_items(data), "open-to-work", country_name(code))
        if not page_jobs and isinstance(data, dict):
            page_jobs = _map_items([data], "open-to-work", country_name(code))
        jobs.extend(page_jobs)
        if not page_jobs:
            break

    unique = _filter_remote_country(_unique(jobs), code)
    return unique, [status("open-to-work", unique, last_error)]


def _map_items(
    items: list[Any], site: str, fallback_location: str
) -> list[dict[str, Any]]:
    jobs = []
    for raw in items:
        if not isinstance(raw, dict):
            continue
        job = to_job(raw, site=site, fallback_location=fallback_location)
        if job:
            jobs.append(job)
    return jobs


def _filter_remote_country(jobs: list[dict[str, Any]], code: str) -> list[dict[str, Any]]:
    aliases = country_aliases(code)
    filtered = []
    for job in jobs:
        location = (job.get("location") or "").lower()
        if not location or any(alias in location for alias in aliases) or "remote" in location:
            filtered.append(job)
    return filtered or jobs


def _unique(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for job in jobs:
        key = (job.get("job_url") or "").strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(job)
    return unique


PROVIDERS: dict[str, ProviderFn] = {
    "jsearch": search_jsearch,
    "jobs-api": search_jobs_api,
    "job-posting-feed": search_job_posting_feed,
    "daily-international": search_daily_international,
    "remote-jobs": search_remote_jobs,
    "open-to-work": search_open_to_work,
}
