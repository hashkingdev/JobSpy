import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:123123@localhost:5432/job_bidding",
)

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "")
RAPIDAPI_HOST = os.getenv("RAPIDAPI_HOST", "jsearch.p.rapidapi.com")
JOBS_API_HOST = os.getenv("JOBS_API_HOST", "jobs-api14.p.rapidapi.com")
JOB_POSTING_FEED_HOST = os.getenv(
    "JOB_POSTING_FEED_HOST", "job-posting-feed-api.p.rapidapi.com"
)
DAILY_INTERNATIONAL_HOST = os.getenv(
    "DAILY_INTERNATIONAL_HOST", "daily-international-job-postings.p.rapidapi.com"
)
REMOTE_JOBS_HOST = os.getenv("REMOTE_JOBS_HOST", "remote-jobs-api1.p.rapidapi.com")
REMOTE_JOBS_ATS_HOST = os.getenv("REMOTE_JOBS_ATS_HOST", "remote-jobs1.p.rapidapi.com")
OPEN_TO_WORK_HOST = os.getenv(
    "OPEN_TO_WORK_HOST", "open-to-work-remote-api.p.rapidapi.com"
)
JSEARCH_SEARCH_URL = os.getenv(
    "JSEARCH_SEARCH_URL",
    "https://jsearch.p.rapidapi.com/search-v2",
)
JSEARCH_DATE_POSTED = os.getenv("JSEARCH_DATE_POSTED", "today")
JSEARCH_QUERY = os.getenv("JSEARCH_QUERY", "full stack software engineer in United States")
JSEARCH_COUNTRY = os.getenv("JSEARCH_COUNTRY", "us")
JSEARCH_NUM_PAGES = int(os.getenv("JSEARCH_NUM_PAGES", "10"))
JSEARCH_WORK_FROM_HOME = os.getenv("JSEARCH_WORK_FROM_HOME", "true").lower() == "true"
