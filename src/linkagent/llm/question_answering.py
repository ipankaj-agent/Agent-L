from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from linkagent.llm.client import OpenRouterClient

logger = logging.getLogger(__name__)

PROMPT_TEMPLATE_PATH = Path(__file__).resolve().parent / "prompts" / "answer.md"


async def answer_question(
    question: str,
    options: Optional[list[dict]] = None,
) -> Optional[str]:
    """Send a form question to the LLM and return a concise answer."""
    prompt = _build_prompt(question, options)
    if not prompt:
        return None

    client = OpenRouterClient()
    return client.invoke(prompt)


def _build_prompt(
    question: str,
    options: Optional[list[dict]] = None,
) -> str:
    """Load the answer prompt template and substitute the current question."""
    try:
        template = PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        logger.warning("Answer prompt template was not found; using fallback prompt")
        template = (
            "Answer the following form question briefly and directly.\n"
            "Question: {question}"
        )

    if not template:
        template = (
            "Answer the following form question briefly and directly.\n"
            "Question: {question}"
        )

    prompt = template.replace("{question}", question)

    if options:
        option_text = "\n".join(f"- {o['label']}" for o in options)
        prompt = prompt.replace(
            "{options}",
            f"Available options:\n{option_text}"
        )
    else:
        prompt = prompt.replace("{options}", "")

    return prompt