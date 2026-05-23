"""
main.py
=======
FastAPI application for the Lumina Hair Studio AI agent backend.

Endpoints
---------
POST /chat
    Process a single user message within a session.
    Creates the session automatically if it doesn't exist.

POST /summary
    Generate and return a structured end-of-session summary.

GET  /session/{session_id}
    (Debug/monitoring) Return raw session state — disable in production.

GET  /health
    Liveness probe for load balancers / container orchestrators.

Run locally
-----------
    uvicorn main:app --reload --port 8000

Or with hot-reload + verbose logging:
    uvicorn main:app --reload --port 8000 --log-level debug
"""

from __future__ import annotations

import logging
import sys
import uuid
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from agent import orchestrator, state

# ---------------------------------------------------------------------------
# Logging configuration — structured JSON in prod; readable text in dev
# ---------------------------------------------------------------------------
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("closira.main")

# ---------------------------------------------------------------------------
# FastAPI application setup
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Closira — Lumina Hair Studio AI Agent",
    description=(
        "Multi-stage conversational AI backend for customer support. "
        "Handles FAQ answering, lead qualification, escalation detection, "
        "and session summarisation — all grounded strictly in the SOP."
    ),
    version="1.0.0",
    docs_url="/docs",       # Swagger UI
    redoc_url="/redoc",     # ReDoc
)

# Allow browser-based clients (e.g. a future React frontend) during development.
# Tighten allowed_origins before deploying to production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ===========================================================================
# Request / Response Schemas (Pydantic v2)
# ===========================================================================

class ChatRequest(BaseModel):
    """Request body for POST /chat."""
    session_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique session identifier. Auto-generated if omitted.",
        examples=["user-abc-123"],
    )
    message: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="The user's raw input message.",
        examples=["What services do you offer?"],
    )


class ChatResponse(BaseModel):
    """Response body for POST /chat."""
    response: str = Field(..., description="The AI agent's reply.")
    current_stage: str = Field(..., description="Active pipeline stage.")
    is_escalated: bool = Field(..., description="True if session has been escalated.")
    escalation_reason: str | None = Field(
        None, description="Human-readable escalation trigger, or null."
    )


class SummaryRequest(BaseModel):
    """Request body for POST /summary."""
    session_id: str = Field(
        ..., description="Session to summarise.", examples=["user-abc-123"]
    )


# ===========================================================================
# Exception handlers
# ===========================================================================

@app.exception_handler(KeyError)
async def key_error_handler(request: Request, exc: KeyError) -> JSONResponse:
    """Return 404 for missing sessions rather than a 500."""
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": str(exc)},
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    """Return 422 for validation / parse failures (e.g. LLM JSON parse error)."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": str(exc)},
    )


@app.exception_handler(RuntimeError)
async def runtime_error_handler(request: Request, exc: RuntimeError) -> JSONResponse:
    """Catch-all for Groq API failures — return 503 Service Unavailable."""
    logger.error("RuntimeError: %s", exc)
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": f"Upstream LLM error: {exc}"},
    )


# ===========================================================================
# Endpoints
# ===========================================================================

@app.get("/health", tags=["Ops"])
async def health() -> dict:
    """
    Liveness probe.
    Returns 200 OK with a simple status object.
    Container orchestrators (Kubernetes, ECS) should poll this.
    """
    return {"status": "ok", "service": "closira-lumina-agent"}


@app.post("/chat", response_model=ChatResponse, tags=["Agent"])
async def chat(body: ChatRequest) -> ChatResponse:
    """
    **POST /chat** — Process one user message within a session.

    - Creates the session automatically on first call.
    - Runs escalation detection concurrently with reply generation.
    - Returns the agent reply, current stage, and escalation status.

    Once `is_escalated` is `true`, the session is locked and all subsequent
    messages receive a static handoff response.
    """
    logger.info(
        "POST /chat | session=%s | stage=%s | msg_preview=%.60s",
        body.session_id,
        state.get_or_create_session(body.session_id).get("current_stage"),
        body.message,
    )

    result = orchestrator.process_message(
        session_id=body.session_id,
        user_message=body.message,
    )

    return ChatResponse(**result)


@app.post("/summary", tags=["Agent"])
async def summary(body: SummaryRequest) -> dict[str, Any]:
    """
    **POST /summary** — Generate a structured end-of-session summary.

    Triggers Stage 4 of the pipeline. The summary is generated fresh on each
    call (idempotent — calling twice produces the same result for the same
    history).

    Returns a JSON object with:
    - `customer_intent`
    - `key_details_collected`
    - `sop_gaps_identified`
    - `recommended_next_action`
    """
    logger.info("POST /summary | session=%s", body.session_id)

    sess = state.get_session(body.session_id)
    if sess is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{body.session_id}' does not exist.",
        )

    result = orchestrator.generate_summary(body.session_id)
    return result


@app.get("/session/{session_id}", tags=["Debug"])
async def get_session_debug(session_id: str) -> dict[str, Any]:
    """
    **GET /session/{session_id}** — Return raw session state for debugging.

    ⚠️  DISABLE THIS ENDPOINT IN PRODUCTION — it exposes PII and conversation
    history without authentication.
    """
    sess = state.get_session(session_id)
    if sess is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found.",
        )
    return sess
