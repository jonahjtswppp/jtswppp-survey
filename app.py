import os
import csv
import io
import random
import psycopg2
from flask import Flask, request, jsonify, send_from_directory, Response
from markupsafe import escape
from datetime import datetime, timezone

app = Flask(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")

# Change this to adjust the passing threshold.
PASS_PERCENT = 80

# Bump when the question set changes, so old scores stay comparable only to
# attempts from the same version. v1 was 10 questions, v2 was 20.
QUIZ_VERSION = 3

# How many questions each historical version had, for rendering old attempts.
VERSION_TOTALS = {1: 10, 2: 20}

# Retired questions: no longer asked, kept only so historical attempts still
# render with the question text and correct answer that applied at the time.
# Never reuse a retired id for new wording -- its database column holds answers
# to the old question, and reusing it would relabel that stored history.
RETIRED_QUESTIONS = [
    {
        "id": "q1",
        "text": "At what fuel level must you refuel the company truck?",
        "choices": {
            "a": "Half tank",
            "b": "One-quarter tank",
            "c": "When the light comes on",
            "d": "Empty",
        },
        "correct": "b",
        "explanation": "Fuel when the tank reaches one-quarter full and keep your receipts.",
    },
    {
        "id": "q2",
        "text": "You are in an at-fault accident in the company vehicle and were not impaired. How much do you pay first?",
        "choices": {
            "a": "$100",
            "b": "$250",
            "c": "$500",
            "d": "Nothing",
        },
        "correct": "b",
        "explanation": "At fault means you pay the first $250 in damages. If impaired, employment is terminated.",
    },
    {
        "id": "q3",
        "text": "How soon must the accident report form be submitted?",
        "choices": {
            "a": "Within 24 hours",
            "b": "Within 48 hours",
            "c": "By end of the week",
            "d": "Only if there is damage over $250",
        },
        "correct": "a",
        "explanation": "Submit the accident report form within 24 hours.",
    },
    {
        "id": "q4",
        "text": "Which tools must you bring before leaving for your route?",
        "choices": {
            "a": "Only tools for items on your route",
            "b": "Tools for ALL maintenance items, regardless of route",
            "c": "Only sweeping tools",
            "d": "Whatever the manager lists that day",
        },
        "correct": "b",
        "explanation": "Bring tools for all maintenance items, plus at least 1 extra of each install item.",
    },
    {
        "id": "q5",
        "text": "Which set is the extra install items you bring regardless of route?",
        "choices": {
            "a": "Sign, inlet protection, camera, camera stand, 100' silt fence, 10 straw wattle stakes",
            "b": "Sign, camera, 50' silt fence, 5 wattle stakes",
            "c": "Inlet protection, tripod, 100' silt fence, 20 stakes",
            "d": "Camera, camera stand, washout bin, sign",
        },
        "correct": "a",
        "explanation": "The SOP lists exactly: sign, inlet protection, camera, camera stand, 100' silt fence, and 10 straw wattle stakes.",
    },
    {
        "id": "q6",
        "text": "You find tracked-out dirt on the road. What must you NOT do?",
        "choices": {
            "a": "Use the leaf blower first",
            "b": "Hose it into the storm drain",
            "c": "Sweep it back onto the lot",
            "d": "Take BEFORE photos",
        },
        "correct": "b",
        "explanation": "Hosing track out into storm drains violates the Utah SWPPP permit.",
    },
    {
        "id": "q7",
        "text": "How should a jobsite camera's solar panel be positioned?",
        "choices": {
            "a": "Facing north at 30 degrees",
            "b": "Facing south at 45 degrees",
            "c": "Facing east at 45 degrees",
            "d": "Facing south at 90 degrees",
        },
        "correct": "b",
        "explanation": "Solar panel faces south at a 45-degree angle.",
    },
    {
        "id": "q8",
        "text": "What must be done before taking inspection pictures?",
        "choices": {
            "a": "Call the manager",
            "b": "Complete all cleaning activities",
            "c": "Install a new camera",
            "d": "Film a marketing video",
        },
        "correct": "b",
        "explanation": "Complete all cleaning before inspection so photos show the true BMP condition.",
    },
    {
        "id": "q9",
        "text": "Leaving a storage unit lot: when do you enter the gate code?",
        "choices": {
            "a": "Only to enter",
            "b": "To leave too, even if the gate is already open",
            "c": "Only if the gate is closed",
            "d": "Never, the gate opens automatically",
        },
        "correct": "b",
        "explanation": "Re-enter the gate code to leave, even if the gate is already open.",
    },
    {
        "id": "q10",
        "text": "Marketing video rules: what is the max length for a talking clip, and who do you send the clip to?",
        "choices": {
            "a": "60 seconds, Tyler",
            "b": "30 seconds, Chloe",
            "c": "30 seconds, Mason",
            "d": "15 seconds, Chloe",
        },
        "correct": "b",
        "explanation": "Keep talking clips under 30 seconds, then text the clip to Chloe.",
    },
    {
        "id": "q11",
        "text": "You finish loading the truck at the storage unit. What is the correct order?",
        "choices": {
            "a": "Close unit, lock unit, lock key in key box, re-enter gate code to leave",
            "b": "Close unit, lock key in key box, lock unit, re-enter gate code to leave",
            "c": "Lock unit, close unit, lock key in key box, leave without re-entering the code",
            "d": "Re-enter gate code, close unit, lock unit, lock key in key box",
        },
        "correct": "a",
        "explanation": "Close the unit, lock the unit, lock the key in the box, then re-enter the gate code to leave, even if the gate is already open.",
    },
    {
        "id": "q12",
        "text": "Which is the complete pre-drive safety inspection list?",
        "choices": {
            "a": "Lights, tires, fluids, windshield, brakes, wipers",
            "b": "Lights, tires, fluids, windshield, brakes, horn",
            "c": "Lights, tires, oil, mirrors, brakes, wipers",
            "d": "Lights, tires, fluids, windshield, seatbelts, wipers",
        },
        "correct": "a",
        "explanation": "The pre-drive inspection covers lights, tires, fluids, windshield, brakes, and wipers. Also note the starting odometer.",
    },
    {
        "id": "q13",
        "text": "What is the correct order for the middle of a sweeping job?",
        "choices": {
            "a": "Leaf blower, sweep sidewalk into street, sweep street into gutter, loosen gutter material with shovel, sweep into dustpan",
            "b": "Sweep street into gutter, sweep sidewalk into street, leaf blower, shovel, dustpan",
            "c": "Leaf blower, sweep street into gutter, sweep sidewalk into street, dustpan, shovel",
            "d": "Shovel, leaf blower, sweep sidewalk into street, sweep street into gutter, dustpan",
        },
        "correct": "a",
        "explanation": "Blow small dirt and dust first, sweep the sidewalk into the street, the street into the gutter, loosen gutter material with the shovel, then collect it in the dustpan.",
    },
    {
        "id": "q14",
        "text": "You find a hardened washout spill (concrete, grout, or similar). What is the correct procedure?",
        "choices": {
            "a": "Take BEFORE photo, check how hard the surface is, break it up with the pickaxe if needed, scrape into a bucket, put it in the dumpster, take AFTER photo",
            "b": "Hose it to soften it, sweep it into the gutter, take AFTER photo",
            "c": "Break it up with the pickaxe and dump the pieces back on the lot",
            "d": "Cover it with dirt and note it for the next visit",
        },
        "correct": "a",
        "explanation": "Washout material must be removed and never allowed into storm drains. Break up cured spills with the pickaxe and dispose of all material in the dumpster.",
    },
    {
        "id": "q15",
        "text": "After checking or fixing a jobsite camera, how must you document it?",
        "choices": {
            "a": "Photo of connectivity status in the Reolink app, uploaded to a new folder named with the date and jobsite in the camera maintenance logs",
            "b": "Text the manager a screenshot of the camera feed",
            "c": "Photo of the solar panel, uploaded to the general inspection folder",
            "d": "No documentation is needed if the camera was already connected",
        },
        "correct": "a",
        "explanation": "Document camera status with a photo showing connectivity in the Reolink app and upload it to a new date and jobsite folder in camera maintenance logs. Then report to your manager before leaving the site.",
    },
    {
        "id": "q16",
        "text": "For a tripod marketing video, where do you place the phone and what must you do around talking?",
        "choices": {
            "a": "8 to 10 feet away at chest height, whole body and work in frame, wait 2 seconds before and after talking",
            "b": "3 to 5 feet away at eye level, face only in frame, start talking immediately",
            "c": "15 to 20 feet away at ground level, zoom in on the work",
            "d": "8 to 10 feet away at waist height, zoom in as needed, wait 5 seconds before talking",
        },
        "correct": "a",
        "explanation": "Tripod videos use 8 to 10 feet at chest height with your whole body and the work in frame. Wait 2 seconds before and after talking. Do not zoom, walk closer instead.",
    },
    {
        "id": "q17",
        "text": "Which marketing video type is Tier 1 (highest chance to win)?",
        "choices": {
            "a": "Tool/Equipment Spotlight",
            "b": "Problem Solving",
            "c": "B-Roll",
            "d": "Camera Setup",
        },
        "correct": "b",
        "explanation": "Tier 1 includes Client Moments, Day in the Life, Problem Solving, Before and After, and Site Walkthrough. Tool Spotlight and Camera Setup are Tier 2, B-Roll is Tier 3.",
    },
    {
        "id": "q18",
        "text": "Which of these is NOT on the inspection photo list?",
        "choices": {
            "a": "Track out pad",
            "b": "Portable toilet",
            "c": "Employee parking area",
            "d": "Dumpster",
        },
        "correct": "c",
        "explanation": "The list includes perimeter controls, erosion controls, concrete washout, SWPPP sign, spills, track out pad, dumpster, portable toilet, inlet protection, material storage areas, road entrance, and an overall jobsite picture.",
    },
    {
        "id": "q19",
        "text": "How often must the truck be cleaned, and what does it require?",
        "choices": {
            "a": "Weekly: no trash or debris in cab or bed, tools returned to the storage unit, cab and bed blown out",
            "b": "Monthly: wash the exterior and vacuum the cab",
            "c": "Weekly: wash the exterior and refuel",
            "d": "After every route: empty the bed only",
        },
        "correct": "a",
        "explanation": "Clean the truck once a week. Remove all trash and debris, return tools and equipment to designated storage unit locations, and blow out the cab and bed.",
    },
    {
        "id": "q20",
        "text": "Which three items must be in the vehicle before you depart?",
        "choices": {
            "a": "Water, first aid kit, phone charger",
            "b": "Water, fire extinguisher, phone charger",
            "c": "Water, first aid kit, flashlight",
            "d": "First aid kit, phone charger, sunscreen",
        },
        "correct": "a",
        "explanation": "Before leaving, make sure water, a first aid kit, and a phone charger are in the vehicle.",
    },
]

# The live v3 question set. Correct answers and explanations live here,
# server-side only, and are never sent to the browser until after grading.
# Ids continue from the retired set (q21+) so no column is ever reused.
QUESTIONS = [
    {
        "id": "q21",
        "text": "When must you refuel the company truck, and what must you keep?",
        "choices": {
            "a": "At one-quarter tank, and keep your receipts",
            "b": "At half tank, and keep your receipts",
            "c": "At one-quarter tank, no receipt needed",
            "d": "Only when the low fuel light comes on, and keep your receipts",
        },
        "correct": "a",
        "explanation": "Fuel when the tank reaches one-quarter full and keep your receipts.",
    },
    {
        "id": "q22",
        "text": "You are in an at-fault accident in the company truck and were not impaired. How much do you pay first, and when is the accident report form due?",
        "choices": {
            "a": "$250, within 24 hours",
            "b": "$500, within 24 hours",
            "c": "$250, within 48 hours",
            "d": "$100, within 72 hours",
        },
        "correct": "a",
        "explanation": "If at fault, you pay the first $250 in damages. Submit the accident report form within 24 hours.",
    },
    {
        "id": "q23",
        "text": "Which tools must you bring when you leave for your route?",
        "choices": {
            "a": "Tools for all maintenance items, regardless of whether they are on your route",
            "b": "Only tools for the maintenance items on your route",
            "c": "Only sweeping tools and a camera kit",
            "d": "Whatever the manager lists the morning of the route",
        },
        "correct": "a",
        "explanation": "Bring tools for all maintenance items regardless of route, and make sure you have tools and materials for all install items.",
    },
    {
        "id": "q24",
        "text": "Besides one extra of each install item you are scheduled to install, which extra install materials must you bring regardless of route?",
        "choices": {
            "a": "A sign, inlet protection, a camera, a camera stand, 100' of silt fence, and 10 straw wattle stakes",
            "b": "A sign, inlet protection, a camera, a camera stand, 50' of silt fence, and 10 straw wattle stakes",
            "c": "A sign, inlet protection, a camera, a camera stand, 100' of silt fence, and 20 straw wattle stakes",
            "d": "A sign, a camera, a tripod, 100' of silt fence, and 10 straw wattle stakes",
        },
        "correct": "a",
        "explanation": "Bring one additional sign, inlet protection, camera, camera stand, 100' of silt fence, and 10 straw wattle stakes, plus at least 1 extra of each install item.",
    },
    {
        "id": "q25",
        "text": "Which three items must be in the vehicle before you depart?",
        "choices": {
            "a": "Water, first aid kit, phone charger",
            "b": "Water, fire extinguisher, phone charger",
            "c": "Water, first aid kit, flashlight",
            "d": "First aid kit, phone charger, extra gloves",
        },
        "correct": "a",
        "explanation": "Make sure water, a first aid kit, and a phone charger are in the vehicle.",
    },
    {
        "id": "q26",
        "text": "You are leaving the storage unit lot and the gate is already open. What do you do?",
        "choices": {
            "a": "Re-enter the gate code anyway",
            "b": "Drive out, the gate is already open",
            "c": "Wait for the gate to close, then drive out",
            "d": "Call the manager to close the gate",
        },
        "correct": "a",
        "explanation": "To leave, re-enter the gate code, even if the gate is already open.",
    },
    {
        "id": "q27",
        "text": "You find a dirty install item in storage. What do you do?",
        "choices": {
            "a": "Do not install it, and contact the manager for cleaning or repair",
            "b": "Wipe it off on site and install it",
            "c": "Install it if the dirt is only cosmetic",
            "d": "Install it and report it at the end of the day",
        },
        "correct": "a",
        "explanation": "Never install broken, defective, dirty, or unmaintained items. Contact the manager if items need cleaning or repair.",
    },
    {
        "id": "q28",
        "text": "During a sweeping job, where does the collected dirt go?",
        "choices": {
            "a": "Dirt back onto the lot",
            "b": "Dirt in the dumpster",
            "c": "Dirt in the washout container",
            "d": "Dirt into the storm drain",
        },
        "correct": "a",
        "explanation": "Dispose of dirt back onto the lot.",
    },
    {
        "id": "q29",
        "text": "Why must you never hose tracked-out dirt into storm drains?",
        "choices": {
            "a": "It is a violation of the Utah SWPPP permit",
            "b": "It wastes water and the client is billed for it",
            "c": "It is only discouraged by company policy",
            "d": "It is allowed as long as the dirt is clean fill",
        },
        "correct": "a",
        "explanation": "Hosing down track out is a violation of the Utah SWPPP permit. Sweep dirt back onto the lot when possible.",
    },
    {
        "id": "q30",
        "text": "For before and after pictures, how should the AFTER pictures be taken, and when must all pictures be uploaded?",
        "choices": {
            "a": "From the same angles as the BEFORE pictures, uploaded before you leave the jobsite",
            "b": "From whichever angle looks best, uploaded by end of day",
            "c": "From the same angles as the BEFORE pictures, uploaded the next morning",
            "d": "Only AFTER pictures are needed, uploaded before you leave the jobsite",
        },
        "correct": "a",
        "explanation": "Take AFTER pictures from the same angles as before, and upload all pictures to the respective files before you leave the jobsite.",
    },
    {
        "id": "q31",
        "text": "You find a hardened washout spill. What is the correct handling?",
        "choices": {
            "a": "Note if we are taking care of washout spills, take a BEFORE picture, break it up with the pickaxe if needed, scrape it into a bucket, put it in the dumpster, take an AFTER picture",
            "b": "Take a BEFORE picture, break it up with the pickaxe if needed, scrape it into a bucket, put it in the dumpster, take an AFTER picture",
            "c": "Take a BEFORE picture, break it up with the pickaxe and spread the pieces on the lot, take an AFTER picture",
            "d": "Take a BEFORE picture, cover it with dirt, take an AFTER picture",
        },
        "correct": "a",
        "explanation": "Washout material must be removed and never allowed into storm drains. Use the pickaxe on hard or cured spills and put all material in the dumpster.",
    },
    {
        "id": "q32",
        "text": "Before taking inspection pictures, what must be done, and what must each photo show?",
        "choices": {
            "a": "Complete all cleaning first. Show the full BMP, its surroundings, and whether water or another substance is leaving it",
            "b": "Take the inspection pictures first, then clean. Show the BMP up close",
            "c": "Complete all cleaning first. Show only the BMP close up",
            "d": "Get manager approval first. Show the BMP with a date stamp only",
        },
        "correct": "a",
        "explanation": "Complete all cleaning activities before inspection. Photos show the complete BMP, surroundings for context, and water flow and function.",
    },
    {
        "id": "q33",
        "text": "How should a jobsite camera's solar panel be set up?",
        "choices": {
            "a": "Facing south at a 45-degree angle",
            "b": "Facing north at a 45-degree angle",
            "c": "Facing south at a 90-degree angle",
            "d": "Facing east at a 30-degree angle",
        },
        "correct": "a",
        "explanation": "Confirm the solar panel is facing south at a 45-degree angle.",
    },
    {
        "id": "q34",
        "text": "How often must each employee film a marketing video?",
        "choices": {
            "a": "Once a week, and the best video earns $15",
            "b": "Once a month, and the best video earns $15",
            "c": "Once a week, and the best video earns $50",
            "d": "Twice a week, and the best video earns $15",
        },
        "correct": "a",
        "explanation": "Each employee films one video per week (4 per month). The best video created receives a $15 award.",
    },
    {
        "id": "q35",
        "text": "When you return the truck at the end of the day, which is required?",
        "choices": {
            "a": "Remove all personal and company tools, inventory, and items, remove trash, record the ending odometer, and lock all doors and windows",
            "b": "Leave tools in the truck for the next day, record the ending odometer, and lock the doors",
            "c": "Refuel to full, remove trash, and leave the windows cracked for airflow",
            "d": "Remove only personal items, and record the odometer the next morning",
        },
        "correct": "a",
        "explanation": "On return, take out all personal and company tools, inventory, and items, remove trash and debris, organize vehicle items, record the ending odometer, and lock all doors and windows.",
    },
]

# Every question ever asked. Drives the database columns and the admin detail
# view, so historical attempts keep rendering against their own questions.
QUESTION_BANK = RETIRED_QUESTIONS + QUESTIONS

QUESTION_BY_ID = {q["id"]: q for q in QUESTIONS}
# Canonical 1-N numbering over the *active* set, used when reporting unanswered
# questions. The order employees see is shuffled; these numbers stay fixed.
QUESTION_NUMBER = {q["id"]: i + 1 for i, q in enumerate(QUESTIONS)}

TOTAL_QUESTIONS = len(QUESTIONS)
PASS_SCORE = -(-PASS_PERCENT * TOTAL_QUESTIONS // 100)  # ceil, e.g. 80% of 15 -> 12

SURVEY_FEATURES = [
    "live_camera_dashboard",
    "homeowner_portal",
    "compliance_documents",
    "hourly_photo_log",
    "build_timelapse",
    "motion_activated_security",
    "view_and_pay_invoices",
]


# Without a timeout, psycopg2.connect blocks until the OS gives up (minutes),
# which leaves the browser waiting forever on "Submitting...". Fail fast instead
# so the employee gets a real error they can act on.
DB_CONNECT_TIMEOUT = 10


def get_db():
    return psycopg2.connect(DATABASE_URL, connect_timeout=DB_CONNECT_TIMEOUT)


def init_db():
    # Columns for every question ever asked, so retired columns keep their data.
    answer_cols = ",\n".join(
        f"            {q['id']}_answer TEXT,\n"
        f"            {q['id']}_correct BOOLEAN"
        for q in QUESTION_BANK
    )
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS survey_responses (
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
    """)
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS quiz_attempts (
            id SERIAL PRIMARY KEY,
            submitted_at TIMESTAMPTZ NOT NULL,
            full_name TEXT NOT NULL,
            score INTEGER NOT NULL,
            percentage INTEGER NOT NULL,
            passed BOOLEAN NOT NULL,
            quiz_version INTEGER NOT NULL,
            total_questions INTEGER NOT NULL,
{answer_cols}
        )
    """)
    conn.commit()

    # --- Migration from the version 1 (10-question) schema -----------------
    # CREATE TABLE IF NOT EXISTS leaves an existing table alone, so bring an
    # older quiz_attempts table forward. Each statement commits on its own:
    # if one fails the rest still run, and all of these are safe to re-run.
    migrations = [
        # Columns added in version 2.
        "ALTER TABLE quiz_attempts ADD COLUMN IF NOT EXISTS quiz_version INTEGER",
        "ALTER TABLE quiz_attempts ADD COLUMN IF NOT EXISTS total_questions INTEGER",
    ]
    for q in QUESTION_BANK:
        migrations.append(
            f"ALTER TABLE quiz_attempts ADD COLUMN IF NOT EXISTS {q['id']}_answer TEXT"
        )
        migrations.append(
            f"ALTER TABLE quiz_attempts ADD COLUMN IF NOT EXISTS {q['id']}_correct BOOLEAN"
        )
    migrations += [
        # site_crew is no longer collected. Old values are kept, but the column
        # must stop being NOT NULL or every new insert would fail.
        "ALTER TABLE quiz_attempts ALTER COLUMN site_crew DROP NOT NULL",
        # Stamp pre-versioning attempts as version 1 (the 10-question quiz).
        "UPDATE quiz_attempts SET quiz_version = 1 WHERE quiz_version IS NULL",
        "UPDATE quiz_attempts SET total_questions = 10 WHERE total_questions IS NULL",
    ]

    for statement in migrations:
        try:
            cur.execute(statement)
            conn.commit()
        except Exception as e:
            conn.rollback()
            # Expected when the column never existed (e.g. site_crew on a fresh
            # database). Logged rather than raised so startup still completes.
            app.logger.info("Migration skipped (%s): %s", statement.split(" ADD ")[0], e)

    cur.close()
    conn.close()


# --- Pages ---------------------------------------------------------------

@app.route("/")
def quiz_page():
    return send_from_directory(".", "jtswppp-sop-quiz.html")


@app.route("/survey")
def survey_page():
    return send_from_directory(".", "jtswppp-feature-survey.html")


# --- Quiz ----------------------------------------------------------------

@app.route("/quiz/questions")
def quiz_questions():
    """All 20 questions, with both question order and choice order shuffled
    per attempt, so easy and hard questions come out interleaved.

    Only the choice keys and text go out -- never which key is correct.
    Answers are tracked by question id, so the shuffled order is harmless.
    """
    pool = list(QUESTIONS)
    random.shuffle(pool)

    out = []
    for q in pool:
        keys = list(q["choices"].keys())
        random.shuffle(keys)
        out.append({
            "id": q["id"],
            "text": q["text"],
            "choices": [{"key": k, "text": q["choices"][k]} for k in keys],
        })
    return jsonify({
        "questions": out,
        "total": TOTAL_QUESTIONS,
        "pass_percent": PASS_PERCENT,
        "pass_score": PASS_SCORE,
        "quiz_version": QUIZ_VERSION,
    })


@app.route("/quiz/submit", methods=["POST"])
def quiz_submit():
    data = request.get_json(force=True, silent=True) or {}

    full_name = (data.get("full_name") or "").strip()
    if not full_name:
        return jsonify({"ok": False, "error": "Your full name is required."}), 400

    answers = data.get("answers") or {}
    if not isinstance(answers, dict):
        return jsonify({"ok": False, "error": "Malformed answers."}), 400

    # Missing questions are reported by their canonical 1-20 number, which is
    # independent of the shuffled order this employee saw.
    missing = sorted(
        QUESTION_NUMBER[q["id"]] for q in QUESTIONS
        if answers.get(q["id"]) not in q["choices"]
    )
    if missing:
        nums = ", ".join(str(n) for n in missing)
        return jsonify({
            "ok": False,
            "error": f"Please answer every question. {len(missing)} still unanswered.",
            "missing": missing,
            "missing_detail": nums,
        }), 400

    # Review order follows the order the employee actually saw, when the client
    # reports it. Falls back to canonical order.
    client_order = data.get("order")
    if (isinstance(client_order, list)
            and sorted(client_order) == sorted(QUESTION_BY_ID.keys())):
        review_ids = client_order
    else:
        review_ids = [q["id"] for q in QUESTIONS]

    # Grade server-side.
    score = 0
    results_by_id = {}
    for q in QUESTIONS:
        chosen = answers[q["id"]]
        is_correct = chosen == q["correct"]
        if is_correct:
            score += 1
        results_by_id[q["id"]] = {
            "question": q["text"],
            "your_answer": q["choices"][chosen],
            "correct_answer": q["choices"][q["correct"]],
            "is_correct": is_correct,
            "explanation": q["explanation"],
        }

    breakdown = []
    for position, qid in enumerate(review_ids, start=1):
        entry = dict(results_by_id[qid])
        entry["number"] = position
        breakdown.append(entry)

    percentage = round(score / TOTAL_QUESTIONS * 100)
    passed = percentage >= PASS_PERCENT

    result = {
        "ok": True,
        "full_name": full_name,
        "score": score,
        "total": TOTAL_QUESTIONS,
        "percentage": percentage,
        "passed": passed,
        "pass_percent": PASS_PERCENT,
        "quiz_version": QUIZ_VERSION,
        "breakdown": breakdown,
    }

    if not DATABASE_URL:
        # Local development only. On Railway DATABASE_URL is always set, so a
        # real attempt can never silently go unrecorded.
        app.logger.warning("DATABASE_URL not set -- attempt graded but not stored.")
        result["recorded"] = False
        return jsonify(result)

    cols = ["submitted_at", "full_name", "score", "percentage", "passed",
            "quiz_version", "total_questions"]
    vals = [datetime.now(timezone.utc), full_name, score, percentage, passed,
            QUIZ_VERSION, TOTAL_QUESTIONS]
    for q in QUESTIONS:
        cols += [f"{q['id']}_answer", f"{q['id']}_correct"]
        vals += [q["choices"][answers[q["id"]]], results_by_id[q["id"]]["is_correct"]]

    placeholders = ", ".join(["%s"] * len(vals))
    statement = f"INSERT INTO quiz_attempts ({', '.join(cols)}) VALUES ({placeholders})"

    def do_insert():
        conn = get_db()
        cur = conn.cursor()
        cur.execute(statement, vals)
        conn.commit()
        cur.close()
        conn.close()

    try:
        try:
            do_insert()
        except psycopg2.Error:
            # The table or a column may be missing because init_db() could not
            # run at startup. Repair the schema once and retry before giving up,
            # so a bad boot does not permanently stop scores being recorded.
            app.logger.warning("Insert failed; re-running init_db() and retrying.")
            init_db()
            do_insert()
    except Exception as e:
        # Log the full detail for the deploy logs, and send back the error class
        # so a failure is diagnosable from the browser without digging.
        app.logger.error("DB error saving attempt: %s: %s", type(e).__name__, e)
        return jsonify({
            "ok": False,
            "error": "Could not save your score. Please tell your manager.",
            "detail": f"{type(e).__name__}: {str(e)[:200]}",
        }), 500

    result["recorded"] = True
    return jsonify(result)


# --- Admin ---------------------------------------------------------------

def require_admin():
    """Returns a Response to send back if auth failed, else None."""
    if not ADMIN_PASSWORD:
        return Response(
            "Admin pages are disabled because ADMIN_PASSWORD is not set.",
            503,
            mimetype="text/plain",
        )
    auth = request.authorization
    if not auth or auth.password != ADMIN_PASSWORD:
        return Response(
            "Authentication required.",
            401,
            {"WWW-Authenticate": 'Basic realm="JT SWPPP Admin"'},
        )
    return None


ADMIN_CSS = """
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  :root {
    --dark: #013040; --mid: #016080; --light: #02BFFF; --lighter: #e6f7ff;
    --text: #1a1a1a; --text-muted: #6b7280; --border: #e2e8f0; --bg: #f8fafc;
    --white: #fff; --danger: #dc2626; --success: #059669;
  }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: var(--bg); color: var(--text); }
  .page-header { background: var(--dark); padding: 24px; }
  .logo { font-size: 13px; font-weight: 600; letter-spacing: .12em;
          text-transform: uppercase; color: var(--light); margin-bottom: 8px; }
  .page-header h1 { font-size: 20px; color: #fff; font-weight: 600; }
  .container { max-width: 1000px; margin: 0 auto; padding: 24px 16px 48px; }
  .bar { display: flex; justify-content: space-between; align-items: center;
         gap: 12px; margin-bottom: 16px; flex-wrap: wrap; }
  .count { font-size: 13px; color: var(--text-muted); }
  .btn { display: inline-block; padding: 9px 16px; font-size: 14px; font-weight: 600;
         color: #fff; background: var(--dark); border: none; border-radius: 8px;
         text-decoration: none; cursor: pointer; }
  .btn.sec { background: var(--white); color: var(--text-muted);
             border: 1px solid var(--border); font-weight: 500; }
  .card { background: var(--white); border: 1px solid var(--border);
          border-radius: 12px; overflow: hidden; }
  .scroll { overflow-x: auto; }
  table { width: 100%; border-collapse: collapse; font-size: 14px; }
  th { text-align: left; font-size: 11.5px; text-transform: uppercase;
       letter-spacing: .06em; color: var(--text-muted); padding: 12px 14px;
       border-bottom: 1px solid var(--border); white-space: nowrap; }
  td { padding: 12px 14px; border-bottom: 1px solid var(--border); }
  tr:last-child td { border-bottom: none; }
  tr:hover td { background: #fafcfe; }
  td a { color: var(--mid); font-weight: 500; text-decoration: none; }
  td a:hover { text-decoration: underline; }
  .pill { display: inline-block; padding: 3px 10px; border-radius: 999px;
          font-size: 12px; font-weight: 600; }
  .pill.pass { background: #e8f7f1; color: var(--success); }
  .pill.fail { background: #fdeaea; color: var(--danger); }
  .ver { display: inline-block; padding: 3px 9px; border-radius: 999px;
         background: var(--lighter); color: var(--mid);
         font-size: 12px; font-weight: 600; }
  .note { background: #fff8e1; border: 1px solid #f0d98a; color: #7a5c00;
          border-radius: 8px; font-size: 13px; line-height: 1.5;
          padding: 10px 12px; margin-bottom: 12px; }
  .empty { padding: 36px 20px; text-align: center; color: var(--text-muted);
           font-size: 14px; }
  .meta { background: var(--dark); color: #fff; border-radius: 12px;
          padding: 16px 18px; margin-bottom: 16px; }
  .meta h2 { font-size: 18px; margin-bottom: 4px; }
  .meta p { font-size: 13px; opacity: .7; }
  .q { background: var(--white); border: 1px solid var(--border);
       border-left: 3px solid var(--border); border-radius: 10px;
       padding: 14px 16px; margin-bottom: 8px; }
  .q.right { border-left-color: var(--success); }
  .q.wrong { border-left-color: var(--danger); }
  .q-text { font-size: 14px; font-weight: 500; line-height: 1.45; margin-bottom: 8px; }
  .q-line { font-size: 13px; color: var(--text-muted); line-height: 1.6; }
  .q-line b { color: var(--text); font-weight: 600; }
"""


def admin_shell(title, body):
    return Response(
        f"<!DOCTYPE html><html lang=en><head><meta charset=UTF-8>"
        f"<meta name=viewport content='width=device-width, initial-scale=1'>"
        f"<title>{escape(title)}</title><style>{ADMIN_CSS}</style></head>"
        f"<body>{body}</body></html>",
        mimetype="text/html",
    )


# Columns read for the admin views and CSV. site_crew is deliberately absent:
# old values stay in the database but are no longer displayed or exported.
ATTEMPT_COLUMNS = (
    ["id", "submitted_at", "full_name", "score", "percentage", "passed",
     "quiz_version", "total_questions"]
    + [c for q in QUESTION_BANK for c in (f"{q['id']}_answer", f"{q['id']}_correct")]
)


def attempt_total(row, idx):
    """How many questions this attempt actually had.

    Stored on the row for version 2 onward; falls back to the known total for
    older versions so pre-existing attempts render as x/10, not x/20.
    """
    stored = row[idx["total_questions"]]
    if stored:
        return stored
    return VERSION_TOTALS.get(row[idx["quiz_version"]], TOTAL_QUESTIONS)


def fetch_attempts():
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        f"SELECT {', '.join(ATTEMPT_COLUMNS)} FROM quiz_attempts "
        "ORDER BY submitted_at DESC, id DESC"
    )
    rows = cur.fetchall()
    col_names = [d[0] for d in cur.description]
    cur.close()
    conn.close()
    return col_names, rows


@app.route("/admin/scores")
def admin_scores():
    denied = require_admin()
    if denied:
        return denied
    if not DATABASE_URL:
        return admin_shell("Scores", (
            "<div class=page-header><div class=logo>JT SWPPP</div>"
            "<h1>SOP Quiz Scores</h1></div><div class=container><div class=card>"
            "<p class=empty>No database configured. Attempts are recorded once "
            "this is deployed with <code>DATABASE_URL</code> set.</p></div></div>"
        ))

    cols, rows = fetch_attempts()
    idx = {name: i for i, name in enumerate(cols)}

    if rows:
        body_rows = []
        for r in rows:
            passed = r[idx["passed"]]
            when = r[idx["submitted_at"]]
            total = attempt_total(r, idx)
            version = r[idx["quiz_version"]] or 1
            body_rows.append(
                "<tr>"
                f"<td><a href='/admin/scores/{r[idx['id']]}'>{escape(r[idx['full_name']])}</a></td>"
                f"<td>{when.strftime('%b %-d, %Y %-I:%M %p')}</td>"
                f"<td>{r[idx['score']]}/{total} &middot; {r[idx['percentage']]}%</td>"
                f"<td><span class=ver>v{version}</span></td>"
                f"<td><span class='pill {'pass' if passed else 'fail'}'>"
                f"{'PASS' if passed else 'FAIL'}</span></td>"
                "</tr>"
            )
        table = (
            "<div class='card scroll'><table><thead><tr>"
            "<th>Name</th><th>Date</th><th>Score</th><th>Quiz</th><th>Result</th>"
            "</tr></thead><tbody>" + "".join(body_rows) + "</tbody></table></div>"
        )
    else:
        table = "<div class=card><p class=empty>No attempts yet.</p></div>"

    return admin_shell("SOP Quiz Scores", (
        "<div class=page-header><div class=logo>JT SWPPP</div>"
        "<h1>SOP Quiz Scores</h1></div>"
        "<div class=container><div class=bar>"
        f"<span class=count>{len(rows)} attempt{'' if len(rows) == 1 else 's'} "
        f"&middot; v{QUIZ_VERSION} passing is {PASS_SCORE}/{TOTAL_QUESTIONS} "
        f"({PASS_PERCENT}%) &middot; v1 had 10 questions, v2 had 20</span>"
        "<a class=btn href='/admin/scores.csv'>Download CSV</a>"
        f"</div>{table}</div>"
    ))


@app.route("/admin/scores/<int:attempt_id>")
def admin_attempt(attempt_id):
    denied = require_admin()
    if denied:
        return denied
    if not DATABASE_URL:
        return Response("No database configured.", 503, mimetype="text/plain")

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        f"SELECT {', '.join(ATTEMPT_COLUMNS)} FROM quiz_attempts WHERE id = %s",
        (attempt_id,),
    )
    row = cur.fetchone()
    cols = [d[0] for d in cur.description]
    cur.close()
    conn.close()

    if not row:
        return Response("Attempt not found.", 404, mimetype="text/plain")

    idx = {name: i for i, name in enumerate(cols)}
    passed = row[idx["passed"]]
    total = attempt_total(row, idx)
    version = row[idx["quiz_version"]] or 1

    # Walk the whole bank, not just the live set: an attempt only has data for
    # the questions it was actually asked, and retired questions still render
    # against their own original wording. Numbering is per attempt.
    blocks = []
    position = 0
    for q in QUESTION_BANK:
        given = row[idx[f"{q['id']}_answer"]]
        ok = row[idx[f"{q['id']}_correct"]]
        if given is None and ok is None:
            continue
        position += 1
        correct_text = q["choices"][q["correct"]]
        lines = (
            f"<div class=q-line><b>{'Correct' if ok else 'Answered'}:</b> "
            f"{escape(given) if given is not None else '&mdash;'}</div>"
        )
        if not ok:
            lines += (
                f"<div class=q-line><b>Correct answer:</b> {escape(correct_text)}</div>"
                f"<div class=q-line>{escape(q['explanation'])}</div>"
            )
        blocks.append(
            f"<div class='q {'right' if ok else 'wrong'}'>"
            f"<div class=q-text>{position}. {escape(q['text'])}</div>"
            f"{lines}</div>"
        )

    note = ""
    if version < QUIZ_VERSION:
        note = (
            f"<p class=note>Taken on quiz v{version} ({total} questions). "
            f"The current quiz is v{QUIZ_VERSION} with {TOTAL_QUESTIONS} questions, "
            "so this score is not directly comparable.</p>"
        )

    when = row[idx["submitted_at"]].strftime("%b %-d, %Y at %-I:%M %p")
    return admin_shell(f"Attempt — {row[idx['full_name']]}", (
        "<div class=page-header><div class=logo>JT SWPPP</div>"
        "<h1>Attempt detail</h1></div>"
        "<div class=container>"
        "<a class='btn sec' href='/admin/scores'>&larr; All scores</a>"
        "<div class=meta style='margin-top:16px'>"
        f"<h2>{escape(row[idx['full_name']])} &mdash; "
        f"{row[idx['score']]}/{total} ({row[idx['percentage']]}%) "
        f"{'PASS' if passed else 'FAIL'}</h2>"
        f"<p>Quiz v{version} &middot; {when}</p></div>"
        f"{note}{''.join(blocks)}</div>"
    ))


@app.route("/admin/health")
def admin_health():
    """Diagnostics for 'the quiz will not submit'. Reports whether the database
    is configured, reachable, and shaped the way an insert needs."""
    denied = require_admin()
    if denied:
        return denied

    report = {
        "database_url_set": bool(DATABASE_URL),
        "quiz_version": QUIZ_VERSION,
        "active_questions": TOTAL_QUESTIONS,
        "connect_timeout_seconds": DB_CONNECT_TIMEOUT,
        "startup_db_error": STARTUP_DB_ERROR,
    }

    if not DATABASE_URL:
        report["verdict"] = ("DATABASE_URL is not set. Attach a Postgres service "
                             "in Railway; scores cannot be saved without it.")
        return jsonify(report), 503

    try:
        started = datetime.now(timezone.utc)
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        report["connected"] = True
        report["connect_seconds"] = round(
            (datetime.now(timezone.utc) - started).total_seconds(), 2)

        cur.execute("""
            SELECT column_name, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'quiz_attempts'
        """)
        cols = {name: nullable for name, nullable in cur.fetchall()}
        report["table_exists"] = bool(cols)
        report["column_count"] = len(cols)

        # The two things that actually break an insert.
        missing = [c for c in ATTEMPT_COLUMNS if c not in cols]
        report["missing_columns"] = missing
        not_null_blockers = sorted(
            c for c, nullable in cols.items()
            if nullable == "NO" and c not in ATTEMPT_COLUMNS and c != "id"
        )
        report["not_null_columns_we_never_write"] = not_null_blockers

        cur.execute("SELECT COUNT(*) FROM quiz_attempts")
        report["attempts_stored"] = cur.fetchone()[0]
        cur.close()
        conn.close()

        if missing:
            report["verdict"] = f"Insert will fail: missing columns {missing}."
        elif not_null_blockers:
            report["verdict"] = (
                f"Insert will fail: {not_null_blockers} are NOT NULL but are never "
                "written. The startup migration should have dropped these.")
        else:
            report["verdict"] = "Healthy. Inserts should succeed."
        return jsonify(report)

    except Exception as e:
        report["connected"] = False
        report["error"] = f"{type(e).__name__}: {str(e)[:300]}"
        report["verdict"] = ("Cannot reach the database. Check that the Postgres "
                             "service is attached to this service in Railway.")
        return jsonify(report), 500


@app.route("/admin/scores.csv")
def admin_scores_csv():
    denied = require_admin()
    if denied:
        return denied
    if not DATABASE_URL:
        return Response("No database configured.", 503, mimetype="text/plain")

    cols, rows = fetch_attempts()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(cols)
    writer.writerows(rows)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=quiz_attempts.csv"},
    )


# --- Legacy feature survey ----------------------------------------------

@app.route("/submit", methods=["POST"])
def submit():
    data = request.get_json(force=True)

    company_name = (data.get("company_name") or "").strip()

    allocations = {}
    total = 0
    for feature in SURVEY_FEATURES:
        try:
            val = max(0, int(data.get(feature, 0)))
        except (TypeError, ValueError):
            val = 0
        allocations[feature] = val
        total += val

    if total > 100:
        return jsonify({"ok": False, "error": "Total allocation exceeds $100."}), 400

    if total == 0:
        return jsonify({"ok": False, "error": "No budget allocated."}), 400

    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO survey_responses (
                submitted_at, company_name,
                live_camera_dashboard, homeowner_portal, compliance_documents,
                hourly_photo_log, build_timelapse, motion_activated_security,
                view_and_pay_invoices, total_allocated
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            datetime.now(timezone.utc),
            company_name,
            allocations["live_camera_dashboard"],
            allocations["homeowner_portal"],
            allocations["compliance_documents"],
            allocations["hourly_photo_log"],
            allocations["build_timelapse"],
            allocations["motion_activated_security"],
            allocations["view_and_pay_invoices"],
            total,
        ))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        app.logger.error("DB error: %s", e)
        return jsonify({"ok": False, "error": "Database error. Please try again."}), 500

    return jsonify({"ok": True})


@app.route("/export")
def export():
    denied = require_admin()
    if denied:
        return denied

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM survey_responses ORDER BY submitted_at ASC")
    rows = cur.fetchall()
    col_names = [desc[0] for desc in cur.description]
    cur.close()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(col_names)
    writer.writerows(rows)

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=survey_responses.csv"}
    )


STARTUP_DB_ERROR = None

if DATABASE_URL:
    try:
        init_db()
    except Exception as _e:
        # A database that is slow or briefly unreachable at deploy time must not
        # take the whole site down -- an uncaught error here kills the gunicorn
        # worker and every route 502s, including the pages that would explain
        # why. Record it, keep serving, and surface it at /admin/health.
        STARTUP_DB_ERROR = f"{type(_e).__name__}: {_e}"
        app.logger.error("init_db() failed at startup: %s", STARTUP_DB_ERROR)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
