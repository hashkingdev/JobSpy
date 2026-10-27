from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

DATE_POSTED = Literal["today", "3days", "72h", "week", "month"]
LOCATION_TYPE = Literal["remote", "hybrid", "onsite"]
SOURCE = Literal[
    "jsearch",
    "jobs-api",
    "job-posting-feed",
    "daily-international",
    "remote-jobs",
    "open-to-work",
]


class CustomBoard(BaseModel):
    id: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=120)
    url: Optional[str] = Field(default=None, max_length=500)

    @field_validator("url", mode="before")
    @classmethod
    def normalize_url(cls, value: str | None) -> str | None:
        if not value:
            return None
        value = str(value).strip()
        if not value:
            return None
        if not value.startswith(("http://", "https://")):
            value = f"https://{value}"
        return value


class SearchRequest(BaseModel):
    source: SOURCE = "jsearch"
    role: str = Field(default="full stack software engineer", min_length=1, max_length=300)
    location_type: LOCATION_TYPE = "remote"
    country: str = Field(default="usa", max_length=80)
    sites: list[str] = Field(default_factory=list)
    custom_boards: list[CustomBoard] = Field(default_factory=list)
    job_type: Optional[str] = None
    date_posted: DATE_POSTED = "today"
    num_pages: int = Field(default=10, ge=1, le=20)
    results_wanted: int = Field(default=100, ge=1, le=100)

    @field_validator("date_posted", mode="before")
    @classmethod
    def normalize_date(cls, value: str) -> str:
        if value == "72h":
            return "3days"
        return value

    @field_validator("job_type", mode="before")
    @classmethod
    def empty_job_type(cls, value: str | None) -> str | None:
        if value == "":
            return None
        return value


class JobLinkOut(BaseModel):
    job_url: str
    title: Optional[str] = None
    company: Optional[str] = None
    site: Optional[str] = None
    location: Optional[str] = None
    job_type: Optional[str] = None
    date_posted: Optional[str] = None
    job_description: Optional[str] = None


class SaveRequest(BaseModel):
    jobs: list[JobLinkOut]


class SaveResponse(BaseModel):
    saved: int
    skipped: int
