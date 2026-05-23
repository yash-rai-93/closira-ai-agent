"""
agent/state.py
==============
In-memory session state management for the Lumina Hair Studio AI agent.

Each session is tracked independently via a session_id string. All state
is held in the module-level SESSION_STORE dict — intentionally simple for
local/demo deployments. For production, replace with Redis or a DB layer.

Session Schema
--------------
{
    "session_id"       : str,          # UUID or caller-supplied string
    "chat_history"     : list[dict],   # [{role, content}, ...] fed to LLM
    "current_stage"    : str,          # "faq" | "lead_qualification" | "escalation" | "summary"
    "lead_data"        : dict,         # Extracted lead fields from Stage 2
    "is_escalated"     : bool,         # True once any escalation trigger fires
    "escalation_reason": str | None,   # Human-readable reason for the escalation
    "unanswered_count" : int,          # Counter for out-of-scope questions (Stage 3 logic)
    "lead_question_idx": int,          # Which lead-qual question we are on (0 or 1)
}
"""

from __future__ import annotations

import threading
from typing import Any

# ---------------------------------------------------------------------------
# Module-level store  (swap for Redis client in production)
# ---------------------------------------------------------------------------
SESSION_STORE: dict[str, dict[str, Any]] = {}

# Lock protects concurrent writes in multi-threaded ASGI/WSGI deployments.
_STORE_LOCK = threading.Lock()

# ---------------------------------------------------------------------------
# Stage constants — single source of truth used across the codebase
# ---------------------------------------------------------------------------
STAGE_FAQ = "faq"
STAGE_LEAD = "lead_qualification"
STAGE_ESCALATION = "escalation"
STAGE_SUMMARY = "summary"


def create_session(session_id: str) -> dict[str, Any]:
    """
    Create and persist a brand-new session.

    Idempotent: if the session already exists, the existing session is
    returned unchanged so that duplicate POST /chat calls never wipe state.

    Parameters
    ----------
    session_id : str
        Caller-supplied identifier (UUID, username, etc.)

    Returns
    -------
    dict
        The newly created (or existing) session dict.
    """
    with _STORE_LOCK:
        if session_id not in SESSION_STORE:
            SESSION_STORE[session_id] = {
                "session_id": session_id,
                # Conversation history fed verbatim to the LLM
                "chat_history": [],
                # Every new session starts at FAQ answering
                "current_stage": STAGE_FAQ,
                # Lead data populated during Stage 2
                "lead_data": {
                    "interested_service": None,
                    "wants_consultation": None,
                },
                # Escalation flags
                "is_escalated": False,
                "escalation_reason": None,
                # Tracks consecutive out-of-scope questions for auto-escalation
                "unanswered_count": 0,
                # Tracks which of the 2 lead-qual questions has been asked
                "lead_question_idx": 0,
            }
        return SESSION_STORE[session_id]


def get_session(session_id: str) -> dict[str, Any] | None:
    """
    Retrieve an existing session.

    Returns None if the session does not exist (caller must handle this).
    """
    return SESSION_STORE.get(session_id)


def get_or_create_session(session_id: str) -> dict[str, Any]:
    """
    Convenience: retrieve session if it exists, otherwise create it.
    The typical call path for POST /chat.
    """
    session = get_session(session_id)
    if session is None:
        session = create_session(session_id)
    return session


def append_message(session_id: str, role: str, content: str) -> None:
    """
    Append a single message to the session's chat history.

    Parameters
    ----------
    session_id : str
    role       : "user" | "assistant"
    content    : Raw text of the message
    """
    session = get_session(session_id)
    if session is None:
        raise KeyError(f"Session '{session_id}' does not exist.")
    with _STORE_LOCK:
        session["chat_history"].append({"role": role, "content": content})


def set_stage(session_id: str, stage: str) -> None:
    """Transition the session to a new stage."""
    session = get_session(session_id)
    if session is None:
        raise KeyError(f"Session '{session_id}' does not exist.")
    with _STORE_LOCK:
        session["current_stage"] = stage


def escalate_session(session_id: str, reason: str) -> None:
    """
    Mark a session as escalated.

    Once escalated, the orchestrator will reject further automated processing
    and route all responses to the human handoff message.

    Parameters
    ----------
    session_id : str
    reason     : str  Human-readable trigger reason, stored for audit logs.
    """
    session = get_session(session_id)
    if session is None:
        raise KeyError(f"Session '{session_id}' does not exist.")
    with _STORE_LOCK:
        session["is_escalated"] = True
        session["escalation_reason"] = reason
        session["current_stage"] = STAGE_ESCALATION


def update_lead_data(session_id: str, key: str, value: str) -> None:
    """
    Store a single lead-data field extracted during Stage 2.

    Parameters
    ----------
    session_id : str
    key        : Field name (e.g. "interested_service")
    value      : Extracted value from the conversation
    """
    session = get_session(session_id)
    if session is None:
        raise KeyError(f"Session '{session_id}' does not exist.")
    with _STORE_LOCK:
        session["lead_data"][key] = value


def increment_unanswered(session_id: str) -> int:
    """
    Increment the unanswered-question counter and return the new value.
    Used by the orchestrator to auto-escalate after 2 consecutive out-of-scope
    questions, per SOP escalation_triggers[repeated_unanswered_questions].
    """
    session = get_session(session_id)
    if session is None:
        raise KeyError(f"Session '{session_id}' does not exist.")
    with _STORE_LOCK:
        session["unanswered_count"] += 1
        return session["unanswered_count"]


def reset_unanswered(session_id: str) -> None:
    """Reset the unanswered counter after a successfully answered question."""
    session = get_session(session_id)
    if session:
        with _STORE_LOCK:
            session["unanswered_count"] = 0


def delete_session(session_id: str) -> None:
    """Remove a session entirely (e.g., post-summary cleanup)."""
    with _STORE_LOCK:
        SESSION_STORE.pop(session_id, None)
