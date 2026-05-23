"""
agent/groq_client.py
====================
Thin, well-typed wrapper around the Groq Python SDK.

Responsibilities
----------------
- Initialise the Groq client once from environment variable GROQ_API_KEY.
- Expose two public call-modes:
    chat_completion()  — standard multi-turn conversation (Stages 1 & 2)
    json_completion()  — forces JSON output and validates parse (Stages 3 & 4)
- Centralise retry / timeout / error-handling so orchestrator.py stays clean.
- Never import session state here (keeps concerns separated).

Environment
-----------
GROQ_API_KEY   : Required. Obtain from https://console.groq.com/
GROQ_MODEL     : Optional. Defaults to "llama3-70b-8192".
                 Use "llama3-8b-8192" for lower latency / cost during dev.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

from groq import Groq, APIConnectionError, APITimeoutError, RateLimitError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Model selection — overridable via env var
# ---------------------------------------------------------------------------
DEFAULT_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# ---------------------------------------------------------------------------
# Retry configuration
# ---------------------------------------------------------------------------
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 1.5  # exponential: 1.5 → 3.0 → 6.0


# ---------------------------------------------------------------------------
# Client singleton
# ---------------------------------------------------------------------------
def _build_client() -> Groq:
    """
    Build the Groq SDK client.
    Raises RuntimeError with a clear message if API key is missing.
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY environment variable is not set. "
            "Export it before starting the server:\n"
            "  export GROQ_API_KEY=gsk_..."
        )
    return Groq(api_key=api_key)


# Lazy singleton — created on first use so import does not fail at test time.
_client: Groq | None = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        _client = _build_client()
    return _client


# ---------------------------------------------------------------------------
# Core request helper (handles retries internally)
# ---------------------------------------------------------------------------
def _call_with_retry(
    messages: list[dict],
    system_prompt: str,
    model: str,
    temperature: float,
    max_tokens: int,
    response_format: dict | None,
) -> str:
    """
    Call the Groq Chat Completions endpoint with automatic retry on transient
    errors (connection errors, timeouts, rate limits).

    Returns the raw text content of the first choice.
    Raises RuntimeError if all retries are exhausted.
    """
    client = _get_client()

    # Prepend the system prompt as the first message
    full_messages = [{"role": "system", "content": system_prompt}] + messages

    call_kwargs: dict[str, Any] = {
        "model": model,
        "messages": full_messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    # Groq supports JSON mode — reduces hallucinated non-JSON wrapping
    if response_format:
        call_kwargs["response_format"] = response_format

    last_error: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.debug("Groq API call attempt %d/%d", attempt, MAX_RETRIES)
            completion = client.chat.completions.create(**call_kwargs)
            content = completion.choices[0].message.content
            logger.debug("Groq response received (%d chars)", len(content or ""))
            return content or ""

        except RateLimitError as exc:
            logger.warning("Rate limit hit on attempt %d: %s", attempt, exc)
            last_error = exc
            # Rate limit: longer back-off
            time.sleep(RETRY_BACKOFF_SECONDS * attempt * 2)

        except (APIConnectionError, APITimeoutError) as exc:
            logger.warning("Transient API error on attempt %d: %s", attempt, exc)
            last_error = exc
            time.sleep(RETRY_BACKOFF_SECONDS * attempt)

        except Exception as exc:
            # Non-retryable — re-raise immediately
            logger.error("Non-retryable Groq error: %s", exc)
            raise

    raise RuntimeError(
        f"Groq API call failed after {MAX_RETRIES} attempts. "
        f"Last error: {last_error}"
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def chat_completion(
    messages: list[dict],
    system_prompt: str,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.3,
    max_tokens: int = 512,
) -> str:
    """
    Generate a free-text conversational response.

    Used by: Stage 1 (FAQ answering) and Stage 2 (lead qualification).

    Parameters
    ----------
    messages      : Chat history in [{role, content}] format.
    system_prompt : System instructions to prepend.
    model         : Groq model string.
    temperature   : Lower = more deterministic / factual.
    max_tokens    : Hard cap on response length.

    Returns
    -------
    str  Raw assistant text response.
    """
    return _call_with_retry(
        messages=messages,
        system_prompt=system_prompt,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        response_format=None,
    )


def json_completion(
    messages: list[dict],
    system_prompt: str,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.0,
    max_tokens: int = 512,
) -> dict:
    """
    Generate a response that MUST be valid JSON.

    Used by: Stage 3 (escalation classification) and Stage 4 (summary).
    Enables Groq's JSON mode to minimise parse failures.
    Raises ValueError if the response cannot be parsed as JSON after stripping
    common LLM artefacts (markdown fences, leading/trailing whitespace).

    Parameters
    ----------
    messages      : Prompt messages.
    system_prompt : Instructions (should explicitly demand JSON output).
    model         : Groq model string.
    temperature   : 0.0 for maximum determinism on structured outputs.
    max_tokens    : Keep generous for summary (up to 1024 tokens).

    Returns
    -------
    dict  Parsed JSON object.
    """
    raw = _call_with_retry(
        messages=messages,
        system_prompt=system_prompt,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        response_format={"type": "json_object"},
    )

    # --- Defensive parse: strip markdown fences the model may emit anyway ---
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        # Remove opening fence (```json or ```)
        cleaned = cleaned.split("\n", 1)[-1]
    if cleaned.endswith("```"):
        cleaned = cleaned.rsplit("```", 1)[0]
    cleaned = cleaned.strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        logger.error("JSON parse failure. Raw response:\n%s", raw)
        raise ValueError(
            f"LLM did not return valid JSON. Parse error: {exc}\n"
            f"Raw output: {raw[:300]}"
        ) from exc


__all__ = ["chat_completion", "json_completion", "DEFAULT_MODEL"]
