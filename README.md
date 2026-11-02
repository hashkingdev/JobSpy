# JobSpy Web App

A job-link collector. The React frontend searches company career boards (Greenhouse, Lever, Ashby) and RapidAPI job feeds through the FastAPI backend and saves postings to Postgres. A daily collector gathers a fixed number of job links that open without a login (direct company career pages and applicant tracking systems such as Greenhouse, Lever, Ashby, Workable) and skips login-walled boards such as LinkedIn, Indeed, Glassdoor, ZipRecruiter and Dice.

## Backend

```
pip install -r backend/requirements.txt
python backend/run.py
```

Runs uvicorn on `http://127.0.0.1:8000`. Configure `backend/.env` with `DATABASE_URL`, `RAPIDAPI_KEY`, and the provider hosts (see `backend/config.py` for the full list and defaults).

Endpoints:

- `GET /api/health`
- `POST /api/jobs/search` - query one provider (`company-boards`, `jsearch`, `jobs-api`, `job-posting-feed`, `daily-international`, `remote-jobs`, `open-to-work`). `no_login_only` (default true) drops login-walled links; `remote_only` (default true) drops anything that is not fully remote.
- `POST /api/jobs/save` - upsert job links into the `job_links` table
- `GET /api/daily/status` - today's count, target, schedule, last run
- `POST /api/daily/run` - collect now until today's target is reached
- `GET /api/daily/links?date=YYYY-MM-DD` - links saved on a day (default today)
- `GET /api/daily/runs` - recent run history

## Daily collection

While the backend is running, a background scheduler runs once a day at `DAILY_RUN_AT` (server local time). If the backend was off at that time, it runs as soon as it starts. Each run walks the configured date windows (`today`, then `week`, then `month`), roles and sources, keeps only links that are fully remote and open without a login, skips URLs already in the database, and stops when today's count of verified-remote links reaches `DAILY_TARGET`. Press **Run now** on the **Daily 100** tab to collect on demand.

### Company boards (no API key, no quota)

`company-boards` is the first source the collector tries. It reads the public job APIs of Greenhouse, Lever and Ashby for every company listed in `backend/ats_boards.json` (about 760 boards), so it needs no RapidAPI key and has no monthly quota. Every link is the employer's own posting, which opens and accepts applications without an account. All boards are fetched in parallel (about 15 seconds) and cached for `ATS_CACHE_MINUTES`, so the daily run over all roles and windows costs one fetch.

A job matches a role when every word of the role appears in the title (engineer/developer, full stack/fullstack, node/node.js and similar are treated as the same word). The `country` setting drops postings whose location names another country or region ("Remote - Canada", "EMEA"). Add boards with `ATS_BOARDS_EXTRA=greenhouse:slug,lever:slug,ashby:slug`; the slug is the company part of the board URL (`boards.greenhouse.io/<slug>`, `jobs.lever.co/<slug>`, `jobs.ashbyhq.com/<slug>`).

### 100% remote filter

Every job is checked before it is saved (`backend/remote.py`):

1. If the title, location, work-arrangement field or description mentions **hybrid**, **on-site**, **in-office**, **in-person**, days in the office, relocation, a commutable distance or "not remote", the job is dropped.
2. Otherwise it is kept when the provider flags it remote, or the title, location or work arrangement says remote, work from home, telecommute or similar.
3. A description-only match must say the job itself is remote ("fully remote", "this role is remote", "remotely in the United States", "work from home", ...). A passing "remote" ("remote sensors", "remote-cluster", "experience with remote-first teams") does not count.
4. Jobs with no remote wording at all are dropped.

The no-login filter also blocks sign-up aggregators (JobLeads, Teal, Jobright, DailyRemote, ...) and free web-hosting domains used by scraper sites that mirror postings, so what is left is the employer's own page or ATS.

RapidAPI plans matter: the BASIC plans for `jsearch` (200 requests/month), `jobs-api` (50 requests/month) and `job-posting-feed` (5 requests/month) run out fast. When a source answers "quota exhausted" or "subscribe first", the collector skips it for the rest of the run instead of waiting. Those feeds are only a top-up; the company boards alone reach the daily target.

Kept rows are stored with `remote = true` and show a **Remote** badge on the **Daily 100** tab. Rows saved before this filter existed have no verdict and show as unverified; they do not count toward the daily target. Set `REMOTE_ONLY=false` (or `DAILY_REMOTE_ONLY=false` for the collector only) to turn the filter off.

Optional `.env` settings:

| Variable | Default | Meaning |
| --- | --- | --- |
| `DAILY_ENABLED` | `true` | Start the scheduler |
| `DAILY_TARGET` | `100` | Links to collect per day |
| `DAILY_RUN_AT` | `08:00` | Daily run time, 24h local |
| `DAILY_ROLES` | `full stack software engineer, full stack developer, ...` (28 roles) | Comma-separated roles, tried in order until the target is met; put the roles you care about first |
| `DAILY_FALLBACK_DATE_POSTED` | `week,month` | If the `today` pass comes up short, search these wider windows in turn (empty disables) |
| `DAILY_RATE_LIMIT_WAIT` / `DAILY_RATE_LIMIT_RETRIES` | `62` / `2` | Seconds to wait, and how many times, when a RapidAPI source answers 429 |
| `DAILY_MAX_MINUTES` | `30` | Stop a run (status `short`) after this long |
| `DAILY_SOURCES` | `company-boards` then the six RapidAPI providers | Comma-separated providers, tried in order |
| `ATS_BOARDS_EXTRA` | empty | Extra company boards, `greenhouse:slug,lever:slug,ashby:slug` |
| `ATS_BOARDS_FILE` | `backend/ats_boards.json` | Replace the built-in board list with your own JSON file |
| `ATS_CACHE_MINUTES` / `ATS_WORKERS` | `20` / `16` | How long fetched boards are reused, and how many are fetched in parallel |
| `DAILY_COUNTRY` / `DAILY_LOCATION_TYPE` / `DAILY_JOB_TYPE` / `DAILY_DATE_POSTED` | `usa` / `remote` / empty / `today` | Search filters |
| `REMOTE_ONLY` | `true` | Keep only fully remote jobs in searches and the daily run |
| `DAILY_REMOTE_ONLY` | same as `REMOTE_ONLY` | Override the remote filter for the collector only |
| `JSEARCH_DIRECT_ONLY` | `true` | Keep only JSearch results with an employer-direct apply link; aggregators and scraper mirrors are dropped |
| `NO_LOGIN_STRICT` | `false` | Also drop ATSs that need an account to apply (Workday, iCIMS, Taleo, ADP, ...) |
| `NO_LOGIN_BLOCK_EXTRA` / `NO_LOGIN_ALLOW_EXTRA` | empty | Comma-separated domains to add to or remove from the block list |

## Frontend

```
cd frontend
npm install
npm run dev
```

Runs Vite on `http://localhost:5173` and proxies `/api` to the backend. The **Daily 100** tab shows progress toward today's target, the last run's per-source breakdown, and lets you copy or download the day's links as CSV.
