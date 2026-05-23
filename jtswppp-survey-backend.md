# JT SWPPP Feature Survey -- Backend Build

## Project Goal
Add a backend to an existing static HTML survey so form submissions are collected and stored. Deploy the full stack (frontend + backend) to Railway.

---

## Current State
- Repo: `https://github.com/jonahjtswppp/jtswppp-surve`
- Branch: `main`
- Current files: `jtswppp-feature-survey.html` (single static HTML file)
- No server, no backend, no database yet

---

## What We Need to Build

### 1. Backend Server
- **Language:** Python (Flask) -- keep it simple
- **Single endpoint:** `POST /submit` -- receives form data and saves it
- **Response:** JSON success/error message back to the frontend

### 2. Data Storage
- **Option A (simplest):** Google Sheets via the Sheets API -- responses go straight to a spreadsheet Jonah can view
- **Option B:** PostgreSQL database -- Railway provides this as a free add-on
- Start with Option A unless Jonah prefers otherwise

### 3. Frontend Update
- Update the HTML form's `action` or add a `fetch()` call to hit the `/submit` endpoint
- Show a success message after submission

### 4. Railway Configuration
- Add a `Procfile` or `railway.toml` so Railway knows how to run the Flask app
- Add `requirements.txt` with dependencies
- Set environment variables in Railway dashboard (API keys, DB URLs, etc.)

---

## File Structure to Create

```
jtswppp-surve/
├── app.py                  # Flask server
├── requirements.txt        # Python dependencies
├── Procfile                # Railway run command
├── jtswppp-feature-survey.html  # Existing file (will be updated)
└── .gitignore              # Already needs cleanup
```

---

## Step-by-Step Plan

1. **Read the existing HTML** -- understand what fields the form has
2. **Create `app.py`** -- Flask server with `/submit` POST route
3. **Create `requirements.txt`** -- Flask, gunicorn, and any storage library
4. **Create `Procfile`** -- `web: gunicorn app:app`
5. **Update the HTML form** -- point it at the backend endpoint
6. **Set up data storage** -- Google Sheets or Railway Postgres
7. **Test locally** -- `flask run`, submit the form, confirm data is saved
8. **Push to GitHub** -- Railway auto-deploys on push
9. **Connect Railway to GitHub** -- if not already done
10. **Set environment variables** in Railway dashboard
11. **Verify live deployment**

---

## Notes
- Jonah is the developer -- direct, no hand-holding needed
- Keep the stack minimal -- no frameworks beyond Flask
- No `.DS_Store` or screenshots in the repo -- add `.gitignore` early
- The survey is for JT SWPPP clients to submit feature requests/feedback

---

## First Action for Agent
Ask Jonah to paste the contents of `jtswppp-feature-survey.html` so you can see the form fields before writing any backend code.
