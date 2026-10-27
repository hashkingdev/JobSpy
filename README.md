# JobSpy Web App

A small job-link collector. The React frontend searches RapidAPI job feeds through the FastAPI backend and saves selected postings to Postgres.

## Backend

```
pip install -r backend/requirements.txt
python backend/run.py
```

Runs uvicorn on `http://127.0.0.1:8000`. Configure `backend/.env` with `DATABASE_URL`, `RAPIDAPI_KEY`, and the provider hosts (see `backend/config.py` for the full list and defaults).

Endpoints:

- `GET /api/health`
- `POST /api/jobs/search` - query one provider (`jsearch`, `jobs-api`, `job-posting-feed`, `daily-international`, `remote-jobs`, `open-to-work`)
- `POST /api/jobs/save` - upsert job links into the `job_links` table

## Frontend

```
cd frontend
npm install
npm run dev
```

Runs Vite on `http://localhost:5173` and proxies `/api` to the backend.
