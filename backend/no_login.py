"""Filter job links down to ones that can be opened and applied to without an account."""

from __future__ import annotations

from typing import Any, Iterable
from urllib.parse import urlparse

from backend.config import NO_LOGIN_ALLOW_EXTRA, NO_LOGIN_BLOCK_EXTRA, NO_LOGIN_STRICT

# Job boards and aggregators that put a login wall in front of the posting or the apply button.
LOGIN_WALL_DOMAINS = {
    "linkedin.com",
    "glassdoor.com",
    "glassdoor.co.uk",
    "glassdoor.ca",
    "glassdoor.co.in",
    "indeed.com",
    "ziprecruiter.com",
    "dice.com",
    "monster.com",
    "careerbuilder.com",
    "simplyhired.com",
    "wellfound.com",
    "angel.co",
    "hired.com",
    "builtin.com",
    "lensa.com",
    "talent.com",
    "jooble.org",
    "adzuna.com",
    "snagajob.com",
    "theladders.com",
    "ladders.com",
    "upwork.com",
    "jobcase.com",
    "whatjobs.com",
    "jobrapido.com",
    "neuvoo.com",
    "jobs2careers.com",
    "bebee.com",
    "jobilize.com",
    "learn4good.com",
    "trabajo.org",
    "recruit.net",
    "salary.com",
    "jobgether.com",
    "jobot.com",
    "cybercoders.com",
    "toptal.com",
    "turing.com",
    "flexjobs.com",
    "remoterocketship.com",
    "google.com",
    "facebook.com",
    "x.com",
    "twitter.com",
}

# Applicant tracking systems that are public to read but ask you to create an account to apply.
# Blocked only when NO_LOGIN_STRICT=true.
ACCOUNT_TO_APPLY_DOMAINS = {
    "myworkdayjobs.com",
    "myworkdaysite.com",
    "icims.com",
    "taleo.net",
    "successfactors.com",
    "oraclecloud.com",
    "brassring.com",
    "adp.com",
    "ultipro.com",
    "paycomonline.net",
    "paylocity.com",
    "dayforcehcm.com",
    "csod.com",
    "avature.net",
    "eightfold.ai",
    "phenom.com",
}


def _split_env(value: str) -> set[str]:
    return {
        part.strip().lower().removeprefix("www.")
        for part in value.split(",")
        if part.strip()
    }


BLOCKED = (LOGIN_WALL_DOMAINS | _split_env(NO_LOGIN_BLOCK_EXTRA)) - _split_env(
    NO_LOGIN_ALLOW_EXTRA
)
if NO_LOGIN_STRICT:
    BLOCKED |= ACCOUNT_TO_APPLY_DOMAINS - _split_env(NO_LOGIN_ALLOW_EXTRA)


def host_of(url: str | None) -> str:
    if not url:
        return ""
    try:
        host = urlparse(url.strip()).netloc.lower()
    except ValueError:
        return ""
    return host.split("@")[-1].split(":")[0].removeprefix("www.")


def _matches(host: str, domains: Iterable[str]) -> bool:
    return any(host == domain or host.endswith(f".{domain}") for domain in domains)


def is_no_login_url(url: str | None) -> bool:
    host = host_of(url)
    if not host or not url.lower().startswith(("http://", "https://")):
        return False
    return not _matches(host, BLOCKED)


def pick_no_login_url(candidates: Iterable[str | None]) -> str | None:
    for url in candidates:
        if url and is_no_login_url(url):
            return url
    return None


def filter_no_login(jobs: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    kept = [job for job in jobs if is_no_login_url(job.get("job_url"))]
    return kept, len(jobs) - len(kept)
