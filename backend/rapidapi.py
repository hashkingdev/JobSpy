from __future__ import annotations

from typing import Any

import requests

from backend.config import RAPIDAPI_KEY

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
    "uk": "United Kingdom",
    "de": "Germany",
    "fr": "France",
    "in": "India",
    "au": "Australia",
    "nl": "Netherlands",
    "ie": "Ireland",
    "sg": "Singapore",
}

COUNTRY_ALIASES = {
    "us": ("us", "usa", "united states"),
    "ca": ("ca", "canada"),
    "gb": ("gb", "uk", "united kingdom"),
    "de": ("de", "germany"),
    "fr": ("fr", "france"),
    "in": ("in", "india"),
    "au": ("au", "australia"),
    "nl": ("nl", "netherlands"),
    "ie": ("ie", "ireland"),
    "sg": ("sg", "singapore"),
}

URL_KEYS = (
    "job_url",
    "applyUrl",
    "apply_url",
    "applicationUrl",
    "url_direct",
    "externalApplyUrl",
    "url",
    "link",
    "jobUrl",
    "href",
)


def country_code(value: str | None, default: str = "us") -> str:
    return COUNTRY_CODES.get((value or default).lower(), default)


def country_name(code: str) -> str:
    return COUNTRY_NAMES.get(code, "United States")


def country_aliases(code: str) -> tuple[str, ...]:
    return COUNTRY_ALIASES.get(code, (code,))


SUBSCRIBE_HINTS = {
    "jobs-api14.p.rapidapi.com": "https://rapidapi.com/Pat92/api/jobs-api14",
    "job-posting-feed-api.p.rapidapi.com": "https://rapidapi.com/fantastic-jobs-fantastic-jobs-default/api/job-posting-feed-api",
    "active-jobs-db.p.rapidapi.com": "https://rapidapi.com/fantastic-jobs-fantastic-jobs-default/api/active-jobs-db",
    "daily-international-job-postings.p.rapidapi.com": "https://rapidapi.com/techmap-io-techmap-io-default/api/daily-international-job-postings",
    "remote-jobs-api1.p.rapidapi.com": "https://rapidapi.com/bareq/api/remote-jobs-api1",
    "remote-jobs1.p.rapidapi.com": "https://rapidapi.com/remote-jobs-remote-jobs-default/api/remote-jobs1",
    "open-to-work-remote-api.p.rapidapi.com": "https://rapidapi.com/maurobonfietti/api/open-to-work-remote-api",
}


class RapidAPIError(RuntimeError):
    def __init__(self, host: str, status_code: int, body: str):
        self.host = host
        self.status_code = status_code
        self.body = body
        super().__init__(format_rapidapi_error(host, status_code, body))


def require_key() -> str:
    if not RAPIDAPI_KEY:
        raise ValueError("RAPIDAPI_KEY is missing. Add it to backend/.env")
    return RAPIDAPI_KEY


def format_rapidapi_error(host: str, status_code: int, body: str) -> str:
    subscribe = SUBSCRIBE_HINTS.get(host)
    lowered = (body or "").lower()
    if status_code == 403 and "not subscribed" in lowered:
        if subscribe:
            return f"Subscribe to this API on RapidAPI first: {subscribe}"
        return f"This RapidAPI key is not subscribed to {host}."
    if status_code == 429:
        return f"{host} rate-limited this key. Wait a minute and search again."
    return f"{host} error {status_code}: {body[:300]}"


def rapidapi_request(
    method: str,
    url: str,
    host: str,
    *,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
    extra_headers: dict[str, str] | None = None,
    timeout: int = 60,
) -> Any:
    headers = {
        "X-RapidAPI-Key": require_key(),
        "X-RapidAPI-Host": host,
        "Accept": "application/json",
    }
    if extra_headers:
        headers.update(extra_headers)
    response = requests.request(
        method,
        url,
        headers=headers,
        params=params,
        json=json_body,
        timeout=timeout,
    )
    if response.status_code >= 400:
        raise RapidAPIError(host, response.status_code, response.text[:400])
    if not response.content:
        return {}
    try:
        return response.json()
    except ValueError as exc:
        raise RuntimeError(f"{host} returned a non-JSON response") from exc


def extract_items(payload: Any) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    for key in ("data", "jobs", "results", "result", "items", "records"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            nested = extract_items(value)
            if nested:
                return nested
    return []


def first_http_url(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str) and value.startswith(("http://", "https://")):
            return value
        if isinstance(value, dict):
            found = pick_url(value)
            if found:
                return found
        if isinstance(value, list):
            for item in value:
                found = first_http_url(item)
                if found:
                    return found
    return None


def pick_url(raw: dict[str, Any]) -> str | None:
    for key in URL_KEYS:
        found = first_http_url(raw.get(key))
        if found:
            return found
    for key in ("jobProviders", "job_providers", "providers", "apply_options"):
        found = first_http_url(raw.get(key))
        if found:
            return found
    json_ld = raw.get("jsonLD") or raw.get("jsonLd") or raw.get("jsonld")
    if isinstance(json_ld, dict):
        return pick_url(json_ld)
    return None


def pick_text(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, dict):
            found = pick_text(
                value.get("name"),
                value.get("title"),
                value.get("location"),
                value.get("city"),
                value.get("label"),
            )
            if found:
                return found
        if isinstance(value, list):
            parts = [pick_text(item) for item in value]
            joined = ", ".join(part for part in parts if part)
            if joined:
                return joined
    return None


def pick_company(raw: dict[str, Any]) -> str | None:
    return pick_text(
        raw.get("company"),
        raw.get("companyName"),
        raw.get("company_name"),
        raw.get("organization"),
        raw.get("employer"),
        raw.get("employer_name"),
        raw.get("hiringOrganization"),
    )


def pick_title(raw: dict[str, Any]) -> str | None:
    return pick_text(
        raw.get("title"),
        raw.get("job_title"),
        raw.get("position"),
        raw.get("role"),
        raw.get("name"),
    )


def pick_location(raw: dict[str, Any], fallback: str | None = None) -> str | None:
    return (
        pick_text(
            raw.get("location"),
            raw.get("job_location"),
            raw.get("city"),
            raw.get("locations_derived"),
            raw.get("countries"),
            raw.get("country"),
        )
        or fallback
    )


def to_job(
    raw: dict[str, Any],
    *,
    site: str,
    fallback_location: str | None = None,
) -> dict[str, Any] | None:
    url = pick_url(raw)
    if not url:
        return None
    return {
        "job_url": url,
        "title": pick_title(raw),
        "company": pick_company(raw),
        "site": pick_text(raw.get("jobProvider"), raw.get("source"), raw.get("portal"))
        or site,
        "location": pick_location(raw, fallback_location),
        "job_type": pick_text(
            raw.get("job_type"),
            raw.get("employmentType"),
            raw.get("employmentTypes"),
            raw.get("contractType"),
        ),
        "date_posted": pick_text(
            raw.get("date_posted"),
            raw.get("datePosted"),
            raw.get("postedTimeAgo"),
            raw.get("dateCreated"),
            raw.get("date_created"),
        ),
    }


def status(site: str, jobs: list[dict[str, Any]], error: str | None = None) -> dict[str, Any]:
    return {
        "site": site,
        "count": len(jobs),
        "error": error or (None if jobs else f"{site} returned no jobs for this query"),
    }
