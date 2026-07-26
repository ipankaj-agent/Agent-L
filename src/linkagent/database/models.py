from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class JobRecord:
    job_id: int
    session_id: int
    linkedin_job_id: int
    title: str
    description: str | None = None
    resume_id: int | None = None
    status: str = "pending"
    created_at: str | None = None
    questions_answers: list[dict[str, Any]] = field(default_factory=list)
