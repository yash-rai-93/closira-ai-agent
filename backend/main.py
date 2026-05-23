"""
main.py
=======
FastAPI backend for the Lumina Hair Studio AI agent.

Designed to be consumed by any frontend (React, Vue, mobile, etc.) via REST.
All endpoints return JSON. CORS is configured via the ALLOWED_ORIGINS env var.

Endpoints
---------
GET  /health                    — Liveness probe
POST /chat                      — Send a message, get a reply
POST /summary                   — Generate end-of-session summary
GET  /session/{session_id}      — Fetch current session state (for UI sync)
DELETE /session/{session_id}    — Clear a session (e.g. on user logout)
"""

from __future__ import annotations

import logging
import os
import sys
import uuid
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from agent import orchestrator, state

# ---------------------------------------------------------------------------
# Load .env file (no-op if it doesn't exist — env vars already set)
# ---------------------------------------------------------------------------
load_dotenv()

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("closira.api")

# ---------------------------------------------------------------------------
# CORS — read allowed origins from env so you can tighten this per environment
# e.g. ALLOWED_ORIGINS="https://myfrontend.com,https://staging.myfrontend.com"
# Defaults to * for local development only.
# ---------------------------------------------------------------------------
_raw_origins = os.getenv("ALLOWED_ORIGINS", "*")
ALLOWED_ORIGINS = [o.strip() for o in _raw_origins.split(",")] if _raw_origins != "*" else ["*"]

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Closira — Lumina Hair Studio AI Agent",
    description=(
        "Multi-stage conversational AI backend. "
        "Handles FAQ answering, lead qualification, escalation, and summarisation."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


# ===========================================================================
# Pydantic Schemas
# ===========================================================================

class ChatRequest(BaseModel):
    session_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Session ID. Auto-generated UUID if omitted — frontend should persist and reuse.",
        examples=["user-abc-123"],
    )
    message: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="User's message text.",
        examples=["What services do you offer?"],
    )

class ChatResponse(BaseModel):
    session_id: str
    response: str
    current_stage: str
    is_escalated: bool
    escalation_reason: str | None

class SummaryRequest(BaseModel):
    session_id: str

class SessionStateResponse(BaseModel):
    session_id: str
    current_stage: str
    is_escalated: bool
    escalation_reason: str | None
    lead_data: dict
    message_count: int


# ===========================================================================
# Endpoints
# ===========================================================================

@app.get("/health", tags=["Ops"])
async def health() -> dict:
    """Liveness probe. Returns 200 OK. Use this for Docker/k8s health checks."""
    return {"status": "ok", "service": "closira-lumina-agent", "version": "1.0.0"}


@app.post("/chat", response_model=ChatResponse, tags=["Agent"])
async def chat(body: ChatRequest) -> ChatResponse:
    """
    Send a user message and receive the agent's reply.

    - Creates the session automatically on first call with a given session_id.
    - Returns session_id in the response so the frontend can persist it.
    - Once `is_escalated` is true, the session is locked.
    """
    logger.info("POST /chat | session=%s | msg=%.60s...", body.session_id, body.message)

    try:
        result = orchestrator.process_message(
            session_id=body.session_id,
            user_message=body.message,
        )
    except RuntimeError as exc:
        logger.error("Groq API failure: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"AI service temporarily unavailable: {exc}",
        )
    except Exception as exc:
        logger.error("Unexpected error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred.",
        )

    return ChatResponse(session_id=body.session_id, **result)


@app.post("/summary", tags=["Agent"])
async def summary(body: SummaryRequest) -> dict[str, Any]:
    """
    Generate a structured end-of-session summary.

    Call this when the user ends the chat, or poll it after `is_escalated = true`.
    Returns a JSON object suitable for CRM ingestion.
    """
    logger.info("POST /summary | session=%s", body.session_id)

    sess = state.get_session(body.session_id)
    if sess is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{body.session_id}' not found.",
        )

    try:
        result = orchestrator.generate_summary(body.session_id)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"AI service temporarily unavailable: {exc}",
        )

    return result


@app.get("/session/{session_id}", response_model=SessionStateResponse, tags=["Session"])
async def get_session(session_id: str) -> SessionStateResponse:
    """
    Fetch the current state of a session.

    Useful for the frontend to:
    - Re-hydrate UI state after a page refresh.
    - Display the current stage indicator.
    - Check escalation status.
    """
    sess = state.get_session(session_id)
    if sess is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found.",
        )
    return SessionStateResponse(
        session_id=sess["session_id"],
        current_stage=sess["current_stage"],
        is_escalated=sess["is_escalated"],
        escalation_reason=sess["escalation_reason"],
        lead_data=sess["lead_data"],
        message_count=len(sess["chat_history"]),
    )


@app.delete("/session/{session_id}", tags=["Session"])
async def delete_session(session_id: str) -> dict:
    """
    Delete a session and all its data.

    Call this when the user explicitly ends or resets the conversation.
    """
    sess = state.get_session(session_id)
    if sess is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found.",
        )
    state.delete_session(session_id)
    logger.info("Session '%s' deleted.", session_id)
    return {"deleted": True, "session_id": session_id}
