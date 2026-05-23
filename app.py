import os
import csv
import io
import psycopg2
from flask import Flask, request, jsonify, send_from_directory, Response
from datetime import datetime, timezone

app = Flask(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL")

FEATURES = [
    "live_camera_dashboard",
    "homeowner_portal",
    "compliance_documents",
    "hourly_photo_log",
    "build_timelapse",
    "motion_activated_security",
    "view_and_pay_invoices",
]


def get_db():
    conn = psycopg2.connect(DATABASE_URL)
    return conn


def init_db():
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
    conn.commit()
    cur.close()
    conn.close()


@app.route("/")
def index():
    return send_from_directory(".", "jtswppp-feature-survey.html")


@app.route("/submit", methods=["POST"])
def submit():
    data = request.get_json(force=True)

    company_name = (data.get("company_name") or "").strip()

    # Parse and validate each feature allocation
    allocations = {}
    total = 0
    for feature in FEATURES:
        try:
            val = int(data.get(feature, 0))
            val = max(0, val)
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


if DATABASE_URL:
    init_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
