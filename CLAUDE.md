# JT SWPPP SOP Quiz — Project Context

## What This Project Is
A graded SOP knowledge quiz for JT SWPPP field staff. Employees enter their full
name, answer 15 questions on company policy and field procedure, and get a score
recorded under their name. Admins review all attempts at `/admin/scores`.

The original client-facing "$100 budget allocation" feature survey is still in the
repo and still works, now at `/survey`.

## Stack
Flask + PostgreSQL, deployed on Railway. No frameworks beyond Flask — keep it that way.

## Files
- `jtswppp-sop-quiz.html` — The quiz frontend (start → one question at a time → results)
- `jtswppp-feature-survey.html` — The original client feature survey
- `app.py` — Flask server: questions, grading, storage, admin pages
- `requirements.txt` — Flask 3.1.1, gunicorn 23.0.0, psycopg2-binary 2.9.10
- `Procfile` — `web: gunicorn app:app` (for Railway)
- `.gitignore` — Ignores .env, __pycache__, .venv, .DS_Store, logs
- `jtswppp-survey-backend.md` — Build notes

## Routes
| Route | What it does |
|---|---|
| `GET /` | Serves the quiz |
| `GET /quiz/questions` | The 15 active questions with **both question order and choice order shuffled per request**. Never includes which choice is correct. |
| `POST /quiz/submit` | Grades server-side, saves the attempt, returns score + full answer breakdown |
| `GET /admin/scores` | All attempts, newest first: name, date, score, quiz version, pass/fail (password protected) |
| `GET /admin/scores/<id>` | One attempt's detail, showing which questions were missed |
| `GET /admin/scores.csv` | CSV of all attempts (password protected) |
| `GET /survey` | Serves the original feature survey |
| `POST /submit` | Saves a feature survey response |
| `GET /export` | CSV of survey responses (password protected) |

## The Question Lists (editing questions)
`app.py` holds two lists plus a combined one:

| Name | What it is |
|---|---|
| `QUESTIONS` | The **live** set, currently `q21`–`q35` (15 questions). Served and graded. |
| `RETIRED_QUESTIONS` | Questions no longer asked, `q1`–`q20`. Never served; kept only so old attempts render with the wording and correct answer that applied then. |
| `QUESTION_BANK` | `RETIRED_QUESTIONS + QUESTIONS`. Drives the database columns and the admin detail view. |

**To edit question wording, choices, or explanations:** change `QUESTIONS` and restart.
**To add or remove a question:** give new ones unused ids, bump `QUIZ_VERSION`, and add
the previous total to `VERSION_TOTALS`.

**Never reuse a retired id for different wording.** Each id owns a database column
(`q14_answer`), so reusing `q14` for a new question would silently relabel every
stored answer to the old one. Ids only ever go up. When a question leaves the live
set, move it to `RETIRED_QUESTIONS` rather than deleting it — deleting it makes old
attempts un-renderable.

## Key Design Rules
- **Correct answers live only in `app.py`.** Each question holds its correct key and
  explanation. `/quiz/questions` strips both before sending. The browser only ever
  sees choice keys (`a`–`d`) and choice text, so employees cannot read the answers
  from page source.
- **Grading is server-side only.** The client posts `{question_id: choice_key}` and
  the server decides what's right.
- **`PASS_PERCENT = 80`** is a single constant at the top of `app.py`. Change it there.
  `PASS_SCORE` is derived from it (ceiling), so 80% of 15 questions = 12.
- **Both question order and choice order are randomized per attempt**, so questions
  come out interleaved rather than in source order.
- **Answers are keyed by question id, never by position.** This is what makes the
  shuffle safe — ids are stable, so storage, grading and the admin views all line up
  regardless of the order an employee saw. Never store by index.
- **Retakes are allowed.** Every attempt is a new row; nothing is overwritten.
- **No gate codes, key box codes, or access codes anywhere in the quiz.** `q26` covers
  *when* to re-enter the gate code, never what it is. Keep it that way.

## Quiz Versioning
`QUIZ_VERSION = 3` at the top of `app.py`. Every attempt stores its version and its
`total_questions`, so scores from different question sets never get mixed up:

| Version | Questions | Ids | Entry fields |
|---|---|---|---|
| v1 | 10 | `q1`–`q10` | Full name + site/crew |
| v2 | 20 | `q1`–`q20` | Full name only |
| v3 (current) | 15 | `q21`–`q35` | Full name only |

`/admin/scores` shows a version pill per row and renders each score out of that
attempt's own total (`9/10` for v1, `18/20` for v2, `13/15` for v3). The attempt
detail view walks `QUESTION_BANK` and renders only the questions that attempt has
data for, so each one shows its own original wording, and flags older versions as
not directly comparable.

**Bump `QUIZ_VERSION` whenever the question set changes**, and add the old total to
`VERSION_TOTALS`. Adding questions also means new columns — see the schema note below.

## Removed: Site/crew
v1 collected a site/crew field. It is no longer asked for, submitted, validated,
displayed, or exported. Old values remain in the `site_crew` column — the migration
only drops its `NOT NULL` constraint so new inserts succeed. `ATTEMPT_COLUMNS` in
`app.py` deliberately omits it, which is what keeps it out of both the admin views
and the CSV. Do not re-add it to that list.

## Environment Variables
| Var | Required | Purpose |
|---|---|---|
| `DATABASE_URL` | Yes in production | Postgres connection (Railway sets this automatically) |
| `ADMIN_PASSWORD` | Yes to use admin pages | HTTP Basic password for `/admin/*` and `/export`. Any username works; only the password is checked. Never hardcode it. |

If `ADMIN_PASSWORD` is unset, the admin pages return 503 rather than opening up.

## Local Development
There is no local Postgres on the dev machine. Run:

```bash
PORT=5050 ADMIN_PASSWORD=localtest .venv/bin/python app.py
```

With `DATABASE_URL` unset, the quiz grades and shows results normally but the
response carries `recorded: false` and the results page shows a "local preview —
score not recorded" notice. `/admin/scores` reports that no database is configured.
This fallback only triggers when `DATABASE_URL` is entirely absent, so on Railway
(where it is always set) a database failure returns a 500 and the employee is told
to resubmit — an attempt can never be silently dropped in production.

## Database Schema (created and migrated by `init_db()` on startup)
```sql
CREATE TABLE quiz_attempts (
    id SERIAL PRIMARY KEY,
    submitted_at TIMESTAMPTZ NOT NULL,
    full_name TEXT NOT NULL,
    score INTEGER NOT NULL,
    percentage INTEGER NOT NULL,
    passed BOOLEAN NOT NULL,
    quiz_version INTEGER NOT NULL,
    total_questions INTEGER NOT NULL,
    q1_answer TEXT, q1_correct BOOLEAN,
    ...                              -- through q35, generated from QUESTION_BANK
)
```
Columns come from `QUESTION_BANK`, not just the live set, so retired questions keep
their columns and their data. The table only ever gains columns.

`init_db()` runs `CREATE TABLE IF NOT EXISTS` and then a list of idempotent
migrations, because `IF NOT EXISTS` leaves an existing table untouched. The
migrations:

1. `ADD COLUMN IF NOT EXISTS` for `quiz_version`, `total_questions`, and every
   `qN_answer` / `qN_correct` pair in `QUESTION_BANK` (this is what adds q11–q20 to a
   v1 table and q21–q35 to a v2 table).
2. `ALTER COLUMN site_crew DROP NOT NULL` — **essential**: without it every new
   insert fails, since site/crew is no longer collected.
3. Backfill `quiz_version = 1` and `total_questions = 10` for rows that predate
   versioning.

Each statement commits separately and failures are logged, not raised, so a
statement that is already satisfied (or a column that never existed, like
`site_crew` on a fresh database) cannot block startup. All of them are re-runnable.

**If you add questions:** bump `QUIZ_VERSION`, add the previous total to
`VERSION_TOTALS`, and the new columns get added automatically on next boot.

`survey_responses` (the original feature survey table) is unchanged.

## Quiz Flow
1. Start screen requires a full name before the Start button enables. Nothing else
   is asked for.
2. `GET /quiz/questions` loads all 15 active questions with question order and choice
   order both shuffled for that attempt.
3. One question at a time with a "3 of 15" progress indicator, Back/Next, and answers
   changeable at any point. Right/wrong is never shown mid-quiz.
4. "Submit quiz" replaces "Next" only on the last question, and submitting is blocked
   until all 15 are answered — the user is told how many and exactly which canonical
   question numbers are still blank. The server re-checks this independently.
5. Results screen shows name, score (`12 / 15`), percentage, PASS/FAIL, then every
   question with their answer, the correct answer, and the explanation. The review is
   ordered to match the order that employee actually saw: the client sends its display
   order as `order`, and the server validates it is a true permutation of the question
   ids before using it, falling back to canonical order.

## Deploy on Railway
1. Push to the connected GitHub repo (`jonahjtswppp/jtswppp-surve`) — Railway auto-deploys.
2. PostgreSQL add-on provides `DATABASE_URL` automatically.
3. **Set `ADMIN_PASSWORD` manually** in the Railway dashboard, or the admin pages stay disabled.
4. Railway detects the `Procfile` and runs gunicorn.
5. `init_db()` creates both tables on first run.
