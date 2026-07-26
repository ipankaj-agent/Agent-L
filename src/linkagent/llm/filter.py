from __future__ import annotations

import logging
from typing import Optional
from pathlib import Path

from linkagent.llm.client import OpenRouterClient


logger = logging.getLogger(__name__)

PROMPT_TEMPLATE_PATH = Path(__file__).resolve().parent / "prompts" / "score.md"


def build_filter_prompt(job_description: str) -> str:
    """Create a prompt for filtering a job using the template."""
    try:
        template = PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        logger.exception("Job filter prompt template was not found; using fallback prompt")
        template = (
            "You are an AI job filter.\n\n"
            "Based on the following job description, determine whether the job "
            "should be SKIP or APPLY.\n\n"
            "Respond with ONLY one word: SKIP or APPLY.\n\n"
            "Job Description:\n"
            "{job_description}"
        )

    return template.replace("{job_description}", job_description)


def filter_job(
    job_description: str,
    llm_client: Optional[object] = None,
) -> bool:
    """Return True if the job should be skipped, otherwise False."""
    prompt = build_filter_prompt(job_description)

    client = llm_client or OpenRouterClient()
    try:
        response = client.invoke(prompt)
        if response:
            decision = response.strip().strip('"').strip().upper()
            logger.info("Job filter decision: %s", decision)

            if decision == "SKIP":
                return True

            if decision == "APPLY":
                return False

    except Exception as e:
        logger.exception("Failed to filter job... Will continue apply : {e}")

    # If filtering fails, don't skip the job.
    logger.info("NO Filtration Found for the job")
    return False