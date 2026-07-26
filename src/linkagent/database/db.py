from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from linkagent.database.models import JobRecord


def init_db(db_path: str | Path | None = None) -> Path:
    """Create the SQLite database and required tables if they do not exist."""
    path = Path(db_path) if db_path is not None else Path("data/storage/applications.db")
    path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER,
                linkedin_job_id INTEGER UNIQUE,
                title TEXT NOT NULL,
                description TEXT,
                resume_id INTEGER,
                status TEXT DEFAULT 'pending',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (resume_id) REFERENCES resumes(id),
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER NOT NULL,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                field_type TEXT,
                options TEXT,
                FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                finished_at DATETIME
            );
            """
        )
        conn.commit()

    return path

def start_session(
    db_path: str | Path | None = None,
) -> int:
    """Start a new application session and return its ID."""
    path = init_db(db_path)

    with sqlite3.connect(path) as conn:
        cursor = conn.execute(
            "INSERT INTO sessions DEFAULT VALUES"
        )
        conn.commit()
        return cursor.lastrowid
    
def finish_session(
    session_id: int,
    db_path: str | Path | None = None,
) -> None:
    """Mark an application session as completed."""
    path = init_db(db_path)

    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            UPDATE sessions
            SET finished_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (session_id,),
        )
        conn.commit()

def get_session_id(
    db_path: str | Path | None = None,
) -> int:
    """Return the most recently created session ID."""

    path = init_db(db_path)

    with sqlite3.connect(path) as conn:
        row = conn.execute(
            """
            SELECT id
            FROM sessions
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()

    if row is None:
        raise RuntimeError("No sessions found.")

    return row[0]

def save_job_application(
    *,
    linkedin_job_id: int,
    title: str,
    description: str | None = None,
    questions: list[dict[str, Any]] | None = None,
    resume_id: int | None = None,
    status: str = "pending",
    db_path: str | Path | None = None,
) -> int | None:
    """Persist a successfully applied job and any captured questions to SQLite."""
    path = init_db(db_path)

    with sqlite3.connect(path) as conn:
        existing_job = conn.execute(
            "SELECT id FROM jobs WHERE linkedin_job_id = ?",
            (linkedin_job_id,),
        ).fetchone()


        session_id: int = get_session_id(db_path)

        if existing_job is not None:
            job_id = existing_job[0]
        else:
            cursor = conn.execute(
                """
                INSERT INTO jobs (session_id, linkedin_job_id, title, description, resume_id, status)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (session_id, linkedin_job_id, title, description, resume_id, status),
            )
            job_id = cursor.lastrowid

        for question in questions or []:
            conn.execute(
                """
                INSERT INTO questions (job_id, question, answer, field_type, options)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    question.get("question", ""),
                    question.get("answer") or "",
                    question.get("field_type"),
                    json.dumps(question.get("options")) if question.get("options") else None,
                ),
            )

        # Note: # Verify that questions.job_id references jobs.id (not linkedin_job_id). 

        conn.commit()

    return job_id


def fetch_jobs(
    db_path: str | Path | None = None,
) -> list[JobRecord]:
    """Load jobs and their captured questions from the database."""
    path = init_db(db_path)
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        job_rows = conn.execute(
            "SELECT id, session_id, linkedin_job_id, title, description, resume_id, status, created_at FROM jobs ORDER BY created_at DESC"
        ).fetchall()

        question_rows = conn.execute(
            "SELECT job_id, question, answer, field_type, options FROM questions ORDER BY id"
        ).fetchall()

    questions_by_job: dict[int, list[dict[str, Any]]] = {}
    for row in question_rows:
        options = None
        if row["options"]:
            try:
                options = json.loads(row["options"])
            except (json.JSONDecodeError, TypeError):
                options = row["options"]

        questions_by_job.setdefault(row["job_id"], []).append(
            {
                "question": row["question"],
                "answer": row["answer"],
                "field_type": row["field_type"],
                "options": options,
            }
        )

    return [
        JobRecord(
            job_id=row["id"],
            session_id=row["session_id"],
            linkedin_job_id=row["linkedin_job_id"],
            title=row["title"],
            description=row["description"],
            resume_id=row["resume_id"],
            status=row["status"] or "pending",
            created_at=row["created_at"],
            questions_answers=questions_by_job.get(row["id"], []),
        )
        for row in job_rows
    ]


def fetch_status_counts(db_path: str | Path) -> dict[str, int]:
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute("""
            SELECT status, COUNT(*) AS count
            FROM jobs
            GROUP BY status
        """).fetchall()

    return {status: count for status, count in rows}


def job_exists(
    linkedin_job_id: int,
    db_path: str | Path | None = None,
) -> bool:
    """Return True if a LinkedIn job ID already exists in the database."""
    path = init_db(db_path)

    with sqlite3.connect(path) as conn:
        result = conn.execute(
            "SELECT 1 FROM jobs WHERE linkedin_job_id = ? LIMIT 1",
            (linkedin_job_id,),
        ).fetchone()

    return result is not None

def get_unsubmitted_job_ids(
    db_path: str | Path | None = None,
) -> list[int]:
    """Return LinkedIn job IDs whose status is not 'submitted'."""
    path = init_db(db_path)

    with sqlite3.connect(path) as conn:
        rows = conn.execute(
            """
            SELECT linkedin_job_id
            FROM jobs
            WHERE status != ?
            ORDER BY id DESC
            """,
            ("submitted",),
        ).fetchall()

    return [row[0] for row in rows]


def update_job_application(
    *,
    linkedin_job_id: int,
    title: str | None = None,
    description: str | None = None,
    questions: list[dict[str, Any]] | None = None,
    resume_id: int | None = None,
    status: str | None = None,
    session_id: int | None = None,
    db_path: str | Path | None = None,
) -> bool:
    """
    Update an existing job application.

    If questions are provided, existing questions are removed and replaced.
    Returns True if the job exists and was updated, otherwise False.
    """
    path = init_db(db_path)

    with sqlite3.connect(path) as conn:
        row = conn.execute(
            """
            SELECT id
            FROM jobs
            WHERE linkedin_job_id = ?
            """,
            (linkedin_job_id,),
        ).fetchone()

        if row is None:
            return False

        job_id = row[0]

        updates: list[str] = []
        values: list[Any] = []

        if title is not None:
            updates.append("title = ?")
            values.append(title)

        if description is not None:
            updates.append("description = ?")
            values.append(description)

        if resume_id is not None:
            updates.append("resume_id = ?")
            values.append(resume_id)

        if status is not None:
            updates.append("status = ?")
            values.append(status)

        if session_id is not None:
            updates.append("session_id = ?")
            values.append(session_id)

        if updates:
            values.append(linkedin_job_id)
            conn.execute(
                f"""
                UPDATE jobs
                SET {", ".join(updates)}
                WHERE linkedin_job_id = ?
                """,
                values,
            )

        if questions is not None:
            conn.execute(
                "DELETE FROM questions WHERE job_id = ?",
                (job_id,),
            )

            conn.executemany(
                """
                INSERT INTO questions (
                    job_id,
                    question,
                    answer,
                    field_type,
                    options
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        job_id,
                        q.get("question", ""),
                        q.get("answer") or "",
                        q.get("field_type"),
                        json.dumps(q.get("options"))
                        if q.get("options") is not None
                        else None,
                    )
                    for q in questions
                ],
            )

        conn.commit()

    return True