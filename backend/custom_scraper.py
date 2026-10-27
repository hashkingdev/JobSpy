from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup
import pandas as pd

from jobspy import scrape_jobs
from jobspy.util import create_session

from backend.schemas import CustomBoard, SearchRequest

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

JOB_HREF_HINTS = (
    "/job/",
    "/jobs/",
    "/job?",
    "/careers/",
    "/career/",
    "/position",
    "/opening",
    "/vacancy",
    "/vacancies",
    "viewjob",
    "jobid",
    "job_id",
    "jk=",
    "gh_jid",
)

SKIP_HREF = (
    "javascript:",
    "mailto:",
    "tel:",
    "/login",
    "/signup",
    "/register",
    "/privacy",
    "/terms",
    "/cookie",
)

SKIP_TEXT = {
    "learn more",
    "read more",
    "apply",
    "apply now",
    "see all",
    "view all",
    "log in",
    "sign in",
    "sign up",
}


def scrape_custom_board(
    board: CustomBoard,
    payload: SearchRequest,
    role: str,
    location: str,
    hours_old: int,
    job_type: str | None,
) -> list[dict[str, Any]]:
    jobs_by_url: dict[str, dict[str, Any]] = {}
    for job in _scrape_via_google(board, payload, role, location, hours_old, job_type):
        jobs_by_url[job["job_url"]] = job
    if board.url:
        for job in _scrape_via_html(board, role, location, payload.results_wanted):
            jobs_by_url.setdefault(job["job_url"], job)
    return list(jobs_by_url.values())[: payload.results_wanted]


def _scrape_via_google(
    board: CustomBoard,
    payload: SearchRequest,
    role: str,
    location: str,
    hours_old: int,
    job_type: str | None,
) -> list[dict[str, Any]]:
    domain = _domain(board.url)
    term = f"{role} jobs"
    if domain:
        term += f" site:{domain}"
    else:
        term += f" {board.label}"
    if payload.location_type == "remote":
        term += " remote"
    elif payload.location_type == "hybrid":
        term += " hybrid"
    if location:
        term += f" in {location}"

    try:
        frame = scrape_jobs(
            site_name=["google"],
            search_term=role,
            google_search_term=term,
            location=None if payload.location_type == "remote" else location,
            is_remote=payload.location_type == "remote",
            results_wanted=payload.results_wanted,
            hours_old=hours_old,
            country_indeed=payload.country or "usa",
            job_type=job_type,
            verbose=0,
        )
    except Exception:
        return []

    if frame is None or frame.empty:
        return []

    jobs = []
    for record in frame.replace({pd.NA: None}).to_dict(orient="records"):
        job_url = _as_str(record.get("job_url")) or _as_str(record.get("job_url_direct"))
        if not job_url:
            continue
        jobs.append(
            {
                "job_url": job_url,
                "title": _as_str(record.get("title")),
                "company": _as_str(record.get("company")),
                "site": board.id,
                "location": _as_str(record.get("location")),
                "job_type": _as_str(record.get("job_type")),
                "date_posted": _as_str(record.get("date_posted")),
                "job_description": _as_str(record.get("description")),
            }
        )
    return jobs


def _scrape_via_html(
    board: CustomBoard, role: str, location: str, results_wanted: int
) -> list[dict[str, Any]]:
    session = create_session(is_tls=False, has_retry=True)
    session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"})
    jobs_by_url: dict[str, dict[str, Any]] = {}

    for page_url in _search_urls(board.url, role, location):
        try:
            response = session.get(page_url, timeout=20, allow_redirects=True)
            response.raise_for_status()
        except Exception:
            continue
        soup = BeautifulSoup(response.text, "html.parser")
        for job in _jobs_from_json_ld(soup, board):
            jobs_by_url.setdefault(job["job_url"], job)
        for job in _jobs_from_links(soup, response.url, board):
            jobs_by_url.setdefault(job["job_url"], job)
        if len(jobs_by_url) >= results_wanted:
            break

    return list(jobs_by_url.values())[:results_wanted]


def _search_urls(base_url: str, role: str, location: str) -> list[str]:
    filled = (
        base_url.replace("{role}", role)
        .replace("{query}", role)
        .replace("{location}", location or "")
    )
    parsed = urlparse(filled)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    urls = [filled]
    if "{" not in base_url:
        urls.extend(
            [
                _with_query(filled, {"q": role}),
                f"{origin}/jobs?q={_quote(role)}",
                f"{origin}/jobs/search?q={_quote(role)}",
                f"{origin}/careers?q={_quote(role)}",
                f"{origin}/search?q={_quote(role)}",
            ]
        )
    unique: list[str] = []
    seen: set[str] = set()
    for url in urls:
        if url not in seen:
            seen.add(url)
            unique.append(url)
    return unique[:5]


def _jobs_from_json_ld(soup: BeautifulSoup, board: CustomBoard) -> list[dict[str, Any]]:
    jobs = []
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        if not script.string:
            continue
        try:
            payload = json.loads(script.string)
        except json.JSONDecodeError:
            continue
        for item in _walk_json(payload):
            types = item.get("@type")
            type_names = types if isinstance(types, list) else [types]
            if "JobPosting" not in type_names:
                continue
            url = item.get("url") or item.get("applicationUrl")
            title = item.get("title")
            if not url or not title:
                continue
            org = item.get("hiringOrganization") or {}
            company = org.get("name") if isinstance(org, dict) else None
            jobs.append(
                {
                    "job_url": str(url),
                    "title": str(title),
                    "company": str(company) if company else None,
                    "site": board.id,
                    "location": _json_ld_location(item),
                    "job_type": None,
                    "date_posted": str(item["datePosted"]) if item.get("datePosted") else None,
                    "job_description": _as_str(item.get("description")),
                }
            )
    return jobs


def _jobs_from_links(
    soup: BeautifulSoup, page_url: str, board: CustomBoard
) -> list[dict[str, Any]]:
    page_host = _domain(page_url)
    jobs = []
    seen: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        href = urljoin(page_url, anchor["href"])
        text = " ".join(anchor.get_text(" ", strip=True).split())
        if not _looks_like_job_link(href, text, page_host):
            continue
        if href in seen:
            continue
        seen.add(href)
        title = text if 8 <= len(text) <= 180 else text or href
        jobs.append(
            {
                "job_url": href,
                "title": title[:500],
                "company": None,
                "site": board.id,
                "location": None,
                "job_type": None,
                "date_posted": None,
                "job_description": None,
            }
        )
    return jobs


def _looks_like_job_link(href: str, text: str, page_host: str | None) -> bool:
    lowered = href.lower()
    if lowered.startswith(("javascript:", "mailto:", "tel:")):
        return False
    if any(part in lowered for part in SKIP_HREF):
        return False
    if text.lower() in SKIP_TEXT:
        return False
    host = _domain(href)
    if page_host and host and host != page_host and not host.endswith(f".{page_host}"):
        return False
    if any(hint in lowered for hint in JOB_HREF_HINTS):
        return True
    return bool(page_host and host == page_host and 12 <= len(text) <= 120)


def _walk_json(data: Any):
    if isinstance(data, list):
        for item in data:
            yield from _walk_json(item)
    elif isinstance(data, dict):
        yield data
        if "@graph" in data:
            yield from _walk_json(data["@graph"])
        if "itemListElement" in data:
            yield from _walk_json(data["itemListElement"])
        if "item" in data:
            yield from _walk_json(data["item"])


def _json_ld_location(item: dict[str, Any]) -> str | None:
    location = item.get("jobLocation")
    if isinstance(location, list) and location:
        location = location[0]
    if not isinstance(location, dict):
        return None
    address = location.get("address")
    if isinstance(address, str):
        return address
    if isinstance(address, dict):
        parts = [
            address.get("addressLocality"),
            address.get("addressRegion"),
            address.get("addressCountry"),
        ]
        return ", ".join(part for part in parts if part) or None
    return None


def _domain(url: str | None) -> str | None:
    if not url:
        return None
    host = urlparse(url).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return host or None


def _with_query(url: str, extra: dict[str, str]) -> str:
    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query.update(extra)
    return urlunparse(parsed._replace(query=urlencode(query)))


def _quote(value: str) -> str:
    return urlencode({"q": value})[2:]


def _as_str(value: Any) -> str | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    return text or None
