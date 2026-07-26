import hashlib
import logging
import os
import threading
import time
from typing import Any, Optional

from dotenv import load_dotenv
from openai import OpenAI, RateLimitError

try:
    import redis
except ImportError:  # pragma: no cover - optional dependency
    redis = None

load_dotenv()

logger = logging.getLogger(__name__)

OPENROUTER_MODEL = "openai/gpt-oss-120b"
RETRY_MODEL = [
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning-20260428:free",
    "liquid/lfm-2.5-1.2b-thinking-20260120:free",
    "nvidia/nemotron-3.5-content-safety-20260604:free",
]
MAX_RETRIES = 3

class OpenRouterClient:
    """Thin wrapper around the OpenRouter chat-completions endpoint via the OpenAI SDK.

    Mimics the minimal interface used by the rest of the codebase:
        client.invoke(prompt: str) -> str | None

    If the response is routed to a model in ``RETRY_MODEL`` (including known
    content-safety models that return non‑actionable text), the client will
    re‑call the LLM up to ``MAX_RETRIES`` times hoping to be routed to a
    different model.  If after the retries the model is still one of the
    undesirable ones, the response is discarded and ``None`` is returned.
    """

    _instance: Optional["OpenRouterClient"] = None
    _instance_lock = threading.Lock()

    def __new__(cls, *args: Any, **kwargs: Any) -> "OpenRouterClient":
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = OPENROUTER_MODEL,
        timeout: int = 60,
        redis_client: Optional[Any] = None,
        cache_ttl: Optional[int] = None,
    ) -> None:
        if getattr(self, "_initialized", False):
            return

        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY", "")
        self.model = model
        self.timeout = timeout
        self._redis_client = self._initialize_redis_client(redis_client)
        self._cache_ttl = cache_ttl or int(os.getenv("LLM_CACHE_TTL_SECONDS", "604800")) # 7 days
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self.api_key,
            default_headers={
                "HTTP-Referer": "https://LinkAgent/",
                "X-OpenRouter-Title": "LinkAgent",
            },
        )
        self._initialized = True

    def _initialize_redis_client(self, redis_client: Optional[Any]) -> Optional[Any]:
        if redis_client is not None:
            try:
                getattr(redis_client, "get")
                getattr(redis_client, "setex")
            except AttributeError:
                logger.warning("Provided Redis client is not initialized; continuing without cache")
                return None
            return redis_client

        if redis is None:
            return None

        redis_url = os.getenv("REDIS_URL")
        if not redis_url:
            return None

        try:
            client = redis.from_url(redis_url, decode_responses=True)
            client.ping()
            logger.info("Successfully connected to redis")
            return client
        except Exception as exc:
            logger.exception("Redis unavailable, continuing without cache: %s", exc)
            return None

    def _cache_key(self, prompt: str) -> str:
        payload = f"{self.model}:{prompt}"
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        return f"linkagent:llm:{digest}"

    def _get_cached_response(self, prompt: str) -> Optional[str]:
        if not self._redis_client:
            return None

        try:
            key = self._cache_key(prompt)
            logger.info(f"Used Response from Cached Key : {key}")
            cached_response = self._redis_client.get(key)
        except Exception as exc:
            logger.warning("Redis cache read failed: %s", exc)
            return None

        if cached_response is not None:
            logger.info("Returning cached LLM response")
        return cached_response

    def _set_cached_response(self, prompt: str, response: str) -> None:
        if not self._redis_client:
            return

        try:
            key = self._cache_key(prompt)
            logger.info(f"Setting caching for Key : {key}")
            self._redis_client.setex(self._cache_key(prompt), self._cache_ttl, response)
        except Exception as exc:
            logger.warning("Redis cache write failed: %s", exc)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def invoke(self, prompt: str) -> Optional[str]:
        """Send a prompt and return text content, with retry logic for unwanted models."""
        cached_response = self._get_cached_response(prompt)
        if cached_response is not None:
            return cached_response

        # We start with attempt 1 and go up to MAX_RETRIES +1 (the final fallback).
        for attempt in range(0, MAX_RETRIES + 1):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                )
            except RateLimitError:
                if attempt == MAX_RETRIES:
                    logger.error("Rate limit exceeded after %d retries", MAX_RETRIES)
                    return None

                delay = 2 * (attempt + 1)  # 2s, 4s, 6s...
                logger.warning("Rate limited. Retrying in %d seconds...", delay)
                time.sleep(delay)
                continue
            except Exception as e:
                logger.info(f"LLM Inference failed on attempt {attempt}")
                if attempt == MAX_RETRIES + 1:
                    return None
                continue

            # Determine the actual model used for this request
            routed_model = getattr(response, "model", None)
            logger.info("OpenRouter routed to model: %s (attempt %d)", routed_model, attempt)

            # If the routed model is one we want to avoid, initiate a retry
            # unless we are already on the final allowed attempt.
            if routed_model in RETRY_MODEL and attempt < MAX_RETRIES:
                logger.info(
                    "Response from %s – retrying (%d/%d)",
                    RETRY_MODEL,
                    attempt,
                    MAX_RETRIES,
                )
                continue

            if routed_model in RETRY_MODEL and attempt == MAX_RETRIES:
                logger.warning(
                    "Final attempt also routed to %s – skipping this response",
                    RETRY_MODEL,
                )

            extracted_response = self._extract_content(response)
            if extracted_response is None:
                logger.warning("Extracted Response is None")
                continue

            self._set_cached_response(prompt, extracted_response)
            return extracted_response

        # Should never be reached, but guard
        return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _extract_content(self, response) -> Optional[str]:
        """Safely extract text content from an OpenAI chat response."""
        try:
            choices = response.choices
            if not choices:
                return None
            msg = choices[0].message
            if msg is None:
                return None

            # Handle text
            if isinstance(msg.content, str) and msg.content.strip():
                return msg.content

            # Handle structured content
            if isinstance(msg.content, list):
                logger.warning("Received List message instead of raw text")
                text = "".join(
                    part.get("text", "") for part in msg.content if part.get("type") == "text"
                )
                if text.strip():
                    return text

            # Handle tool calls
            if getattr(msg, "tool_calls", None):
                logger.warning("Received tool call instead of text")
                return None

            logger.warning("Empty or unsupported content in response")
            return None
        except (AttributeError, IndexError, TypeError) as e:
            logger.exception("Failed to extract content: %s", e)
            return None
