from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional

from linkagent.llm.client import OpenRouterClient

logger = logging.getLogger(__name__)

PROMPT_TEMPLATE_PATH = Path(__file__).resolve().parent / "prompts" / "tailor.md"


def extract_summary_from_resume_text(resume_text: str) -> str:
    """Best-effort extraction of the existing summary from resume text."""
    if not resume_text:
        return ""

    paragraphs = [part.strip() for part in re.split(r"\n{2,}", resume_text) if part.strip()]
    if not paragraphs:
        return ""

    for paragraph in paragraphs:
        lowered = paragraph.lower()
        if any(marker in lowered for marker in ("summary", "profile", "about", "overview", "objective")):
            return paragraph.replace("\n", " ").strip()

    return paragraphs[0].replace("\n", " ").strip()


def build_tailoring_prompt(job_description: str, current_summary: str) -> str:
    """Create an ATS-focused prompt for tailoring a resume summary from the template."""
    try:
        template = PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8").strip()
    except FileNotFoundError as e:
        logger.exception("Tailoring prompt template was not found; using fallback prompt")
        template = (
            "You are an expert resume writer. Tailor the following resume summary to align with the job description.\n\n"
            "Current Summary: {current_summary}\n\n"
            "Job Description: {job_description}\n\n"
            "Please provide a concise, ATS-friendly summary that highlights relevant skills and experience."
        )

    return (
        template.replace("{current_summary}", current_summary or "No existing summary provided.")
        .replace("{job_description}", job_description)
    )


def generate_tailored_summary(
    job_description: str,
    current_summary: str = "",
    llm_client: Optional[object] = None,
    resume_text: Optional[str] = None,
) -> str:
    """Generate a tailored summary using the LLM when available, else use a fallback."""
    prompt = build_tailoring_prompt(job_description, current_summary)

    client = llm_client or OpenRouterClient()
    try:
        response = client.invoke(prompt)
        if response:
            cleaned = response.strip().strip('"').strip()
            logger.info("Generated tailored summary: %s", cleaned)
            if cleaned:
                return cleaned
    except Exception as e:
        logger.exception("Failed to generate tailored summary")

    return current_summary

