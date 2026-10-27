from __future__ import annotations

from typing import Any

from backend.no_login import filter_no_login
from backend.providers import PROVIDERS
from backend.schemas import SearchRequest


def search_job_links(
    payload: SearchRequest,
) -> tuple[list[dict[str, Any]], list[str], list[dict[str, Any]]]:
    provider = PROVIDERS.get(payload.source)
    if not provider:
        raise ValueError(f"Unknown job source: {payload.source}")
    jobs, site_status = provider(payload)
    for job in jobs:
        job.pop("matched_site", None)
    if payload.no_login_only:
        jobs, dropped = filter_no_login(jobs)
        site_status.append(
            {
                "site": "no-login filter",
                "count": len(jobs),
                "error": None,
                "dropped": dropped,
            }
        )
    failed = [item["site"] for item in site_status if item.get("error")]
    return jobs, failed, site_status
