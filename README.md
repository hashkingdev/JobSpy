# JobSpy Web App

A job-link collector. The React frontend searches RapidAPI job feeds through the FastAPI backend and saves postings to Postgres. A daily collector gathers a fixed number of job links that open without a login (direct company career pages and applicant tracking systems such as Greenhouse, Lever, Ashby, Workable) and skips login-walled boards such as LinkedIn, Indeed, Glassdoor, ZipRecruiter and Dice.

## Backend

```
pip install -r backend/requirements.txt
python backend/run.py
```

Runs uvicorn on `http://127.0.0.1:8000`. Configure `backend/.env` with `DATABASE_URL`, `RAPIDAPI_KEY`, and the provider hosts (see `backend/config.py` for the full list and defaults).

Endpoints:

- `GET /api/health`
- `POST /api/jobs/search` - query one provider (`jsearch`, `jobs-api`, `job-posting-feed`, `daily-international`, `remote-jobs`, `open-to-work`). `no_login_only` (default true) drops login-walled links.
- `POST /api/jobs/save` - upsert job links into the `job_links` table
- `GET /api/daily/status` - today's count, target, schedule, last run
- `POST /api/daily/run` - collect now until today's target is reached
- `GET /api/daily/links?date=YYYY-MM-DD` - links saved on a day (default today)
- `GET /api/daily/runs` - recent run history

## Daily collection

While the backend is running, a background scheduler runs once a day at `DAILY_RUN_AT` (server local time). If the backend was off at that time, it runs as soon as it starts. Each run walks the configured roles and sources, keeps only no-login links, skips URLs already in the database, and stops when today's saved count reaches `DAILY_TARGET`. Press **Run now** on the **Daily 100** tab to collect on demand.

Optional `.env` settings:

| Variable | Default | Meaning |
| --- | --- | --- |
| `DAILY_ENABLED` | `true` | Start the scheduler |
| `DAILY_TARGET` | `100` | Links to collect per day |
| `DAILY_RUN_AT` | `08:00` | Daily run time, 24h local |
| `DAILY_ROLES` | `full stack software engineer, full stack developer, ...` | Comma-separated roles, tried in order until the target is met |
| `DAILY_SOURCES` | all six providers | Comma-separated providers, tried in order |
| `DAILY_COUNTRY` / `DAILY_LOCATION_TYPE` / `DAILY_JOB_TYPE` / `DAILY_DATE_POSTED` | `usa` / `remote` / empty / `today` | Search filters |
| `NO_LOGIN_STRICT` | `false` | Also drop ATSs that need an account to apply (Workday, iCIMS, Taleo, ADP, ...) |
| `NO_LOGIN_BLOCK_EXTRA` / `NO_LOGIN_ALLOW_EXTRA` | empty | Comma-separated domains to add to or remove from the block list |

## Frontend

```
cd frontend
npm install
npm run dev
```

Runs Vite on `http://localhost:5173` and proxies `/api` to the backend. The **Daily 100** tab shows progress toward today's target, the last run's per-source breakdown, and lets you copy or download the day's links as CSV.
