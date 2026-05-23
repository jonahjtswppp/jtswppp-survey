# JT SWPPP Feature Survey — Project Context

## What This Project Is
A "$100 budget allocation" survey for JT SWPPP clients to vote on which product features to build. Built as a single HTML file, now being upgraded with a Flask backend and Railway deployment.

## Current State
All files have been written and are ready to push to GitHub. The repo already exists and is connected (`origin/main`). Files just need to be staged, committed, and pushed.

## Files in This Folder
- `jtswppp-feature-survey.html` — The survey frontend (modified: company name field added, submit now uses fetch() to POST to /submit)
- `app.py` — Flask server with a `POST /submit` endpoint that saves responses to PostgreSQL
- `requirements.txt` — Flask 3.1.1, gunicorn 23.0.0, psycopg2-binary 2.9.10
- `Procfile` — `web: gunicorn app:app` (for Railway)
- `.gitignore` — Ignores .env, __pycache__, .DS_Store, screenshots, etc.
- `jtswppp-survey-backend.md` — Build plan/notes doc

## Immediate Task: Push to GitHub
Run the following git commands:

```bash
git add .
git commit -m "Add Flask backend, Procfile, requirements, gitignore"
git push
```

The `.DS_Store` and deleted screenshots will be cleaned up by the new `.gitignore` going forward.

## After Pushing: Deploy on Railway
1. Go to railway.app and create a new project
2. Connect it to the GitHub repo (`jonahjtswppp/jtswppp-surve`)
3. Add a **PostgreSQL** plugin/add-on to the project
4. Railway will automatically set the `DATABASE_URL` environment variable
5. Railway will detect the `Procfile` and deploy the Flask app automatically
6. On first run, `init_db()` in `app.py` will create the `survey_responses` table automatically

## Database Schema (auto-created by app.py)
```sql
CREATE TABLE survey_responses (
    id SERIAL PRIMARY KEY,
    submitted_at TIMESTAMPTZ NOT NULL,
    company_name TEXT,
    live_camera_dashboard INTEGER DEFAULT 0,
    homeowner_portal INTEGER DEFAULT 0,
    compliance_documents INTEGER DEFAULT 0,
    hourly_photo_log INTEGER DEFAULT 0,
    build_timelapse INTEGER DEFAULT 0,
    motion_activated_security INTEGER DEFAULT 0,
    view_and_pay_invoices INTEGER DEFAULT 0,
    total_allocated INTEGER DEFAULT 0
)
```

## How the Submit Flow Works
1. User fills in company name + allocates $100 across 7 features
2. Frontend sends `POST /submit` with JSON payload:
   `{ company_name, live_camera_dashboard, homeowner_portal, compliance_documents, hourly_photo_log, build_timelapse, motion_activated_security, view_and_pay_invoices }`
3. Flask validates total ≤ $100, inserts row into Postgres, returns `{ "ok": true }`
4. Frontend shows the results page

## Key Constraints
- Keep the stack minimal — Flask only, no extra frameworks
- No `.DS_Store` or screenshots in the repo
- The only required env variable is `DATABASE_URL` (set automatically by Railway Postgres)
