"""Keep only jobs that are fully remote: no hybrid, on-site or in-office requirement.

Every job is judged on what the provider says about it (a remote flag or a work
arrangement field) plus the words in its title, location and description.  A job
is kept only when nothing points to an office and at least one thing says remote.
"""

from __future__ import annotations

import re
from typing import Any

# Anything that means the job needs you in an office at least some of the time.
NOT_REMOTE_PATTERNS = [
    r"\bhybrid\b",
    r"\bon[\s-]?site\b",
    r"\bin[\s-]?office\b",
    r"\bin[\s-]?person\b",
    r"\boffice[\s-]?based\b",
    r"\bno remote\b",
    r"\bnot remote\b",
    r"\bnot (?:a |be )?(?:fully |100% )?remote\b",
    r"\bremote (?:work )?(?:is )?not (?:available|an option|offered|possible|permitted)\b",
    r"\b\d+\s*(?:-|to|–)?\s*\d*\s*days?\s*(?:per|a|each)\s*(?:week|month)\b[^.]{0,40}\boffice\b",
    r"\bdays?\s+(?:in|at)\s+(?:the\s+|our\s+)?office\b",
    r"\breturn[\s-]to[\s-]office\b",
    r"\brelocat(?:e|ion)\s+(?:is\s+|will be\s+)?required\b",
    r"\bmust (?:be willing to )?relocate\b",
    r"\bwork(?:ing)? from (?:the|our) office\b",
    r"\bcommut(?:e|able|ing) (?:distance|to)\b",
    r"\blocal candidates only\b",
]

# Explicit remote wording.
REMOTE_PATTERNS = [
    r"\bremote\b",
    r"\bremotely\b",
    r"\bwork[\s-]?from[\s-]?home\b",
    r"\bwfh\b",
    r"\bwork[\s-]?from[\s-]?anywhere\b",
    r"\btelecommut\w*\b",
    r"\btelework\w*\b",
    r"\bhome[\s-]?based\b",
    r"\bfully distributed\b",
    r"\bdistributed team\b",
]

# A bare "remote" inside a long description is often noise ("remote sensors",
# "remote-cluster environments", "experience with remote-first teams"), so a
# description-only match must state that the job itself is remote.
REMOTE_DESCRIPTION_PATTERNS = [
    r"\b(?:fully|100%|entirely|permanently|completely)[\s-]+remote\b",
    r"\bremote[\s-]+(?:only|first)\b(?!\s+(?:teams?|companies|culture|environments?|experience))",
    r"\bremote[\s-]+(?:position|role|opportunity|job|employee|hire)\b",
    r"\b(?:this|the)\s+(?:role|position|job|opportunity)\s+(?:is|can be|will be|may be)\s+(?:held\s+)?(?:fully\s+|100%\s+)?remote(?:ly)?\b",
    r"\b(?:can|may|able to|eligible to)\s+(?:be\s+)?(?:work|be held|be performed|be done|be based)\s+remotely\b",
    r"\b(?:or|and|held|performed|done|based|working|work)\s+remotely\s+(?:in|within|from|across|anywhere)\b",
    r"\bwork[\s-]?from[\s-]?(?:home|anywhere)\b",
    r"\bremote\s+(?:within|in|from|across)\s+(?:the\s+)?(?:us|usa|u\.s\.|united states|north america|canada|anywhere)\b",
    r"\bremote\s*[-(:]\s*(?:us|usa|united states|anywhere|worldwide|global)\b",
    r"\blocation\s*:\s*remote\b",
    r"\b(?:telecommut|telework)\w*\b",
    r"\bremote\s+work(?:ing)?\s+(?:is\s+)?(?:available|offered|supported|permitted|allowed|possible)\b",
    r"\bremote\s+(?:is\s+)?(?:ok|okay|welcome|friendly)\b",
    r"\bwork\s+remotely\b(?!\s+(?:occasionally|sometimes|up to|on occasion|part of|some))",
]

_NOT_REMOTE = re.compile("|".join(NOT_REMOTE_PATTERNS), re.IGNORECASE)
_REMOTE = re.compile("|".join(REMOTE_PATTERNS), re.IGNORECASE)
_REMOTE_DESCRIPTION = re.compile("|".join(REMOTE_DESCRIPTION_PATTERNS), re.IGNORECASE)


def _text(*values: Any) -> str:
    return " ".join(str(value) for value in values if isinstance(value, str) and value.strip())


def remote_verdict(job: dict[str, Any]) -> tuple[bool, str]:
    """Return (is_fully_remote, reason)."""
    headline = _text(job.get("title"), job.get("location"), job.get("work_arrangement"))
    description = _text(job.get("job_description"))
    flag = job.get("remote")

    blocker = _NOT_REMOTE.search(headline) or _NOT_REMOTE.search(description)
    if blocker:
        return False, f"mentions '{blocker.group(0).strip()}'"
    if flag is True:
        return True, "provider marks it remote"
    hit = _REMOTE.search(headline)
    if hit:
        return True, f"'{hit.group(0)}' in title, location or work arrangement"
    if flag is False:
        return False, "provider marks it not remote"
    hit = _REMOTE_DESCRIPTION.search(description)
    if hit:
        return True, f"'{hit.group(0)}' in description"
    if _REMOTE.search(description):
        return False, "only a passing mention of remote in the description"
    return False, "no remote wording"


def filter_remote(jobs: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """Keep fully remote jobs, mark them, and return (kept, dropped_count)."""
    kept: list[dict[str, Any]] = []
    for job in jobs:
        ok, reason = remote_verdict(job)
        job["remote"] = ok
        job["remote_reason"] = reason
        if ok:
            kept.append(job)
    return kept, len(jobs) - len(kept)
