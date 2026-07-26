from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import sqlite3
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[3]
PACKAGE_ROOT = Path(__file__).resolve().parents[1]

DB_PATH = BASE_DIR / "data" / "storage" / "applications.db"
UI_DIR = PACKAGE_ROOT / "ui"

app = FastAPI()

app.mount("/dist", StaticFiles(directory=UI_DIR / "dist"), name="dist")


@app.get("/")
def dashboard():
    return FileResponse(UI_DIR / "index.html")



def fetch_jobs(session_id: int | None = None):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    if session_id is None:
        cur.execute("""
            SELECT
                id,
                session_id,
                linkedin_job_id,
                title,
                description,
                status,
                created_at
            FROM jobs
            ORDER BY created_at DESC
        """)
    else:
        cur.execute("""
            SELECT
                id,
                session_id,
                linkedin_job_id,
                title,
                description,
                status,
                created_at
            FROM jobs
            WHERE session_id = ?
            ORDER BY created_at DESC
        """, (session_id,))

    rows = cur.fetchall()

    jobs = []

    for row in rows:
        cur.execute("""
            SELECT
                question,
                answer,
                field_type,
                options
            FROM questions
            WHERE job_id = ?
        """, (row["id"],))

        questions = [
            {
                "question": q["question"],
                "answer": q["answer"],
                "field_type": q["field_type"],
                "options": q["options"].split(",") if q["options"] else [],
            }
            for q in cur.fetchall()
        ]

        jobs.append({
            "job_id": row["id"],
            "session_id": row["session_id"],
            "linkedin_job_id": row["linkedin_job_id"],
            "title": row["title"],
            "description": row["description"],
            "status": row["status"],
            "created_at": row["created_at"],
            "questions_answers": questions,
        })

    conn.close()

    return jobs

@app.get("/api/jobs")
def jobs():
    return fetch_jobs()

@app.get("/api/jobs/{session_id}")
def jobs_by_session(session_id: int):
    return fetch_jobs(session_id)

@app.get("/api/sessions")
def sessions():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
        SELECT
            s.id,
            s.started_at,
            s.finished_at,
            COUNT(j.id) AS total_jobs
        FROM sessions s
        LEFT JOIN jobs j
            ON j.session_id = s.id
        GROUP BY s.id
        ORDER BY s.started_at DESC
    """)

    sessions = [dict(row) for row in cur.fetchall()]

    conn.close()

    return sessions

