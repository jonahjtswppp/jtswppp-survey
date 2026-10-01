# JT SWPPP SOP Quiz — Backend Build

## Project Goal
Convert the existing client feature survey into a graded SOP quiz for field staff
that records every employee's score, then shows them the correct answers and
explanations. Keep the original survey working alongside it.

Built on the same stack and deployed the same way: Flask + Postgres on Railway.

---

## Current State
- Repo: `https://github.com/jonahjtswppp/jtswppp-surve`
- Working branch: `convert-survey-to-quiz`
- Quiz served at `/`, original feature survey moved to `/survey`
- Postgres holds two tables: `quiz_attempts` (new) and `survey_responses` (unchanged)
- **Quiz v3:** 15 questions, name-only entry, 80% to pass (12 of 15)

---

## Version History
| Version | Questions | Ids | Entry fields | Notes |
|---|---|---|---|---|
| v1 | 10 | `q1`–`q10` | Full name + site/crew | Original quiz |
| v2 | 20 | `q1`–`q20` | Full name only | 10 harder questions added; site/crew dropped; question order randomized |
| v3 | 15 | `q21`–`q35` | Full name only | Question set rewritten: combined two-part questions, tightened distractors |

Every attempt row stores `quiz_version` and `total_questions`, so v1 scores render as
`x/10` and v2 as `x/20`, never averaged against v3's `x/15`. Pre-existing rows are
stamped v1 by the migration.

### Why v3 uses fresh ids
Each question id owns a database column (`q7_answer`). The v3 rewrite reworded
questions and changed which topic sits at which number, so reusing `q1`–`q15` would
have left stored v2 answers sitting under new question text — `q9_answer` would read
"Only to enter" under a question about storm drains. Ids therefore continue at `q21`,
and the old twenty move to `RETIRED_QUESTIONS`: never served, but still used to render
historical attempts correctly. **Ids only ever go up; retired questions are never
deleted and never reused.**

---

## What Was Built

### 1. Quiz Frontend — `jtswppp-sop-quiz.html`
Single static file, same palette and card styling as the original survey
(`--dark #013040`, `--mid #016080`, `--light #02BFFF`, 560px container, system font
stack). Three screens toggled by an `.active` class:

- **Start** — Full name only, required before Start enables.
- **Quiz** — One question at a time, "3 of 15" progress bar, Back/Next, answers
  changeable. Never reveals right/wrong during the quiz. "Submit quiz" appears only
  on the last question.
- **Results** — Score card (PASS green / FAIL red), name and score, then every
  question with the employee's answer, the correct answer, and the explanation,
  ordered to match the order that employee saw.

The HTML hardcodes no question count. The intro line, the "all N questions" rule, the
pass threshold, and the progress indicator are all derived from `/quiz/questions` at
load, so changing `PASS_PERCENT` or the question list in `app.py` needs no HTML edit.

Mobile-first: single column, 15px+ answer buttons with ~48px tap targets, 16px
inputs so iOS doesn't zoom on focus, and a narrow-screen media query at 420px.

### 2. Backend — `app.py`
- `QUESTIONS` — the 15 live questions (`q21`–`q35`), each with choices, the correct
  key, and an explanation. **The only place correct answers exist.**
- `RETIRED_QUESTIONS` — `q1`–`q20`, never served; kept for rendering history.
- `QUESTION_BANK` — both lists combined. Drives database columns and the admin
  detail view.
- `PASS_PERCENT = 80` — single constant; `PASS_SCORE` derives from it by ceiling, so
  15 questions gives 12 to pass.
- `QUIZ_VERSION = 3` and `VERSION_TOTALS = {1: 10, 2: 20}` — version stamping.
- `QUESTION_NUMBER` — fixed 1–15 numbering over the live set, used when reporting
  unanswered questions. Independent of display order.
- `GET /quiz/questions` — shuffles **question order and choice order** per request,
  stripping `correct` and `explanation` before serializing.
- `POST /quiz/submit` — validates the name and that all 15 are answered (rejecting
  unknown choice keys), grades, inserts the attempt, returns the breakdown.

### 3. Storage
Reuses the existing Railway Postgres. Insert-only table `quiz_attempts` with name,
timestamp, score, percentage, pass/fail, `quiz_version`, `total_questions`, plus
`qN_answer` / `qN_correct` per question id. Retakes add rows; nothing is overwritten.

**Answers are stored by question id, never by position.** Because the order is
shuffled per attempt, position-based storage would silently scramble score history;
`q14_answer` always means question 14.

Railway Postgres is a separate service with its own volume, so attempts survive
redeploys. No change to the hosting setup was needed.

#### Migration from v1
`CREATE TABLE IF NOT EXISTS` does nothing to an existing table, so `init_db()` follows
it with a list of idempotent, individually-committed migrations:

1. `ADD COLUMN IF NOT EXISTS` for `quiz_version`, `total_questions`, and every
   `qN_answer` / `qN_correct` pair in `QUESTION_BANK` (adds q11–q20 to a v1 table,
   q21–q35 to a v2 table).
2. `ALTER COLUMN site_crew DROP NOT NULL` — **without this every new insert fails**,
   because site/crew is no longer collected but the v1 column was `NOT NULL`.
3. Backfill `quiz_version = 1`, `total_questions = 10` on rows that predate versioning.

Failures are logged rather than raised, so an already-applied statement or a column
that never existed (`site_crew` on a fresh database) cannot block startup.

### 4. Admin
- `GET /admin/scores` — all attempts newest first (name, date, score, quiz version,
  pass/fail), with a CSV download button. Names link to detail. Each score renders out
  of its own attempt's total.
- `GET /admin/scores/<id>` — one attempt, each question marked right/wrong, with the
  correct answer and explanation shown for the misses. Questions that did not exist
  when the attempt was taken are skipped, and pre-v2 attempts carry a note that the
  score is not directly comparable.
- `GET /admin/scores.csv` — full CSV export.

`ATTEMPT_COLUMNS` drives the admin SELECTs and the CSV, and deliberately omits
`site_crew`. That single list is what keeps old crew data in the database but out of
every view and export.

All three use HTTP Basic auth against `ADMIN_PASSWORD` (env var, never hardcoded).
If the var is unset the pages return **503**, so they fail closed rather than open.
The pre-existing `/export` route for survey data was unprotected and is now behind
the same check.

---

## Security Notes
- **Answers are not in the page.** Verified by grepping the built HTML for answer
  text and explanation strings — zero hits. The browser only receives choice keys
  and choice text.
- **Grading is server-side only.** A tampered client can change which key it submits,
  not whether that key is correct.
- **Unknown choice keys are rejected** rather than silently scored wrong.
- **No access codes in the quiz.** `q26` covers *when* to re-enter the gate code; no
  actual code or combination appears anywhere in any version, live or retired.
- **Shuffling cannot be exploited.** Choice keys are shuffled in presentation only;
  the server resolves a submitted key against its own copy of the question.

---

## Local Development
No Postgres on the dev machine, by design — scores are only recorded once deployed.

```bash
PORT=5050 ADMIN_PASSWORD=localtest .venv/bin/python app.py
```

With `DATABASE_URL` absent, the quiz grades and renders results but returns
`recorded: false` and the results page shows a "local preview — score not recorded"
banner. This path triggers **only** when `DATABASE_URL` is entirely unset; in
production a database error returns a 500 and asks the employee to resubmit, so a
real attempt is never silently lost.

Note: `psycopg2-binary==2.9.10` has no wheel for the dev machine's Python 3.9, so
2.9.12 is installed in the local `.venv`. `requirements.txt` is left at 2.9.10 for
Railway, which runs a newer Python.

---

## Deploy Checklist
1. Merge `convert-survey-to-quiz` and push — Railway auto-deploys.
2. Confirm the Postgres add-on is attached (`DATABASE_URL` set automatically).
3. **Set `ADMIN_PASSWORD` in the Railway dashboard** — admin pages are disabled until you do.
4. `init_db()` creates `quiz_attempts` and runs the v1 migration on first boot.
   **Check the deploy logs**: `ALTER COLUMN site_crew DROP NOT NULL` must succeed if
   any v1 attempts already exist, or submissions will fail with a 500.
5. Take the quiz once on the live URL, then confirm the attempt at `/admin/scores`
   shows v2 and a score out of 20.
6. If v1 attempts existed, confirm they still render as `x/10` with a v1 pill.

---

## Verified Locally
**v3 (15 questions):**
- 15 questions served, all from `q21`–`q35`; no retired question is ever served.
- Question order and choice order both differ per request.
- `/quiz/questions` payload keys are only `id`, `text`, `choices`, `key` — no `correct`
  or `explanation` field, and no explanation text in the payload or the HTML.
- 15/15 → 100% PASS; 12/15 → 80% PASS (threshold boundary); 11/15 → 73% FAIL.
- Blank name rejected. Partial submission reports the count and which numbers are blank.
- No duplicate choice text and no invalid `correct` key in any live question
  (checked programmatically across all 15).
- **Three-version admin rendering** against a stubbed DB: v1 → `9/10` with 10 blocks,
  v2 → `18/20` with 20 blocks, v3 → `13/15` with 15 blocks. The v2 detail shows its
  own original wording with no v3 text bleeding in, which is the thing fresh ids
  protect. No crew in any view; CSV header is 78 columns with no `site_crew`.

**Carried over from v2 testing** (logic unchanged since):
- ID mapping under shuffle: submitted with one answer wrong and a fully reversed
  display order — the wrong answer was attributed to its own question id, not to the
  position it occupied, and the review came back in the employee's display order.

Not yet exercised: the real Postgres insert and the v1 migration against live data.
Both need a database — no Postgres, Docker, or Homebrew on the dev machine — so they
get verified on first deploy. **The migration is the risky part of this change**; check
the Railway deploy logs for "Migration skipped" lines on first boot.

---

## Notes
- Jonah is the developer — direct, no hand-holding needed.
- Keep the stack minimal — no frameworks beyond Flask.
- No `.DS_Store` or screenshots in the repo. Note that `.DS_Store` is still tracked
  in git from an early commit despite being in `.gitignore`; `git rm --cached .DS_Store`
  clears it.
